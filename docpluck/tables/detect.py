"""
Table region detection.

Pipeline (per spec §5.2):
  1. Caption-regex pre-scan on layout.raw_text -> CaptionMatch list.
  2. For each caption, search ±window in PDF pt for geometric signal:
     - lattice signal: ≥2 horizontal rules + (≥1 vertical rule OR clean
       column-gap whitespace).
     - whitespace signal: ≥3 y-clustered rows with stable column boundaries.
  3. Otherwise: caption_only with a 200-pt block below the caption.
  4. Bbox = union of (caption line) ∪ (rules/word cluster) ∪ (footnote).
  5. Caption + footnote text are sliced from layout.raw_text.

In thorough mode, a second pass scans every page not already covered by a
caption-anchored region for ≥3 horizontal rules and emits them as caption_only
candidates with label=None, caption=None.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Literal

from docpluck.extract_layout import LayoutDoc

from .bbox_utils import Bbox, words_in_bbox
from .captions import CaptionMatch, find_caption_matches


GeometrySignal = Literal["lattice", "whitespace", "caption_only"]


@dataclass(frozen=True)
class CandidateRegion:
    label: str | None
    page: int                         # 1-indexed
    bbox: Bbox                        # pdfplumber top-down: (x0, top, x1, bottom)
    caption: str | None
    footnote: str | None
    geometry_signal: GeometrySignal
    caption_match: CaptionMatch | None


SEARCH_BELOW_PT: float = 250.0
SEARCH_ABOVE_PT: float = 150.0
LATTICE_MIN_HORIZONTAL_RULES: int = 2
THOROUGH_MIN_RULES: int = 3
WHITESPACE_MIN_ROWS: int = 3
COLUMN_STABILITY_FRACTION: float = 0.6
ROW_Y_BUCKET_PT: float = 5.0


def find_table_regions(layout: LayoutDoc, *, thorough: bool = False) -> list[CandidateRegion]:
    """Detect table regions in the document.

    Default mode (`thorough=False`): caption-anchored only — every region has
    `caption_match is not None`.

    Thorough mode: also scans every page not already covered for ≥3 horizontal
    rules and emits caption_only regions for them (label=None, caption=None).
    """
    captions = [
        m for m in find_caption_matches(layout.raw_text, list(layout.page_offsets))
        if m.kind == "table"
    ]

    regions: list[CandidateRegion] = []
    for cap in captions:
        region = _region_for_caption(layout, cap)
        if region is not None:
            regions.append(region)

    if thorough:
        regions.extend(_find_uncaptioned_tables(layout, exclude_pages={r.page for r in regions}))

    return regions


def _region_for_caption(layout: LayoutDoc, cap: CaptionMatch) -> CandidateRegion | None:
    page_obj = layout.pages[cap.page - 1]
    caption_bbox = _bbox_of_caption_line(page_obj, cap)
    if caption_bbox is None:
        return None

    below_bbox = _extend(caption_bbox, dy=SEARCH_BELOW_PT, direction="down")
    above_bbox = _extend(caption_bbox, dy=SEARCH_ABOVE_PT, direction="up")

    detected = _detect_geometry(layout, page=cap.page, search_bbox=below_bbox)
    if detected is None:
        detected = _detect_geometry(layout, page=cap.page, search_bbox=above_bbox)

    if detected is not None:
        signal, geom_bbox = detected
    else:
        signal = "caption_only"
        geom_bbox = below_bbox

    full_bbox = _union(caption_bbox, geom_bbox)
    footnote = _detect_footnote_below(layout, page=cap.page, bbox=full_bbox)
    if footnote is not None:
        full_bbox = _union(full_bbox, footnote.bbox)

    caption_text = _full_caption_text(layout.raw_text, cap)
    footnote_text = footnote.text if footnote is not None else None

    return CandidateRegion(
        label=cap.label,
        page=cap.page,
        bbox=full_bbox,
        caption=caption_text,
        footnote=footnote_text,
        geometry_signal=signal,
        caption_match=cap,
    )


@dataclass(frozen=True)
class _Footnote:
    text: str
    bbox: Bbox


def _bbox_of_caption_line(page_obj, cap: CaptionMatch) -> Bbox | None:
    """Find the y-cluster of chars whose joined text contains the start of the caption line."""
    chars = page_obj.chars or ()
    if not chars:
        return None
    target = cap.line_text.strip()
    if not target:
        return None
    target_prefix = target[:20]

    rows: dict[int, list[dict]] = defaultdict(list)
    for c in chars:
        rows[round(c.get("top", 0))].append(c)

    for top_key in sorted(rows.keys()):
        row_chars = sorted(rows[top_key], key=lambda c: c.get("x0", 0))
        joined = "".join(c.get("text", "") for c in row_chars)
        if target_prefix in joined:
            x0 = min(c["x0"] for c in row_chars)
            x1 = max(c["x1"] for c in row_chars)
            top = min(c["top"] for c in row_chars)
            bottom = max(c["bottom"] for c in row_chars)
            return (x0, top, x1, bottom)
    return None


def _extend(bbox: Bbox, *, dy: float, direction: Literal["down", "up"]) -> Bbox:
    x0, top, x1, bottom = bbox
    if direction == "down":
        return (x0, bottom, x1, bottom + dy)
    return (x0, max(0.0, top - dy), x1, top)


def _union(a: Bbox, b: Bbox) -> Bbox:
    return (min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3]))


def _detect_geometry(layout: LayoutDoc, *, page: int, search_bbox: Bbox) -> tuple[GeometrySignal, Bbox] | None:
    """Returns (signal, geometry_bbox) if found, else None."""
    page_obj = layout.pages[page - 1]
    horiz = _horizontal_rules_in(page_obj, search_bbox)
    vert = _vertical_rules_in(page_obj, search_bbox)
    has_whitespace_cols = _whitespace_columns_stable(layout, page=page, bbox=search_bbox)

    if len(horiz) >= LATTICE_MIN_HORIZONTAL_RULES and (len(vert) >= 1 or has_whitespace_cols):
        rule_bbox = _union_of_primitives(list(horiz) + list(vert), fallback=search_bbox)
        return ("lattice", rule_bbox)
    if has_whitespace_cols:
        return ("whitespace", search_bbox)
    return None


def _horizontal_rules_in(page_obj, bbox: Bbox) -> list[dict]:
    """Lines that are wider than tall and lie inside bbox (with small slack)."""
    x0, top, x1, bottom = bbox
    out: list[dict] = []
    for ln in page_obj.lines or ():
        width = ln["x1"] - ln["x0"]
        height = ln["bottom"] - ln["top"]
        if width > max(height, 0.5) * 5:
            if x0 - 2 <= ln["x0"] and ln["x1"] <= x1 + 2 and top - 2 <= ln["top"] <= bottom + 2:
                out.append(dict(ln))
    return out


def _vertical_rules_in(page_obj, bbox: Bbox) -> list[dict]:
    """Lines that are taller than wide and lie inside bbox."""
    x0, top, x1, bottom = bbox
    out: list[dict] = []
    for ln in page_obj.lines or ():
        width = ln["x1"] - ln["x0"]
        height = ln["bottom"] - ln["top"]
        if height > max(width, 0.5) * 5:
            if x0 - 2 <= ln["x0"] <= x1 + 2 and top - 2 <= ln["top"] and ln["bottom"] <= bottom + 2:
                out.append(dict(ln))
    return out


def _union_of_primitives(rules: list[dict], fallback: Bbox) -> Bbox:
    if not rules:
        return fallback
    return (
        min(r["x0"] for r in rules),
        min(r["top"] for r in rules),
        max(r["x1"] for r in rules),
        max(r["bottom"] for r in rules),
    )


def _whitespace_columns_stable(layout: LayoutDoc, *, page: int, bbox: Bbox) -> bool:
    """Test whether ≥WHITESPACE_MIN_ROWS y-clustered rows of words have stable column boundaries."""
    words = words_in_bbox(layout, bbox=bbox, page=page)
    if len(words) < 9:  # at least 3 rows × 3 cols
        return False

    rows: dict[float, list[dict]] = defaultdict(list)
    for w in words:
        bucket = round((w["top"] + w["bottom"]) / 2 / ROW_Y_BUCKET_PT) * ROW_Y_BUCKET_PT
        rows[bucket].append(w)

    row_signatures: list[tuple[int, ...]] = []
    for ws in rows.values():
        ws.sort(key=lambda w: w["x0"])
        if len(ws) < 2:
            continue
        sig = tuple(round(w["x0"]) for w in ws)
        row_signatures.append(sig)

    if len(row_signatures) < WHITESPACE_MIN_ROWS:
        return False

    sig_lengths = [len(s) for s in row_signatures]
    modal_len = max(set(sig_lengths), key=sig_lengths.count)
    matching = sum(1 for s in row_signatures if len(s) == modal_len)
    return matching / len(row_signatures) >= COLUMN_STABILITY_FRACTION


def _detect_footnote_below(layout: LayoutDoc, *, page: int, bbox: Bbox) -> _Footnote | None:
    page_obj = layout.pages[page - 1]
    chars = page_obj.chars or ()
    if not chars:
        return None
    body_size = _modal_font_size(chars)
    x0, top, x1, bottom = bbox
    candidates = [
        c for c in chars
        if c.get("top", 0) >= bottom and c.get("x0", 0) >= x0 - 5 and c.get("x1", 0) <= x1 + 5
    ]
    if not candidates:
        return None
    smaller = [c for c in candidates if c.get("size", body_size) < body_size * 0.92]
    if len(smaller) < 5:
        return None
    fx0 = min(c["x0"] for c in smaller)
    fx1 = max(c["x1"] for c in smaller)
    ftop = min(c["top"] for c in smaller)
    fbot = max(c["bottom"] for c in smaller)
    smaller.sort(key=lambda c: (c["top"], c["x0"]))
    text = "".join(c.get("text", "") for c in smaller).strip()
    return _Footnote(text=text, bbox=(fx0, ftop, fx1, fbot))


def _modal_font_size(chars) -> float:
    sizes: list[float] = []
    for c in chars:
        s = c.get("size")
        if s:
            sizes.append(round(float(s), 1))
    if not sizes:
        return 10.0
    counts: dict[float, int] = defaultdict(int)
    for s in sizes:
        counts[s] += 1
    return max(counts.items(), key=lambda kv: kv[1])[0]


def _full_caption_text(raw_text: str, cap: CaptionMatch) -> str:
    """Caption is the matched line + continuation up to the next paragraph break."""
    end = raw_text.find("\n\n", cap.char_end)
    if end == -1:
        end = min(cap.char_end + 500, len(raw_text))
    return raw_text[cap.char_start:end].replace("\n", " ").strip()


def _find_uncaptioned_tables(layout: LayoutDoc, *, exclude_pages: set[int]) -> list[CandidateRegion]:
    out: list[CandidateRegion] = []
    for i, page_obj in enumerate(layout.pages, start=1):
        if i in exclude_pages:
            continue
        horiz_rules = [
            ln for ln in page_obj.lines or ()
            if (ln["x1"] - ln["x0"]) > 50
            and (ln["x1"] - ln["x0"]) > max(ln["bottom"] - ln["top"], 0.5) * 5
        ]
        if len(horiz_rules) < THOROUGH_MIN_RULES:
            continue
        x0 = min(ln["x0"] for ln in horiz_rules)
        x1 = max(ln["x1"] for ln in horiz_rules)
        top = min(ln["top"] for ln in horiz_rules)
        bottom = max(ln["bottom"] for ln in horiz_rules)
        out.append(CandidateRegion(
            label=None,
            page=i,
            bbox=(x0, top, x1, bottom),
            caption=None,
            footnote=None,
            geometry_signal="lattice",
            caption_match=None,
        ))
    return out


__all__ = ["find_table_regions", "CandidateRegion", "GeometrySignal"]
