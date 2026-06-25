"""
Whitespace (column-gap) cell clustering for lineless tables.

Algorithm (per spec §5.4):
  1. Cluster words by y (gap > 1.2 × median line-height → new row).
  2. Find column boundaries from word x-gaps (gap > 5pt) that persist
     across ≥60% of rows.
  3. Assign each word to a column whose interval contains its x-midpoint.
  4. Concatenate words within (row, col) → cell text; normalize.
  5. First row is header iff avg word-height > body × 1.05.

Returns [] when fewer than 3 rows or fewer than 2 columns can be derived.
"""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

from docpluck.extract_layout import LayoutDoc

from . import Cell
from .bbox_utils import chars_in_bbox, words_in_bbox
from .detect import CandidateRegion


WHITESPACE_MIN_ROWS: int = 3
ROW_GAP_RATIO: float = 1.2
ROW_GAP_FLOOR_PT: float = 5.0
COLUMN_GAP_PT: float = 5.0
COLUMN_STABILITY_FRACTION: float = 0.6
HEADER_HEIGHT_RATIO: float = 1.05
BODY_HEIGHT_FALLBACK: float = 10.0

# Char-level fallback (RC-T, 2026-06-25): on tight-kerned PDFs pdfplumber's word
# grouper glues a whole numeric row into ONE "word" (e.g. ip_feldman Table 10's
# ``.29***−.21***.07``), so the WORD-gap column detector finds no gaps and returns
# []. The chars themselves are still cleanly separated by large inter-COLUMN gaps
# (~20-80pt) vs tiny inter-CHAR gaps (~0-3pt). This is the char-level absolute-x-gap
# fallback the `pdfplumber_extract_words_unreliable` lesson mandates. A bigger gap
# floor than COLUMN_GAP_PT is required because adjacent chars within a word are
# ~0pt apart but a column break is large — 12pt cleanly separates the two regimes
# (verified: ip_feldman T10 column gaps are 23-78pt; the widest intra-cell gap,
# the space before a leading minus, is < 6pt).
CHAR_COLUMN_GAP_PT: float = 12.0
# Tolerance for clustering candidate column boundaries across rows in the char
# path: a real column edge wobbles a few points row-to-row (leading minus signs,
# right-alignment), so boundaries within this band are one column.
CHAR_BOUNDARY_BUCKET_PT: float = 8.0


def whitespace_cells(layout: LayoutDoc, *, region: CandidateRegion) -> list[Cell]:
    """Cluster words inside `region` into a grid of Cells using whitespace gaps.

    Falls back to a CHAR-level grid (``char_whitespace_cells``) when the word-based
    column detector cannot find ≥2 columns — the tight-kerned-PDF case where
    pdfplumber pre-joins a numeric row into a single word (RC-T, 2026-06-25).
    """
    words = words_in_bbox(layout, bbox=region.bbox, page=region.page)
    if len(words) < WHITESPACE_MIN_ROWS:
        return []

    rows = _cluster_into_rows(words)
    if len(rows) < WHITESPACE_MIN_ROWS:
        return []

    column_xs = _find_stable_column_boundaries(rows, bbox=region.bbox)
    if len(column_xs) < 3:
        # Word-gap detection failed (likely tight-kerning glued the row into one
        # word). Retry at the char level before giving up.
        return char_whitespace_cells(layout, region=region)

    body_height = _modal_word_height(words)
    header_row_is_header = _row_is_header(rows[0], body_height)

    cells: list[Cell] = []
    for r, row_words in enumerate(rows):
        if not row_words:
            continue
        row_top = min(w["top"] for w in row_words)
        row_bot = max(w["bottom"] for w in row_words)
        is_header = header_row_is_header if r == 0 else False
        for c, (x_left, x_right) in enumerate(zip(column_xs[:-1], column_xs[1:])):
            in_cell = [
                w for w in row_words
                if x_left <= (w["x0"] + w["x1"]) / 2 <= x_right
            ]
            in_cell.sort(key=lambda w: w["x0"])
            text = _normalize_cell_text(" ".join(w.get("text", "") for w in in_cell))
            cells.append({
                "r": r,
                "c": c,
                "rowspan": 1,
                "colspan": 1,
                "text": text,
                "is_header": is_header,
                "bbox": (x_left, row_top, x_right, row_bot),
            })
    return cells


