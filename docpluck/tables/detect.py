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

    # A caption is often NARROWER than its table (a one-line label above a wider
    # grid), so a search box clipped to the caption width drops the table's
    # right-hand columns — efendic Table 2's ``p`` column sits ~44pt right of the
    # caption's end; efendic Table 1's third column is clipped entirely. The search
    # box is built at the CAPTION width and ``_detect_geometry_widen_aware`` then
    # tries a content-WIDENED copy of the band, keeping whichever aligned run has
    # MORE columns (a real run beats ``None``; more columns beats fewer; ties keep
    # the narrow incumbent, so a paper that already extracts correctly is
    # byte-unchanged). This recovers wide-table columns WITHOUT the two-column-page
    # regression a blanket-widen would cause: on a genuine two-column page, widening
    # pulls the neighbouring text column into the band and destroys the run, so the
    # arbitration falls back to the narrow run (ieee_access_7 Table 3).
    #
    # CRUCIAL — widening (and the narrow/wide arbitration) applies ONLY to the
    # aligned-run (whitespace) path, inside ``_detect_geometry_widen_aware``. The
    # ``caption_only`` FALLBACK below keeps the CAPTION-WIDTH below-box: a widened
    # fallback box reaches sideways into a stacked neighbour table and makes the
    # region-driven Camelot pass mis-segment it (cog_emo page 13 stacks Table 8's
    # intercorrelation matrix above Table 9's results table — widening Table 9's
    # caption_only region collapsed its 8 columns to 2). When an aligned run IS
    # found the run's own tight bbox is used, so the wide search band never leaks
    # into the result. Keyed on a layout invariant, paper-agnostic.
    below_bbox = _extend(caption_bbox, dy=SEARCH_BELOW_PT, direction="down")
    above_bbox = _extend(caption_bbox, dy=SEARCH_ABOVE_PT, direction="up")

    detected = _detect_geometry_widen_aware(layout, page=cap.page, search_bbox=below_bbox)
    if detected is None:
        detected = _detect_geometry_widen_aware(layout, page=cap.page, search_bbox=above_bbox)

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


_LIGATURE_FOLD = str.maketrans({
    "ﬀ": "ff", "ﬁ": "fi", "ﬂ": "fl",
    "ﬃ": "ffi", "ﬄ": "ffl", "ﬅ": "ft", "ﬆ": "st",
})


def _normalize_for_char_match(s: str) -> str:
    """Fold ligatures, drop whitespace, lowercase — for matching caption text
    against layout-channel joined chars (which routinely drop spaces between
    words inside a y-row and keep PDF ligature glyphs unchanged)."""
    return s.translate(_LIGATURE_FOLD).replace(" ", "").replace("\t", "").lower()


