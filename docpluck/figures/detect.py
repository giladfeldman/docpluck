"""
Figure region detection — caption + bbox metadata only (level A).

For each Figure N caption match, infer the figure bbox by looking for
graphics primitives (rects, lines, curves) above (APA convention) or
below the caption. v2.0 emits metadata only — no image extraction.

See spec §5.7.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from docpluck.extract_layout import LayoutDoc

from docpluck.tables.bbox_utils import Bbox
from docpluck.tables.captions import CaptionMatch, find_caption_matches

from . import Figure


SEARCH_ABOVE_PT: float = 400.0
SEARCH_BELOW_PT: float = 400.0
FALLBACK_HEIGHT_PT: float = 200.0


def find_figures(layout: LayoutDoc) -> list[Figure]:
    """Detect figures in the document.

    Returns a list of Figure dicts in document order. Each figure has a
    1-indexed sequential id ("f1", "f2", ...), the parsed label
    ("Figure N"), the 1-indexed page, an inferred bbox, and the caption text.
    """
    captions = [
        m for m in find_caption_matches(layout.raw_text, list(layout.page_offsets))
        if m.kind == "figure"
    ]

    figures: list[Figure] = []
    for i, cap in enumerate(captions, start=1):
        bbox = _figure_bbox_for(layout, cap)
        figures.append({
            "id": f"f{i}",
            "label": cap.label,
            "page": cap.page,
            "bbox": bbox,
            "caption": _full_caption_text(layout.raw_text, cap),
        })
    return figures


# --- helpers ---


def _figure_bbox_for(layout: LayoutDoc, cap: CaptionMatch) -> Bbox:
    page_obj = layout.pages[cap.page - 1]
    caption_bbox = _bbox_of_caption_line(page_obj, cap)
    if caption_bbox is None:
        page_w = float(getattr(page_obj, "width", 612.0))
        return (50.0, 100.0, page_w - 50.0, 300.0)

    above = _graphics_bbox_in_band(page_obj, caption_bbox, direction="above", max_pt=SEARCH_ABOVE_PT)
    if above is not None:
        return _union(caption_bbox, above)
    below = _graphics_bbox_in_band(page_obj, caption_bbox, direction="below", max_pt=SEARCH_BELOW_PT)
    if below is not None:
        return _union(caption_bbox, below)

    # No graphics found; emit bbox = caption + FALLBACK_HEIGHT_PT block above (best effort)
    cx0, ctop, cx1, cbottom = caption_bbox
    return (cx0, max(0.0, ctop - FALLBACK_HEIGHT_PT), cx1, cbottom)


def _graphics_bbox_in_band(page_obj, caption_bbox: Bbox, *, direction: str, max_pt: float) -> Bbox | None:
    cx0, ctop, cx1, cbottom = caption_bbox
    if direction == "above":
        band_top, band_bot = max(0.0, ctop - max_pt), ctop
    else:
        band_top, band_bot = cbottom, cbottom + max_pt

    primitives: list[dict[str, Any]] = []
    for collection in (page_obj.rects, page_obj.lines, page_obj.curves):
        for p in collection or ():
            primitives.append(p)
    if not primitives:
        return None
    in_band = [
        p for p in primitives
        if "top" in p and "bottom" in p
        and band_top <= ((p["top"] + p["bottom"]) / 2) <= band_bot
    ]
    if not in_band:
        return None
    return (
        min(p["x0"] for p in in_band),
        min(p["top"] for p in in_band),
        max(p["x1"] for p in in_band),
        max(p["bottom"] for p in in_band),
    )


def _union(a: Bbox, b: Bbox) -> Bbox:
    return (min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3]))


def _bbox_of_caption_line(page_obj, cap: CaptionMatch) -> Bbox | None:
    chars = page_obj.chars or ()
    if not chars:
        return None
    target = cap.line_text.strip()
    if not target:
        return None
    target_prefix = target[:20]

    rows: defaultdict[int, list[dict[str, Any]]] = defaultdict(list)
    for c in chars:
        rows[round(c.get("top", 0))].append(c)

    for top_key in sorted(rows.keys()):
        row_chars = sorted(rows[top_key], key=lambda c: c.get("x0", 0))
        joined = "".join(c.get("text", "") for c in row_chars)
        if target_prefix in joined:
            return (
                min(c["x0"] for c in row_chars),
                min(c["top"] for c in row_chars),
                max(c["x1"] for c in row_chars),
                max(c["bottom"] for c in row_chars),
            )
    return None


def _full_caption_text(raw_text: str, cap: CaptionMatch) -> str:
    end = raw_text.find("\n\n", cap.char_end)
    if end == -1:
        end = min(cap.char_end + 500, len(raw_text))
    return raw_text[cap.char_start:end].replace("\n", " ").strip()


__all__ = ["find_figures"]