def char_whitespace_cells(layout: LayoutDoc, *, region: CandidateRegion) -> list[Cell]:
    """Char-level grid recovery — the tight-kerned-PDF fallback for whitespace_cells.

    Identical algorithm to ``whitespace_cells`` but operating on individual CHARS
    rather than pdfplumber words, with a larger column-gap floor
    (``CHAR_COLUMN_GAP_PT``) to separate inter-column gaps from inter-char gaps.
    Used only when the word path found < 2 columns, so it never changes a table
    that already extracts correctly.

    Returns [] when fewer than 3 rows or fewer than 2 columns can be derived from
    chars either — i.e. the region genuinely has no recoverable tabular grid (the
    caller then falls through to the existing raw_text / caption-only path).
    """
    chars = chars_in_bbox(layout, bbox=region.bbox, page=region.page)
    # Drop whitespace-only chars: pdfplumber emits space glyphs with their own
    # bbox, which would corrupt both row clustering and gap measurement.
    chars = [c for c in chars if (c.get("text", "") or "").strip()]
    if len(chars) < WHITESPACE_MIN_ROWS:
        return []

    rows = _cluster_into_rows(chars)
    if len(rows) < WHITESPACE_MIN_ROWS:
        return []

    column_xs = _find_stable_column_boundaries(
        rows, bbox=region.bbox, gap_pt=CHAR_COLUMN_GAP_PT, bucket_pt=CHAR_BOUNDARY_BUCKET_PT
    )
    if len(column_xs) < 3:
        return []

    body_height = _modal_word_height(chars)
    header_row_is_header = _row_is_header(rows[0], body_height)

    cells: list[Cell] = []
    for r, row_chars in enumerate(rows):
        if not row_chars:
            continue
        row_top = min(c["top"] for c in row_chars)
        row_bot = max(c["bottom"] for c in row_chars)
        is_header = header_row_is_header if r == 0 else False
        for c, (x_left, x_right) in enumerate(zip(column_xs[:-1], column_xs[1:])):
            in_cell = [
                ch for ch in row_chars
                if x_left <= (ch["x0"] + ch["x1"]) / 2 <= x_right
            ]
            in_cell.sort(key=lambda ch: ch["x0"])
            text = _normalize_cell_text(_join_chars(in_cell))
            cells.append({
                "r": r,
                "c": c,
                "rowspan": 1,
                "colspan": 1,
                "text": text,
                "is_header": is_header,
                "bbox": (x_left, row_top, x_right, row_bot),
            })
    return cells


# --- helpers ---


