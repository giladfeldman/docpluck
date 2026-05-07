"""
Lattice (ruling-line) cell clustering for tables with horizontal/vertical rules.

Algorithm (per spec §5.3):
  1. Cluster horizontal segments by y → row separators (sorted ascending).
  2. Cluster vertical segments by x → column separators (sorted ascending).
     If no vertical rules: derive columns from word x-gaps inside the region.
  3. Build grid cells from adjacent (row, column) separator pairs.
  4. Assign chars to cells by midpoint containment.
  5. Concatenate chars per cell in reading order; normalize whitespace +
     U+00AD soft-hyphen + U+2212 unicode-minus.
  6. Mark first row as header iff bold-dominant or avg-size > body × 1.05.
"""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

from docpluck.extract_layout import LayoutDoc

from . import Cell
from .bbox_utils import chars_in_bbox, words_in_bbox
from .detect import CandidateRegion


SNAP_TOLERANCE_PT: float = 2.0
LATTICE_MIN_HORIZONTAL_RULES: int = 2
WORD_COLUMN_GAP_PT: float = 8.0
HEADER_FONT_SIZE_RATIO: float = 1.05
HEADER_BOLD_RATIO: float = 0.5
BODY_SIZE_FALLBACK: float = 10.0


def lattice_cells(layout: LayoutDoc, *, region: CandidateRegion) -> list[Cell]:
    """Cluster chars in `region` into a grid of Cells using ruling-line geometry.

    Returns an empty list if the region has fewer than 2 horizontal rule
    separators after clustering, or if no column separators can be derived.
    """
    page_obj = layout.pages[region.page - 1]
    rx0, rtop, rx1, rbottom = region.bbox

    horizontal_rules = _horizontal_rules_in_region(page_obj, region.bbox)
    horiz_ys = _cluster_positions([_line_y(ln) for ln in horizontal_rules])
    if len(horiz_ys) < LATTICE_MIN_HORIZONTAL_RULES:
        return []

    vertical_rules = _vertical_rules_in_region(page_obj, region.bbox)
    vert_xs = _cluster_positions([_line_x(ln) for ln in vertical_rules])
    if len(vert_xs) < 2:
        vert_xs = _derive_columns_from_words(layout, region=region)
        if len(vert_xs) < 2:
            return []

    chars = chars_in_bbox(layout, bbox=region.bbox, page=region.page)
    body_size = _modal_font_size(chars)

    cells: list[Cell] = []
    for r, (y_top, y_bot) in enumerate(zip(horiz_ys[:-1], horiz_ys[1:])):
        row_chars: list[dict[str, Any]] = [
            ch for ch in chars
            if y_top <= (ch["top"] + ch["bottom"]) / 2 <= y_bot
        ]
        row_is_header = _row_is_header(row_chars, body_size) if r == 0 else False
        for c, (x_left, x_right) in enumerate(zip(vert_xs[:-1], vert_xs[1:])):
            cell_chars = [
                ch for ch in row_chars
                if x_left <= (ch["x0"] + ch["x1"]) / 2 <= x_right
            ]
            cell_chars.sort(key=lambda ch: (ch["top"], ch["x0"]))
            text = _normalize_cell_text("".join(ch.get("text", "") for ch in cell_chars))
            cells.append({
                "r": r,
                "c": c,
                "rowspan": 1,
                "colspan": 1,
                "text": text,
                "is_header": row_is_header,
                "bbox": (x_left, y_top, x_right, y_bot),
            })

    return cells


# --- helpers ---


def _horizontal_rules_in_region(page_obj, bbox: tuple[float, float, float, float]) -> list[dict]:
    """Lines wider than tall, lying inside the region (with 2pt slack)."""
    x0, top, x1, bottom = bbox
    out: list[dict] = []
    for ln in page_obj.lines or ():
        width = ln["x1"] - ln["x0"]
        height = ln["bottom"] - ln["top"]
        if width > max(height, 0.5) * 5:
            if x0 - 2 <= ln["x0"] and ln["x1"] <= x1 + 2 and top - 2 <= ln["top"] <= bottom + 2:
                out.append(dict(ln))
    return out