def _bbox_of_caption_line(page_obj, cap: CaptionMatch) -> Bbox | None:
    """Find the y-cluster of chars whose joined text contains the start of the caption line.

    Robustness layers (each successively more forgiving — added 2026-05-25 after
    the R1 sweep showed _region_for_caption returning None 11/11 on the B1 corpus
    because layout chars join without inter-word spaces and contain raw PDF
    ligatures, while cap.line_text comes from the de-ligatured text channel with
    spaces preserved):
      1. Exact prefix match against joined chars (legacy path).
      2. Normalized prefix match — fold ligatures, strip whitespace, lowercase
         on both sides. Catches the dominant B1 failure shape (Table5.Reﬂection…
         vs Table 5. Reflection…).
      3. Label-only match — search for the normalized cap.label (e.g. ``table5``)
         anywhere in the joined row. Catches captions whose body text on the
         page differs from the text-channel line_text (cross-page caption,
         glyph substitution).
    """
    chars = page_obj.chars or ()
    if not chars:
        return None
    target = cap.line_text.strip()
    if not target:
        return None
    target_prefix = target[:20]
    target_prefix_norm = _normalize_for_char_match(target_prefix)
    label_norm = _normalize_for_char_match(cap.label)  # e.g. "table5"

    rows: dict[int, list[dict]] = defaultdict(list)
    for c in chars:
        rows[round(c.get("top", 0))].append(c)

    # Pass 1+2: prefix-based match (legacy or normalized).
    for top_key in sorted(rows.keys()):
        row_chars = sorted(rows[top_key], key=lambda c: c.get("x0", 0))
        joined = "".join(c.get("text", "") for c in row_chars)
        joined_norm = _normalize_for_char_match(joined)
        if target_prefix in joined or (
            target_prefix_norm and target_prefix_norm in joined_norm
        ):
            x0 = min(c["x0"] for c in row_chars)
            x1 = max(c["x1"] for c in row_chars)
            top = min(c["top"] for c in row_chars)
            bottom = max(c["bottom"] for c in row_chars)
            return (x0, top, x1, bottom)

    # Pass 3: label-only fallback. The row must additionally start near the
    # left margin (label-style caption, not an inline back-reference like
    # "(see Table 5)") to avoid false-positive matches on body prose.
    page_width = float(getattr(page_obj, "width", 0.0) or 0.0)
    left_margin_cap = page_width * 0.5 if page_width else float("inf")
    for top_key in sorted(rows.keys()):
        row_chars = sorted(rows[top_key], key=lambda c: c.get("x0", 0))
        joined = "".join(c.get("text", "") for c in row_chars)
        joined_norm = _normalize_for_char_match(joined)
        if not label_norm or label_norm not in joined_norm:
            continue
        # Reject if the label appears mid-row rather than at/near the start.
        label_pos = joined_norm.find(label_norm)
        if label_pos > 4:  # tolerate a couple leading chars (e.g., "*Table 5")
            continue
        x0 = min(c["x0"] for c in row_chars)
        if x0 > left_margin_cap:
            continue  # right column of a 2-column page, not a caption row
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


def _widen_to_content_x(layout: LayoutDoc, *, page: int, bbox: Bbox) -> Bbox:
    """Widen ``bbox`` horizontally to span all words whose vertical midpoint falls
    inside its y-range, so a table wider than its caption isn't column-clipped.

    Only ever EXPANDS the x-range (``min``/``max`` against the existing bounds);
    the y-range is untouched. Returns ``bbox`` unchanged when the band holds no
    words. The caller (``_detect_geometry_widen_aware``) never trusts a widened
    band blindly — it arbitrates the widened aligned run against the narrow one and
    keeps only the more-columnar result — so widening the SEARCH window cannot
    over-capture: a widen that pulls in a neighbour text column simply destroys the
    aligned run and loses the arbitration.

    This is the single unified widen helper for the "caption narrower than table"
    concern (it replaced an earlier right-edge-only ``_widen_to_page_content``:
    word-extent widening is tighter than reaching to the page margin, and widening
    BOTH edges is safe here precisely because of the arbitration described above)."""
    x0, top, x1, bottom = bbox
    page_obj = layout.pages[page - 1]
    xs0: list[float] = []
    xs1: list[float] = []
    for w in page_obj.words:
        mid_y = (w["top"] + w["bottom"]) / 2
        if top <= mid_y <= bottom:
            xs0.append(w["x0"])
            xs1.append(w["x1"])
    if not xs0:
        return bbox
    return (min(x0, min(xs0)), top, max(x1, max(xs1)), bottom)


def _union(a: Bbox, b: Bbox) -> Bbox:
    return (min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3]))


def _detect_geometry(layout: LayoutDoc, *, page: int, search_bbox: Bbox) -> tuple[GeometrySignal, Bbox] | None:
    """Returns (signal, geometry_bbox) if found, else None.

    For the whitespace signal the returned bbox is the y-extent of the *aligned
    row run* (the contiguous block of column-aligned rows), NOT the full
    ``search_bbox``. A table is followed in the SEARCH_BELOW window by ordinary
    body prose in two-column APA layouts; that prose neither shares the table's
    column count nor its column edges, so clipping to the aligned run gives the
    region-driven Camelot pass a tight box that holds the grid alone. Returning
    the full window instead let the region balloon ~250-440pt past the grid into
    the prose, and Camelot stream then mis-segments the dominant prose columns
    (the grid is lost → 0×0 caption-only stub). Keyed on the structural
    signature "tabular rows are column-aligned; the prose that follows is not".
    """
    page_obj = layout.pages[page - 1]
    horiz = _horizontal_rules_in(page_obj, search_bbox)
    vert = _vertical_rules_in(page_obj, search_bbox)
    run_bbox = _aligned_row_run(layout, page=page, bbox=search_bbox)
    has_whitespace_cols = run_bbox is not None

    if len(horiz) >= LATTICE_MIN_HORIZONTAL_RULES and (len(vert) >= 1 or has_whitespace_cols):
        rule_bbox = _union_of_primitives(list(horiz) + list(vert), fallback=search_bbox)
        return ("lattice", rule_bbox)
    if run_bbox is not None:
        return ("whitespace", run_bbox)
    return None


