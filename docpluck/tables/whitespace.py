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
from collections import Counter, defaultdict
from itertools import pairwise
from typing import Any

from docpluck.extract_layout import LayoutDoc

from . import Cell
from .bbox_utils import chars_in_bbox, words_in_bbox
from .cell_cleaning import (
    _is_header_like_row,
    clean_cell_text,
    normalize_cell_whitespace,
    repair_cells,
)
from .detect import CandidateRegion

WHITESPACE_MIN_ROWS: int = 3
ROW_GAP_RATIO: float = 1.2
ROW_GAP_FLOOR_PT: float = 5.0
COLUMN_GAP_PT: float = 5.0
COLUMN_STABILITY_FRACTION: float = 0.6
HEADER_HEIGHT_RATIO: float = 1.05
BODY_HEIGHT_FALLBACK: float = 10.0

# Word break inside a line whose glyphs carry no space glyph, as a fraction of the
# font size: the rotated-table path (`docpluck.tables.rotated`) splits words at
# it and `_text_by_lines` re-joins a touching sub/superscript at it. MEASURED, not
# borrowed: over the 31 rotated-table pages of the corpus manifest, consecutive
# glyphs on one line sit either <= 0.02 font sizes apart (34,618 pairs: inside a
# word) or >= 0.09 (word spaces, most at 0.16-0.34), with none between.
# `extract_layout._join_chars_with_spaces`'s 0.20 would glue the 2,068 pairs at
# 0.19 -- every word of 10.1098/rsos.140072 p5's Table 1 caption.
WORD_GAP_RATIO: float = 0.10

# A row taller than this multiple of the row threshold is a SMEAR — the signature
# that licenses anchor-relative re-clustering. Same factor the census defaults to
# (`tools/diag/row_cluster_census.py --smear-factor`).
_SMEAR_FACTOR: float = 2.0

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
    # Gates on RAW, repair on the way out — never the other order. See
    # `_repaired_view`.
    cells = _trim_trailing_prose_rows(cells)
    if not _whitespace_grid_is_clean(cells, own_caption_number=_region_caption_number(region)):
        return []
    return repair_cells(cells, layout=layout)


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
    # Gates on RAW, repair on the way out — never the other order. See
    # `_repaired_view`.
    cells = _trim_trailing_prose_rows(cells)
    if not _whitespace_grid_is_clean(cells, own_caption_number=_region_caption_number(region)):
        return []
    return repair_cells(cells, layout=layout)


def rotated_frame_cells(
    words: list[dict[str, Any]], *, own_caption_number: int | None = None
) -> tuple[list[Cell], str | None]:
    """Grid a ROTATED table's words, already turned upright by
    ``docpluck.tables.rotated``, with the same clustering and the same gates as
    :func:`whitespace_cells`. Returns ``(cells, None)`` or ``([], reason)``.

    Two things differ from the upright word path, both measured on
    ``10.1038/s41467-024-45528-0`` Table 4 (p6, printed sideways), and both are
    why this is a separate entry point rather than a flag on the upright one
    (whose output would otherwise move for every upright table):

    * **Columns are voted on column STARTS, not gap midpoints.** The words here
      are real words (rotated glyphs carry no space glyph, so the caller splits
      them on a font-relative gap, L-007), and a label column of ragged width
      scatters gap midpoints so no boundary reaches the stability threshold --
      the upright word path found ``[50, 735]``, one column. The char path's
      start-edge voting finds the four data columns at x=369/462/562/650, but at
      its 12pt char gap it misses the last: two of that table's column gaps are
      6.3pt. At word level the separation is ``COLUMN_GAP_PT`` (5pt) against a
      measured 1.8-2.4pt word space, so both are used here: start-edge voting on
      words.
    * **A cell's text is assembled LINE BY LINE.** Row clustering merges the
      visual lines of a two-line cell into one row, which is right, but sorting
      its words by x alone interleaves them (``Composite Care, score adjusted
      ...``). Words are grouped into lines first (:func:`_text_by_lines`).

    And one gate is added: :func:`_grid_has_inner_gutter`. A rotated table
    reaches this path because Camelot did not grid it, so there is no second
    capture to arbitrate against, and an UNDER-segmented grid -- two published
    columns fused into one cell -- puts values under the wrong header, which is
    worse than the flat text the caller falls back to.
    """
    words = [w for w in words if (w.get("text") or "").strip()]
    if len(words) < WHITESPACE_MIN_ROWS:
        return [], "too_few_words"
    # Rows are clustered from printed LINES, not from words (`_rows_from_lines`),
    # so that a subscript cannot chain two rows: on 10.1001/jamanetworkopen.
    # 2023.39337 Table 2 the ``1c`` of ``HbA1c``, clustered as a word, sat between
    # the HbA1c row and the next and merged their values into shared cells.
    rows = _rows_from_lines(_visual_lines(words))
    if len(rows) < WHITESPACE_MIN_ROWS:
        return [], "too_few_rows"
    bbox = (
        min(w["x0"] for w in words),
        min(w["top"] for w in words),
        max(w["x1"] for w in words),
        max(w["bottom"] for w in words),
    )
    column_xs = _find_stable_column_boundaries(
        rows, bbox=bbox, gap_pt=COLUMN_GAP_PT, bucket_pt=CHAR_BOUNDARY_BUCKET_PT
    )
    if len(column_xs) < 3:
        return [], "no_stable_columns"
    body_height = _modal_word_height(words)
    header_row_is_header = _row_is_header(rows[0], body_height)
    columns = list(pairwise(column_xs))

    def column_of(w: dict[str, Any]) -> int:
        mid = (w["x0"] + w["x1"]) / 2
        return next((i for i, (a, b) in enumerate(columns) if a <= mid <= b), len(columns) - 1)

    assigned = [{id(w): column_of(w) for w in row_words} for row_words in rows]
    _keep_header_phrases_whole(rows, assigned, column_of)
    cells: list[Cell] = []
    cell_words: dict[tuple[int, int], list[dict[str, Any]]] = {}
    for r, row_words in enumerate(rows):
        row_top = min(w["top"] for w in row_words)
        row_bot = max(w["bottom"] for w in row_words)
        for c, (x_left, x_right) in enumerate(columns):
            in_cell = [w for w in row_words if assigned[r][id(w)] == c]
            cell_words[(r, c)] = in_cell
            cells.append({
                "r": r,
                "c": c,
                "rowspan": 1,
                "colspan": 1,
                "text": _normalize_cell_text(_text_by_lines(in_cell)),
                "is_header": header_row_is_header if r == 0 else False,
                "bbox": (x_left, row_top, x_right, row_bot),
            })
    if _grid_has_inner_gutter(cell_words.values()):
        return [], "column_fused_in_cell"
    cells = _trim_trailing_prose_rows(cells)
    if not _whitespace_grid_is_clean(cells, own_caption_number=own_caption_number, rotated_frame=True):
        return [], "grid_not_clean"
    return repair_cells(cells), None


