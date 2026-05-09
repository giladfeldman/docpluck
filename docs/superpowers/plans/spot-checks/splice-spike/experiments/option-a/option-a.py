"""
option-a.py  --  pdfplumber text-strategy with cropped bbox

Experiment: extract APA table cells using pdfplumber's text strategy on
page regions cropped to each table's bbox (as reported by docpluck's
extract_pdf_structured).

Run from project root:
    python docs/superpowers/plans/spot-checks/splice-spike/experiments/option-a/option-a.py

Outputs: korbmacher_table1.md, ziano_table1.md (in the same directory as
this script).

Approach
--------
1. Run extract_pdf_structured(thorough=True) to get table bbox and metadata.
2. Open PDF with pdfplumber, crop page to bbox.
3. Try multiple extract_tables() settings (text strategy) and score each.
4. Also try a custom word-grid builder:
   - Use extract_words() to get word positions.
   - Cluster words into rows by y-coordinate (gap=6pts).
   - Detect columns by finding x-coordinate gaps (> col_x_gap pts).
   - Assign each word to the nearest column.
   - Merge stars-on-separate-rows DOWN into the next data row.
5. Pick the cleanest result; render as Markdown pipe-table.

Key findings from inspection:
- korbmacher: stars appear on rows BEFORE the data row; words run together
  (PDF encoding: "Usingamouse" not "Using a mouse").
- ziano: two side-by-side tables; very complex multi-line cells.
"""

from __future__ import annotations

import io
import sys
from pathlib import Path
from collections import defaultdict

# -- Ensure project root is on sys.path -----------------------------------
SCRIPT = Path(__file__).resolve()
# Script path: <repo>/docs/superpowers/plans/spot-checks/splice-spike/experiments/option-a/option-a.py
# parents[0] = option-a/
# parents[1] = experiments/
# parents[2] = splice-spike/
# parents[3] = spot-checks/
# parents[4] = plans/
# parents[5] = superpowers/
# parents[6] = docs/
# parents[7] = <repo root>
REPO_ROOT = SCRIPT.parents[7]
sys.path.insert(0, str(REPO_ROOT))

import pdfplumber  # noqa: E402
from docpluck.extract_structured import extract_pdf_structured  # noqa: E402

# -- Constants ------------------------------------------------------------
APA_DIR = REPO_ROOT.parent / "PDFextractor" / "test-pdfs" / "apa"
OUT_DIR = SCRIPT.parent

# -- Settings candidates (for extract_tables approach) --------------------
SETTINGS_CANDIDATES = [
    # 1. Pure text, tight
    {"vertical_strategy": "text", "horizontal_strategy": "text",
     "intersection_x_tolerance": 3, "intersection_y_tolerance": 3,
     "text_x_tolerance": 3, "text_y_tolerance": 3},
    # 2. Pure text, medium
    {"vertical_strategy": "text", "horizontal_strategy": "text",
     "intersection_x_tolerance": 5, "intersection_y_tolerance": 5,
     "text_x_tolerance": 5, "text_y_tolerance": 5},
    # 3. Pure text, loose
    {"vertical_strategy": "text", "horizontal_strategy": "text",
     "intersection_x_tolerance": 10, "intersection_y_tolerance": 10,
     "text_x_tolerance": 10, "text_y_tolerance": 10},
    # 4. Mixed text vertical / lines horizontal
    {"vertical_strategy": "text", "horizontal_strategy": "lines",
     "intersection_x_tolerance": 5, "intersection_y_tolerance": 5,
     "text_x_tolerance": 5, "text_y_tolerance": 5},
    # 5. Mixed lines vertical / text horizontal
    {"vertical_strategy": "lines", "horizontal_strategy": "text",
     "intersection_x_tolerance": 5, "intersection_y_tolerance": 5,
     "text_x_tolerance": 5, "text_y_tolerance": 5},
    # 6. Text with min_words constraints
    {"vertical_strategy": "text", "horizontal_strategy": "text",
     "intersection_x_tolerance": 5, "intersection_y_tolerance": 5,
     "text_x_tolerance": 5, "text_y_tolerance": 5,
     "min_words_vertical": 3, "min_words_horizontal": 1},
    # 7. Very loose for landscape/wide
    {"vertical_strategy": "text", "horizontal_strategy": "text",
     "intersection_x_tolerance": 15, "intersection_y_tolerance": 10,
     "text_x_tolerance": 10, "text_y_tolerance": 10},
]


