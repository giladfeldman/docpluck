"""Camelot-based table cell extraction.

Per [LESSONS.md L-006](../../LESSONS.md#l-006), Camelot ``flavor="stream"`` is the
chosen library for extracting cell-structured content from APA-style
whitespace-aligned tables. This module wraps Camelot and converts results
into docpluck's :class:`Table` TypedDict shape so callers can mix Camelot
output with the rest of the table pipeline.

License: Camelot is MIT (atlanhq/camelot). Stream flavor does NOT require
Ghostscript (only lattice does). Camelot is an OPTIONAL dependency: if the
library is not installed, this module's functions return ``[]`` and callers
silently fall back to the existing pdfplumber path.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

import re

from docpluck.tables import Cell, Table
from docpluck.tables.render import cells_to_html
from docpluck.telemetry import record_fallback


# Patterns used to detect rows that look like running headers / page footers.
# These are rows where the joined cell content matches one of:
#   - Journal name + Vol./No./year ("Personality and Social Psychology Bulletin 00(0)")
#   - "Journal of X, Vol. N, No. M, ..." style
#   - Single small integer (page number)
#   - Author-list short header ("Ip and Feldman", "Korbmacher et al.")
_RUNNING_HEADER_PATTERNS = [
    re.compile(r"\b(?:[A-Z][\w&'-]*\s+){1,8}\d+\s*\([^)]*\)\s*$"),     # "...Journal Name 00(0)"
    re.compile(r"\bVol\.?\s*\d+\b", re.IGNORECASE),                    # contains "Vol. N"
    re.compile(r"\bNo\.\s*\d+\b", re.IGNORECASE),                      # contains "No. N"
    re.compile(r"^\s*\d{1,4}\s*$"),                                    # page number only
    re.compile(r"^\s*[A-Z][\w'-]+(?:\s+(?:and|&|et\s+al\.?))\s+[A-Z][\w'-]+\s*$"),  # "Ip and Feldman"
    re.compile(r"^\s*[A-Z][\w'-]+\s+et\s+al\.?\s*$"),                  # "Korbmacher et al."
    re.compile(r"\bJournal\s+of\s+\w+", re.IGNORECASE),                # "...Journal of X..."
    re.compile(r"\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}\b"),
    re.compile(r"https?://", re.IGNORECASE),                           # DOI/URL footer
    re.compile(r"^\s*\d+\s*\([^)]*\)\s*\d{4}\s*$"),                    # "13(7) 2022"
    re.compile(r"\bPersonality\s+and\s+Social\s+Psychology\b", re.IGNORECASE),
    re.compile(r"\bJudgment\s+and\s+Decision\b", re.IGNORECASE),
    re.compile(r"\bSocial\s+Psychological\s+and\s+Personality\s+Science\b", re.IGNORECASE),
    re.compile(r"\bMeta-?Psychology\b", re.IGNORECASE),
    re.compile(r"\bJournal\s+of\s+Economic\s+Psychology\b", re.IGNORECASE),
]

_CAPTION_ROW_PATTERN = re.compile(
    r"^\s*(?:Table|Fig\.?|Figure)\s+\d+(?:\.\d+)?\s*[.:]",
    re.IGNORECASE,
)

# Same anchor as ``_CAPTION_ROW_PATTERN`` but capturing the integer table number,
# for the caption-marker pairing hint (see ``_leading_table_caption_number``).
_TABLE_CAPTION_NUMBER_PATTERN = re.compile(
    r"^\s*Table\s+(\d+)(?:\.\d+)?\s*[.:]",
    re.IGNORECASE,
)

# A caption-continuation TAIL fragment that pdftotext/Camelot leaves as the first
# grid row when the region top includes the caption's last wrapped line — a bare
# parenthetical year ("(2019)") or a lone "(citation)" with nothing else in the
# row. Dropped only when it is the SOLE populated cell of a leading row (a real
# header/data row never consists of just a parenthetical year).
_CAPTION_TAIL_FRAGMENT_RE = re.compile(r"^\(\s*\d{4}[a-z]?\s*\)$")


def _row_joined(row: list[str]) -> str:
    return " ".join(c for c in row if c).strip()


def _looks_like_running_header(row: list[str]) -> bool:
    joined = _row_joined(row)
    if not joined or len(joined) > 120:
        return False
    # If only one column has content, more likely a running header
    nonempty = [c for c in row if c]
    if len(nonempty) > 2:
        return False
    for pat in _RUNNING_HEADER_PATTERNS:
        if pat.search(joined):
            return True
    return False


def _strip_running_header_rows(rows: list[list[str]]) -> list[list[str]]:
    """Drop rows at the top or bottom that look like page running headers/footers."""
    out = list(rows)
    while out and _looks_like_running_header(out[0]):
        out.pop(0)
    while out and _looks_like_running_header(out[-1]):
        out.pop()
    return out


def _leading_table_caption_number(rows: list[list[str]]) -> int | None:
    """Return the integer ``N`` if one of the first 3 rows IS a ``Table N.``
    caption line — i.e. Camelot absorbed the table's own caption into the grid.

    This is a strong, deterministic table-identity signal (cf. PDFFigures 2.0's
    caption-start consistency check): a grid that literally starts with
    ``Table 9. Summary …`` is Table 9's, regardless of how a downstream
    token-overlap pairing would score it. Used by ``extract_structured`` to
    pin the grid to its true caption, sidestepping the same-page-caption
    mispairing where two captions tie on caption-line token overlap.

    Scans the SAME 3-row window ``_drop_caption_first_row`` uses (the caption is
    always at the top); the anchored ``^\\s*Table\\s+\\d+\\s*[.:]`` shape (start of
    row, terminated by ``.``/``:``) is the same one already trusted to DROP these
    rows, so an inline back-reference like ``see Table 2`` mid-row does not match.
    Returns the FIRST such number found.
    """
    for row in rows[:3]:
        m = _TABLE_CAPTION_NUMBER_PATTERN.match(_row_joined(row))
        if m:
            try:
                return int(m.group(1))
            except (ValueError, TypeError):
                return None
    return None


def _drop_caption_first_row(rows: list[list[str]]) -> list[list[str]]:
    """Drop "Table N. Caption text" rows from among the first 3 rows.

    Camelot sometimes includes the caption line as a table row. The caller has
    already extracted the caption from the surrounding text, so this row is
    duplicate noise. Scan the first 3 rows to catch cases where the running
    header occupies row 0 and the caption is at row 1 or 2.

    Also drops a LEADING caption-continuation tail fragment — a row whose sole
    populated cell is a bare parenthetical year (``(2019)``) — which a region
    whose top edge includes the caption's last wrapped line leaves above the real
    header row (chandrashekar Table 4: the caption's ``…LeBel et al. (2019)`` tail
    became grid row 0). Only a leading single-cell ``(YYYY)`` row qualifies, so a
    real header/data row is never removed.
    """
    out: list[list[str]] = []
    seen_caption = False
    started = False
    for i, row in enumerate(rows):
        if i < 3 and not seen_caption and _CAPTION_ROW_PATTERN.search(_row_joined(row)):
            seen_caption = True
            continue
        if not started:
            nonempty = [c for c in row if c and c.strip()]
            if len(nonempty) == 1 and _CAPTION_TAIL_FRAGMENT_RE.match(nonempty[0].strip()):
                continue  # leading caption-tail fragment row → drop
        started = True
        out.append(row)
    return out


# A "purely numeric" cell: starts with a number-like token (-?digits, optional
# decimal, optional %, optional ± SD, etc.). Citations like "p. 3" or
# "(Finucane et al., 2000, p. 3)" should NOT match — they're prose with a
# number embedded, not data cells.
_PURE_NUMERIC_RE = re.compile(
    r"^\s*-?\d+(?:\.\d+)?\s*[%*]?\s*$"      # 0.45, -0.15, 95%, 5*
    r"|^\s*\(?\d+(?:\.\d+)?\)?\s*\(.*\)\s*$"  # 5 (3.2), (5)
    r"|^\s*[-+−–]?\.\d+\s*[*]*\s*$"           # .45, -.45, .45***
    r"|^\s*[χβtFpr]\s*[=<>]?\s*\d"            # χ²=, β=, t=, F=, p=, r=
)


def _is_data_cell(cell: str) -> bool:
    """A "data cell" is either:
      - purely numeric (a stat value: 0.45, 95%, χ²=12.3, etc.), or
      - a short categorical label (≤25 chars, ≤4 words) that doesn't end with
        a sentence terminator.
    Long prose with embedded citations like "(Finucane et al., 2000, p. 3)"
    should NOT count as a data cell.
    """
    if not cell:
        return False
    s = cell.strip()
    if len(s) > 60:
        return False
    if _PURE_NUMERIC_RE.match(s):
        return True
    # Short categorical labels: ≤25 chars, ≤4 words, no terminal period.
    # The end-period check rejects body-prose endings like "...as we found.".
    if len(s) <= 25 and s.split() and len(s.split()) <= 4 and not s.endswith((".", "!", "?")):
        return True
    return False


def _is_table_like(rows: list[list[str]]) -> bool:
    """Heuristic: ≥40% of non-empty rows have at least one numeric/short cell.

    Rejects "tables" that are entirely 2-column journal body prose.
    """
    nonempty = [r for r in rows if any(c for c in r)]
    if len(nonempty) < 2:
        return False
    data_like = sum(
        1 for r in nonempty
        if any(_is_data_cell(c) for c in r if c)
    )
    return (data_like / len(nonempty)) >= 0.4


def _row_looks_like_prose(row: list[str]) -> bool:
    """A row is "prose-like" if it has no data cells AND ≥1 cell of long text
    that ends with sentence punctuation OR is clearly a continuation."""
    if not any(c for c in row):
        return False
    if any(_is_data_cell(c) for c in row if c):
        return False
    longs = [c for c in row if c and len(c) > 30]
    if not longs:
        return False
    # At least one long cell — looks prose-y.
    return True


def _trim_prose_tail(rows: list[list[str]]) -> list[list[str]]:
    """Trim trailing prose rows from a Camelot table.

    Camelot sometimes bundles a real small table at the top of a 2-column page
    with 50+ rows of body prose below it. We keep the data rows at the top,
    trim where the prose run begins.

    Rule: walk from the end backwards. Drop while the row is empty or prose-like.
    Then walk from the start forward; stop at the first run of ≥3 consecutive
    prose-like rows and trim there.
    """
    if not rows:
        return rows
    # Drop trailing empty/prose rows.
    while rows and (not any(c for c in rows[-1]) or _row_looks_like_prose(rows[-1])):
        rows = rows[:-1]
    if not rows:
        return rows
    # Forward scan: find first run of ≥3 consecutive prose rows.
    n = len(rows)
    i = 0
    while i < n:
        # Skip non-prose rows
        if not _row_looks_like_prose(rows[i]):
            i += 1
            continue
        # Found a prose row — count run length
        j = i
        while j < n and _row_looks_like_prose(rows[j]):
            j += 1
        run_len = j - i
        if run_len >= 3:
            # Trim everything from i onward
            return rows[:i]
        i = j
    return rows

if TYPE_CHECKING:
    pass


def _pick_best_per_page(stream_tables: list, lattice_tables: list) -> list:
    """Given Camelot's stream and lattice outputs, pick the better extraction
    per (page, bbox-region).

    Heuristic: for each page, lattice usually wins when it returns ≥1 high-
    accuracy SUBSTANTIVE table on that page (lattice means the PDF has visible
    ruled lines, which is a strong tabularity signal). Otherwise stream wins.

    v2.3.0 fix (per jama_open_1 regression caught by ``scripts/verify_corpus.py``):
    a lattice table must have **≥ 2 rows AND ≥ 2 cols** to count as "the page
    has lattice tables." Lattice often returns 1×1 / 1×2 / 2×1 artifacts on
    pages with text boxes, signature blocks, or running-header rules (JAMA
    PDFs are full of these). Those artifacts were causing the real 7×45
    stream tables to be discarded on pages 6/8/9 of jama_open_1. Two of those
    three tables produced clean HTML in the splice spike — the regression
    re-surfaced when the size check was missing.
    """
    by_page: dict[int, list] = {}
    for ct in stream_tables:
        page = getattr(ct, "page", 1)
        by_page.setdefault(page, []).append(("stream", ct))
    pages_with_lattice: dict[int, list] = {}
    for ct in lattice_tables:
        page = getattr(ct, "page", 1)
        try:
            acc = float(getattr(ct, "accuracy", 0))
        except (ValueError, TypeError):
            acc = 0.0
        if acc < 80.0:
            continue
        # Require a SUBSTANTIVE lattice table (≥ 2 rows AND ≥ 2 cols) before
        # treating the page as "owned by lattice." 1×N / N×1 results are
        # almost always text-box / rule-line artifacts, not real tables.
        try:
            n_rows = len(ct.df)
            n_cols = len(ct.df.columns)
        except Exception as exc:
            record_fallback("camelot_table_shape_exception", detail=type(exc).__name__)
            continue
        if n_rows < 2 or n_cols < 2:
            continue
        pages_with_lattice.setdefault(page, []).append(("lattice", ct))

    out: list = []
    for page in sorted(set(list(by_page.keys()) + list(pages_with_lattice.keys()))):
        if page in pages_with_lattice:
            stream_cts = [ct for _, ct in by_page.get(page, [])]
            for _, ct in pages_with_lattice[page]:
                out.append(_augment_lattice_with_stream_rows(ct, stream_cts))
        else:
            for _, ct in by_page.get(page, []):
                out.append(ct)
    return out


def _augment_lattice_with_stream_rows(lattice_ct, stream_cts: list):
    """Tier-2 (v2.4.94): recover rows a lattice table vertically TRUNCATED.

    Lattice flavor extracts clean headers + merged cells, but only inside the
    table's *ruled* region — when a table's lower rows sit below the ruling
    lines (PROSECCO Table 2: the "adjusted" / "remnant" rows), lattice stops at
    the box bottom while STREAM captured the whole table. The page-level
    winner-take-all then discards the fuller stream table.

    Fix: when a same-page stream table has the SAME column count, OVERLAPS the
    lattice bbox, and extends BELOW it, append the stream rows whose vertical
    centre falls below the lattice bbox (the rows lattice missed) onto the
    lattice frame — so the merged table keeps lattice's clean headers AND gains
    every data row. Stream's split value/parenthetical cells are rejoined later
    by ``_merge_continuation_rows``.

    Gated hard (equal n_cols + bbox overlap + extends-below) so a table lattice
    captured in full, or an unrelated stream table, is never touched. Returns
    ``lattice_ct`` unchanged (possibly mutated in place) — any failure is a
    transparent no-op.
    """
    try:
        import pandas as pd

        l_df = lattice_ct.df
        l_cols = len(l_df.columns)
        l_bbox = tuple(getattr(lattice_ct, "_bbox", ()) or ())
        if len(l_bbox) < 4:
            return lattice_ct
        l_ymin = l_bbox[1]
    except Exception as exc:
        record_fallback("lattice_augment_setup_exception", detail=type(exc).__name__)
        return lattice_ct

    best: tuple[int, list[list[str]], tuple] | None = None
    for s in stream_cts:
        try:
            s_df = s.df
            if len(s_df.columns) != l_cols:
                continue
            s_bbox = tuple(getattr(s, "_bbox", ()) or ())
            if len(s_bbox) < 4 or not _bboxes_overlap(s_bbox, l_bbox):
                continue
            if s_bbox[1] >= l_ymin:  # stream does not extend below the lattice box
                continue
            s_rows = getattr(s, "rows", None)
            if not s_rows or len(s_rows) != len(s_df):
                continue
            extra: list[list[str]] = []
            for r in range(len(s_df)):
                top, bottom = s_rows[r][0], s_rows[r][1]
                if (top + bottom) / 2.0 < l_ymin:
                    extra.append([str(s_df.iloc[r, c]) for c in range(l_cols)])
            if extra and (best is None or len(extra) > best[0]):
                best = (len(extra), extra, s_bbox)
        except Exception as exc:
            record_fallback("lattice_augment_scan_exception", detail=type(exc).__name__)
            continue

    if best is None:
        return lattice_ct
    try:
        import pandas as pd

        _, extra, s_bbox = best
        lattice_ct.df = pd.concat(
            [lattice_ct.df, pd.DataFrame(extra, columns=lattice_ct.df.columns)],
            ignore_index=True,
        )
        # Widen the bbox downward so caption/figure overlap logic sees the full
        # table extent; keep the lattice top edge.
        lattice_ct._bbox = (
            min(l_bbox[0], s_bbox[0]),
            min(l_bbox[1], s_bbox[1]),
            max(l_bbox[2], s_bbox[2]),
            l_bbox[3],
        )
    except Exception as exc:
        record_fallback("lattice_augment_merge_exception", detail=type(exc).__name__)
    return lattice_ct


def _camelot_table_to_dict(
    ct,
    idx: int,
    *,
    accuracy_threshold: float = 50.0,
    id_prefix: str = "camelot_t",
    label: str | None = None,
    allow_categorical: bool = False,
) -> Table | None:
    """Convert one Camelot table object into a docpluck Table dict, applying the
    shared row-cleaning pipeline (running-header strip, caption-row drop, prose
    trim, table-likeness gate) and cell emission.

    Returns ``None`` when the table is below ``accuracy_threshold``, too small,
    or doesn't survive the cleaning gate. ``label`` (when given — the
    region-driven path knows the caption by construction) is carried onto the
    dict; the legacy auto-detect path passes ``None`` and lets the caller pair.

    ``allow_categorical`` relaxes the region-path clean-grid gate to accept a
    purely CATEGORICAL table (text labels + text values, no numeric data cells —
    e.g. a replication-classification "Design facet | Same/Different" grid). The
    default numeric-data-row requirement is the right guard for the generic
    whitespace fallback, but the SIDE-BY-SIDE region path bounds the table by
    construction (gutter-clipped column + table-bottom clip + high Camelot
    accuracy), so a categorical grid there is trustworthy. The prose-fragment and
    caption-absorption guards still apply.
    """
    try:
        accuracy = float(ct.accuracy)
    except (AttributeError, ValueError, TypeError):
        accuracy = 0.0
    if accuracy < accuracy_threshold:
        return None
    df = ct.df
    try:
        n_rows = len(df)
        n_cols = len(df.columns)
    except Exception as exc:
        record_fallback("camelot_table_frame_exception", detail=type(exc).__name__)
        return None
    if n_rows < 2 or n_cols < 2:
        return None

    # Build the row matrix first; trim noisy rows; then emit cells.
    row_matrix: list[list[str]] = []
    for r in range(n_rows):
        row_cells: list[str] = [
            str(df.iloc[r, c]).replace("\n", " ").strip()
            for c in range(n_cols)
        ]
        row_matrix.append(row_cells)

    row_matrix = _strip_running_header_rows(row_matrix)
    # Capture the table's own absorbed caption number BEFORE the caption row is
    # dropped — it is the most reliable identity signal for caption pairing
    # (see ``_leading_table_caption_number``).
    caption_hint = _leading_table_caption_number(row_matrix)
    row_matrix = _drop_caption_first_row(row_matrix)
    # Trim trailing prose rows (Camelot sometimes bundles a small real table at
    # the top of a 2-column page with body prose below).
    row_matrix = _trim_prose_tail(row_matrix)
    if not _is_table_like(row_matrix):
        return None

    n_rows = len(row_matrix)
    n_cols = max((len(r) for r in row_matrix), default=0)

    cells: list[Cell] = []
    raw_row_texts: list[str] = []
    for r, row_cells in enumerate(row_matrix):
        for c, text in enumerate(row_cells):
            if not text:
                continue
            cells.append(
                {
                    "r": r,
                    "c": c,
                    "rowspan": 1,
                    "colspan": 1,
                    "text": text,
                    "is_header": (r == 0),
                    "bbox": (0.0, 0.0, 0.0, 0.0),
                }
            )
        row_text = " ".join(s for s in row_cells if s).strip()
        if row_text:
            raw_row_texts.append(row_text)

    # Region-driven path only: apply the prose-contamination + caption-absorption
    # guard. A caption-anchored region extends a fixed distance from the caption,
    # so on a SHORT / PROSE table it absorbs surrounding 2-column body text
    # (cog_emo Table 3 "study procedure paragraph") or reaches into a neighbouring
    # table's caption (cog_emo Table 9). The legacy auto-detect path is left
    # untouched here: applying this strict data-table gate to it wholesale rejects
    # legitimate-but-imperfect auto-detected tables (cog_emo Tables 5/6/7 — the
    # right tables with some header/prose bleed), a net regression. Auto-detect
    # keeps its own _trim_prose_tail / _is_table_like gate.
    if id_prefix.startswith("region"):
        from .whitespace import _trim_trailing_prose_rows, _whitespace_grid_is_clean
        cells = _trim_trailing_prose_rows(cells, allow_categorical=allow_categorical)
        if not _whitespace_grid_is_clean(cells, allow_categorical=allow_categorical):
            return None
        if not cells:
            return None
        # Recompute shape + raw_text from the trimmed cell set.
        n_rows = max((c["r"] for c in cells), default=-1) + 1
        n_cols = max((c["c"] for c in cells), default=-1) + 1
        kept_rows = sorted({c["r"] for c in cells})
        by_row: dict[int, list[Cell]] = {}
        for c in cells:
            by_row.setdefault(c["r"], []).append(c)
        raw_row_texts = []
        for r in kept_rows:
            row_text = " ".join(
                (c.get("text") or "") for c in sorted(by_row[r], key=lambda c: c["c"])
            ).strip()
            if row_text:
                raw_row_texts.append(row_text)

    try:
        page = int(ct.page)
    except (AttributeError, ValueError, TypeError):
        page = 1
    try:
        cam_bbox = tuple(ct._bbox)
    except (AttributeError, TypeError):
        cam_bbox = (0.0, 0.0, 0.0, 0.0)

    try:
        html = cells_to_html(cells)
    except Exception as exc:
        record_fallback("camelot_html_render_exception", detail=type(exc).__name__)
        html = None

    return {
        "id": f"{id_prefix}{idx}",
        "label": label,
        "page": page,
        "bbox": cam_bbox,
        "caption": None,
        "footnote": None,
        "kind": "structured",
        "rendering": "whitespace",
        # Clip to [0, 1] — Camelot's `accuracy` is occasionally ≥ 100 due to
        # floating-point arithmetic; without this clip, ``confidence > 1.0``
        # fails the ``test_table_html_renders_when_structured`` invariant.
        "confidence": max(0.0, min(1.0, accuracy / 100.0)),
        "n_rows": n_rows,
        "n_cols": n_cols,
        "header_rows": 1,
        "cells": cells,
        "html": html,
        "raw_text": "\n".join(raw_row_texts),
        # Internal-only pairing hint: the table's own absorbed caption number, if
        # any. Consumed + popped by ``extract_structured._find_caption_for_table``;
        # never surfaces in the public Table output.
        "_caption_hint_number": caption_hint,
    }


def extract_tables_camelot(
    pdf_bytes: bytes,
    *,
    accuracy_threshold: float = 50.0,
) -> list[Table]:
    """Run Camelot stream on each page; return tables as docpluck Table dicts.

    Returns ``[]`` if camelot is not installed or fails to run. Tables below
    ``accuracy_threshold`` (Camelot's self-reported accuracy 0–100) are filtered
    out. Tables with fewer than 2 rows or 2 columns are filtered out.

    The returned dicts have ``label=None`` and ``caption=None`` because Camelot
    does not extract these. Callers (typically ``extract_structured``) should
    merge these with docpluck-detected tables to recover label/caption.
    """
    try:
        import camelot
    except ImportError:
        return []

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(pdf_bytes)
        tmp_path = tmp.name

    try:
        try:
            # `strip_text="\n"` collapses cell-internal newlines so multi-line
            # cells render as single lines (per Camelot best practice).
            # Run BOTH stream and lattice; pick the better one per (page, region).
            stream_tables = list(
                camelot.read_pdf(tmp_path, pages="all", flavor="stream", strip_text="\n")
            )
        except Exception as exc:
            record_fallback("camelot_stream_exception", detail=type(exc).__name__)
            stream_tables = []
        try:
            lattice_tables = list(
                camelot.read_pdf(
                    tmp_path,
                    pages="all",
                    flavor="lattice",
                    strip_text="\n",
                    line_scale=40,
                    process_background=True,
                )
            )
        except Exception as exc:
            record_fallback("camelot_lattice_exception", detail=type(exc).__name__)
            lattice_tables = []
        tables_obj = _pick_best_per_page(stream_tables, lattice_tables)

        out: list[Table] = []
        for idx, ct in enumerate(tables_obj):
            td = _camelot_table_to_dict(ct, idx, accuracy_threshold=accuracy_threshold)
            if td is not None:
                out.append(td)
        return out
    finally:
        # Best-effort temp cleanup. On Windows, camelot (>=2.0) can still hold
        # the temp-file handle open when we reach here, so ``unlink`` raises
        # ``PermissionError [WinError 32]``. That exception used to propagate out
        # of this function and be swallowed by ``extract_structured``'s broad
        # ``except`` (→ ``camelot_failed``, zero tables) — silently dropping
        # EVERY table on Windows even though extraction succeeded. POSIX allows
        # unlinking an open file, so prod/Linux never saw it. Swallow the
        # cleanup error; the OS temp dir reclaims the file later.
        try:
            Path(tmp_path).unlink(missing_ok=True)
        except OSError:
            pass


def _area_overlap_frac(a: tuple[float, ...], b: tuple[float, ...]) -> float:
    """Fraction of box ``a`` covered by its intersection with ``b``. Both boxes
    are ``(x0, y_a, x1, y_b)`` in the SAME frame; y order is normalized so this
    works whether the tuples are top-down or bottom-up."""
    if len(a) < 4 or len(b) < 4:
        return 0.0
    ax0, ay0, ax1, ay1 = a[0], min(a[1], a[3]), a[2], max(a[1], a[3])
    bx0, by0, bx1, by1 = b[0], min(b[1], b[3]), b[2], max(b[1], b[3])
    ix0, iy0 = max(ax0, bx0), max(ay0, by0)
    ix1, iy1 = min(ax1, bx1), min(ay1, by1)
    if ix1 <= ix0 or iy1 <= iy0:
        return 0.0
    inter = (ix1 - ix0) * (iy1 - iy0)
    area_a = max((ax1 - ax0) * (ay1 - ay0), 1e-6)
    return inter / area_a


def extract_tables_camelot_by_region(
    pdf_bytes: bytes,
    region_specs: list[dict],
    *,
    accuracy_threshold: float = 50.0,
) -> dict[str, Table]:
    """Region-driven Camelot capture: extract exactly one table per caption by
    handing Camelot the caption-anchored region as ``table_areas``.

    This is the reliable alternative to blind ``pages="all"`` auto-detection +
    post-hoc caption pairing. Because each Camelot extraction is constrained to a
    known caption's region, the result IS that caption's table by construction —
    no header absorption, no two-tables-merged-into-one bbox, no pairing
    ambiguity. docpluck already computes the region (``_region_for_caption``); we
    feed it back to Camelot instead of discarding it.

    Args:
        pdf_bytes: the PDF.
        region_specs: one dict per caption, each with keys:
            ``key`` (a stable id used in the returned mapping),
            ``page`` (1-indexed),
            ``area`` (Camelot ``"x1,y1,x2,y2"`` PDF bottom-up string; top-left
                larger-y, bottom-right smaller-y),
            ``area_bu`` (the same box as a 4-tuple ``(x0, y_top, x1, y_bottom)``
                in bottom-up coords, for matching returned tables back).
        accuracy_threshold: passed through to ``_camelot_table_to_dict``.

    Returns:
        ``{key: Table}`` for each caption that yielded a usable table. Captions
        with no region/extraction are simply absent (the caller falls back to its
        existing whitespace/isolated path for those).
    """
    try:
        import camelot
    except ImportError:
        return {}
    if not region_specs:
        return {}

    by_page: dict[int, list[dict]] = {}
    for spec in region_specs:
        by_page.setdefault(int(spec["page"]), []).append(spec)

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(pdf_bytes)
        tmp_path = tmp.name

    def _match_and_emit(specs: list[dict], tables: list) -> None:
        # One-to-one greedy match: each returned table claimed by the spec it
        # best overlaps. Camelot returns tables sorted by POSITION, not in
        # table_areas order, and two caption regions can overlap (a lower
        # caption inside an upper table's region) — so match by bbox, not by
        # index, and let each Camelot table back at most one spec.
        cand: list[tuple[float, int, int]] = []  # (overlap, spec_i, table_i)
        for si, spec in enumerate(specs):
            for ti, t in enumerate(tables):
                tb = tuple(getattr(t, "_bbox", ()) or ())
                frac = _area_overlap_frac(spec["area_bu"], tb)
                if frac > 0.0:
                    cand.append((frac, si, ti))
        cand.sort(reverse=True)
        used_s: set[int] = set()
        used_t: set[int] = set()
        for frac, si, ti in cand:
            if si in used_s or ti in used_t:
                continue
            used_s.add(si)
            used_t.add(ti)
            spec = specs[si]
            td = _camelot_table_to_dict(
                tables[ti], 0,
                accuracy_threshold=accuracy_threshold,
                id_prefix="region_t",
                label=spec.get("label"),
                allow_categorical=bool(spec.get("isolate")),
            )
            if td is not None:
                td["id"] = f"region_{spec['key']}"
                out[spec["key"]] = td

    out: dict[str, Table] = {}
    try:
        for page, specs in by_page.items():
            # Side-by-side column specs (``isolate=True``) MUST run in their own
            # single-area Camelot call: ``stream`` column detection is computed
            # across ALL table_areas in a call, so batching a narrow left column
            # and a narrow right column together makes Camelot collapse each to a
            # single column (chandrashekar Table 4 → 19×1 instead of the 10×2
            # LeBel grid). Isolating each restores correct per-column structure.
            isolated = [s for s in specs if s.get("isolate")]
            batched = [s for s in specs if not s.get("isolate")]
            for spec in isolated:
                try:
                    tables = list(
                        camelot.read_pdf(
                            tmp_path, pages=str(page), flavor="stream",
                            table_areas=[spec["area"]], strip_text="\n",
                            suppress_stdout=True,
                        )
                    )
                except Exception as exc:
                    record_fallback("camelot_region_exception", detail=type(exc).__name__)
                    continue
                _match_and_emit([spec], tables)
            if batched:
                areas = [s["area"] for s in batched]
                try:
                    tables = list(
                        camelot.read_pdf(
                            tmp_path, pages=str(page), flavor="stream",
                            table_areas=areas, strip_text="\n", suppress_stdout=True,
                        )
                    )
                except Exception as exc:
                    record_fallback("camelot_region_exception", detail=type(exc).__name__)
                    continue
                _match_and_emit(batched, tables)
        return out
    finally:
        try:
            Path(tmp_path).unlink(missing_ok=True)
        except OSError:
            pass


def _bboxes_overlap(a: tuple[float, ...], b: tuple[float, ...]) -> bool:
    """Liberal bbox overlap check: intersection area > 0 in any consistent space."""
    if not a or not b or len(a) < 4 or len(b) < 4:
        return False
    if a == (0.0, 0.0, 0.0, 0.0) or b == (0.0, 0.0, 0.0, 0.0):
        return False
    a0, a1, a2, a3 = a[0], a[1], a[2], a[3]
    b0, b1, b2, b3 = b[0], b[1], b[2], b[3]
    return (
        max(a0, b0) < min(a2, b2)
        and max(a1, b1) < min(a3, b3)
    )


def merge_camelot_with_docpluck(
    docpluck_tables: list[Table],
    camelot_tables: list[Table],
) -> list[Table]:
    """Merge Camelot-extracted tables with docpluck-detected tables.

    Strategy:
      1. For each docpluck table, if it has empty ``cells`` (whitespace/isolated
         table that pdfplumber couldn't structure), look for a Camelot table on
         the same page. Replace the empty cells with Camelot's. Preserve
         docpluck's ``label``, ``caption``, ``footnote`` (Camelot doesn't have these).
      2. For Camelot tables on pages where docpluck found nothing covering them,
         add them as new tables (synthesizing a sequential label like "Table N"
         that doesn't collide with docpluck-supplied labels).
      3. Return the merged list, sorted by ``(page, label)``.
    """
    used_camelot: set[int] = set()
    out: list[Table] = []

    # Pass 1: enrich docpluck tables with camelot cells where they exist
    for dt in docpluck_tables:
        if dt.get("cells"):
            out.append(dt)
            continue
        # Find a camelot table on the same page (prefer bbox overlap)
        same_page_idx = [
            i for i, ct in enumerate(camelot_tables)
            if i not in used_camelot and ct.get("page") == dt.get("page")
        ]
        match: int | None = None
        for i in same_page_idx:
            if _bboxes_overlap(camelot_tables[i].get("bbox", ()), dt.get("bbox", ())):
                match = i
                break
        if match is None and same_page_idx:
            # Fallback: same-page largest camelot table
            match = max(same_page_idx, key=lambda i: len(camelot_tables[i].get("cells", [])))
        if match is not None:
            ct = camelot_tables[match]
            used_camelot.add(match)
            enriched = dict(dt)
            enriched["cells"] = ct["cells"]
            enriched["n_rows"] = ct["n_rows"]
            enriched["n_cols"] = ct["n_cols"]
            enriched["header_rows"] = ct.get("header_rows", 1)
            enriched["rendering"] = "whitespace"
            enriched["kind"] = "structured"
            enriched["confidence"] = ct.get("confidence", enriched.get("confidence"))
            enriched["html"] = ct.get("html")
            # Keep docpluck's label/caption/footnote/raw_text/bbox
            out.append(enriched)
        else:
            out.append(dt)

    # Pass 2: add unused camelot tables (pages docpluck missed entirely)
    docpluck_label_count = sum(1 for t in out if t.get("label"))
    camelot_synthesized_idx = 0
    for i, ct in enumerate(camelot_tables):
        if i in used_camelot:
            continue
        synthesized = dict(ct)
        if not synthesized.get("label"):
            camelot_synthesized_idx += 1
            synthesized["label"] = f"Table {docpluck_label_count + camelot_synthesized_idx}"
        out.append(synthesized)

    # Sort by (page, label) for stable ordering
    out.sort(
        key=lambda t: (
            t.get("page") or 0,
            t.get("label") or "",
        )
    )
    return out


__all__ = ["extract_tables_camelot", "merge_camelot_with_docpluck"]