def _keep_header_phrases_whole(rows, assigned, column_of) -> None:
    """In the table's HEADER rows, keep a phrase in one cell when a column
    boundary falls between two of its words that sit a word space apart
    (<= ``COLUMN_GAP_PT``) on one line. Mutates ``assigned`` in place.

    A spanning column head is wider than the column it is voted into, so the
    boundary cuts it: on 10.1177/23780231251321549 Table 2 (p23, sideways)
    ``Model 5`` came out as ``Model`` | ``5``, and the lone ``5`` was then
    blanked by the HTML cleaner as a leaked page number
    (``cell_cleaning_running_header_cell_blanked``) -- a header lost with a
    count but no reason. The whole phrase goes to the column under its MIDDLE:
    10.1177/23780231221103044 Table 1's ``Total Students (Grades 3-8)`` starts
    in the label column's x-range and spans the two data columns it heads.

    Header rows only: the leading rows with fewer than two data cells (a lone
    ``5`` split off a head must not make its row "data"). In a data row a sub-5pt
    gap at a boundary can be two tight VALUES, and joining them would fuse two
    published numbers into one cell.
    """
    for r, row_words in enumerate(rows):
        texts: dict[int, list[str]] = {}
        for w in row_words:
            texts.setdefault(assigned[r][id(w)], []).append(w.get("text", ""))
        if sum(1 for t in texts.values() if _cell_is_clean_data(" ".join(t), marker_letters=True)) >= 2:
            return
        for line in _visual_lines(list(row_words)):
            runs: list[list[dict[str, Any]]] = [[line[0]]]
            for a, b in pairwise(line):
                if b["x0"] - a["x1"] <= COLUMN_GAP_PT:
                    runs[-1].append(b)
                else:
                    runs.append([b])
            for run in runs:
                if len({assigned[r][id(w)] for w in run}) < 2:
                    continue
                mid = {"x0": run[0]["x0"], "x1": run[-1]["x1"]}
                col = column_of(mid)
                for w in run:
                    assigned[r][id(w)] = col


def _word_size(w: dict[str, Any]) -> float:
    return float(w.get("size") or 0.0) or max(w["bottom"] - w["top"], 0.0) or BODY_HEIGHT_FALLBACK


# A word set smaller than this fraction of its line's size, centred within the
# line vertically and touching one of its words, is a sub- or superscript of it. The
# same 0.92 ratio `detect._detect_footnote_below` uses for "set smaller".
_SCRIPT_SIZE_RATIO: float = 0.92


def _is_script_of(w: dict[str, Any], line: list[dict[str, Any]]) -> bool:
    line_size = max(_word_size(x) for x in line)
    if _word_size(w) >= line_size * _SCRIPT_SIZE_RATIO:
        return False
    # Its vertical CENTRE must lie within the line's span, not merely touch it:
    # on 10.1098/rsos.140072 p5 each 5pt dotted rule overlaps the 10pt row above
    # it by 0.9pt, and an overlap test attached all 382 dots to that row.
    centre = (w["top"] + w["bottom"]) / 2
    if not (min(x["top"] for x in line) <= centre <= max(x["bottom"] for x in line)):
        return False
    reach = 0.5 * _word_size(w)
    return any(w["x0"] - x["x1"] <= reach and x["x0"] - w["x1"] <= reach for x in line)