# =========================================================================
# Scoring heuristic for extract_tables grids
# =========================================================================

def score_grid(grid: list[list]) -> float:
    if not grid:
        return 0.0
    n_rows = len(grid)
    col_counts = [len(row) for row in grid]
    modal_cols = max(set(col_counts), key=col_counts.count)
    if modal_cols < 2 or n_rows < 2:
        return 0.0

    consistency = sum(1 for c in col_counts if c == modal_cols) / n_rows
    filled = tiny = total = 0
    for row in grid:
        for cell in row:
            total += 1
            if cell and str(cell).strip():
                filled += 1
                if len(str(cell).split()) <= 1:
                    tiny += 1
    if total == 0:
        return 0.0
    fill = filled / total
    tiny_pen = tiny / max(total, 1)
    score = consistency * 0.4 + fill * 0.4 - tiny_pen * 0.2
    score += min(n_rows / 10, 0.1) + min(modal_cols / 10, 0.1)
    return score


# =========================================================================
# Custom word-grid builder with column-gap detection
# =========================================================================

def _cluster_rows(words: list[dict], y_gap: float = 6.0) -> list[list[int]]:
    """Cluster word indices into rows by top (y) coordinate."""
    indexed = sorted(enumerate(words), key=lambda iv: iv[1]["top"])
    clusters: list[list[int]] = []
    current: list[int] = []
    prev_top: float | None = None
    for idx, w in indexed:
        top = w["top"]
        if prev_top is None or top - prev_top <= y_gap:
            current.append(idx)
        else:
            clusters.append(current)
            current = [idx]
        prev_top = top
    if current:
        clusters.append(current)
    # Sort within each cluster left-to-right
    for cl in clusters:
        cl.sort(key=lambda i: words[i]["x0"])
    return clusters


def _detect_col_boundaries(words: list[dict], row_clusters: list[list[int]],
                            col_x_gap: float = 20.0) -> list[float]:
    """
    Find column left-edge boundaries by looking at large horizontal gaps
    between words across all rows.  Returns sorted list of x0 positions
    that represent the start of each column.
    """
    # Collect all x0 positions across all rows
    all_x0 = sorted(set(round(words[i]["x0"], 0)
                        for cl in row_clusters for i in cl))
    if not all_x0:
        return []

    # Find gap positions: wherever consecutive x0s differ by > col_x_gap
    # we consider a new column to start.
    col_starts: list[float] = [all_x0[0]]
    for prev, cur in zip(all_x0, all_x0[1:]):
        if cur - prev > col_x_gap:
            col_starts.append(cur)
    return col_starts


def _assign_col(x0: float, col_starts: list[float]) -> int:
    """Assign word x0 to nearest column index (closest left-edge boundary)."""
    best = 0
    best_dist = abs(x0 - col_starts[0])
    for ci, cs in enumerate(col_starts[1:], 1):
        dist = abs(x0 - cs)
        if dist < best_dist:
            best_dist = dist
            best = ci
    return best


def _is_star_cell(text: str) -> bool:
    """Return True if text is purely significance stars or empty."""
    stripped = text.strip()
    if not stripped:
        return True
    return all(ch in ("*", "∗", "⁎", "†", " ") for ch in stripped)


def _is_star_row(row: list[str]) -> bool:
    """Return True if all non-empty cells in the row are star-only."""
    non_empty = [c for c in row if c.strip()]
    if not non_empty:
        return True
    return all(_is_star_cell(c) for c in non_empty)