def _detect_geometry_widen_aware(
    layout: LayoutDoc, *, page: int, search_bbox: Bbox
) -> tuple[GeometrySignal, Bbox] | None:
    """``_detect_geometry`` that also tries a content-WIDENED copy of the search
    band and keeps whichever whitespace run has MORE columns.

    The caption's x-range often under-covers its table (a short caption over a
    full-width multi-column table — efendic Table 1 clips column 3). Widening the
    band to the page's content x-extent recovers those columns. But on a genuine
    TWO-COLUMN page layout, widening pulls the neighbouring text column into the
    band and destroys the aligned run (ieee_access_7 Table 3: a clean right-column
    run becomes ``None``). Running BOTH and picking the more-columnar run gets the
    recovery without the two-column-layout regression — a real run beats ``None``,
    more columns beats fewer; ties keep the narrow (incumbent) result.

    Lattice detection is unaffected by widening (it keys on ruled lines, not the
    word scan), so it is evaluated once on the original band via ``_detect_geometry``
    and takes precedence — only the whitespace branch is widen-arbitrated.
    """
    base = _detect_geometry(layout, page=page, search_bbox=search_bbox)
    if base is not None and base[0] == "lattice":
        return base

    widened = _widen_to_content_x(layout, page=page, bbox=search_bbox)
    if widened == search_bbox:
        return base  # nothing to widen into — no extra content on the page band

    narrow_run = _aligned_row_run_with_ncols(layout, page=page, bbox=search_bbox)
    wide_run = _aligned_row_run_with_ncols(layout, page=page, bbox=widened)

    # Pick the run with more columns; the widened result must STRICTLY beat the
    # narrow one to be used (ties keep narrow, the safe incumbent), so a paper that
    # already extracts correctly on the caption-width band is byte-unchanged.
    narrow_n = narrow_run[1] if narrow_run else 0
    wide_n = wide_run[1] if wide_run else 0
    if wide_run is not None and wide_n > narrow_n:
        return ("whitespace", wide_run[0])
    if narrow_run is not None:
        return ("whitespace", narrow_run[0])
    return base


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


# Two column-START edges across rows count as "the same column" when their x0
# differs by at most this many points. The slack must absorb the left-edge jitter
# of a right-aligned / centered numeric column — whose start shifts by roughly its
# widest-cell width when a value's sign or digit count changes (e.g. a B column
# whose negative ``20.09`` starts ~7pt left of a positive ``2.56``) — while
# staying far below the inter-column GUTTER of a real table (typically ≥40pt), so
# genuinely distinct columns are never merged. Run-growth compares each new row
# against the running per-column MEAN of the run so far (not the first row), so a
# single jittered row can't break an otherwise-aligned table.
_COLUMN_EDGE_TOL_PT: float = 12.0


