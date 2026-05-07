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
from .bbox_utils import words_in_bbox
from .detect import CandidateRegion


WHITESPACE_MIN_ROWS: int = 3
ROW_GAP_RATIO: float = 1.2
ROW_GAP_FLOOR_PT: float = 5.0
COLUMN_GAP_PT: float = 5.0
COLUMN_STABILITY_FRACTION: float = 0.6
HEADER_HEIGHT_RATIO: float = 1.05
BODY_HEIGHT_FALLBACK: float = 10.0


def whitespace_cells(layout: LayoutDoc, *, region: CandidateRegion) -> list[Cell]:
    """Cluster words inside `region` into a grid of Cells using whitespace gaps."""
    words = words_in_bbox(layout, bbox=region.bbox, page=region.page)
    if len(words) < WHITESPACE_MIN_ROWS:
        return []

    rows = _cluster_into_rows(words)
    if len(rows) < WHITESPACE_MIN_ROWS:
        return []

    column_xs = _find_stable_column_boundaries(rows, bbox=region.bbox)
    if len(column_xs) < 3:
        return []

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
) -> list[float]:
    """Find x-positions where ≥COLUMN_STABILITY_FRACTION of rows have a word-gap > COLUMN_GAP_PT."""
    if not rows:
        return []
    candidates: defaultdict[int, int] = defaultdict(int)
    valid_rows = 0
    for row in rows:
        if len(row) < 2:
            continue
        valid_rows += 1
        row_sorted = sorted(row, key=lambda w: w["x0"])
        for prev, curr in zip(row_sorted[:-1], row_sorted[1:]):
            gap = curr["x0"] - prev["x1"]
            if gap > COLUMN_GAP_PT:
                mid = round((prev["x1"] + curr["x0"]) / 2)
                candidates[mid] += 1

    if valid_rows == 0:
        return []
    threshold = max(1, int(valid_rows * COLUMN_STABILITY_FRACTION))
    stable = sorted(float(x) for x, count in candidates.items() if count >= threshold)
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


_WHITESPACE_RE = re.compile(r"\s+")


def _normalize_cell_text(text: str) -> str:
    text = text.replace("­", "")    # soft hyphen
    text = text.replace("−", "-")   # unicode minus → ASCII hyphen
    return _WHITESPACE_RE.sub(" ", text).strip()


__all__ = ["whitespace_cells"]