def word_grid_with_gap_cols(
    cropped_page,
    y_gap: float = 6.0,
    col_x_gap: float = 20.0,
    word_x_tolerance: float = 3.0,
    word_y_tolerance: float = 3.0,
    merge_stars_direction: str = "down",  # "down" or "up"
) -> list[list[str]]:
    """
    Build a (row x col) cell grid from pdfplumber word positions.

    Column detection:  find horizontal gaps > col_x_gap to define column starts.
    Row detection:     cluster words with top coords within y_gap of each other.
    Star merging:      star-only rows are merged INTO the adjacent data row.
      merge_stars_direction="down"  -> stars above a data row are appended to it
                                       (korbmacher pattern: stars precede data)
      merge_stars_direction="up"    -> stars below a data row are appended to it
                                       (more common PDF pattern)
    """
    words = cropped_page.extract_words(
        x_tolerance=word_x_tolerance, y_tolerance=word_y_tolerance,
        keep_blank_chars=False,
    )
    if not words:
        return []

    row_clusters = _cluster_rows(words, y_gap=y_gap)
    col_starts = _detect_col_boundaries(words, row_clusters, col_x_gap=col_x_gap)
    if not col_starts:
        return []

    n_cols = len(col_starts)

    # Build raw grid
    raw_grid: list[list[str]] = []
    for cl in row_clusters:
        row_cells: dict[int, list[str]] = {}
        for wi in cl:
            w = words[wi]
            ci = _assign_col(w["x0"], col_starts)
            row_cells.setdefault(ci, []).append(w["text"])
        row = [" ".join(row_cells.get(ci, [])) for ci in range(n_cols)]
        # Skip entirely empty rows
        if any(c.strip() for c in row):
            raw_grid.append(row)

    if not raw_grid:
        return []

    # Star-merging pass
    if merge_stars_direction == "down":
        # Stars appear BEFORE the row they annotate -> merge into the NEXT row
        merged: list[list[str]] = []
        pending_stars: list[str] | None = None  # stars waiting to be appended
        for row in raw_grid:
            if _is_star_row(row):
                # Buffer the stars (we don't know n_cols target yet — use current)
                if pending_stars is None:
                    pending_stars = row[:]
                else:
                    # Accumulate multiple star rows
                    for ci, cell in enumerate(row):
                        if cell.strip() and ci < len(pending_stars):
                            sep = " " if pending_stars[ci].strip() else ""
                            pending_stars[ci] = pending_stars[ci] + sep + cell.strip()
            else:
                if pending_stars:
                    # Append buffered stars to this data row
                    for ci, star_cell in enumerate(pending_stars):
                        if star_cell.strip() and ci < len(row):
                            sep = " " if row[ci].strip() else ""
                            row[ci] = row[ci] + sep + star_cell.strip()
                    pending_stars = None
                merged.append(row)
        # If trailing stars with no following row, append as own row
        if pending_stars and any(c.strip() for c in pending_stars):
            merged.append(pending_stars)
        return merged

    else:  # "up"
        merged = []
        for row in raw_grid:
            if _is_star_row(row) and merged:
                prev = merged[-1]
                for ci, cell in enumerate(row):
                    if cell.strip() and ci < len(prev):
                        sep = " " if prev[ci].strip() else ""
                        prev[ci] = prev[ci] + sep + cell.strip()
            else:
                merged.append(row)
        return merged


def score_word_grid(grid: list[list[str]]) -> float:
    """Score a word-grid (higher = cleaner table)."""
    if not grid:
        return 0.0
    n_rows = len(grid)
    col_counts = [len(row) for row in grid]
    modal_cols = max(set(col_counts), key=col_counts.count) if col_counts else 0
    if modal_cols < 2 or n_rows < 2:
        return 0.0
    consistency = sum(1 for c in col_counts if c == modal_cols) / n_rows
    filled = total = 0
    for row in grid:
        for cell in row:
            total += 1
            if cell.strip():
                filled += 1
    fill = filled / max(total, 1)
    # Reward multi-word cells (shows spaces inserted correctly)
    multi_word = sum(1 for row in grid for cell in row if len(cell.split()) > 1)
    mw_rate = multi_word / max(total, 1)
    # Penalize too many rows (likely star-row splitting)
    row_pen = max(0.0, (n_rows - 15) / 50)
    return consistency * 0.35 + fill * 0.35 + mw_rate * 0.3 - row_pen


# =========================================================================
# Try all approaches, pick best
# =========================================================================