def _aligned_row_run(layout: LayoutDoc, *, page: int, bbox: Bbox) -> Bbox | None:
    """Find the largest contiguous (in y) run of column-aligned word rows inside
    ``bbox`` and return its bounding box, or ``None`` if no run qualifies.

    A table body is a *contiguous* block of rows that share a column count AND
    column-start edges. Body prose that follows a short table in the
    SEARCH_BELOW window (ubiquitous in two-column APA layouts) breaks both
    invariants — variable word counts per line and no edge alignment to the
    table's columns — so it is excluded from the run rather than (as the old
    global-fraction test did) diluting the table's signal below threshold and
    vetoing detection entirely. Two improvements over the prior boolean test:

      1. **Contiguous run, not global fraction.** ≥WHITESPACE_MIN_ROWS
         consecutive rows must share the modal column count (within
         COLUMN_STABILITY_FRACTION of the run). Trailing/leading non-table rows
         no longer matter.
      2. **Clipped bbox.** Returns the run's y-extent so the caller can build a
         region tight to the grid (the region-driven Camelot pass needs this —
         a too-tall region makes stream mis-segment the prose below the table).

    Column-START alignment (not full-signature equality) is the stability test:
    right-aligned data columns keep a stable left edge even when the label
    column's width varies row to row (memory: tight-kerned numeric columns are
    left-edge-stable). Keyed on a layout invariant, paper-agnostic.
    """
    words = words_in_bbox(layout, bbox=bbox, page=page)
    if len(words) < 9:  # at least 3 rows × 3 cols
        return None

    rows: dict[float, list[dict]] = defaultdict(list)
    for w in words:
        bucket = round((w["top"] + w["bottom"]) / 2 / ROW_Y_BUCKET_PT) * ROW_Y_BUCKET_PT
        rows[bucket].append(w)

    # y-ordered rows, each with ≥2 words; keep the words for bbox + edge tests.
    ordered: list[tuple[float, list[dict]]] = []
    for bucket in sorted(rows.keys()):
        ws = sorted(rows[bucket], key=lambda w: w["x0"])
        if len(ws) >= 2:
            ordered.append((bucket, ws))

    if len(ordered) < WHITESPACE_MIN_ROWS:
        return None

    # A table's rows share a column count. Try every width that occurs at least
    # WHITESPACE_MIN_ROWS times as a candidate table-width (not only the single
    # global modal): when body prose below the table is more voluminous than the
    # table itself, the prose's row width can be the global modal and the table
    # would be missed. Keep the LARGEST aligned run found across all candidate
    # widths. Each candidate's run is grown by column-edge alignment, so a
    # spurious prose width yields no qualifying run.
    sig_lengths = [len(ws) for _, ws in ordered]
    candidate_widths = sorted(
        {w for w in sig_lengths if sig_lengths.count(w) >= WHITESPACE_MIN_ROWS},
        reverse=True,
    )

    best: list[tuple[float, list[dict]]] | None = None
    for width in candidate_widths:
        run = _longest_aligned_run(ordered, width)
        if run is not None and (best is None or len(run) > len(best)):
            best = run

    if best is None or len(best) < WHITESPACE_MIN_ROWS:
        return None

    run_words = [w for _, ws in best for w in ws]
    x0 = min(w["x0"] for w in run_words)
    x1 = max(w["x1"] for w in run_words)
    top = min(w["top"] for w in run_words)
    bottom = max(w["bottom"] for w in run_words)
    return (x0, top, x1, bottom)


def _aligned_row_run_with_ncols(
    layout: LayoutDoc, *, page: int, bbox: Bbox
) -> tuple[Bbox, int] | None:
    """Like :func:`_aligned_row_run` but also returns the run's modal column count.

    The caller (``_detect_geometry_widen_aware``) needs the column count to choose
    between a narrow (caption-width) and a content-widened search band: widening
    lets a full-width table recover its right columns (efendic Table 1: 2→3 cols),
    but on a TWO-COLUMN page layout it pulls the neighbouring text column into the
    band and destroys the run (ieee_access_7 Table 3: a clean run becomes
    ``None``). So we run BOTH and keep whichever yields more columns — a real run
    beats ``None``, more columns beats fewer — which strictly dominates either
    band alone.
    """
    run = _aligned_row_run(layout, page=page, bbox=bbox)
    if run is None:
        return None
    # Recompute the modal column count over the rows that fall in the run's bbox.
    words = words_in_bbox(layout, bbox=run, page=page)
    rows: dict[float, list[dict]] = defaultdict(list)
    for w in words:
        bucket = round((w["top"] + w["bottom"]) / 2 / ROW_Y_BUCKET_PT) * ROW_Y_BUCKET_PT
        rows[bucket].append(w)
    widths = [len(ws) for ws in rows.values() if len(ws) >= 2]
    if not widths:
        return None
    ncols = max(set(widths), key=widths.count)
    return run, ncols


