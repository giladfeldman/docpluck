"""
Bbox -> char-range and bbox -> word/char slicing utilities.

Operates on the LayoutDoc abstraction from docpluck/extract_layout.py.
Bbox parameters use pdfplumber's top-down convention: (x0, top, x1, bottom).

See spec §5.8.
"""

from __future__ import annotations

from typing import Any

from docpluck.extract_layout import LayoutDoc


Bbox = tuple[float, float, float, float]


def bbox_to_char_range(
    layout: LayoutDoc,
    *,
    bbox: Bbox,
    page: int,
) -> tuple[int, int]:
    """Map a (page, bbox) to (char_start, char_end) in layout.raw_text.

    Args:
        layout: LayoutDoc from extract_pdf_layout().
        bbox: (x0, top, x1, bottom) in pdfplumber coordinates.
        page: 1-indexed page number.

    Returns:
        (char_start, char_end) inclusive-exclusive offsets in raw_text.

    Raises:
        ValueError: if page is out of range.
    """
    if not (1 <= page <= len(layout.pages)):
        raise ValueError(f"page {page} out of range [1, {len(layout.pages)}]")

    page_offsets = layout.page_offsets
    page_start = page_offsets[page - 1]
    page_end = page_offsets[page] if page < len(page_offsets) else len(layout.raw_text)

    chars = chars_in_bbox(layout, bbox=bbox, page=page)
    if not chars:
        return (page_start, page_start)

    # Reading order: top-to-bottom, then left-to-right.
    chars_sorted = sorted(chars, key=lambda c: (c.get("top", 0), c.get("x0", 0)))
    page_text = layout.raw_text[page_start:page_end]
    if not page_text:
        return (page_start, page_start)

    first_text = chars_sorted[0].get("text", "")
    last_text = chars_sorted[-1].get("text", "")
    if not first_text:
        return (page_start, page_start)

    first_offset = page_text.find(first_text)
    last_offset = page_text.rfind(last_text)
    if first_offset == -1:
        first_offset = 0
    if last_offset == -1:
        last_offset = len(page_text)

    char_start = page_start + first_offset
    char_end = page_start + last_offset + len(last_text)
    if char_end < char_start:
        char_end = char_start
    return (char_start, char_end)


def words_in_bbox(
    layout: LayoutDoc,
    *,
    bbox: Bbox,
    page: int,
) -> list[dict[str, Any]]:
    """All words in layout whose midpoint falls inside bbox on the given page."""
    if not (1 <= page <= len(layout.pages)):
        raise ValueError(f"page {page} out of range [1, {len(layout.pages)}]")
    page_obj = layout.pages[page - 1]
    x0, top, x1, bottom = bbox
    return [
        dict(w) for w in page_obj.words
        if x0 <= (w["x0"] + w["x1"]) / 2 <= x1
        and top <= (w["top"] + w["bottom"]) / 2 <= bottom
    ]


def chars_in_bbox(
    layout: LayoutDoc,
    *,
    bbox: Bbox,
    page: int,
) -> list[dict[str, Any]]:
    """All chars in layout whose midpoint falls inside bbox on the given page."""
    if not (1 <= page <= len(layout.pages)):
        raise ValueError(f"page {page} out of range [1, {len(layout.pages)}]")
    page_obj = layout.pages[page - 1]
    x0, top, x1, bottom = bbox
    return [
        dict(c) for c in page_obj.chars
        if x0 <= (c["x0"] + c["x1"]) / 2 <= x1
        and top <= (c["top"] + c["bottom"]) / 2 <= bottom
    ]


__all__ = ["bbox_to_char_range", "words_in_bbox", "chars_in_bbox", "Bbox"]