def best_grid_for_region(
    pdf_path: Path,
    bbox: tuple[float, float, float, float],
    page_index: int,
    merge_direction: str = "up",
) -> tuple[list[list], str]:
    """Try all extract_tables settings + word-grid approach. Return best."""
    results: list[tuple[float, list[list], str]] = []

    with pdfplumber.open(pdf_path) as pdf:
        page = pdf.pages[page_index]
        cropped = page.crop(bbox)
        print(f"  Page {page_index+1}: {page.width:.0f}x{page.height:.0f}, "
              f"bbox={tuple(round(x, 1) for x in bbox)}")

        # --- extract_tables candidates ---
        for idx, settings in enumerate(SETTINGS_CANDIDATES):
            label = (f"extract_tables[v={settings['vertical_strategy'][:4]} "
                     f"h={settings['horizontal_strategy'][:4]} "
                     f"xtol={settings.get('intersection_x_tolerance', 5)}]")
            try:
                tables = cropped.extract_tables(table_settings=settings)
            except Exception as exc:
                print(f"    [{idx}] {label} -> ERROR: {exc}")
                continue
            if not tables:
                print(f"    [{idx}] {label} -> 0 tables")
                continue
            grid = max(tables, key=lambda g: sum(len(r) for r in g))
            grid = [[str(c) if c is not None else "" for c in row] for row in grid]
            sc = score_grid(grid)
            n_rows = len(grid)
            n_cols = max((len(r) for r in grid), default=0)
            print(f"    [{idx}] {label} -> {n_rows}r x {n_cols}c  score={sc:.3f}")
            results.append((sc, grid, label))

        # --- word-grid candidates (gap-based column detection) ---
        word_grid_params = [
            # (y_gap, col_x_gap, wx_tol, wy_tol, direction)
            (6.0, 20.0, 3.0, 3.0, merge_direction),
            (6.0, 15.0, 3.0, 3.0, merge_direction),
            (6.0, 30.0, 3.0, 3.0, merge_direction),
            (8.0, 20.0, 3.0, 3.0, merge_direction),
            (8.0, 30.0, 3.0, 3.0, merge_direction),
            (6.0, 20.0, 5.0, 5.0, merge_direction),
        ]
        for y_gap, col_x_gap, wx_tol, wy_tol, direction in word_grid_params:
            label = (f"word_grid_gap[ygap={y_gap} colgap={col_x_gap} "
                     f"stars={direction}]")
            try:
                grid = word_grid_with_gap_cols(
                    cropped, y_gap=y_gap, col_x_gap=col_x_gap,
                    word_x_tolerance=wx_tol, word_y_tolerance=wy_tol,
                    merge_stars_direction=direction,
                )
            except Exception as exc:
                print(f"    {label} -> ERROR: {exc}")
                continue
            if not grid:
                print(f"    {label} -> empty")
                continue
            sc = score_word_grid(grid)
            n_rows = len(grid)
            n_cols = max((len(r) for r in grid), default=0)
            print(f"    {label} -> {n_rows}r x {n_cols}c  score={sc:.3f}")
            results.append((sc, grid, label))

    if not results:
        return [], "no-result"
    best_sc, best_grid, best_label = max(results, key=lambda t: t[0])
    print(f"  Best: {best_label}  (score={best_sc:.3f})")
    return best_grid, best_label


# =========================================================================
# Grid -> Markdown pipe-table
# =========================================================================

def grid_to_markdown(grid: list[list]) -> str:
    if not grid:
        return "_No cells extracted._"

    def clean(cell) -> str:
        if cell is None:
            return ""
        s = str(cell)
        s = " ".join(s.split())
        s = s.replace("|", "\\|")
        return s

    n_cols = max(len(row) for row in grid)

    def pad(row: list) -> list[str]:
        cells = [clean(c) for c in row]
        while len(cells) < n_cols:
            cells.append("")
        return cells

    lines: list[str] = []
    header = pad(grid[0])
    lines.append("| " + " | ".join(header) + " |")
    lines.append("| " + " | ".join(["---"] * n_cols) + " |")
    for row in grid[1:]:
        lines.append("| " + " | ".join(pad(row)) + " |")
    return "\n".join(lines)


# =========================================================================
# Per-paper entry point
# =========================================================================

