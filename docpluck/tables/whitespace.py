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
    cells = _trim_trailing_prose_rows(cells)
    return cells if _whitespace_grid_is_clean(cells) else []


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
    cells = _trim_trailing_prose_rows(cells)
    return cells if _whitespace_grid_is_clean(cells) else []


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
# brackets, and the bare single-letter stat/df markers academic tables use.
_STAT_TOKEN_RE = re.compile(
    r"[-+−]?\d*\.?\d+|[<>=≤≥]|\[[^\]]*\]|\bp\b|\bt\b|\bF\b|\bd\b|\br\b|\bM\b|\bSD\b|\bdf\b|\bn\b|\bN\b",
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


def _trim_trailing_prose_rows(cells: list[Cell]) -> list[Cell]:
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
    """
    if not cells:
        return cells
    by_row: dict[int, list[Cell]] = defaultdict(list)
    for c in cells:
        by_row[c["r"]].append(c)
    row_indices = sorted(by_row)
    prose_flags = [
        _row_is_prose([(c.get("text") or "").strip() for c in by_row[r]])
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


# A "clean" standalone data cell: a number (incl. APA leading-dot / signed / CI
# bracket / parenthesised), a comparison-op'd p, or a short stat marker. Used to
# confirm a whitespace grid is a real DATA table, not absorbed prose.
_CLEAN_DATA_CELL_RE = re.compile(
    r"^\s*(?:[<>=≤≥]\s*)?[-+−(\[]?\s*\d*\.?\d+"
    r"(?:\s*[,\-–—−]\s*[-+−]?\d*\.?\d+)?\s*[)\]%]?\s*$"
)
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
_CAPTION_LABEL_RE = re.compile(r"\b(?:Table|Figure|TABLE|FIGURE)\s+\d+\s*[.:]")

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


def _whitespace_grid_is_clean(cells: list[Cell]) -> bool:
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

    Returns False ⇒ caller discards the grid and falls back to the caption-only
    stub (clean, no false structure) instead of emitting garbage.
    """
    if not cells:
        return False
    for c in cells:
        txt = c.get("text") or ""
        if _UNMAPPED_GLYPH_RE.search(txt):
            return False
        # A caption label inside a cell ⇒ the region absorbed an adjacent table's
        # caption (cog_emo Table 9's region reached up into Table 8's tail and
        # pulled in the "Table 9." caption line). Mis-bounded → reject.
        if _CAPTION_LABEL_RE.search(txt):
            return False
    by_row: dict[int, list[Cell]] = defaultdict(list)
    for c in cells:
        by_row[c["r"]].append(c)
    clean_data_rows = 0
    garbled_rows = 0
    prose_cell_rows = 0
    for row_cells in by_row.values():
        texts = [(c.get("text") or "").strip() for c in row_cells]
        if any(_cell_is_garbled(t) for t in texts):
            garbled_rows += 1
        if any(_CLEAN_DATA_CELL_RE.match(t) for t in texts if t):
            clean_data_rows += 1
        if any(_cell_is_prose(t) for t in texts):
            prose_cell_rows += 1
    total_rows = len(by_row)
    # Prose-contamination reject (region-driven false-positive guard, 2026-06-29):
    # a caption-anchored region can over-capture the surrounding 2-column body
    # text, and a wrapped prose line that happens to contain a year or sample size
    # ("…participants (n = 264) were asked…") satisfies _CLEAN_DATA_CELL_RE, so
    # prose masquerades as data (cog_emo Table 3: a 27×4 grid that is entirely the
    # High/Low-Empathy procedure paragraph). Detect rows carrying a CELL that is a
    # genuine sentence fragment (``_cell_is_prose`` — many words, lowercase, spaces;
    # NOT a stat/label cell), and reject when such rows are a large share of the
    # grid. A real data/label table has almost none (its cells are numbers and
    # short labels), so this never trips a clean table.
    if total_rows and prose_cell_rows * 3 >= total_rows:
        return False
    return clean_data_rows >= _MIN_CLEAN_DATA_ROWS and clean_data_rows > garbled_rows


__all__ = ["whitespace_cells", "char_whitespace_cells"]