def _cluster_into_rows(words: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    """Sort words by reading order, then split into rows on y-gap > median × 1.2."""
    if not words:
        return []
    sorted_words = sorted(words, key=lambda w: (w["top"], w["x0"]))
    heights = [max(w["bottom"] - w["top"], 0.0) for w in sorted_words]
    if heights:
        sorted_heights = sorted(heights)
        median_h = sorted_heights[len(sorted_heights) // 2]
    else:
        median_h = BODY_HEIGHT_FALLBACK
    threshold = max(median_h * ROW_GAP_RATIO, ROW_GAP_FLOOR_PT)

    rows: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = [sorted_words[0]]
    for w in sorted_words[1:]:
        prev_top = current[-1]["top"]
        if w["top"] - prev_top > threshold:
            rows.append(current)
            current = [w]
        else:
            current.append(w)
    if current:
        rows.append(current)
    return rows


def _find_stable_column_boundaries(
    rows: list[list[dict[str, Any]]],
    *,
    bbox: tuple[float, float, float, float],
    gap_pt: float = COLUMN_GAP_PT,
    bucket_pt: float = 0.0,
) -> list[float]:
    """Find x-positions where ≥COLUMN_STABILITY_FRACTION of MULTI-COLUMN rows have a
    gap > ``gap_pt``.

    ``gap_pt`` defaults to the word-level ``COLUMN_GAP_PT``; the char-level fallback
    passes the larger ``CHAR_COLUMN_GAP_PT`` so it doesn't split a tight inter-char
    gap into a spurious boundary.

    ``bucket_pt`` (char-path only, default 0 = exact) groups candidate boundaries
    that fall within ±bucket_pt of each other before the stability vote — a real
    column edge wobbles a few points row-to-row (ip_feldman T10's two data columns
    start at x≈218-224 and x≈273-285), so exact-integer voting would scatter one
    true boundary across several sub-threshold candidates and find nothing.

    The denominator is the count of rows that ACTUALLY span ≥2 columns (have at
    least one gap > ``gap_pt``), NOT every row with ≥2 tokens. Single-column
    section-label rows (``Negative well-being``) and the wrapped caption must not
    dilute the stability fraction — otherwise a table whose data rows are
    interspersed with label rows never reaches the threshold.
    """
    if not rows:
        return []

    if bucket_pt <= 0:
        # ---- WORD path: BYTE-IDENTICAL to the pre-2026-06-25 implementation. ----
        # Vote on gap MIDPOINTS; denominator is every row with ≥2 tokens (NOT just
        # multi-column rows). Kept exactly as-was so the char-path addition cannot
        # perturb any table that already extracts correctly.
        candidates: defaultdict[int, int] = defaultdict(int)
        valid_rows = 0
        for row in rows:
            if len(row) < 2:
                continue
            valid_rows += 1
            row_sorted = sorted(row, key=lambda w: w["x0"])
            for prev, curr in zip(row_sorted[:-1], row_sorted[1:]):
                gap = curr["x0"] - prev["x1"]
                if gap > gap_pt:
                    mid = round((prev["x1"] + curr["x0"]) / 2)
                    candidates[mid] += 1
        if valid_rows == 0:
            return []
        threshold = max(1, int(valid_rows * COLUMN_STABILITY_FRACTION))
        stable = sorted(float(x) for x, count in candidates.items() if count >= threshold)
        boundaries = [bbox[0]] + stable + [bbox[2]]
        deduped: list[float] = []
        for b in boundaries:
            if not deduped or b - deduped[-1] > 1.0:
                deduped.append(b)
        return deduped

    # ---- CHAR path (bucket_pt > 0): column-START-edge voting. ----
    # Vote on the x0 of the run FOLLOWING each large gap — in a right-aligned
    # numeric table the LABEL column is variable-width (so gap midpoints scatter),
    # while the DATA columns are left-aligned to fixed x (stable left edges).
    # Denominator is the count of rows that ACTUALLY span ≥2 columns (≥1 gap >
    # gap_pt) — single-column label rows (``Negative well-being``) and the wrapped
    # caption must not dilute the stability fraction.
    row_marks: list[list[float]] = []
    for row in rows:
        if len(row) < 2:
            continue
        row_sorted = sorted(row, key=lambda w: w["x0"])
        marks = [
            curr["x0"]
            for prev, curr in zip(row_sorted[:-1], row_sorted[1:])
            if (curr["x0"] - prev["x1"]) > gap_pt
        ]
        if marks:
            row_marks.append(marks)
    valid_rows = len(row_marks)
    if valid_rows == 0:
        return []

    all_marks = sorted(m for marks in row_marks for m in marks)
    clusters: list[list[float]] = []
    for m in all_marks:
        if clusters and m - clusters[-1][-1] <= bucket_pt:
            clusters[-1].append(m)
        else:
            clusters.append([m])
    threshold = max(1, int(valid_rows * COLUMN_STABILITY_FRACTION))
    stable = []
    for cl in clusters:
        lo, hi = cl[0] - 0.01, cl[-1] + 0.01
        rows_hit = sum(1 for marks in row_marks if any(lo <= m <= hi for m in marks))
        if rows_hit >= threshold:
            # Column STARTS are boundaries; nudge left so the boundary sits in
            # the gap, not on the first glyph's x0.
            stable.append(min(cl) - 0.5)
    stable.sort()

    boundaries = [bbox[0]] + stable + [bbox[2]]
    # Deduplicate near-identical boundaries (within 1pt).
    deduped: list[float] = []
    for b in boundaries:
        if not deduped or b - deduped[-1] > 1.0:
            deduped.append(b)
    return deduped


def _modal_word_height(words: list[dict[str, Any]]) -> float:
    heights: list[float] = []
    for w in words:
        h = w.get("bottom", 0) - w.get("top", 0)
        if h > 0:
            heights.append(round(h, 1))
    if not heights:
        return BODY_HEIGHT_FALLBACK
    counts: defaultdict[float, int] = defaultdict(int)
    for h in heights:
        counts[h] += 1
    return max(counts.items(), key=lambda kv: kv[1])[0]


def _row_is_header(row_words: list[dict[str, Any]], body_height: float) -> bool:
    if not row_words:
        return False
    heights = [w["bottom"] - w["top"] for w in row_words if w["bottom"] - w["top"] > 0]
    if not heights:
        return False
    avg = sum(heights) / len(heights)
    return avg > body_height * HEADER_HEIGHT_RATIO


# Intra-cell word-break threshold for the char path. Adjacent glyphs within a
# word sit ~0pt apart; a space between words in the same cell is ~2-4pt. A column
# break (handled by CHAR_COLUMN_GAP_PT) is ≥12pt. 1.8pt cleanly separates an
# intra-word gap (insert nothing) from an inter-word gap (insert a space) without
# tripping on kerning.
CHAR_WORD_BREAK_PT: float = 1.8


def _join_chars(chars: list[dict[str, Any]]) -> str:
    """Concatenate already-x-sorted chars, inserting a single space where a
    horizontal gap indicates a word break. Chars carry no whitespace glyphs of
    their own (the caller stripped them), so spacing must be reconstructed from
    geometry — otherwise ``Depressive symptoms`` joins to ``Depressivesymptoms``.
    """
    out: list[str] = []
    prev_x1: float | None = None
    for ch in chars:
        t = ch.get("text", "") or ""
        if not t:
            continue
        x0 = ch.get("x0", 0.0)
        if prev_x1 is not None and (x0 - prev_x1) > CHAR_WORD_BREAK_PT:
            out.append(" ")
        out.append(t)
        prev_x1 = ch.get("x1", x0)
    return "".join(out)


_WHITESPACE_RE = re.compile(r"\s+")


def _normalize_cell_text(text: str) -> str:
    text = text.replace("­", "")    # soft hyphen
    text = text.replace("−", "-")   # unicode minus → ASCII hyphen
    return _WHITESPACE_RE.sub(" ", text).strip()


__all__ = ["whitespace_cells", "char_whitespace_cells"]