def extract_and_render(
    pdf_path: Path,
    target_page: int,
    table_label_hint: str,
    merge_direction: str = "up",
) -> tuple[str | None, str | None, list[list], str]:
    """Return (caption, footnote, best_grid, settings_label)."""
    pdf_bytes = pdf_path.read_bytes()
    print(f"\n[extract_pdf_structured] {pdf_path.name}")
    result = extract_pdf_structured(pdf_bytes, thorough=True)

    print(f"  Found {len(result['tables'])} table(s):")
    for t in result["tables"]:
        print(f"    {t['id']} label={t['label']!r} page={t['page']} "
              f"bbox={tuple(round(x, 1) for x in t['bbox'])} "
              f"rendering={t['rendering']!r}")

    candidate = None
    for t in result["tables"]:
        if t["page"] == target_page:
            if t["label"] and table_label_hint.lower() in t["label"].lower():
                candidate = t
                break
    if candidate is None:
        for t in result["tables"]:
            if t["page"] == target_page:
                candidate = t
                break
    if candidate is None:
        candidate = result["tables"][0] if result["tables"] else None

    if candidate is None:
        print("  WARNING: No table found!")
        return None, None, [], "no-table"

    print(f"  Using: {candidate['id']}  label={candidate['label']!r}  "
          f"page={candidate['page']}  rendering={candidate['rendering']!r}")

    grid, label = best_grid_for_region(
        pdf_path, candidate["bbox"], candidate["page"] - 1,
        merge_direction=merge_direction,
    )
    return candidate.get("caption"), candidate.get("footnote"), grid, label


def write_md(out_path: Path, heading: str, caption: str | None,
             footnote: str | None, grid: list[list], settings_label: str,
             extra_note: str = "") -> None:
    lines = [f"### {heading}", ""]
    if caption:
        lines.append(f"_{caption}_")
        lines.append("")
    lines.append(grid_to_markdown(grid))
    lines.append("")
    if footnote:
        lines.append(f"**Note.** {footnote}")
        lines.append("")
    lines.append("---")
    lines.append(f"_Settings used: {settings_label}_")
    if extra_note:
        lines.append("")
        lines.append(extra_note)
    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"  Written: {out_path}")


# =========================================================================
# Main
# =========================================================================

def main() -> None:
    # Paper 1: korbmacher_2022_kruger.pdf -- Table 1, page 7
    # Stars appear ABOVE the data row they annotate -> merge_direction="down"
    k_pdf = APA_DIR / "korbmacher_2022_kruger.pdf"
    print("=" * 70)
    print("PAPER 1: korbmacher_2022_kruger.pdf  (Table 1, page 7)")
    print("=" * 70)
    cap_k, fn_k, grid_k, label_k = extract_and_render(
        k_pdf, target_page=7, table_label_hint="table 1",
        merge_direction="down",
    )
    n_rows_k = len(grid_k)
    n_cols_k = max((len(r) for r in grid_k), default=0)
    print(f"\n  Best grid: {n_rows_k}r x {n_cols_k}c  [{label_k}]")
    write_md(
        OUT_DIR / "korbmacher_table1.md",
        heading="Table 1",
        caption=cap_k,
        footnote=fn_k,
        grid=grid_k,
        settings_label=label_k,
    )

    # Paper 2: ziano_2021_joep.pdf -- Table 1, page 2 (landscape)
    z_pdf = APA_DIR / "ziano_2021_joep.pdf"
    print("\n" + "=" * 70)
    print("PAPER 2: ziano_2021_joep.pdf  (Table 1, page 2, landscape)")
    print("=" * 70)
    cap_z, fn_z, grid_z, label_z = extract_and_render(
        z_pdf, target_page=2, table_label_hint="table 1",
        merge_direction="up",
    )
    n_rows_z = len(grid_z)
    n_cols_z = max((len(r) for r in grid_z), default=0)
    print(f"\n  Best grid: {n_rows_z}r x {n_cols_z}c  [{label_z}]")
    write_md(
        OUT_DIR / "ziano_table1.md",
        heading="Table 1",
        caption=cap_z,
        footnote=fn_z,
        grid=grid_z,
        settings_label=label_z,
        extra_note="_Note: this paper has two side-by-side tables on a landscape page._",
    )

    print("\nDone.")


if __name__ == "__main__":
    main()