def _vertical_rules_in_region(page_obj, bbox: tuple[float, float, float, float]) -> list[dict]:
    """Lines taller than wide, lying inside the region (with 2pt slack)."""
    x0, top, x1, bottom = bbox
    out: list[dict] = []
    for ln in page_obj.lines or ():
        width = ln["x1"] - ln["x0"]
        height = ln["bottom"] - ln["top"]
        if height > max(width, 0.5) * 5:
            if x0 - 2 <= ln["x0"] <= x1 + 2 and top - 2 <= ln["top"] and ln["bottom"] <= bottom + 2:
                out.append(dict(ln))
    return out


def _line_y(ln: dict) -> float:
    """y-coordinate of a horizontal rule (midpoint of top/bottom)."""
    return (ln["top"] + ln["bottom"]) / 2


def _line_x(ln: dict) -> float:
    """x-coordinate of a vertical rule (midpoint of x0/x1)."""
    return (ln["x0"] + ln["x1"]) / 2


def _cluster_positions(positions: list[float]) -> list[float]:
    """Cluster positions within SNAP_TOLERANCE_PT into single representative values, sorted asc."""
    if not positions:
        return []
    positions_sorted = sorted(positions)
    clusters: list[list[float]] = [[positions_sorted[0]]]
    for v in positions_sorted[1:]:
        if v - clusters[-1][-1] <= SNAP_TOLERANCE_PT:
            clusters[-1].append(v)
        else:
            clusters.append([v])
    return [sum(c) / len(c) for c in clusters]


def _derive_columns_from_words(layout: LayoutDoc, *, region: CandidateRegion) -> list[float]:
    """Fallback: cluster word x-gaps to find column boundaries.

    Returns a sorted list of x-coordinates including region.bbox left/right edges.
    """
    words = words_in_bbox(layout, bbox=region.bbox, page=region.page)
    if not words:
        return []
    words_sorted = sorted(words, key=lambda w: w["x0"])
    boundaries: list[float] = [region.bbox[0]]
    last_x1 = words_sorted[0]["x1"]
    for w in words_sorted[1:]:
        gap = w["x0"] - last_x1
        if gap > WORD_COLUMN_GAP_PT:
            boundaries.append((last_x1 + w["x0"]) / 2)
        last_x1 = max(last_x1, w["x1"])
    boundaries.append(region.bbox[2])
    # Sort + dedup with snap clustering so near-identical boundaries collapse.
    return _cluster_positions(boundaries)


def _modal_font_size(chars: list[dict[str, Any]]) -> float:
    sizes: list[float] = []
    for c in chars:
        s = c.get("size")
        if s:
            sizes.append(round(float(s), 1))
    if not sizes:
        return BODY_SIZE_FALLBACK
    counts: defaultdict[float, int] = defaultdict(int)
    for s in sizes:
        counts[s] += 1
    return max(counts.items(), key=lambda kv: kv[1])[0]


def _row_is_header(row_chars: list[dict[str, Any]], body_size: float) -> bool:
    if not row_chars:
        return False
    sizes = [c.get("size", body_size) for c in row_chars if c.get("size")]
    avg_size = sum(sizes) / len(sizes) if sizes else body_size
    if avg_size > body_size * HEADER_FONT_SIZE_RATIO:
        return True
    bold_count = sum(1 for c in row_chars if "Bold" in str(c.get("fontname", "")))
    return bold_count >= len(row_chars) * HEADER_BOLD_RATIO


_WHITESPACE_RE = re.compile(r"\s+")


def _normalize_cell_text(text: str) -> str:
    text = text.replace("­", "")    # soft hyphen
    text = text.replace("−", "-")   # unicode minus → ASCII hyphen
    return _WHITESPACE_RE.sub(" ", text).strip()


__all__ = ["lattice_cells"]