def _visual_lines(words: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    """``words`` grouped into printed lines, top to bottom, each sorted by x.

    A word joins the current line when its top is within half a line height of
    the line's first word, taking the taller of the two words: a superscript or a
    minus sign drawn on its own baseline (about 1pt off on
    10.1038/s41467-024-45528-0 p6; 2.6pt for ``· min−1)`` on 10.1098/rsos.140072
    p5) stays on its line, and the next line of a wrapped cell (a full line pitch
    down) does not. Per pair, not a page median: on rsos p5 the median word is a
    5pt leader dot, and a median tolerance split that 10pt header line in two.

    A word further off than that still joins a line when it is a sub- or
    superscript of it (:func:`_is_script_of`: smaller, centred within the line,
    touching a word): the ``1c`` of ``HbA1c`` on 10.1001/jamanetworkopen.2023.39337
    p8 sits too low for the first rule and otherwise formed a line of its own.
    """
    if not words:
        return []
    ordered = sorted(words, key=lambda w: (w["top"], w["x0"]))
    lines: list[list[dict[str, Any]]] = []
    for w in ordered:
        if lines:
            anchor = lines[-1][0]
            height = max(anchor["bottom"] - anchor["top"], w["bottom"] - w["top"], 0.0)
            if w["top"] - anchor["top"] <= 0.5 * (height or BODY_HEIGHT_FALLBACK):
                lines[-1].append(w)
                continue
            host = next((ln for ln in reversed(lines[-2:]) if _is_script_of(w, ln)), None)
            if host is not None:
                host.append(w)
                continue
        lines.append([w])
    return [sorted(line, key=lambda w: w["x0"]) for line in lines]


def _rows_from_lines(lines: list[list[dict[str, Any]]]) -> list[list[dict[str, Any]]]:
    """Group printed lines into table rows by the table's OWN line spacing.

    The table's ROW pitch is its modal line pitch. Two lines are one row (a
    wrapped label, or an estimate over its CI) only when they sit clearly closer
    than that -- ``ROW_GAP_RATIO`` times closer -- and every other line starts a
    row. Pitches are taken between the median BOTTOM of each line's base
    (full-size) words. Not their tops: a word carrying a raised significance
    star has a taller box, so on 10.1177/00031224241252079 Table 3 (p15,
    sideways) the estimate lines' tops sat 2.3pt high, every pitch alternated
    13.3 / 8.7pt instead of 11 / 11, and each standard error was grouped with
    the NEXT row's estimate -- ``(.948) 8.441***`` in one cell. When the pitches do not separate,
    lines stay apart: an estimate and its CI in two rows is a split a consumer
    can see, a merge of two published rows into one cell is not.

    NOT `_cluster_into_rows`' rule, and the difference is measured.
    ``max(1.2 x median height, 5pt)`` ignores leading, and a table set with
    lines 1.1-1.2 font sizes apart has every pitch under it:
    10.1080/23743603.2021.1878340 Table 8 (p24, sideways) came out as 4 "rows",
    one cell holding the five lines ``Decoy effect / Control / Regret-Salient /
    Low-Reversibility / Condition effect``. Measured from the table itself,
    evenly spaced lines are one row each, while 10.1038/s41467-024-45528-0
    Table 4 (8.5pt inside a two-line cell, 12pt between rows) and
    10.1001/jamanetworkopen.2023.39337 Table 2 keep their two-line cells.

    Not the TIGHTEST pitch either, which was tried first: on
    10.1177/23780231251314667 Table 1 the row pitch varies 14.0-16.5pt with no
    wrapped cell at all, and ``1.2 x 14.0`` merged every row into two.
    """
    if not lines:
        return []
    baselines = []
    heights = []
    for ln in lines:
        base = max(_word_size(w) for w in ln) * _SCRIPT_SIZE_RATIO
        base_words = [w for w in ln if _word_size(w) >= base]
        bottoms = sorted(w["bottom"] for w in base_words)
        baselines.append(bottoms[len(bottoms) // 2])
        heights.append(_word_size(base_words[0]))
    heights.sort()
    median_h = heights[len(heights) // 2] or BODY_HEIGHT_FALLBACK
    pitches = [b - a for a, b in pairwise(baselines)]
    counts = Counter(round(p * 2) / 2 for p in pitches if p >= 0.5 * median_h)
    row_pitch = max(counts.items(), key=lambda kv: (kv[1], kv[0]))[0] if counts else 0.0
    rows: list[list[dict[str, Any]]] = [list(lines[0])]
    for pitch, ln in zip(pitches, lines[1:]):
        if pitch < 0.5 * median_h or pitch * ROW_GAP_RATIO < row_pitch:
            rows[-1].extend(ln)
        else:
            rows.append(list(ln))
    return rows


def _text_by_lines(words: list[dict[str, Any]]) -> str:
    """A cell's text, line by line; within a line a sub- or superscript touching
    its neighbour (``HbA`` + ``1c``) is joined without a space. Only a SCRIPT --
    one word set smaller than the other: same-size words were split by the word
    extractor for a reason, and a slanted face's boxes overlap its word spaces
    (10.1215/00703370-10878053 Table 1's note came out ``Notes:Sample`` when any
    touching pair was joined)."""
    out: list[str] = []
    for line in _visual_lines(words):
        text = ""
        prev = None
        for w in line:
            small, big = sorted((_word_size(w), _word_size(prev))) if prev is not None else (0, 0)
            touching = prev is not None and small < big * _SCRIPT_SIZE_RATIO and (
                w["x0"] - prev["x1"] <= WORD_GAP_RATIO * small
            )
            text += (w.get("text", "") if touching or prev is None else " " + w.get("text", ""))
            prev = w
        out.append(text)
    return " ".join(out)


def _grid_has_inner_gutter(cells_words) -> bool:
    """True when some cell holds two words on one printed line separated by a
    column-sized gap (> ``COLUMN_GAP_PT``): the column detector missed a
    boundary, and that cell is two published columns fused.

    Measured on 10.1016/j.jesp.2020.103977 Table 4 (p8, sideways): its columns
    are filled on few rows, so only some boundaries clear the stability vote and
    one cell read ``Omission will be associated with a bias towards lower
    Immorality -1.21 [-1.55, -1.46 [-1.83,`` -- a hypothesis, a rating
    attribute and two scenarios' estimates in one cell. On 10.1038/s41467-024-
    45528-0 Table 4, which grids correctly, no cell has a gap over 2.4pt.

    A gap is BRIDGED, and so not a gutter, when another word of the same cell
    lies in it and overlaps the line vertically: a subscript or superscript set
    on its own baseline. On 10.1001/jamanetworkopen.2023.39337 Table 2 (p8) the ``1c``
    of ``HbA1c`` falls to a line of its own and left a 7pt gap in ``HbA level,
    %``, which is one column.
    """
    for words in cells_words:
        words = list(words)
        for line in _visual_lines(words):
            top = min(w["top"] for w in line)
            bottom = max(w["bottom"] for w in line)
            for a, b in pairwise(line):
                if b["x0"] - a["x1"] <= COLUMN_GAP_PT:
                    continue
                bridged = any(
                    w["x1"] > a["x1"] and w["x0"] < b["x0"]
                    and w["top"] < bottom and w["bottom"] > top
                    for w in words
                    if w is not a and w is not b
                )
                if not bridged:
                    return True
    return False


def _region_caption_number(region: CandidateRegion) -> int | None:
    """The table number of the caption this region was anchored on, if known.

    Feeds ``_whitespace_grid_is_clean``'s identity-based own-caption exemption
    (RC-T cycle 4). Returns None for a region with no caption match, which keeps
    the strict "any caption condemns the grid" behaviour.
    """
    cap = getattr(region, "caption_match", None)
    return getattr(cap, "number", None) if cap is not None else None


# --- helpers ---


def _cluster_into_rows(words: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    """Sort words by reading order, then split into rows on y-gap > median x 1.2.

    The gap is measured to the PREVIOUS WORD. That is a known defect, it is still
    here, and the reason is worth reading before anyone changes it again.

    THE DEFECT. Words are sorted by ``(top, x0)``, so in a wrapped or staggered
    block the running "previous top" creeps forward in sub-threshold steps and the
    threshold is never crossed: an arbitrarily tall band collapses into ONE row,
    which then fails every downstream grid guard on its own merits and the table is
    dropped. Measured with ``python tools/diag/row_cluster_census.py`` over the
    26-paper baseline: **30 of 60 caption-anchored regions smear, across 8 papers.**
    Real, systematic, and not one paper's quirk.

    THE 2026-08-04 REVERT'S PREMISE WAS FALSE, and that much IS now settled. It
    justified reverting an anchor-relative fix with *"a real row can legitimately be
    TALL: xiao Table 4's row 2 spans 94.4pt"*. Re-measured 2026-08-19: that row is
    the ENTIRE table body — stacked header, five product rows, five CI continuation
    lines, 75 words — and the table emitted ``cells=0``. Four geometric
    discriminators had been designed and rejected around a constraint that did not
    exist.

    THE REAL BLOCKER, measured 2026-08-19 and NEW. Anchor-relative clustering was
    implemented, closed the chain merge, recovered ``xiao`` Table 4 (0 -> 35 cells)
    and ``chan_feldman``'s grids — and regressed ``efendic_2022_affect``. That paper
    gets NO whitespace grid under this rule (0 cells, honest raw_text fallback);
    under the anchor rule it gets a mis-segmented 3-column grid that separates each
    corrupt ``2X.XX`` B-coefficient from the CI proving it negative, so
    **11 published negative coefficients ship as positive numbers** (``21.09`` for
    ``-1.09``) on the PRODUCTION path. By this project's ranking — rank defects by
    whether the wrong output ANNOUNCES ITSELF — a sign-flipped regression
    coefficient outranks a missing grid, so the anchor rule does not ship.

    THREE CONTAINMENTS WERE TRIED AND ALL FAILED; do not re-try them blind:

    1. **continuation re-merge** (fold an indented single-baseline line back into
       the row above) — it CHAINED, re-creating the chain merge through its own
       repair; corpus guard-diff showed 21 tables losing cells (-867);
    2. **bounded fixed-point on ``recover_minus_via_ci_pairing``** — the hypothesis
       was that a corrupt CI bracket had to be repaired before the estimate beside
       it became reachable. It converges in 2 passes and fixed a different line; the
       11 estimates were untouched, so the hypothesis was wrong;
    3. **signature-keyed hybrid** (previous-word by default, anchor only where the
       previous-word result actually smears) — ``efendic`` smears too, so the gate
       does not separate the classes.

    WHAT A REAL FIX NEEDS. Not a fifth clustering threshold. The anchor rule is
    right about rows and wrong about COLUMNS: the grids it enables on ``efendic``
    are under-segmented (3 columns for a 5-column table, one cell fusing two rows'
    labels and values). The clustering change is therefore blocked on column
    segmentation quality, i.e. on real per-cell geometry — register A1/G6a — or on a
    grid-quality gate that can reject an under-segmented grid before it displaces a
    correct raw_text fallback. Either way, gate the next attempt on
    ``tests/test_minus_sign_recovery_real_pdf.py`` as well as the corpus guard-diff:
    the guard-diff CANNOT see this defect, because it compares cell counts and
    lengths and never values.
    """
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
        if w["top"] - current[-1]["top"] > threshold:
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
    """Whitespace/soft-hyphen/minus canonicalisation only — NO glyph repair.

    v2.4.133 added a ``clean_cell_text`` call here so the layout-derived channel
    would stop shipping unrepaired cells to ``flatten`` / ``cells[].text`` /
    ``raw_text``. The goal was right, the placement was not: both builders run
    the structural gates (:func:`_trim_trailing_prose_rows`,
    :func:`_whitespace_grid_is_clean`) on the cells built here, so repairing at
    build silently changed what those gates judge — and one of their predicates
    changes in the DELETING direction (see :func:`_repaired_view`). The repair
    now happens at :func:`cell_cleaning.repair_cells`, after the gates and before the return,
    so every channel still receives repaired text and no gate verdict moved.
    """
    return normalize_cell_whitespace(text)


def _repaired_view(cells: list[Cell]) -> dict[tuple[int, int], str]:
    """``{(r, c): repaired_text}`` for a gate that needs both forms of a cell.

    ## Why a gate needs both, and why the rule is per-predicate

    The structural gates run on RAW cells (see :func:`_normalize_cell_text`), but
    some of their predicates should judge the text docpluck actually SHIPS, which
    is the repaired form. Two independent reviews converged on splitting the
    predicates by what a rejection COSTS:

      * **content-deleting** — ``_row_is_prose`` / ``_cell_is_prose`` drive
        :func:`_trim_trailing_prose_rows`, which cuts from the first sustained
        prose row to the END of the grid. A repair must never flip one of these
        INTO deleting, so a row is prose only when it is prose in BOTH forms.
        The vector is real: the W0i class prints ``×`` as ``3``, so the raw
        interaction label ``Direction 3 manipulated attribute`` carries a digit
        and reads as data, while the repaired ``Direction × manipulated
        attribute`` has no digit and reads as prose. Three such rows deleted
        every row below them. Pinned by ``test_repair_never_deletes_a_row.py``.
      * **validity** — ``_cell_is_garbled`` / ``_cell_is_clean_data`` /
        ``_CAPTION_LABEL_RE`` decide whether the grid is publishable at all.
        These judge the REPAIRED form, because that is what a consumer receives:
        a cell whose only defect is a recoverable ``(cid:0)`` minus is a data
        cell, and a repaired ``<.001`` is data where the raw ``\\.001`` was not.
        Rejecting here costs a table docpluck could have published correctly,
        never a row it silently deletes — the opposite trade, so the opposite
        default. (``whitespace.py``'s own ``_OWN_CAPTION_MAX_ROW`` comment
        states the ranking this follows: a visible missing table beats an
        invisible wrong one.)

    Keyed on ``(r, c)`` rather than list position on purpose:
    :func:`_trim_trailing_prose_rows` FILTERS the cell list, so any parallel-list
    scheme would drift out of alignment the moment it did its job.
    """
    return {(c["r"], c["c"]): clean_cell_text(c.get("text") or "") for c in cells}


# --- prose-contamination guard + data-table quality gate (RC-T) -----------
#
# A caption-anchored whitespace/char region extends a fixed distance below the
# caption (detect.SEARCH_BELOW_PT), so on a SHORT table it absorbs the body
# paragraphs that follow — and on a PROSE table (a "Summary of hypotheses" grid)
# the whole region is sentence text. Before the v2.4.98 caption page-fix these
# regions never resolved (empty line_text → _bbox_of_caption_line None), so the
# fallback silently emitted nothing; now that captions carry real line_text the
# fallback fires on them and would emit garbage grids (cog_emo T1/T3/T4/T9 mashed
# prose; rows lifted from an adjacent matrix). These two guards keep the fallback
# to its purpose — the genuinely-lineless DATA table — and otherwise return [] so
# the caller emits a clean caption-only stub.

# A "statistical token" — any of these in a cell means the row carries data, not
# prose. Numbers (incl. APA leading-dot + signed), comparison/equality ops, CI
# brackets, the interaction/multiplication operators, and the bare single-letter
# stat/df markers academic tables use.
#
# THE OPERATOR CLASS MUST COVER THE NOTATION `clean_cell_text` EMITS. This
# vocabulary is the evidence a row carries data, and the repair chain rewrites
# corrupted glyphs INTO that notation: W0i turns `Direction 3 attribute` into
# `Direction × attribute`, W0c/W0o turn `\.001` into `<.001`. When `×` was
# missing here, the repair removed the row's only digit and the row flipped from
# data to prose — so a correct repair became a deletion signal (register R4).
# `<`, `≤` and `≥` were already covered; `×` and `·` were the gap. An `×` in an
# academic table cell is an interaction term or a dimension ("2 × 2 design"),
# never running prose, so this widens the data side without loosening the prose
# side. See :func:`_repaired_view` for the structural half of the same fix.
_STAT_TOKEN_RE = re.compile(
    r"[-+−]?\d*\.?\d+|[<>=≤≥×·]|\[[^\]]*\]|\bp\b|\bt\b|\bF\b|\bd\b|\br\b|\bM\b|\bSD\b|\bdf\b|\bn\b|\bN\b",
    re.IGNORECASE,
)

# A prose block must be at least this many consecutive rows before we trim it —
# one or two wordy rows could be a legitimate multi-line note, but a sustained
# run is unambiguously absorbed body text.
_PROSE_RUN_MIN: int = 3


def _row_is_prose(cells_text: list[str]) -> bool:
    """True when a whitespace-grid row looks like wrapped body PROSE rather than
    a table data/label/header row.

    A prose row has several word-like tokens and NO statistical token in ANY
    cell. Word-wrap fragments the text mid-word (``"We predicted, b" | "ased on
    the"``), so we count whitespace TOKENS (length ≥2, incl. fragments) rather
    than only whole dictionary words — otherwise a wrapped prose line scores too
    few words. A real data row always carries a number / op / CI / stat marker
    (excluded first); a real section/label row has few tokens (kept). The
    trailing-RUN requirement in ``_trim_trailing_prose_rows`` is what makes this
    safe — one wordy row never trims; only a sustained block of them does.
    """
    joined = " ".join(t for t in cells_text if t).strip()
    if not joined:
        return False
    if _STAT_TOKEN_RE.search(joined):
        return False  # carries a number / op / CI / stat marker → data row
    tokens = [tok for tok in re.split(r"\s+", joined) if len(tok) >= 2]
    return len(tokens) >= 3


# A single CELL that is a body-prose sentence fragment: ≥ this many whitespace
# word-tokens of running text. A real data cell is a number / short label / stat;
# a table never carries a 6-word sentence fragment in one cell, but an
# over-captured body-paragraph line does ("264) were asked to recall a hurting
# experience that"). Used by ``_whitespace_grid_is_clean`` to reject region grids
# that absorbed 2-column body prose.
_PROSE_CELL_MIN_WORDS: int = 6


def _cell_is_prose(text: str) -> bool:
    """True when one cell is a running-prose sentence fragment (≥6 word tokens,
    mostly alphabetic words, not a stat/number list). Robust to wrapped fragments
    and to embedded ``n = ``/``p = `` (which fool the stat-token guard) because it
    keys on word COUNT, not on the absence of an operator."""
    s = (text or "").strip()
    if not s:
        return False
    words = [w for w in re.split(r"\s+", s) if w]
    if len(words) < _PROSE_CELL_MIN_WORDS:
        return False
    # Count tokens that are predominantly alphabetic (letters ≥ half the token) —
    # a numeric/stat row ("239 | 794 | 0.07 | [.01, .12]") has few such tokens
    # even when it is long.
    alpha_words = sum(
        1 for w in words
        if sum(ch.isalpha() for ch in w) * 2 >= len(w) and any(ch.isalpha() for ch in w)
    )
    return alpha_words >= _PROSE_CELL_MIN_WORDS


# A categorical/design table (predictions, 2×2 conditions, factor summaries) is a
# real table that carries NO numeric cells — every cell is a short label
# ("Risk is high", "Negative affect"). The numeric-data gates
# (``_cell_is_clean_data`` / ``_row_is_prose``) therefore read each of its rows as
# prose and discard the whole grid (efendic Table 1: a 5×3 predictions table whose
# region-driven Camelot grid is perfect, then deleted by the prose guards). A cell
# is "categorical-short" when it has at most this many word tokens AND characters —
# tight enough that an over-captured body-prose line (which always carries a
# ``_cell_is_prose`` sentence fragment of ≥6 alpha words) can never satisfy it.
_CATEGORICAL_CELL_MAX_WORDS: int = 5
_CATEGORICAL_CELL_MAX_CHARS: int = 40


def _is_categorical_grid(cells: list[Cell]) -> bool:
    """True when ``cells`` form a RECTANGULAR grid (≥2 rows × ≥2 cols, every row at
    the modal column count, no empty cell) of short, non-prose, non-garbled labels.

    This is the structural signature of a categorical/design table that carries no
    numeric data — a real table the numeric-data gate would otherwise reject. It is
    deliberately strict so it can NEVER accept absorbed two-column body prose:

      * every cell must be ``_CATEGORICAL_CELL_MAX_WORDS``/``_CHARS``-short — a
        wrapped body-paragraph line has a long sentence fragment in a cell;
      * no cell may be a ``_cell_is_prose`` fragment (≥6 alpha words) or
        ``_cell_is_garbled`` (glyph fusion);
      * the grid must be rectangular with no holes — absorbed prose is ragged
        (variable word/column counts per wrapped line).

    Keyed on a layout-structural signature (short uniform aligned labels), never on
    paper identity, so it generalizes to any all-categorical academic table.

    Applied UNCONDITIONALLY (not gated on ``allow_categorical``) inside the
    prose-trim and clean-grid gates, so it serves the generic region path
    (efendic Table 1) as well as the side-by-side isolated-region path. The
    ``allow_categorical`` flag is a looser, opt-in relaxation for grids this
    strict predicate rejects (e.g. a gutter-clipped side-by-side column with a
    hole or a ragged tail).
    """
    if not cells:
        return False
    by_row: dict[int, list[Cell]] = defaultdict(list)
    for c in cells:
        by_row[c["r"]].append(c)
    row_indices = sorted(by_row)
    if len(row_indices) < 2:
        return False
    counts = [len(by_row[r]) for r in row_indices]
    modal = max(set(counts), key=counts.count)
    if modal < 2:
        return False
    if any(n != modal for n in counts):
        return False  # not rectangular — ragged like wrapped prose
    for c in cells:
        text = (c.get("text") or "").strip()
        if not text:
            return False  # a hole in a "rectangular" grid — suspicious
        if _cell_is_prose(text) or _cell_is_garbled(text):
            return False
        words = [w for w in re.split(r"\s+", text) if w]
        if len(words) > _CATEGORICAL_CELL_MAX_WORDS or len(text) > _CATEGORICAL_CELL_MAX_CHARS:
            return False
    return True


def _trim_trailing_prose_rows(
    cells: list[Cell], *, allow_categorical: bool = False
) -> list[Cell]:
    """Drop the body-prose block a whitespace region over-captured below a table.

    Finds the EARLIEST row that begins a sustained run (``≥ _PROSE_RUN_MIN``) of
    consecutive prose rows and cuts from there to the end. Cutting at the first
    sustained prose block (rather than only a strictly-trailing run) is what makes
    this robust to a stray section heading that interrupts the absorbed prose
    (collabra.77859 Table 1: data rows, then a prose block with a lone heading — a
    trailing-only walk would stop at that heading and keep all the prose above
    it). A real table's data rows always carry a number / stat marker, so they
    never form a prose run; requiring a RUN of ``_PROSE_RUN_MIN`` is the
    false-positive guard against a single wordy note or label row. If the
    surviving grid has < 2 rows the whole grid is dropped (``[]``) so the caller
    emits a clean caption-only stub.

    ``allow_categorical`` uses the stricter per-CELL prose test (``_cell_is_prose``
    — a genuine ≥6-word sentence fragment) instead of the row-token heuristic, so
    a purely categorical table (``Design facet | Replication study`` / ``IV
    operationalization | Same``) is not mistaken for a prose run. Those rows have
    3+ short tokens with no stat marker, which ``_row_is_prose`` flags as prose;
    but each cell is a short label, never a sentence, so the per-cell test keeps
    them. Used only by the side-by-side region path, which has already bounded the
    table by geometry.
    """
    if not cells:
        return cells
    # A purely-categorical table (all short labels, no numbers) reads as an
    # all-prose run to ``_row_is_prose`` and would be cut to nothing. Its tight
    # rectangular short-label signature can't be absorbed prose, so leave it whole.
    # Unconditional (serves the generic region path — efendic Table 1) and cheap;
    # the ``allow_categorical`` flag below further relaxes the per-row prose test
    # for the geometry-bounded side-by-side path (which may be ragged/holey and so
    # fail the strict rectangular predicate).
    if _is_categorical_grid(cells):
        return cells
    by_row: dict[int, list[Cell]] = defaultdict(list)
    for c in cells:
        by_row[c["r"]].append(c)
    row_indices = sorted(by_row)
    # BOTH FORMS, and prose only when BOTH agree. This predicate deletes rows —
    # every row from the first sustained prose block to the end of the grid — so
    # a glyph repair must not be able to flip it into deleting. See
    # :func:`_repaired_view` for the measured vector (W0i's `×`-as-`3`).
    rep = _repaired_view(cells)

    def _rep_of(c: Cell) -> str:
        return rep.get((c["r"], c["c"]), c.get("text") or "").strip()

    if allow_categorical:
        prose_flags = [
            any(
                _cell_is_prose((c.get("text") or "").strip())
                and _cell_is_prose(_rep_of(c))
                for c in by_row[r]
            )
            for r in row_indices
        ]
    else:
        prose_flags = [
            _row_is_prose([(c.get("text") or "").strip() for c in by_row[r]])
            and _row_is_prose([_rep_of(c) for c in by_row[r]])
            for r in row_indices
        ]
    # Find the first index that starts a run of >= _PROSE_RUN_MIN prose rows.
    cut_pos: int | None = None
    run = 0
    run_start = 0
    for i, is_prose in enumerate(prose_flags):
        if is_prose:
            if run == 0:
                run_start = i
            run += 1
            if run >= _PROSE_RUN_MIN:
                cut_pos = run_start
                break
        else:
            run = 0
    if cut_pos is None:
        return cells  # no sustained prose block — leave the grid intact
    cut_row = row_indices[cut_pos]
    kept = [c for c in cells if c["r"] < cut_row]
    kept_rows = {c["r"] for c in kept}
    if len(kept_rows) < 2:
        return []
    return kept


# A "clean" data cell: content that is essentially ALL numbers, separators and stat
# punctuation, with no substantive word. Used to confirm a whitespace grid is a real
# DATA table, not absorbed prose.
#
# Judged by NUMERIC DOMINANCE rather than by one token shape (2026-08-04). The previous
# pattern anchored ^…$ around a SINGLE numeric token, so it accepted `2.84`, `.67`,
# `[0.59, 0.73]`, `(170)`, `<.001` — but rejected every multi-token APA COMPOSITE:
#
#     2.84 [1.89]         mean [SD]              <- maier Tables 5 and 7
#     3.47 [1.23] (170)   mean [SD] (n)          <- maier T7, gold-exact
#     2.84 ± 1.89         mean ± SD
#     0.42***             estimate with significance markers
#
# A descriptives table built from those cells scored clean_data_rows = 0 and was
# discarded as "not a data table", so the grid was thrown away and the table rendered
# as a caption-only stub. Chasing each new composite with another alternation does not
# generalise; requiring "at least one digit AND no substantive word" does, and keeps the
# prose side exactly where it was — a cell carrying real words is still not data, which
# is what keeps absorbed body text out of the grid (cog_emo Table 3's 27x4 all-prose
# grid). Guarded by tests/test_clean_data_cell_composites.py.
#
# A "substantive word" is an alphabetic run of 2+ letters, so single-letter statistic
# markers (M, SD is two letters and deliberately NOT allowed here, n, p, r, d) do not
# smuggle prose in: the cell must still be digit-bearing to qualify at all.
#
# THE PARAGRAPH ABOVE IS NOT WHAT THE DEFAULT PATTERN DOES, and on the upright
# path that is now deliberate (measured 2026-09-25). The default pattern admits NO
# letter, so a cell like ``-152 (-1528, 1223) P = 0.86`` is not "data". Admitting
# isolated single letters everywhere was tried: over the 102-paper corpus with
# Camelot off it let four GARBLED upright grids through the gates -- doubled-glyph
# cells like ``SSiiggnnaall--iinnccoonnssiisstteenntt`` (10.15626/mp.2022.3108 Table 10;
# 10.1080/23743603.2021.1878340 Tables 1 and 7; 10.1016/j.jesp.2021.104154 Table
# 14), and two of them then REPLACED a correct raw_text fallback. The upright char
# path's garble is what the letter-free pattern was filtering, by accident.
#
# `marker_letters=True` admits them -- isolated single letters only
# (`_SUBSTANTIVE_WORD_RE`) -- and is used by the ROTATED path alone, whose words are
# built from glyph gaps (no char-path garble) and whose grids pass an extra
# fused-column gate. There it is required: every value cell of
# 10.1038/s41467-024-45528-0 Table 4 carries its own ``P =``.
_CLEAN_DATA_ALLOWED_RE = re.compile(r"^[\d\s.,;:%±*†‡/\-–—−+()\[\]<>=≤≥]+$")
_CLEAN_DATA_WITH_MARKERS_RE = re.compile(r"^[\d\s.,;:%±*†‡/\-–—−+()\[\]<>=≤≥A-Za-z]+$")
_SUBSTANTIVE_WORD_RE = re.compile(r"[A-Za-z]{2,}")


def _cell_is_clean_data(text: str, *, marker_letters: bool = False) -> bool:
    """True when ``text`` is a data cell: digit-bearing and free of substantive
    words (with ``marker_letters``, single-letter markers such as ``P =`` allowed)."""
    s = (text or "").strip()
    if not s:
        return False
    if not any(ch.isdigit() for ch in s):
        return False
    if marker_letters:
        return bool(_CLEAN_DATA_WITH_MARKERS_RE.match(s)) and not _SUBSTANTIVE_WORD_RE.search(s)
    return bool(_CLEAN_DATA_ALLOWED_RE.match(s))
# A severely GARBLED cell — a long run of one repeated letter (vertical-text
# merge: ``caaaaaaaaaDott…``), a very long unbroken alpha token (columns the
# char-fallback fused), or an unmapped-glyph marker. ``(cid:N)`` / U+FFFD mean
# pdfminer/pdfplumber could not decode a glyph; the Camelot HTML path recovers a
# (cid:0)-before-digit minus, but in a fused whitespace cell the marker sits
# mid-token (``[(cid:0)ra00m..er’s,V``) where no recovery applies — its presence
# is itself proof the char extraction for this region is corrupted, not tabular.
_REPEAT_CHAR_RUN_RE = re.compile(r"([A-Za-z])\1{4,}")
_LONG_ALPHA_TOKEN_RE = re.compile(r"[A-Za-z]{24,}")
_UNMAPPED_GLYPH_RE = re.compile(r"\(cid:\d+\)|�")

# A cell that contains a CAPTION label ("Table 9.", "Figure 2:") — structural
# furniture that introduces a table, and so belongs BETWEEN tables, never inside
# a data cell. Its presence proves the region absorbed an adjacent table's (or its
# own) caption line (cog_emo Table 9's region reached up into Table 8's bottom
# rows and pulled in the "Table 9. Summary…" caption). One occurrence condemns
# the grid — the region is mis-bounded. (A trailing ``Note:`` / ``** p < .01``
# footnote is deliberately NOT included: it is a legitimate part of many real
# tables — e.g. cog_emo Table 2's intercorrelation matrix — and rejecting on it
# would discard good grids.)
# ANCHORED at the cell start (2026-08-04). Unanchored, this fired on a mid-sentence
# CROSS-REFERENCE in a footnote/prose cell and condemned the whole grid: maier Table 5's
# region carries "…al. (2007) in Table 8." and "…in Figure 2. We summarized the in-", so
# its 3x5 descriptives grid was discarded and the table rendered as a caption-only stub
# — even though the raw_text channel had captured the data correctly
# (2.84 [1.89] {1.36}* (170) …). That is TEXT-LOSS from a false positive, verified
# against the AI gold.
#
# An ABSORBED caption — the thing this guard exists to catch — always begins its cell;
# a reference has sentence text before it. ``camelot_extract._CAPTION_ROW_PATTERN``
# already encodes exactly this discipline (its comment notes that anchoring is why an
# inline "see Table 2" does not match); the whitespace copy had simply lost the anchor.
# Kept deliberately in sync with that pattern.
_CAPTION_LABEL_RE = re.compile(r"^\s*(?:Table|Figure|TABLE|FIGURE)\s+\d+\s*[.:]")

# A caption-anchored region ALWAYS contains its OWN caption line by construction:
# ``detect._region_for_caption`` returns ``_union(caption_bbox, geom_bbox)`` because
# the region-driven Camelot pass needs the caption for pairing. So the caption-
# absorption guard above must exempt the region's own caption, or it condemns EVERY
# region grid — which is exactly what it did (RC-T cycle 4, reproduced 2026-08-04:
# 19/19 chan_feldman + maier regions rejected on their own caption, zeroing the
# whitespace fallback corpus-wide and truncating rows in the raw_text fallback).
#
# The exemption is deliberately IDENTITY-BASED, not position-based. A position-only
# rule ("the topmost caption is the region's own") was written first and REJECTED in
# review (codex, 2026-08-04) — all three of its failure modes reproduced locally:
#   * a NEIGHBOUR's caption landing in a leading row was blessed as "own", turning the
#     old honest failure ("no table") into a WRONG table published silently;
#   * ``(r, c)`` sort order picks the leftmost caption, which on a side-by-side page is
#     the neighbour's, not the anchor's;
#   * exempting the whole ROW let a second ``Table N.``/``Figure N.`` on that same row
#     ride along free.
# So the exemption requires the cell's caption NUMBER to equal the anchoring caption's,
# and applies per-CELL. A grid whose own caption is char-fragmented across cells simply
# fails to match and is rejected — the safe direction (a visible missing table beats an
# invisible wrong one; cf. the run-4 sign-flip rule).
_OWN_CAPTION_MAX_ROW: int = 2

# Caption number extractor for the identity check. TABLE captions only: a region
# anchored on a table caption that leads with a ``Figure N.`` label has absorbed a
# neighbouring figure and is genuinely mis-bounded.
_OWN_TABLE_CAPTION_NUM_RE = re.compile(r"\b(?:Table|TABLE)\s+(\d+)\s*[.:]")

# A real data table the whitespace fallback should surface has at least this many
# rows bearing a clean standalone numeric/stat cell. Below this it is almost
# certainly absorbed prose or a misdetected region — discard.
_MIN_CLEAN_DATA_ROWS: int = 2


def _cell_is_garbled(text: str) -> bool:
    s = (text or "").strip()
    if not s:
        return False
    if _UNMAPPED_GLYPH_RE.search(s):
        return True
    if _REPEAT_CHAR_RUN_RE.search(s):
        return True
    for tok in s.split():
        if _LONG_ALPHA_TOKEN_RE.match(tok):
            return True
    return False


def _whitespace_grid_is_clean(
    cells: list[Cell],
    *,
    allow_categorical: bool = False,
    own_caption_number: int | None = None,
    rotated_frame: bool = False,
) -> bool:
    """Accept a whitespace/char grid ONLY when it looks like a real DATA table.

    The whitespace fallback is geometry-driven and, on regions it shouldn't have
    fired on (absorbed body prose; multi-column text; vertical-label IEEE tables),
    it emits prose rows or glyph-fused garbage. Camelot already handles the clean
    tables; the fallback exists for the genuinely-lineless data table. So gate it:

      * NO cell may carry an unmapped-glyph marker ((cid:N) / U+FFFD) — a clean
        academic table never contains one and the whitespace path cannot recover
        a mid-token marker; one occurrence condemns the grid.
      * a grid is clean when its rows bearing a clean STANDALONE numeric/stat cell
        are at least ``_MIN_CLEAN_DATA_ROWS`` AND OUTNUMBER its garbled rows.

    A single garbled HEADER row over a block of clean data rows (ip_feldman Table
    10 — the header glyphs interleave but every coefficient row is clean) is kept;
    a grid that is mostly garble with no clean data (ieee_access_3 Table 3
    vertical-label fusion) or mostly prose with no clean standalone numbers
    (cog_emo Table 1 "Summary of hypotheses") is rejected.

    ``allow_categorical`` accepts a grid with NO numeric data cells when it is a
    clean CATEGORICAL table (text labels + text values — a replication-
    classification "Design facet | Same/Different" grid). The numeric-row
    requirement is the correct guard for the generic geometry-driven fallback, but
    the side-by-side region path that sets this flag has already bounded the table
    to one gutter-clipped column ending at the blank band above the next prose, so
    a categorical grid there is trustworthy. The unmapped-glyph, caption-label, and
    prose-fragment guards below STILL apply, so absorbed prose is still rejected.

    ``own_caption_number`` is the number of the caption this region was anchored on
    (``region.caption_match.number``). When supplied, a leading cell naming THAT table
    number is exempt from the caption-absorption reject — see _OWN_CAPTION_MAX_ROW.
    Omit it (the default) to keep the strict "any caption condemns the grid" behaviour,
    which is correct for any caller whose cells are not caption-anchored.

    Returns False ⇒ caller discards the grid and falls back to the caption-only
    stub (clean, no false structure) instead of emitting garbage.
    """
    if not cells:
        return False
    # VALIDITY predicates judge the REPAIRED form — the text every channel
    # actually ships. A cell whose only defect is a recoverable `(cid:0)` minus
    # is a data cell, and a repaired `<.001` is data where the raw `\.001` was
    # not. See :func:`_repaired_view` for why this half of the rule is the
    # opposite of the content-deleting half.
    rep = _repaired_view(cells)

    def _rep_of(c: Cell) -> str:
        return rep.get((c["r"], c["c"]), c.get("text") or "")

    seen_own_caption = False
    for c in cells:
        txt = _rep_of(c)
        if _UNMAPPED_GLYPH_RE.search(txt):
            return False
        # A caption label inside a cell ⇒ the region absorbed an ADJACENT table's
        # caption (cog_emo Table 8's region reached down into Table 9's caption at
        # grid row 4). Mis-bounded → reject.
        #
        # EXEMPT the region's OWN caption: every caption-anchored region contains it
        # by construction (RC-T cycle 4). Exempted only when the caller supplies the
        # anchoring caption number AND this cell names that exact number AND it sits
        # in a leading row — identity, not merely position, so a neighbour's caption
        # can never be mistaken for the anchor's. Only the FIRST such match is
        # exempt: a genuine caption line appears once, so a repeat means the region
        # spans two copies and is mis-bounded.
        if _CAPTION_LABEL_RE.search(txt):
            if own_caption_number is not None and not seen_own_caption and c["r"] <= _OWN_CAPTION_MAX_ROW:
                m = _OWN_TABLE_CAPTION_NUM_RE.search(txt)
                if m and int(m.group(1)) == own_caption_number:
                    seen_own_caption = True
                    continue
            return False
    # A purely-categorical table (predictions / design summary) carries no numeric
    # cells, so the clean-data-row count below is 0 and it would be rejected — yet
    # it is a real table. Accept it on its rectangular short-non-prose-label
    # signature (only AFTER the glyph / caption-absorption rejections above, so a
    # mis-bounded or corrupted grid is still discarded). Unconditional — serves the
    # generic region path (efendic Table 1); the ``allow_categorical`` branch below
    # is a further, looser relaxation for the geometry-bounded side-by-side path.
    if _is_categorical_grid(cells):
        return True
    by_row: dict[int, list[Cell]] = defaultdict(list)
    for c in cells:
        by_row[c["r"]].append(c)
    clean_data_rows = 0
    garbled_rows = 0
    prose_cell_rows = 0
    nonempty_rows = 0
    for row_cells in by_row.values():
        texts = [(c.get("text") or "").strip() for c in row_cells]
        rep_texts = [_rep_of(c).strip() for c in row_cells]
        if any(t for t in texts):
            nonempty_rows += 1
        # Validity → repaired form.
        if any(_cell_is_garbled(t) for t in rep_texts):
            garbled_rows += 1
        if any(_cell_is_clean_data(t, marker_letters=rotated_frame) for t in rep_texts if t):
            clean_data_rows += 1
        # Content-deleting (feeds the prose-contamination REJECT below) → both
        # forms must agree before a row counts against the grid.
        #
        # A LONG ROW LABEL IS NOT ABSORBED PROSE WHEN ITS ROW CARRIES DATA --
        # ROTATED FRAME ONLY (2026-09-25). Measured on 10.1038/s41467-024-45528-0
        # Table 4: 8 of its 14 rows are labelled like "Change in weight (kg)
        # between baseline and day 15", which `_cell_is_prose` rightly calls a
        # >=6-word fragment, and every one of those rows carries four clean
        # result cells beside it. All 8 counted against the grid and it was
        # rejected as body prose. So in the rotated frame a prose cell in the
        # FIRST column is exempt when a clean data cell sits in another column of
        # the same row. Not on the upright path: together with `marker_letters`
        # it let garbled upright grids through (see `_CLEAN_DATA_ALLOWED_RE`).
        row_has_data_beside_label = rotated_frame and any(
            _cell_is_clean_data(rt, marker_letters=True)
            for c, rt in zip(row_cells, rep_texts)
            if c["c"] != 0 and rt
        )
        if any(
            _cell_is_prose(t) and _cell_is_prose(rt)
            and not (c["c"] == 0 and row_has_data_beside_label)
            for c, t, rt in zip(row_cells, texts, rep_texts)
        ):
            prose_cell_rows += 1
    total_rows = len(by_row)
    # Prose-contamination reject (region-driven false-positive guard, 2026-06-29):
    # a caption-anchored region can over-capture the surrounding 2-column body
    # text, and a wrapped prose line that happens to contain a year or sample size
    # ("…participants (n = 264) were asked…") satisfies _cell_is_clean_data, so
    # prose masquerades as data (cog_emo Table 3: a 27×4 grid that is entirely the
    # High/Low-Empathy procedure paragraph). Detect rows carrying a CELL that is a
    # genuine sentence fragment (``_cell_is_prose`` — many words, lowercase, spaces;
    # NOT a stat/label cell), and reject when such rows are a large share of the
    # grid. A real data/label table has almost none (its cells are numbers and
    # short labels), so this never trips a clean table.
    if total_rows and prose_cell_rows * 3 >= total_rows:
        return False
    if allow_categorical:
        # Categorical table: no numeric requirement. The grid must still be
        # mostly non-garbled and carry ≥ _MIN_CLEAN_DATA_ROWS substantive rows.
        return nonempty_rows >= _MIN_CLEAN_DATA_ROWS and garbled_rows * 2 < nonempty_rows
    return clean_data_rows >= _MIN_CLEAN_DATA_ROWS and clean_data_rows > garbled_rows


# A grid is BODY PROSE when this fraction of its rows carry a genuine sentence
# fragment. Expressed as the reciprocal so the test stays integer arithmetic, and
# deliberately the SAME ratio `_whitespace_grid_is_clean`'s prose-contamination
# reject already uses — one concept, one table. A rule stated twice with two
# constants drifts, and the drift is silent.
_PROSE_GRID_ROW_FRACTION: int = 3

# How many leading rows may carry the grid's header. A table's column names sit at
# the top; scanning further would let a mid-table group-separator label veto the
# verdict for a grid that really is absorbed prose.
_HEADER_SCAN_ROWS: int = 3

# A header row must name at least this many columns to veto the prose verdict.
_HEADER_MIN_NAMED_COLUMNS: int = 2


def grid_is_body_prose(cells: list[Cell]) -> bool:
    """True when a captured grid is running BODY PROSE, not a table.

    The ONE content-plausibility question that is safe to ask of a grid from ANY
    capture path, including Camelot's legacy auto-detect. It is deliberately much
    narrower than :func:`_whitespace_grid_is_clean`, which ALSO rejects on unmapped
    glyphs, absorbed foreign captions and too-few clean data rows: widening that
    whole gate to the auto-detect path was tried on 2026-08-04 and rejected,
    because it discarded legitimate-but-imperfect auto-detect grids (cog_emo
    T5/T6/T7). Prose dominance is the sub-test those grids pass and a paragraph of
    Discussion cannot.

    Evidence: ``maier_2023_collabra`` (10.1525/collabra.77859 companion,
    Table 7 "Perceived Impact (Extension): Descriptives") — the auto-detect path
    hands that caption a 4x2 grid whose cells are the Discussion sentence
    *"Following the analyses conducted in Study 1 of Small et al. (2007), we
    carried out a 2 (Explicit Learning) x 2 (Identifiability) two-way ANOVA…"*,
    and because ``_pick_better_table`` arbitrates on SHAPE alone that grid
    replaces the raw_text channel's gold-exact 3x5 descriptives. The rendered
    ``### Table 7`` then carries its caption and ZERO data values.

    A grid rejected here is not deleted: the caller only acts on this verdict when a
    replacement actually exists (see ``extract_structured``), because a rejection that
    substitutes nothing is a deletion wearing a guard's name.

    A HEADER-LIKE ROW VETOES THE VERDICT, and that half is not optional. Prose
    dominance alone has a false positive on the qualitative review table — a real
    table whose cells are legitimately long phrases. Measured on
    ``10.5465/amc.2022.0006`` Table 4, "A Synthesis and Evaluation of the CSR
    Literature": a 33x4 grid under the header ``Criteria | Synthesis and Evaluation |
    Recommendations``, every data cell a sentence-length phrase, and prose dominance
    alone condemned all 70 cells and 2,008 characters of it. A running paragraph
    sliced into a grid has no header row — maier Table 7's four rows are a sentence, a
    stray footnote digit ``4``, and two more sentence fragments — so the row that
    names the columns is exactly the thing the two classes do not share. The
    predicate is ``cell_cleaning._is_header_like_row``, reused rather than restated.
    """
    if not cells:
        return False
    by_row: dict[int, list[Cell]] = defaultdict(list)
    for c in cells:
        by_row[c["r"]].append(c)
    if not by_row:
        return False
    for r in sorted(by_row)[:_HEADER_SCAN_ROWS]:
        row = [
            (c.get("text") or "")
            for c in sorted(by_row[r], key=lambda c: c["c"])
        ]
        # A header NAMES COLUMNS, so it needs at least two of them. Without this,
        # `_is_header_like_row` vetoes on a single short non-numeric cell, and both
        # pre-release reviewers independently showed the same escape on 2026-08-19:
        # prepending one row containing the single word `Overview` to an otherwise
        # unambiguous three-row Discussion paragraph flips the verdict from True to
        # False and waves the whole grid through. Column-splitting a paragraph
        # routinely leaves ONE stray short cell in some row; it does not routinely
        # leave two in the SAME row, because prose cells are long.
        if sum(1 for t in row if t.strip()) < _HEADER_MIN_NAMED_COLUMNS:
            continue
        if _is_header_like_row(row):
            return False
    # A grid CARRYING REAL DATA is never body prose, however much prose it also
    # absorbed. This rule exists to stop a paragraph that contains NO table data from
    # wearing a caption (maier Table 7); it is not a cleanliness test, and using it as
    # one destroys published numbers. Measured on 10.48550/arxiv.2406.11713 Table 1:
    # a 12x7 grid whose rows 0-4 are Discussion prose AND whose rows 5+ are the real
    # table (`Dataset | Scale factor f | Ouput size | FID`, `CIFAR-10 | 2 | 16x16x4 |
    # 1.32`). Prose dominance alone condemned all 27 cells, and the raw_text fallback
    # carried 61 of the 511 characters — the FID values were simply gone. Caught by
    # tools/diag/table_capture_guard_diff.py AFTER the reviewers' round, which is
    # precisely why the gate is re-run on the final tree rather than the reviewed one.
    #
    # `_MIN_CLEAN_DATA_ROWS` is reused, not restated: it is the same threshold
    # `_whitespace_grid_is_clean` uses to decide a grid is a real DATA table.
    clean_data_rows = sum(
        1
        for row in by_row.values()
        if any(_cell_is_clean_data((c.get("text") or "").strip()) for c in row)
    )
    if clean_data_rows >= _MIN_CLEAN_DATA_ROWS:
        return False
    prose_rows = sum(
        1
        for row in by_row.values()
        if any(_cell_is_prose((c.get("text") or "").strip()) for c in row)
    )
    return prose_rows * _PROSE_GRID_ROW_FRACTION >= len(by_row)


__all__ = ["whitespace_cells", "char_whitespace_cells", "rotated_frame_cells", "grid_is_body_prose"]
