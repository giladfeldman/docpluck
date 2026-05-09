"""
Option B: pdfplumber word-cluster from scratch.

Approach:
1. Use extract_pdf_structured(thorough=True) to get table bbox.
2. Crop page to bbox with pdfplumber.
3. extract_words(x_tolerance=2, y_tolerance=2) → Word objects.
4. Cluster by y-proximity (3pt) → YCluster objects.
5. Mark asterisk-only rows (significance markers between data rows).
6. Detect side-by-side tables: gap whose ratio to median gap is >5x,
   in >30% of multi-word rows.
7. Infer column boundaries by clustering all word x0 positions.
8. Build logical rows: fold asterisk rows into adjacent data rows,
   merge multi-line cell continuations.
9. Render as Markdown pipe-table.

Iterations / thresholds discovered from data inspection:
- Y cluster tolerance: 3pt works well (asterisks appear 3-4pt above data text)
- Side-by-side detection: ratio of max-gap to median-gap > 5x, max-gap > 80pt,
  present in >30% of rows with >= 4 words.
- Column gap threshold: 2x median x0-gap works for both korbmacher (5 cols) and
  ziano (7 cols per side).
- Header zone: top 25% of bbox height.
"""

from __future__ import annotations

import io
import sys
import os
from pathlib import Path
from collections import defaultdict
from typing import NamedTuple
import re

# Force UTF-8 output on Windows
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

project_root = Path(__file__).parent.parent.parent.parent.parent.parent
sys.path.insert(0, str(project_root))

import pdfplumber  # type: ignore
from docpluck.extract_structured import extract_pdf_structured

# ──────────── paths ────────────
APA_DIR = Path("C:/Users/filin/Dropbox/Vibe/MetaScienceTools/PDFextractor/test-pdfs/apa")

# ──────────── thresholds ────────
Y_CLUSTER_PT = 3.0          # words within 3pt vertically → same y-cluster
SIDE_BY_SIDE_GAP_ABS = 60.0   # absolute gap threshold to even consider
SIDE_BY_SIDE_GAP_RATIO = 4.0  # max-gap / median-gap > 4x → side-by-side
SIDE_BY_SIDE_ROW_FRAC = 0.20  # fraction of multi-word rows that must show the gap
COL_GAP_FACTOR = 2.0          # column-cluster gap = COL_GAP_FACTOR × median x0-gap
COL_SNAP_TOL = 25.0           # snap word x0 to nearest column within 25pt
HEADER_ZONE_FRAC = 0.25       # top 25% of bbox height is header zone


# ──────────── data types ────────

class Word(NamedTuple):
    text: str
    x0: float
    top: float
    x1: float
    bottom: float


class YCluster(NamedTuple):
    words: list[Word]
    top: float
    bottom: float
    is_asterisk: bool


# ──────────── word extraction ───

def extract_words_from_page(pdf_path: Path, page_num: int, bbox: tuple) -> list[Word]:
    with pdfplumber.open(str(pdf_path)) as pdf:
        page = pdf.pages[page_num - 1]
        cropped = page.crop(bbox)
        raw = cropped.extract_words(x_tolerance=2, y_tolerance=2)
    return [Word(text=w["text"], x0=w["x0"], top=w["top"], x1=w["x1"], bottom=w["bottom"])
            for w in raw]


# ──────────── y-clustering ──────

def _is_significance_token(t: str) -> bool:
    t = t.strip()
    return bool(re.fullmatch(r'[\*∗†‡§]+', t)) or bool(re.fullmatch(r'p\s*[<>=]\s*[\d.]+', t, re.I))


def cluster_by_y(words: list[Word]) -> list[YCluster]:
    if not words:
        return []
    by_y = sorted(words, key=lambda w: (w.top, w.x0))
    groups: list[list[Word]] = [[by_y[0]]]
    for w in by_y[1:]:
        cluster_top = sum(c.top for c in groups[-1]) / len(groups[-1])
        if abs(w.top - cluster_top) <= Y_CLUSTER_PT:
            groups[-1].append(w)
        else:
            groups.append([w])

    result: list[YCluster] = []
    for g in groups:
        g.sort(key=lambda w: w.x0)
        top = min(w.top for w in g)
        bottom = max(w.bottom for w in g)
        is_ast = all(_is_significance_token(w.text) for w in g)
        result.append(YCluster(words=g, top=top, bottom=bottom, is_asterisk=is_ast))
    return result


# ──────────── side-by-side detection ────