def _longest_aligned_run(
    ordered: list[tuple[float, list[dict]]], width: int
) -> list[tuple[float, list[dict]]] | None:
    """Longest contiguous (in y) run of rows of exactly ``width`` words whose
    column-start edges stay aligned, or ``None`` if none reaches the minimum.

    Run-growth compares each new row against the run's running per-column MEAN
    (not the first row), so one jittered row can't sever an otherwise-aligned
    table. A row whose width differs, or whose edges diverge beyond tolerance,
    ends the current run.
    """
    best: list[tuple[float, list[dict]]] | None = None
    i = 0
    n = len(ordered)
    while i < n:
        if len(ordered[i][1]) != width:
            i += 1
            continue
        run = [ordered[i]]
        col_sums = [w["x0"] for w in ordered[i][1]]
        j = i + 1
        while j < n and len(ordered[j][1]) == width:
            edges = [w["x0"] for w in ordered[j][1]]
            ref_means = [s / len(run) for s in col_sums]
            if not _edges_align(ref_means, edges):
                break
            run.append(ordered[j])
            for k, e in enumerate(edges):
                col_sums[k] += e
            j += 1
        if best is None or len(run) > len(best):
            best = run
        i = j if j > i else i + 1
    if best is None or len(best) < WHITESPACE_MIN_ROWS:
        return None
    return best


def _edges_align(a: list[float], b: list[float]) -> bool:
    """True if two equal-length column-start edge lists agree within tolerance."""
    if len(a) != len(b):
        return False
    return all(abs(ea - eb) <= _COLUMN_EDGE_TOL_PT for ea, eb in zip(a, b))


def _whitespace_columns_stable(layout: LayoutDoc, *, page: int, bbox: Bbox) -> bool:
    """Back-compat boolean wrapper: True iff an aligned row run exists in ``bbox``.

    The region/bbox computation now uses :func:`_aligned_row_run` directly (it
    needs the run's y-extent); this thin predicate is retained for callers/tests
    that only ask "does this region contain a whitespace-column table?".
    """
    return _aligned_row_run(layout, page=page, bbox=bbox) is not None


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
    # Keep only the small-font block CONTIGUOUS with the table bottom. A table's
    # Note/footnote sits within ~a line of the grid; other small-font content
    # further down the page (the next figure's caption, a figure note, page
    # furniture) is separated by a large vertical gap. Without this clip the
    # detector vacuums every smaller-font char below the table into one
    # "footnote", and the union balloons the table region down across the
    # intervening body prose — which makes the region-driven Camelot pass
    # mis-segment that prose and lose the grid (efendic Table 2: note at y≈225,
    # then a 223pt gap to the Figure 2 caption — all of it was absorbed,
    # bottom→509). Keyed on the layout invariant "a table note is contiguous
    # with its table", paper-agnostic.
    block = _contiguous_top_block(smaller)
    if len(block) < 5:
        return None
    fx0 = min(c["x0"] for c in block)
    fx1 = max(c["x1"] for c in block)
    ftop = min(c["top"] for c in block)
    fbot = max(c["bottom"] for c in block)
    block.sort(key=lambda c: (c["top"], c["x0"]))
    text = "".join(c.get("text", "") for c in block).strip()
    return _Footnote(text=text, bbox=(fx0, ftop, fx1, fbot))


# A footnote block ends at the first inter-row vertical gap wider than this. One
# normal note line wraps at ~the font's line height (≤~12pt for an 8-pt note); a
# gap several times that means the next small-font content is a separate object
# (figure caption, page furniture), not a continuation of the table's note.
_FOOTNOTE_ROW_GAP_PT: float = 25.0


def _contiguous_top_block(chars: list[dict]) -> list[dict]:
    """Return the chars belonging to the contiguous y-block nearest the top of
    ``chars`` — the rows from the topmost down to (but not past) the first
    vertical gap wider than :data:`_FOOTNOTE_ROW_GAP_PT`."""
    rows: dict[float, list[dict]] = defaultdict(list)
    for c in chars:
        rows[round(c.get("top", 0.0))].append(c)
    ys = sorted(rows.keys())
    if not ys:
        return []
    kept_keys = [ys[0]]
    for prev_y, y in zip(ys, ys[1:]):
        if y - prev_y > _FOOTNOTE_ROW_GAP_PT:
            break
        kept_keys.append(y)
    return [c for k in kept_keys for c in rows[k]]


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
