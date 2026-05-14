"""
Figure region detection — caption + bbox metadata only (level A).

For each Figure N caption match, infer the figure bbox by looking for
graphics primitives (rects, lines, curves) above (APA convention) or
below the caption. v2.0 emits metadata only — no image extraction.

See spec §5.7.
"""

from __future__ import annotations

import re
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
    full = raw_text[cap.char_start:end].replace("\n", " ").strip()
    full = _trim_caption_at_chart_data(full)
    return _trim_caption_at_running_header(full)


# v2.4.24 (cycle 9): caption boundary running-header trim.
# pdftotext occasionally absorbs body prose + the page running header
# into the caption span when there's no `\n\n` separator before the
# next-paragraph body. Example caught in xiao_2021_crsp Figure 2:
#
#   *Figure 2. Study 1 interaction plots. Exploratory analysis To
#   examine whether and to what extent participants perceived… 14
#   Q. XIAO ET AL.*
#
# The actual caption ends at "Study 1 interaction plots." Everything
# after is body + running header. Detect the running-header signature
# at the END of the caption and trim it (along with the body prose run
# that precedes it within the same caption string).
_CAPTION_RUNNING_HEADER_TAIL_RE = re.compile(
    r"\s+\d+\s+[A-Z]\.\s*(?:[A-Z]\.?)?\s+[A-Z]{2,}"
    r"(?:\s+(?:AND|&)\s+[A-Z][A-Z'\-]+)?"
    r"\s+ET\s+AL\.?\s*$"
)


def _trim_caption_at_running_header(caption: str) -> str:
    """If a figure caption was extracted with a trailing page-number +
    running-header (e.g. ``… 14 Q. XIAO ET AL.``), trim it. Also trim
    the body-prose sentence run that immediately precedes the running
    header within the same extracted caption string.
    """
    if not caption:
        return caption
    m = _CAPTION_RUNNING_HEADER_TAIL_RE.search(caption)
    if not m:
        return caption
    trimmed = caption[: m.start()].rstrip()
    last_period = trimmed.rfind(". ")
    if last_period > 0:
        tail = trimmed[last_period + 2:]
        if (
            tail
            and tail[0].isupper()
            and len(tail.split()) >= 5
            and not tail.lower().startswith(("note", "source", "data", "see"))
        ):
            trimmed = trimmed[: last_period + 1]
    return trimmed


# A run of 6+ consecutive digits in a figure caption is almost never
# legitimate caption prose — page counts, statistical n-values, and years
# all top out at 5 digits in academic captions. 6+ digits is a strong signal
# that pdftotext joined chart data (raw bar-chart values, participant counts,
# row IDs) into the caption.
_CHART_DATA_DIGIT_RUN_RE = re.compile(r"\b\d{6,}\b")
# A run of 5+ short numeric tokens (1–4 digits each) separated only by
# whitespace is a v2.4.4 signal — captures axis-tick label sequences
# (``0 5 10 15 20``) and stacked column values (``340 321 280 5 270``)
# that the 6-digit rule misses on charts with small-magnitude data.
# Real captions reference numbers via prose ("with n = 1234 participants",
# "p < .001"), so digit tokens are interleaved with words rather than
# stacked five-in-a-row.
_CHART_DATA_TICK_RUN_RE = re.compile(r"(?:\b\d{1,4}\b[ \t]+){5,}")


def _trim_caption_at_chart_data(caption: str) -> str:
    """Truncate a caption when it transitions from prose to chart-data.

    pdftotext extracts chart elements (axis labels, legend entries, gridline
    values) inline with the figure caption when they share a paragraph in the
    PDF reading order. The resulting caption text looks like::

        Figure 1. Flowchart of Study Sample Selection 4876956 Pairs enrolled
        before April 1, 2015 1117269 Pairs excluded 741469 Withdrawal …

    where the real caption is "Flowchart of Study Sample Selection" and the
    rest is chart data values.

    v2.4.4: two complementary signatures are scanned (see module-level
    constants); the *earlier* match in the caption wins so the caption is
    trimmed at the start of the chart data, not partway through it.

    Conservative: only fires when the caption is ≥ 150 chars (real short
    captions almost never have a chart-data appendage), and only when the
    surviving trimmed caption is ≥ 40 chars (sanity check protects against
    edge cases where the digit run lands near the label).
    """
    if not caption or len(caption) < 150:
        return caption
    candidates: list[int] = []
    m1 = _CHART_DATA_DIGIT_RUN_RE.search(caption)
    if m1 is not None:
        candidates.append(m1.start())
    m2 = _CHART_DATA_TICK_RUN_RE.search(caption)
    if m2 is not None:
        candidates.append(m2.start())
    if not candidates:
        return caption
    cut = min(candidates)
    # Walk back to the previous word boundary.
    while cut > 0 and not caption[cut - 1].isspace():
        cut -= 1
    trimmed = caption[:cut].rstrip(" ,;:")
    # Sanity check.
    if len(trimmed) < 40:
        return caption
    return trimmed


__all__ = ["find_figures"]