def find_split_x(clusters: list[YCluster], bbox_x0: float = 0, bbox_x1: float = 1e9) -> float | None:
    """
    Return the x-coordinate of a persistent large gap, or None.

    Uses ratio of max-gap to median-gap to distinguish between
    "table has wide inter-column spacing" vs "two tables side by side".

    The winning gap cluster must:
    - Have absolute gap > SIDE_BY_SIDE_GAP_ABS
    - Have ratio of max-gap to median-gap > SIDE_BY_SIDE_GAP_RATIO
    - Appear in > SIDE_BY_SIDE_ROW_FRAC of multi-word rows
    - Be in the central 40-80% of the bbox width (not a side-margin artifact)
    """
    bbox_width = bbox_x1 - bbox_x0
    # Valid split range: between 20% and 80% of bbox width
    valid_x_min = bbox_x0 + bbox_width * 0.20
    valid_x_max = bbox_x0 + bbox_width * 0.80

    gap_midpoints: list[float] = []
    qualifying = 0

    for cl in clusters:
        if cl.is_asterisk or len(cl.words) < 4:
            continue
        qualifying += 1
        words = cl.words
        gaps_in_row = [(words[i+1].x0 - words[i].x1) for i in range(len(words)-1)]
        if not gaps_in_row:
            continue
        max_gap = max(gaps_in_row)
        sorted_gaps = sorted(gaps_in_row)
        median_gap = sorted_gaps[len(sorted_gaps) // 2]
        if median_gap <= 0:
            continue
        ratio = max_gap / median_gap
        if max_gap >= SIDE_BY_SIDE_GAP_ABS and ratio >= SIDE_BY_SIDE_GAP_RATIO:
            max_gap_idx = gaps_in_row.index(max_gap)
            mid = (words[max_gap_idx].x1 + words[max_gap_idx + 1].x0) / 2
            # Only count if in valid x range
            if valid_x_min <= mid <= valid_x_max:
                gap_midpoints.append(mid)

    if not gap_midpoints or qualifying < 2:
        return None

    # Cluster midpoints
    gap_midpoints.sort()
    groups: list[list[float]] = [[gap_midpoints[0]]]
    for m in gap_midpoints[1:]:
        if m - groups[-1][-1] < 40.0:
            groups[-1].append(m)
        else:
            groups.append([m])

    # Find biggest qualifying cluster
    # Score by count × centrality (prefer x near midpoint of valid range)
    center_x = (valid_x_min + valid_x_max) / 2
    best_score = -1
    best_group = None
    for g in groups:
        count = len(g)
        if count / qualifying < SIDE_BY_SIDE_ROW_FRAC:
            continue
        mean_x = sum(g) / len(g)
        # Centrality score: 1.0 at center, 0.5 at edges of valid range
        centrality = 1.0 - abs(mean_x - center_x) / (bbox_width * 0.4)
        score = count * max(centrality, 0.1)
        if score > best_score:
            best_score = score
            best_group = g

    if best_group is None:
        return None
    return sum(best_group) / len(best_group)


def split_clusters(clusters: list[YCluster], split_x: float) -> tuple[list[YCluster], list[YCluster]]:
    left, right = [], []
    for cl in clusters:
        lw = [w for w in cl.words if w.x1 <= split_x]
        rw = [w for w in cl.words if w.x0 >= split_x]
        if lw:
            left.append(YCluster(lw, min(w.top for w in lw), max(w.bottom for w in lw),
                                 all(_is_significance_token(w.text) for w in lw)))
        if rw:
            right.append(YCluster(rw, min(w.top for w in rw), max(w.bottom for w in rw),
                                  all(_is_significance_token(w.text) for w in rw)))
    return left, right


# ──────────── column inference ──

def infer_col_starts(clusters: list[YCluster]) -> list[float]:
    """
    Find column x0-start positions using sequential x1→x0 gaps within each row.

    For each row, compute gap between consecutive words (x0[i+1] - x1[i]).
    Column boundaries = gaps above the "bimodal split" between within-word gaps
    and inter-column gaps.

    Within-cell word gaps: small (0-10pt, from normal word spacing)
    Inter-column gaps: large (≥15pt for narrow tables, ≥30pt for APA stat tables)

    We find the gap split threshold as: (within-gap max + inter-gap min) / 2,
    where "within" and "inter" are separated at a natural break in the gap
    distribution (looking for a gap > 2× the gaps below it).
    """
    # Collect (prev_x1, curr_x0) per row for all non-asterisk rows
    all_row_words: list[list[Word]] = []
    for cl in clusters:
        if cl.is_asterisk or len(cl.words) < 2:
            continue
        all_row_words.append(cl.words)

    if not all_row_words:
        # Fallback: use all word x0 positions
        x0_vals = sorted(w.x0 for cl in clusters for w in cl.words if not cl.is_asterisk)
        return x0_vals[:1] if x0_vals else []

    # Compute inter-word gaps across all rows
    all_gaps: list[float] = []
    for row_words in all_row_words:
        for i in range(len(row_words) - 1):
            gap = row_words[i+1].x0 - row_words[i].x1
            if gap >= 0:  # ignore overlapping words (ligatures etc.)
                all_gaps.append(gap)

    if not all_gaps:
        return [min(w.x0 for cl in clusters for w in cl.words)]

    # Find the bimodal split: sort gaps and find the biggest jump
    all_gaps.sort()
    best_jump = 0.0
    split_threshold = all_gaps[-1]  # fallback: everything is one column
    for i in range(len(all_gaps) - 1):
        jump = all_gaps[i+1] - all_gaps[i]
        if jump > best_jump and all_gaps[i] >= 3.0:  # minimum 3pt gap to be meaningful
            best_jump = jump
            split_threshold = (all_gaps[i] + all_gaps[i+1]) / 2

    # Column boundary = gap > split_threshold
    # Find column starts: first word of each new column in each row
    col_start_candidates: list[float] = []
    for row_words in all_row_words:
        col_start_candidates.append(row_words[0].x0)  # first word of row always starts a column
        for i in range(len(row_words) - 1):
            gap = row_words[i+1].x0 - row_words[i].x1
            if gap >= 0 and gap > split_threshold:
                col_start_candidates.append(row_words[i+1].x0)

    if not col_start_candidates:
        return []

    # Cluster the column start candidates (nearby starts = same column)
    col_start_candidates.sort()
    col_groups: list[list[float]] = [[col_start_candidates[0]]]
    for x in col_start_candidates[1:]:
        if x - col_groups[-1][-1] > split_threshold:
            col_groups.append([x])
        else:
            col_groups[-1].append(x)

    return [min(g) for g in col_groups]


def snap(x0: float, cols: list[float]) -> int:
    if not cols:
        return 0
    dists = [(abs(x0 - c), i) for i, c in enumerate(cols)]
    return min(dists)[1]


# ──────────── header detection ──

def count_header_clusters(clusters: list[YCluster], bbox_top: float, bbox_height: float) -> int:
    """
    Count how many leading y-clusters are in the header zone (top 25% of bbox).
    Always at least 1.
    """
    header_bottom = bbox_top + bbox_height * HEADER_ZONE_FRAC
    n = 0
    for cl in clusters:
        if cl.bottom <= header_bottom:
            n += 1
        else:
            break
    return max(1, n)


# ──────────── logical row building ──

def build_rows(
    clusters: list[YCluster],
    col_starts: list[float],
    n_header: int,
) -> tuple[list[dict[int, str]], list[dict[int, str]]]:
    """
    Convert y-clusters → (header_rows, data_rows).

    Asterisk rows are folded into the most recent data row.
    Multi-line cell continuations are merged: a cluster is a continuation
    if it has no word in col 0 OR if the previous cluster also had no col-0 word
    AND the vertical gap is small.
    """
    def assign(cl: YCluster) -> dict[int, list[str]]:
        d: dict[int, list[str]] = defaultdict(list)
        for w in cl.words:
            c = snap(w.x0, col_starts)
            d[c].append(w.text)
        return d

    # Header: merge all header clusters
    hdr: dict[int, list[str]] = defaultdict(list)
    for cl in clusters[:n_header]:
        for c, words in assign(cl).items():
            hdr[c].extend(words)
    header_rows = [{c: " ".join(ws) for c, ws in hdr.items()}] if hdr else []

    # Data rows
    data_clusters = clusters[n_header:]
    logical: list[dict[int, str]] = []
    pending: dict[int, list[str]] = defaultdict(list)
    last_bottom: float | None = None

    for cl in data_clusters:
        if cl.is_asterisk:
            # Fold into last logical row
            for c, words in assign(cl).items():
                if logical:
                    prev = logical[-1].get(c, "")
                    logical[-1][c] = (prev + " " + " ".join(words)).strip()
                # else: drop — no row to attach to yet
            continue

        row_assign = assign(cl)
        is_continuation = False
        if pending and last_bottom is not None:
            y_gap = cl.top - last_bottom
            col0_in_new = 0 in row_assign
            col0_in_pending = 0 in pending
            # Continuation: close vertical gap AND either:
            # (a) new cluster has no col-0 word, OR
            # (b) both have col-0 words but pending col-0 content looks like
            #     a multi-word name (>1 token) — multi-line continuation
            if y_gap < 7.0:
                if not col0_in_new:
                    is_continuation = True
                elif col0_in_pending and not col0_in_new:
                    is_continuation = True

        if is_continuation:
            for c, words in row_assign.items():
                pending[c].extend(words)
        else:
            if pending:
                logical.append({c: " ".join(ws) for c, ws in pending.items()})
            pending = defaultdict(list)
            for c, words in row_assign.items():
                pending[c].extend(words)
        last_bottom = cl.bottom

    if pending:
        logical.append({c: " ".join(ws) for c, ws in pending.items()})

    return header_rows, logical


# ──────────── markdown rendering ────

def to_markdown(header_rows: list[dict[int, str]], data_rows: list[dict[int, str]], n_cols: int) -> str:
    if not header_rows and not data_rows:
        return "(no data)"

    def fmt(d: dict[int, str]) -> str:
        cells = [d.get(c, "").replace("|", "/").strip() for c in range(n_cols)]
        return "| " + " | ".join(cells) + " |"

    sep = "| " + " | ".join(["---"] * n_cols) + " |"
    lines: list[str] = []

    if header_rows:
        for hr in header_rows:
            lines.append(fmt(hr))
        lines.append(sep)
    else:
        if data_rows:
            lines.append(fmt(data_rows[0]))
            lines.append(sep)
            data_rows = data_rows[1:]

    for dr in data_rows:
        lines.append(fmt(dr))
    return "\n".join(lines)


# ──────────── full pipeline ─────

def pipeline(
    pdf_path: Path,
    page_num: int,
    bbox: tuple,
    notes: list[str],
    tag: str,
) -> tuple[str | None, float | None, list[YCluster] | None]:
    """
    Returns (markdown, None, None) for single table,
    or (None, split_x, clusters) when side-by-side detected.
    """
    x0, top, x1, bottom = bbox
    height = bottom - top

    words = extract_words_from_page(pdf_path, page_num, bbox)
    notes.append(f"[{tag}] {len(words)} words extracted")
    if not words:
        return "(no words)", None, None

    clusters = cluster_by_y(words)
    n_ast = sum(1 for c in clusters if c.is_asterisk)
    notes.append(f"[{tag}] {len(clusters)} y-clusters ({n_ast} asterisk-only)")

    split_x = find_split_x(clusters, bbox_x0=x0, bbox_x1=x1)
    if split_x is not None:
        notes.append(f"[{tag}] Side-by-side split at x={split_x:.1f}")
        return None, split_x, clusters

    n_header = count_header_clusters(clusters, top, height)
    notes.append(f"[{tag}] Header: first {n_header} y-clusters")

    # Infer columns from DATA rows only (header rows have different word layout)
    data_clusters = clusters[n_header:]
    col_starts = infer_col_starts(data_clusters if data_clusters else clusters)
    notes.append(f"[{tag}] {len(col_starts)} cols: {[round(c, 1) for c in col_starts]}")

    header_rows, data_rows = build_rows(clusters, col_starts, n_header)
    notes.append(f"[{tag}] {len(header_rows)} header row(s), {len(data_rows)} data rows")

    md = to_markdown(header_rows, data_rows, len(col_starts))
    return md, None, None


def pipeline_split(
    pdf_path: Path,
    page_num: int,
    bbox: tuple,
    split_x: float,
    clusters: list[YCluster],
    notes: list[str],
) -> tuple[str, str]:
    x0, top, x1, bottom = bbox
    height = bottom - top

    left_cls, right_cls = split_clusters(clusters, split_x)

    def one_side(cls: list[YCluster], tag: str) -> str:
        n_header = count_header_clusters(cls, top, height)
        notes.append(f"[{tag}] Header: first {n_header} y-clusters")
        data_cls = cls[n_header:] if len(cls) > n_header else cls
        col_starts = infer_col_starts(data_cls)
        notes.append(f"[{tag}] {len(col_starts)} cols: {[round(c, 1) for c in col_starts]}")
        header_rows, data_rows = build_rows(cls, col_starts, n_header)
        notes.append(f"[{tag}] {len(data_rows)} data rows")
        # Debug: show first few rows
        for i, row in enumerate((header_rows + data_rows)[:5]):
            notes.append(f"  [{tag}] row {i}: { {k: v[:40] for k, v in sorted(row.items())} }")
        return to_markdown(header_rows, data_rows, len(col_starts))

    return one_side(left_cls, "left"), one_side(right_cls, "right")


# ──────────── paper processors ──

def process_korbmacher(pdf_path: Path) -> tuple[str, list[str]]:
    notes: list[str] = []
    pdf_bytes = pdf_path.read_bytes()

    result = extract_pdf_structured(pdf_bytes, thorough=True)
    tables = result["tables"]
    notes.append(f"{len(tables)} tables found (thorough=True)")

    target = next((t for t in tables if t["page"] == 7), None)
    if target is None and tables:
        target = tables[0]
    if target is None:
        return "(no table found)", notes

    notes.append(f"Target: page={target['page']} bbox={[round(v,1) for v in target['bbox']]}")
    bbox = target["bbox"]

    md, split_x, clusters = pipeline(pdf_path, target["page"], bbox, notes, "korb")

    if split_x is not None:
        # korbmacher should NOT split — fall back to single-table rendering
        notes.append("WARNING: Unexpected split in korbmacher; processing as single table")
        col_starts = infer_col_starts(clusters)
        x0, top, x1, bottom = bbox
        n_header = count_header_clusters(clusters, top, bottom - top)
        header_rows, data_rows = build_rows(clusters, col_starts, n_header)
        md = to_markdown(header_rows, data_rows, len(col_starts))

    caption = (
        "*Table 1. Ability domains, comparative difficulty (% judging domain harder than average), "
        "and judgmental weights for own and others' ability.*"
    )
    return f"### Table 1\n\n{caption}\n\n{md}", notes


def process_ziano(pdf_path: Path) -> tuple[str, list[str]]:
    notes: list[str] = []
    pdf_bytes = pdf_path.read_bytes()

    result = extract_pdf_structured(pdf_bytes)
    tables = result["tables"]
    notes.append(f"{len(tables)} tables found")

    target = (
        next((t for t in tables if t.get("label") == "Table 1"), None)
        or next((t for t in tables if t["page"] == 2), None)
        or (tables[0] if tables else None)
    )
    if target is None:
        return "(no table found)", notes

    notes.append(f"Target: page={target['page']} label={target.get('label')!r}")
    bbox = target["bbox"]
    raw_caption = target.get("caption") or "Table 1"
    # Truncate caption for display
    caption_display = raw_caption[:300] + ("..." if len(raw_caption) > 300 else "")

    md, split_x, clusters = pipeline(pdf_path, target["page"], bbox, notes, "ziano")

    if split_x is not None and clusters is not None:
        left_md, right_md = pipeline_split(pdf_path, target["page"], bbox, split_x, clusters, notes)
        return (
            f"### Table 1 (Paying to know)\n\n*{caption_display}*\n\n{left_md}\n\n"
            f"### Table 1 (Choice under risk)\n\n*{caption_display}*\n\n{right_md}"
        ), notes
    else:
        return f"### Table 1\n\n*{caption_display}*\n\n{md}", notes


# ──────────── main ──────────────

def main():
    out_dir = Path(__file__).parent

    print("=" * 60)
    print("korbmacher_2022_kruger.pdf")
    print("=" * 60)
    korb_md, korb_notes = process_korbmacher(APA_DIR / "korbmacher_2022_kruger.pdf")
    for n in korb_notes:
        print(n)
    print("\n--- OUTPUT ---")
    print(korb_md)
    (out_dir / "korbmacher_table1.md").write_text(korb_md, encoding="utf-8")
    (out_dir / "korbmacher_notes_raw.txt").write_text("\n".join(korb_notes), encoding="utf-8")

    print("\n" + "=" * 60)
    print("ziano_2021_joep.pdf")
    print("=" * 60)
    ziano_md, ziano_notes = process_ziano(APA_DIR / "ziano_2021_joep.pdf")
    for n in ziano_notes:
        print(n)
    print("\n--- OUTPUT ---")
    print(ziano_md)
    (out_dir / "ziano_table1.md").write_text(ziano_md, encoding="utf-8")
    (out_dir / "ziano_notes_raw.txt").write_text("\n".join(ziano_notes), encoding="utf-8")

    print("\nDone →", out_dir)


if __name__ == "__main__":
    main()
