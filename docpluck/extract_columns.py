"""Column-aware page text re-extraction (R4 / B6, v2.4.75).

Purpose
=======
pdftotext's default-mode reading-order serializes a two-column academic page
**interleaved between columns** when the column structure carries no explicit
geometric signal pdftotext can latch onto (no rules, no wide gutter detected,
no per-line `<flow>` markup). Symptom: the abstract and the right-side
"Key Points" sidebar of a JAMA Open paper, the Measures section of a
chan_feldman paper, the Methods of a chandrashekar paper — all render with
sentences from one column inserted line-by-line into the other column's
prose. Detected per-page by `docpluck.normalize._detect_column_interleave_pages`
and surfaced as `NormalizationReport.column_interleave_pages`.

Strategy
========
For each flagged page, re-extract that page's text using pdfplumber's char
geometry. Cluster chars into TWO columns by x-center; within each column,
sort lines top-to-bottom and concatenate. Output is "left column first, then
right column" — the canonical reading order for left-to-right scripts.

This module **never** touches pages that aren't flagged. The structural
signature gate (in normalize.py) is what decides which pages need rewriting;
this module is the rewriter. Conservative gates inside `extract_page_text_columns`
prevent emitting garbage on edge cases (single-column pages that get false-
flagged, pages with three+ columns, etc.) — falls through to the page's
original `extract_text()` output when the column-detection signal is weak.

Per CLAUDE.md hard rule 3 ("Never swap text-extraction tool as a fix for
downstream problems"): this is *conditional* per-page re-extraction, NOT a
default replacement. pdftotext stays as the primary text channel; pdfplumber
column-mode runs only for pages that pdftotext got demonstrably wrong.

Per CLAUDE.md hard rule 2 (no AGPL deps): pdfplumber (MIT) is the engine.

API
===
- `extract_page_text_columns(layout_doc, page_index, column_count=2) -> str`
  Re-extract a single page's text using column-aware ordering. Returns the
  page text, or an empty string if the column-detect signal is too weak
  (caller should fall back to the original page text).

- `splice_column_corrected_pages(raw_text, layout_doc, page_offsets, pages_to_fix) -> str`
  Replace flagged pages' text in `raw_text` with column-aware re-extraction.
  `pages_to_fix` is a 1-indexed list (matching `NormalizationReport.column_interleave_pages`).
"""

from __future__ import annotations

import math
from collections import Counter, defaultdict
from typing import Iterable

from .telemetry import record_fallback
from .tempfiles import unlink_temp_pdf
from .version import resolve_pdftotext_executable


# Minimum number of words on a page before we attempt column-mode re-extraction.
# A page with <40 words is likely a figure-only page or a title page — column
# detection is meaningless and the original extraction is at least as good.
_MIN_WORDS_FOR_COLUMN_MODE = 40

# Minimum fraction of words that must fall in EACH detected column for the
# 2-column hypothesis to hold. A 0.25 floor means both columns must carry
# at least a quarter of the page's words; otherwise the page is single-column
# (or has a sidebar so small that interleave isn't the real problem).
_MIN_COLUMN_FRACTION = 0.25

# Y-clustering tolerance for grouping chars into lines (in PDF points).
# Empirically ~5pt for 10-12pt body text. Smaller values over-split lines;
# larger values merge adjacent rows.
_LINE_Y_TOLERANCE = 5.0


def extract_page_text_columns(layout_doc, page_index: int, column_count: int = 2,
                              pdf_bytes: bytes | None = None,
                              allow_gutter_fallback: bool = False) -> str:
    """Re-extract a single page's text via column-aware ordering.

    Strategy: detect the column midline via word-center histogram on the
    layout doc, then use pdfplumber's `crop().extract_text()` on each
    column's bbox to preserve pdfplumber's native word-spacing (better
    than our char-cluster heuristic which loses spaces on tight-kerned
    PDFs). Concatenate left column then right column.

    Args:
        layout_doc: LayoutDoc from docpluck.extract_layout.extract_pdf_layout.
        page_index: 0-based page index.
        column_count: Number of columns to detect (currently only 2 supported).
        pdf_bytes: Raw PDF bytes — required for the crop-extract strategy.
            When None, falls back to the older word-join approach (less
            reliable spacing on tight-kerned papers).
        allow_gutter_fallback: when True AND the word-center histogram fails to
            find a midline, fall back to the full-height gutter-strip detector
            and BYPASS the y-row bilateral gate. Confined to the O5
            reading-order-inversion path (callers pass True only for pages the
            inversion detector flagged, and only under the word-preservation
            guard) so the legacy column-interleave path stays byte-identical.

    Returns:
        The page text in left-then-right column order. Empty string if the
        column-detection signal is too weak.
    """
    if column_count != 2:
        return ""
    if page_index < 0 or page_index >= len(layout_doc.pages):
        return ""
    page = layout_doc.pages[page_index]

    page_width = float(page.width or 0.0)
    page_height = float(page.height or 0.0)
    if page_width <= 0 or page_height <= 0:
        return ""

    # The detectors below keep reading pdfplumber's own coordinates, exactly as
    # they always have, so WHICH pages qualify is unchanged; only the cut is
    # placed in crop space (`_crop_space_words`), translating their midline.
    all_words = list(page.words or ())
    if len(all_words) < _MIN_WORDS_FOR_COLUMN_MODE:
        return ""

    # Step 1: detect column midline.
    #
    # Primary: word-center histogram (handles wide gutters — JAMA Open et al.).
    # Fallback (v2.4.80, O5 region-aware track): a clean full-height central
    # GUTTER STRIP — a vertical x-interval near the page center that NO word
    # crosses across the page's text height. The histogram can't resolve a
    # narrow (~4-17pt) gutter (it fits inside one ~30pt bucket → no valley →
    # None), yet a surviving full-height empty strip is *stronger* evidence of
    # a two-column layout than the histogram valley: dense single-column prose
    # spans the center, and any full-width line crossing the center collapses
    # the strip. When the gutter path supplies the midline we BYPASS the y-row
    # bilateral gate below — that gate false-rejects two-column pages that also
    # carry a banded table (chen page 19: CRediT table above a 2-column
    # reference list), which is exactly the O5 reading-order-inversion case.
    gutter_gated = False
    midline_x = None
    if allow_gutter_fallback:
        # Inversion path: the full-height gutter strip is the STRONGER 2-column
        # discriminator on banded reference pages (table stacked above a
        # 2-column reference list), so try it FIRST and, when it finds a clean
        # strip, use it and bypass the y-row bilateral gate — even if the
        # histogram would also have returned a (table-contaminated, slightly
        # off) midline. chen p19: histogram None → gutter 297. jamison p9:
        # histogram 327 (off, near the gutter) → gutter 297 (the true column
        # boundary), bilateral gate would otherwise reject the CRediT table.
        midline_x = _detect_2col_midline_gutter(all_words, page_width, page_height)
        if midline_x is not None:
            gutter_gated = True
    if midline_x is None:
        midline_x = _detect_2col_midline(all_words, page_width)
        if midline_x is None:
            return ""

    # Step 2: confirm both columns have substantial content.
    left_count = sum(1 for w in all_words if (w["x0"] + w["x1"]) / 2 < midline_x)
    right_count = len(all_words) - left_count
    if (left_count < len(all_words) * _MIN_COLUMN_FRACTION
        or right_count < len(all_words) * _MIN_COLUMN_FRACTION):
        return ""

    # Step 2b (2026-05-25 EC-T1/R4 wrapup): Y-row bilateral gate.
    #
    # A real 2-column body-text page has each TEXT ROW in ONE column at a
    # time — left-column lines and right-column lines run at independent
    # y-positions (different baselines). Cross-column row matching is the
    # exception (a header / title spanning both columns).
    #
    # A table embedded in a single-column page produces a histogram that
    # LOOKS bilateral (left cell-column vs right cell-column with a gutter)
    # but every table row has cells on BOTH sides at the SAME y. So if a
    # high fraction of y-rows have words on both sides of the candidate
    # midline, we're looking at a table not a column layout.
    #
    # Empirical thresholds (sampled 2026-05-25):
    #   - JAMA Open p1 (real 2-column abstract+sidebar): 12.5% bilateral
    #   - amle_1 page 10 (table-heavy): 65.5% bilateral
    #   - amle_1 page 13 (table-heavy): 53.0% bilateral
    #   - amle_1 page 29 (table-heavy): 38.5% bilateral
    # Gate: reject when bilateral fraction ≥ 30%.
    #
    # SKIPPED when the midline came from the full-height gutter strip
    # (`gutter_gated`): the empty-strip test is a stricter 2-column
    # discriminator, and the bilateral fraction false-rejects banded
    # table+column pages (the O5 case). A clean full-height gutter cannot
    # coexist with a full-width table row crossing the center, so the strip's
    # survival already proves the columns are real.
    if not gutter_gated:
        from collections import defaultdict
        rows_lr: dict[int, list[bool]] = defaultdict(lambda: [False, False])
        for w in all_words:
            y_bucket = int(round(w["top"] / _LINE_Y_TOLERANCE) * _LINE_Y_TOLERANCE)
            x_center = (w["x0"] + w["x1"]) / 2
            if x_center < midline_x:
                rows_lr[y_bucket][0] = True
            else:
                rows_lr[y_bucket][1] = True
        if rows_lr:
            bilateral = sum(1 for r in rows_lr.values() if r[0] and r[1])
            if bilateral / len(rows_lr) >= 0.30:
                return ""

    # Step 3: use pdfplumber crop+extract_text if pdf_bytes supplied. This
    # preserves pdfplumber's spacing semantics (which handle kerned text the
    # word-join approach loses).
    if pdf_bytes is not None:
        ox = (getattr(page, "origin", None) or (0.0, 0.0))[0]
        # No fall-through to the word-join below when the crop read declines:
        # `_crop_and_extract` returns "" exactly when the page has no
        # glyph-free cut or no real second column, and the word-join splits at
        # the raw midline with neither check — it would re-admit the page the
        # cut layout just refused.
        return _crop_and_extract(pdf_bytes, page_index, midline_x - ox,
                                 page_width, page_height,
                                 _crop_space_words(page))

    # Without the PDF bytes there is nothing to crop: word-join approach (no
    # inter-word spacing fix).
    left_words = [w for w in all_words if (w["x0"] + w["x1"]) / 2 < midline_x]
    right_words = [w for w in all_words if (w["x0"] + w["x1"]) / 2 >= midline_x]
    left_text = _words_to_column_text(left_words)
    right_text = _words_to_column_text(right_words)
    if not left_text.strip() or not right_text.strip():
        return ""
    return left_text + "\n\n" + right_text


def _crop_and_extract(pdf_bytes: bytes, page_index: int, midline_x: float,
                       page_width: float, page_height: float,
                       words: list[dict] | None = None) -> str:
    """Crop each column and run pdftotext to preserve proper word spacing.

    pdfplumber's `extract_text()` on tight-kerned PDFs (JAMA Open et al.)
    drops inter-word spaces because the PDF positions characters without
    explicit space chars. pdftotext does its own gap analysis to insert
    spaces correctly. pdftotext supports cropping via `-x -y -W -H` flags:
    we run it once per region of the page and concatenate.

    WHERE the cut goes is decided by `_column_cut_layout`, never by the
    detector's midline as such (``midline_x`` is only the hint of which gutter
    to use). pdftotext keeps a glyph in a crop when the glyph's advance box
    merely TOUCHES the crop, so a cut through a glyph puts that glyph in both
    columns: the detector's histogram midline sat inside the text on 27 of the
    38 pages the v2.4.143 corrector rewrote in a 601-paper sample ("125–135" ->
    "125–13" + "35", 10.1016/j.jesp.2017.05.004 p11). The cut now falls only
    where no upright glyph of the column body lies, and the rows that cross
    every such x — a running header, a page number, a "Downloaded from" line —
    are read full width above or below the columns.

    ``words`` must be in crop space (`_crop_space_words`). Returns "" when the
    page has no glyph-free cut or a crop failed — caller falls back.
    """
    if words is None:
        return ""
    shape = _column_cut_layout(words, page_width, hint_x=midline_x)
    if shape is None:
        record_fallback("column_extract_no_glyph_free_cut", detail=f"p{page_index + 1}")
        return ""
    parts = _read_column_regions(pdf_bytes, page_index, shape, page_width,
                                 page_height, label="column_extract")
    if parts is None:
        return ""
    top, left, right, bottom, margin = parts
    if not left or not right:
        record_fallback(
            "column_extract_empty_column",
            detail=f"left={len(left)} right={len(right)}",
        )
        return ""
    return "\n\n".join(p for p in (top, left, right, bottom, margin) if p)


import re as _re

# A reference-LIST entry at line start: "Surname, F." / "Surname, F. M." /
# "Surname, F., & Other, G." — a capitalized surname (incl. Latin-Extended and
# hyphen/apostrophe), comma, one or more initials. Anchored at line start so
# in-text citations (mid-sentence "(Surname, 2011)") do NOT match.
_REF_ENTRY_RE = _re.compile(
    r"^[A-ZÀ-Þ][\w'’\-]+,\s+(?:[A-ZÀ-Þ]\.\s*)+",
    _re.UNICODE,
)
# A standalone reference-section heading line.
_REF_HEADING_RE = _re.compile(
    r"^\s*(?:#+\s*)?(references?|bibliography|works cited|literature cited)\s*$",
    _re.IGNORECASE,
)


def _detect_reference_inversion_pages(
    text: str, page_offsets: Iterable[int], min_stranded: int = 3
) -> tuple[int, ...]:
    """Flag pages whose reference list was reading-order-inverted by pdftotext.

    Structural signature (the O5 case, chen page 19): within ONE form-feed
    page, ``min_stranded`` or more reference-LIST-entry lines appear BEFORE the
    page's ``References`` heading. Reference entries cannot precede their own
    section heading in correct reading order — so their presence above the
    heading on the same page is unambiguous evidence pdftotext serialized the
    page's columns out of order (it emitted a later column before the column
    that carries the heading).

    Cheap + text-only (no pdfplumber call) so it can gate whether the more
    expensive layout extraction + geometric re-order is worth running. Returns
    1-indexed page numbers (matching ``column_interleave_pages`` semantics).

    This keys on a *structure* (entries-before-their-heading), never on paper
    identity — any PDF whose reference columns pdftotext inverts trips it; a
    normally-ordered paper (heading THEN entries) never does.
    """
    offsets = list(page_offsets)
    if not offsets:
        return ()
    flagged: list[int] = []
    n = len(offsets)
    for pi in range(n):
        start = offsets[pi]
        end = offsets[pi + 1] if pi + 1 < n else len(text)
        page = text[start:end]
        lines = page.splitlines()
        heading_idx = None
        for i, ln in enumerate(lines):
            if _REF_HEADING_RE.match(ln):
                heading_idx = i
                break
        if heading_idx is None or heading_idx == 0:
            continue
        stranded = sum(1 for ln in lines[:heading_idx] if _REF_ENTRY_RE.match(ln))
        if stranded >= min_stranded:
            flagged.append(pi + 1)
    return tuple(flagged)


# ── Reference-list ROTATION (a heading-less continuation page) ──
#
# The inversion detector above needs the page's own ``References`` heading, so
# it is blind to every CONTINUATION page of a reference list — and those are the
# majority of reference pages. On such a page pdftotext can still emit the right
# column before the left one (chen_2021_jesp p20, 10.1016/j.jesp.2021.104154;
# collabra.90203 pp18-20, 10.1525/collabra.90203 — both rasterized 2026-09-23).
# The structural signature: an alphabetical reference list serialized
# right-column-first reads as TWO sorted runs, the second of which belongs
# BEFORE the first — "N..Z" then "G..N". Rotating the entry sequence at the
# seam makes it sorted again; a correctly ordered page gains nothing from any
# rotation.
#
# This is only a TRIGGER for the geometric re-extraction. The order that ships
# is decided by page geometry (left column, then right), never by the alphabet,
# and the splice accepts it only as a pure word-preserving reorder that also
# delivers the sortedness gain that triggered it
# (``_reference_rotation_resolved``).
#
# Tolerance, measured not assumed: pdftotext cannot distinguish a new entry
# from a wrapped author line that happens to start "Frank, M. C." or
# "Grahe, J. E.", so chen p20's 64 entry-shaped lines carry ~4 out-of-order
# keys even in the correct order. Hence a longest-sorted-subsequence measure
# rather than a count of descents — a strict "exactly one descent" rule fired
# on 0 of 102 corpus papers, chen included.
_ROTATION_MIN_ENTRIES = 12
_ROTATION_MIN_RUN = 5
_ROTATION_SORTED_FRACTION = 0.85
_ROTATION_MIN_GAIN_FRACTION = 0.2
_ROTATION_MIN_GAIN = 5


def _reference_entry_keys(page: str) -> list[str]:
    """First letter of the first surname of every reference-entry-shaped line,
    accent-stripped and case-folded (``Groß`` -> ``g``, ``Östling`` -> ``o``)."""
    import unicodedata
    keys: list[str] = []
    for ln in page.splitlines():
        m = _REF_ENTRY_RE.match(ln)
        if not m:
            continue
        s = unicodedata.normalize("NFKD", m.group(0).casefold())
        for c in s:
            if c.isalpha() and not unicodedata.combining(c):
                keys.append(c)
                break
    return keys


def _longest_sorted_run(seq: list[str]) -> int:
    """Length of the longest non-decreasing subsequence (patience sorting)."""
    import bisect
    tails: list[str] = []
    for x in seq:
        i = bisect.bisect_right(tails, x)
        if i == len(tails):
            tails.append(x)
        else:
            tails[i] = x
    return len(tails)


def _reference_rotation_gain(keys: list[str]) -> int:
    """How much more sorted the entry sequence becomes under its best rotation,
    or 0 when the page does not carry the rotation signature."""
    n = len(keys)
    if n < _ROTATION_MIN_ENTRIES:
        return 0
    base = _longest_sorted_run(keys)
    best = max(
        (_longest_sorted_run(keys[k:] + keys[:k])
         for k in range(_ROTATION_MIN_RUN, n - _ROTATION_MIN_RUN + 1)),
        default=base,
    )
    gain = best - base
    if (best >= _ROTATION_SORTED_FRACTION * n
            and gain >= max(_ROTATION_MIN_GAIN, _ROTATION_MIN_GAIN_FRACTION * n)):
        return gain
    return 0


def _detect_reference_rotation_pages(
    text: str, page_offsets: Iterable[int]
) -> tuple[int, ...]:
    """Flag pages whose alphabetical reference list reads as a ROTATION —
    a later column serialized before an earlier one. 1-indexed, like
    ``_detect_reference_inversion_pages``. Text-only and cheap."""
    offsets = list(page_offsets)
    flagged: list[int] = []
    n = len(offsets)
    for pi in range(n):
        start = offsets[pi]
        end = offsets[pi + 1] if pi + 1 < n else len(text)
        if _reference_rotation_gain(_reference_entry_keys(text[start:end])):
            flagged.append(pi + 1)
    return tuple(flagged)


def _reference_rotation_resolved(rewritten: str, original: str) -> bool:
    """True when a re-extracted page delivers the sortedness gain its
    rotation promised: the entry sequence's longest sorted run grows by at
    least the detector's own minimum gain.

    RELATIVE, not an absolute "85% sorted" bar — measured 2026-09-23: on
    collabra.142641 p12 wrapped author lines leave the correctly reordered page
    at 20 of 26 keys sorted (77%), up from 13. A page carrying two genuinely
    separate alphabetical lists gains nothing from a left-then-right read and
    is still refused, as is a reorder that leaves the text as it was."""
    kr = _reference_entry_keys(rewritten)
    ko = _reference_entry_keys(original)
    if not kr:
        return False
    gain = _longest_sorted_run(kr) - _longest_sorted_run(ko)
    return gain >= max(_ROTATION_MIN_GAIN, _ROTATION_MIN_GAIN_FRACTION * len(kr))


def _word_multiset(text: str) -> "Counter":
    """Case-folded SUBSTANTIAL-token multiset of ``text`` (whitespace- and
    order-insensitive). Substantial = an alphabetic token of length ≥ 2 — the
    real words whose loss would be a text-loss (rule 0a) or whose appearance
    would be a hallucination (rule 0b).

    Bare digits and single characters are EXCLUDED: pdftotext column-crop
    re-extraction can shed/introduce a stray page-number digit or a split
    initial at a crop boundary, and blocking an otherwise-perfect reorder on
    that noise would defeat the O5 fix. The reorder must preserve every real
    word; trivial digit/punctuation churn is tolerated.
    """
    import re
    toks = re.findall(r"[^\W\d_]{2,}", text.casefold(), flags=re.UNICODE)
    return Counter(toks)


def _char_multiset(text: str) -> "Counter":
    """Every non-whitespace character of ``text``, with multiplicity."""
    return Counter(c for c in text if not c.isspace())


def _accept_reorder(rewritten: str, original_page: str,
                    must_resolve_rotation: bool) -> bool:
    """The splice's acceptance test, one implementation for every geometry.

    Accept ONLY a pure reorder: identical substantial-word multiset AND a
    materially different token order (else it's a no-op the original already
    had right — don't churn whitespace). Unconditional — it rejects column-crop
    word SPLITS (jama_open_1 'adults'→'adu') that the old accept-any path
    shipped. A rotation-flagged page must additionally come out sorted.
    """
    if not rewritten:
        return False
    if _word_multiset(rewritten) != _word_multiset(original_page):
        return False
    # EVERY non-space character, too. The word multiset deliberately ignores
    # digits and 1-char tokens, and that hole shipped: a running header that
    # crosses the gutter was cut by the column crop, the glyph on the cut
    # landed in BOTH crops, and "125–135" became "125–13" + "35"
    # (10.1016/j.jesp.2017.05.004 p11; one extra digit on 30 of 87 corrected
    # reference pages in a 500-paper sample, measured 2026-09-23). A pure
    # reorder cannot change the character inventory; a crop that duplicates or
    # drops a glyph — an initial, a year digit, a page number — does.
    if _char_multiset(rewritten) != _char_multiset(original_page):
        return False
    if rewritten.split() == original_page.split():
        return False
    return (not must_resolve_rotation) or _reference_rotation_resolved(
        rewritten, original_page)


def splice_column_corrected_pages(
    raw_text: str,
    layout_doc,
    page_offsets: Iterable[int],
    pages_to_fix: Iterable[int],
    pdf_bytes: bytes | None = None,
    gutter_fallback_pages: Iterable[int] | None = None,
    banded_pages: Iterable[int] | None = None,
    changed_out: list | None = None,
    rotation_pages: Iterable[int] | None = None,
    edge_trimmed_pages: Iterable[int] | None = None,
) -> str:
    """Splice column-aware re-extracted text into flagged pages of raw_text.

    Word preservation is UNCONDITIONAL (v2.4.82): a page's re-extraction is
    accepted ONLY when it is a pure reorder — identical substantial-word
    multiset AND a materially different token order. A column re-extraction can
    never legitimately drop, split, merge, or invent a word (rules 0a / 0b); the
    previous "accept any non-empty re-extraction" path for non-guarded pages
    shipped real corruptions (jama_open_1 ``adults`` → ``adu``, ieee_access_3
    ``using`` → ``us`` — pdftotext column-crop cutting a word that straddles the
    crop x). A rejected page keeps its ORIGINAL text (possibly still interleaved
    but WORD-CORRECT) — never a corrupted reorder.

    Args:
        raw_text: Original pdftotext output (form-feed separated pages).
        layout_doc: LayoutDoc.
        page_offsets: Char offsets where each page starts in raw_text.
        pages_to_fix: 1-indexed list of page numbers to rewrite (matching
            NormalizationReport.column_interleave_pages).
        gutter_fallback_pages: 1-indexed pages that may use the full-height
            GUTTER-STRIP midline detector (``allow_gutter_fallback``) — the
            stronger 2-column discriminator that bypasses the y-row bilateral
            table gate. The O5 reading-order-inversion pages and (under
            ``DOCPLUCK_COLUMN_CORRECT_GENERAL``) the general-interleave flagged
            pages opt in. Pages NOT in this set use only the word-center
            histogram midline. This set NO LONGER controls word-preservation —
            that gate now applies to every page, always.
        banded_pages: 1-indexed pages that may use the RC-1 Step 2 per-band
            region-aware re-extraction (``extract_page_text_banded``) as a
            FALLBACK when the whole-page corrector returns "" (table-bearing /
            mixed-layout pages it cannot reach). Same unconditional word-
            preservation guard applies, so a band crop that drops/fabricates a
            word is rejected and the page kept as-is.
        rotation_pages: 1-indexed pages flagged by
            ``_detect_reference_rotation_pages``. For these the reorder must
            ALSO leave the reference-entry sequence sorted
            (``_reference_rotation_resolved``); a reorder that does not undo the
            rotation it was triggered for is rejected and the page kept as-is.
        edge_trimmed_pages: 1-indexed pages that may fall back to
            ``extract_page_text_edge_trimmed`` when the whole-page read is
            empty or refused. Same guards.

    Returns:
        Rewritten raw_text with flagged pages' content replaced. Pages whose
        re-extraction the rewriter couldn't confidently column-detect, or whose
        re-extraction would change the word multiset, are left untouched.
    """
    offsets = list(page_offsets)
    pages_set = set(pages_to_fix)
    gf_pages = set(gutter_fallback_pages or ())
    b_pages = set(banded_pages or ())
    r_pages = set(rotation_pages or ())
    e_pages = set(edge_trimmed_pages or ())
    if not pages_set or not offsets:
        return raw_text

    out_parts: list[str] = []
    n_pages = len(offsets)
    cursor = 0
    for page_idx in range(n_pages):
        start = offsets[page_idx]
        end = offsets[page_idx + 1] if page_idx + 1 < n_pages else len(raw_text)
        # Preserve any leading content (header before page 1).
        if start > cursor:
            out_parts.append(raw_text[cursor:start])
        page_number_1idx = page_idx + 1
        if page_number_1idx in pages_set:
            rewritten = extract_page_text_columns(
                layout_doc, page_idx, column_count=2, pdf_bytes=pdf_bytes,
                allow_gutter_fallback=(page_number_1idx in gf_pages),
            )
            # RC-1 Step 2 (v2.4.90): when the whole-page corrector can't reach a
            # page (a table/banner row crosses the gutter, or a few stray rows
            # defeat the full-height gutter strip), fall back to per-band
            # region-aware re-extraction. The SAME unconditional word-
            # preservation guard below validates the result, so a band split
            # that drops/fabricates a word is rejected (page kept as-is).
            if not rewritten and page_number_1idx in b_pages and pdf_bytes is not None:
                rewritten = extract_page_text_banded(layout_doc, page_idx, pdf_bytes)
            original_page = raw_text[start:end]
            accepted = _accept_reorder(
                rewritten, original_page, page_number_1idx in r_pages)
            # Reference pages whose only gutter-crossing rows are header/title/
            # footer furniture: a second geometry, tried when the whole-page
            # read is unavailable OR refused (its 97%-clear tolerance can cut a
            # crossing footer word, "psychology" -> "ps" + "ychology"). Same
            # guards, so it can only ever add a correct reorder.
            if (not accepted and page_number_1idx in e_pages
                    and pdf_bytes is not None):
                rewritten = extract_page_text_edge_trimmed(
                    layout_doc, page_idx, pdf_bytes)
                accepted = _accept_reorder(
                    rewritten, original_page, page_number_1idx in r_pages)
            if accepted:
                # Re-attach the original page's trailing separator (newlines
                # + form-feed) so the corrected page's last word can't glue
                # onto the next page's first word at the splice boundary
                # (bjps_1 'results'+'https'→'resultshttps'; chen running-header
                # 'J' gluing to the prior word) and the \f page structure is
                # preserved for downstream page-aware consumers.
                trailing = original_page[len(original_page.rstrip()):]
                out_parts.append(rewritten.rstrip() + trailing)
                cursor = end
                if changed_out is not None:
                    changed_out.append(page_number_1idx)
                continue
        out_parts.append(raw_text[start:end])
        cursor = end
    if cursor < len(raw_text):
        out_parts.append(raw_text[cursor:])
    return "".join(out_parts)


# ── helpers ──


def _chars_to_word(chars: list[dict]) -> dict:
    """Collapse a list of pdfplumber chars into a single word dict."""
    text = "".join(c.get("text", "") for c in chars)
    x0 = min(c["x0"] for c in chars)
    x1 = max(c["x1"] for c in chars)
    top = min(c["top"] for c in chars)
    bottom = max(c["bottom"] for c in chars)
    return {"text": text, "x0": x0, "x1": x1, "top": top, "bottom": bottom}


def _detect_2col_midline(words: list[dict], page_width: float) -> float | None:
    """Find the x-coordinate of the column gutter in a 2-column page.

    Strategy: build a histogram of x-centers across the page. A 2-column
    page has two peaks (left column center ~ 25% of width, right column
    center ~ 75%) separated by a low-density gutter at ~50%. For a
    contiguous run of low-density buckets in the central region, return
    the midpoint of the RUN (not the first bucket — for a clean
    page-width gutter every bucket inside might be zero).

    Returns None when:
      - no central run satisfies the low-density threshold, OR
      - low-density buckets are scattered (single-column page with mid-
        bucket holes from sparse / regular word placement), i.e. no
        CONTIGUOUS run of ≥2 buckets all under threshold.
    """
    if not words or page_width <= 0:
        return None
    # Histogram in 5% buckets across page width.
    n_buckets = 20
    bucket_width = page_width / n_buckets
    counts = [0] * n_buckets
    for w in words:
        center = (w["x0"] + w["x1"]) / 2
        b = min(int(center / bucket_width), n_buckets - 1)
        if b < 0:
            b = 0
        counts[b] += 1
    # Central buckets (30%-70% of page width).
    central = list(range(6, 14))
    # Peaks must come from outside the central region.
    surrounding = [c for i, c in enumerate(counts) if i < 6 or i >= 14]
    if not surrounding:
        return None
    surrounding_max = max(surrounding) if surrounding else 1
    if surrounding_max == 0:
        return None
    threshold = surrounding_max * 0.2

    # Find the LONGEST contiguous run of central buckets under the threshold.
    best_run: tuple[int, int] | None = None
    run_start: int | None = None
    for b in central + [None]:  # sentinel
        if b is not None and counts[b] < threshold:
            if run_start is None:
                run_start = b
        else:
            if run_start is not None:
                run_end = (b - 1) if b is not None else central[-1]
                length = run_end - run_start + 1
                if best_run is None or length > (best_run[1] - best_run[0] + 1):
                    best_run = (run_start, run_end)
                run_start = None
    # Contiguous-run gate (2026-05-25): require best_run to span ≥2 buckets.
    # A length-1 run inside an otherwise populated central region is an
    # alternating-zeros artifact of periodic word x-positioning (justified
    # text, monospaced layouts, synthetic test fixtures) — not a real gutter.
    # Real 2-column pages always produce a sustained low-density valley
    # (≥2 contiguous buckets under threshold) because both column peaks are
    # wide enough to push down a stretch of central density, not just one
    # bucket. Confirmed against jama_open_1 page 1, whose central counts
    # [8, 12, 4, 9, 4, 2, 2, 2] yield a 3-contiguous-bucket run at the
    # right edge that this gate accepts.
    if best_run is not None and (best_run[1] - best_run[0] + 1) >= 2:
        return (best_run[0] + best_run[1] + 1) / 2 * bucket_width

    # Relaxed fallback: when no contiguous ≥2-bucket run exists, check for
    # a SINGLE deep gutter (count < surrounding_max * 0.10 — half the loose
    # threshold). Real PDFs with narrow sidebars can produce histograms
    # where the gutter is one bucket wide because words from the narrower
    # sidebar fill adjacent buckets at lower density than the main-column
    # peaks.
    #
    # Two gates distinguish a real narrow-sidebar gutter from a periodic-
    # grid false positive (synthetic uniform-spacing fixture, sparse figure-
    # only pages):
    #   (1) Surrounding-density gate — most of the surrounding buckets must
    #       exceed the loose threshold (≥50%). A real text page has dense
    #       prose populating most x-positions; a sparse grid does not.
    #   (2) Neighbor-peak gate — the candidate bucket's immediate neighbors
    #       must both be populated above the loose threshold, confirming
    #       the trough is sandwiched by real peaks rather than by other
    #       scattered zeros.
    surrounding_populated = sum(1 for c in surrounding if c >= threshold)
    if surrounding_populated < len(surrounding) * 0.5:
        return None

    deep_threshold = surrounding_max * 0.10
    best_single = None
    for b in central:
        if counts[b] >= deep_threshold:
            continue
        left = counts[b - 1] if b - 1 >= 0 else 0
        right = counts[b + 1] if b + 1 < n_buckets else 0
        if left < threshold or right < threshold:
            continue
        if best_single is None or counts[b] < counts[best_single]:
            best_single = b
    if best_single is None:
        return None
    return (best_single + 0.5) * bucket_width


# Minimum width (PDF points) of a clean central gutter strip for it to count
# as a two-column separator. ~3pt rejects incidental single-x-column holes;
# real two-column gutters run 4pt (tight Elsevier/JESP) to 20pt+.
_MIN_GUTTER_STRIP_WIDTH = 3.0

# Fraction of the page's vertical text-span that the gutter strip must be empty
# across. 1.0 would require a perfectly clean strip; 0.97 tolerates a stray
# descender / italic kern poking into the gutter on one or two rows while still
# rejecting any genuine full-width line (table row, banner, centered title)
# that truly crosses the center.
_GUTTER_CLEAR_FRACTION = 0.97


def _detect_2col_midline_gutter(words: list[dict], page_width: float,
                                page_height: float) -> float | None:
    """Find the column midline via a clean full-height central gutter strip.

    A *stronger* two-column discriminator than the word-center histogram for
    NARROW gutters: scan candidate vertical strips in the central band
    (35%–65% of page width) and return the center of the widest strip that
    (almost) no word's horizontal extent crosses across the page's text height.

    Why this beats the histogram + bilateral gate for the O5 case: chen page 19
    has a CRediT contributor table stacked ABOVE a two-column reference list.
    The histogram can't resolve the ~4pt reference-column gutter, and the
    whole-page bilateral gate sees the table rows as "both columns at the same
    y" and rejects the page. But a *full-height empty strip* can only survive
    when NO line (table row, banner, full-width heading) spans the center —
    so a surviving strip is unambiguous evidence the page is genuinely
    two-column in its text region, and the gutter's x is the true midline.

    Args:
        words: pdfplumber word dicts for the page (need x0/x1/top/bottom).
        page_width: page width in points.
        page_height: page height in points (unused directly; the text-span is
            derived from the words so margins/headers don't dilute the gate).

    Returns:
        The gutter-center x, or None when no central strip of at least
        ``_MIN_GUTTER_STRIP_WIDTH`` points stays clear across
        ``_GUTTER_CLEAR_FRACTION`` of the text rows.
    """
    if not words or page_width <= 0:
        return None
    lo = page_width * 0.35
    hi = page_width * 0.65
    if hi - lo < _MIN_GUTTER_STRIP_WIDTH:
        return None

    # Bucket the text vertically into rows; a strip must be clear across (most
    # of) the rows that actually carry text — not the whole page height, so a
    # tall page with a short text block isn't judged on empty margin.
    row_keys = set()
    for w in words:
        row_keys.add(int(round(w["top"] / _LINE_Y_TOLERANCE)))
    n_rows = len(row_keys)
    if n_rows < _MIN_WORDS_FOR_COLUMN_MODE // 4:
        # Too few text rows to trust a gutter (figure page, sparse title page).
        return None

    # For each integer x in the central band, count how many distinct text rows
    # have a word spanning that x. A column gutter has near-zero crossing rows.
    from collections import defaultdict
    crossings: dict[int, set] = defaultdict(set)
    lo_i, hi_i = int(lo), int(hi)
    for w in words:
        x0 = max(lo_i, int(w["x0"]))
        x1 = min(hi_i, int(w["x1"]))
        if x1 < x0:
            continue
        rk = int(round(w["top"] / _LINE_Y_TOLERANCE))
        for x in range(x0, x1 + 1):
            crossings[x].add(rk)

    max_cross = n_rows * (1.0 - _GUTTER_CLEAR_FRACTION)
    clear = [x for x in range(lo_i, hi_i + 1) if len(crossings.get(x, ())) <= max_cross]
    if not clear:
        return None
    # Longest contiguous clear run.
    best_lo = best_hi = clear[0]
    run_lo = prev = clear[0]
    for x in clear[1:]:
        if x == prev + 1:
            prev = x
        else:
            if prev - run_lo > best_hi - best_lo:
                best_lo, best_hi = run_lo, prev
            run_lo = prev = x
    if prev - run_lo > best_hi - best_lo:
        best_lo, best_hi = run_lo, prev
    if (best_hi - best_lo) < _MIN_GUTTER_STRIP_WIDTH:
        return None
    center = (best_lo + best_hi) / 2.0
    # Center-constraint (spec refinement #1, 2026-06-07): a real central
    # column gutter sits near the page midline. Requiring the strip center
    # within [0.40W, 0.60W] rejects the bogus off-center "gutters" that sparse
    # table bands produce (a coincidental empty interval at e.g. 0.67W). This is
    # one of the three independent guards (the others: only inversion-flagged
    # pages reach here, and the word-preservation guard rejects any garbling
    # crop) that make the confined gutter use safe where the unconditional
    # whole-page shortcut was a dead end — see the diagnosis spec.
    if not (0.40 * page_width <= center <= 0.60 * page_width):
        return None
    return center


def _words_to_column_text(words: list[dict]) -> str:
    """Render a column's words as text — top-to-bottom, words within a row
    joined by space, distinct rows separated by newline."""
    if not words:
        return ""
    # Group by row (y-cluster).
    rows: dict[int, list[dict]] = defaultdict(list)
    for w in words:
        top_bucket = int(round(w["top"] / _LINE_Y_TOLERANCE) * _LINE_Y_TOLERANCE)
        rows[top_bucket].append(w)
    out_lines: list[str] = []
    for top_key in sorted(rows.keys()):
        row_words = sorted(rows[top_key], key=lambda w: w["x0"])
        line = " ".join(w["text"] for w in row_words)
        if line.strip():
            out_lines.append(line)
    return "\n".join(out_lines)


# ── RC-1 Step 2: per-band region-aware re-extraction (v2.4.90) ──────────────
#
# The whole-page corrector (extract_page_text_columns) corrects a page only when
# a SINGLE column geometry holds across the WHOLE page: the bilateral y-row gate
# and the full-height gutter strip both REJECT a page that carries an embedded
# full-width band (a table row, a banner, a wide title) crossing the column
# centre — so 2-column prose ABOVE/BELOW such a band stays interleaved (the
# dominant RC-1 defect on two-column APA papers — TRIAGE 2026-06-15).
#
# Step 2 segments a flagged page into horizontal y-BANDS and corrects each band
# in isolation: a band whose central gutter strip is clean (2-column prose) is
# re-extracted left-then-right; a band with full-width content (table/banner) is
# kept as-is (full-width crop). Bands are reassembled top-to-bottom. The same
# unconditional word-preservation guard in splice_column_corrected_pages then
# accepts the page ONLY if the result is a pure reorder (rules 0a/0b) — a band
# cut that clips a word is rejected and the page kept as-is, so this can only
# ADD correct reorders, never ship corruption.

# Half-width (pt) of the central gutter strip that must be glyph-free for a row
# to count as two-column. A justified full-width line's inter-word space (~3-4pt)
# is narrower than 2*_BAND_GUTTER_HALF, so a title / abstract line stays
# full-width; a real column gutter (10-30pt) clears it. This is what keeps a
# full-width title from being column-split into fragments.
_BAND_GUTTER_HALF = 4.0

# A band must hold at least this many text rows to be worth column-correcting.
_MIN_BAND_ROWS_FOR_2COL = 2


def _band_gutter_x(words: list[dict], page_width: float) -> float | None:
    """Central-band x crossed by the FEWEST text rows.

    Unlike `_detect_2col_midline_gutter` (which REQUIRES the strip clear across
    ~97% of the page height), this tolerates table/banner rows crossing the
    centre — those become the full-width bands — so it finds the column midline
    on the table-bearing pages the whole-page detector rejects. Returns None
    when there is no page / too few text rows to trust a gutter.
    """
    if not words or page_width <= 0:
        return None
    lo_i, hi_i = int(page_width * 0.35), int(page_width * 0.65)
    if hi_i - lo_i < _MIN_GUTTER_STRIP_WIDTH:
        return None
    all_rows = {int(round(w["top"] / _LINE_Y_TOLERANCE)) for w in words}
    if len(all_rows) < 10:
        return None
    crossings: dict[int, set] = defaultdict(set)
    for w in words:
        x0 = max(lo_i, int(w["x0"]))
        x1 = min(hi_i, int(w["x1"]))
        if x1 < x0:
            continue
        rk = int(round(w["top"] / _LINE_Y_TOLERANCE))
        for x in range(x0, x1 + 1):
            crossings[x].add(rk)
    center = page_width / 2.0
    best_x: int | None = None
    best_n: int | None = None
    for x in range(lo_i, hi_i + 1):
        n = len(crossings.get(x, ()))
        if (best_n is None or n < best_n
                or (n == best_n and abs(x - center) < abs(best_x - center))):
            best_x, best_n = x, n
    return float(best_x) if best_x is not None else None


def _row_is_2col(row_words: list[dict], gx: float) -> bool:
    """A text row is two-column iff the central strip [gx ± Δ] is glyph-free AND
    there is text on BOTH sides of gx. Distinguishes a real column gutter from a
    full-width justified line that merely has a word-space near the centre (a
    title, a spanning table row), which must NOT be column-split.

    Requiring both sides *per row* is deliberately conservative: it under-detects
    two-column rows whose left/right baselines bucket separately, but the pages
    that need this fallback are exactly the table-bearing / mixed ones the
    whole-page corrector already rejects, and on those the conservative test
    yielded materially fewer word-preservation-guard rejections than a
    gutter-clear-only test (corpus scan 2026-06-15: 6 vs 12 rejected of 71).
    Clean two-column pages are handled upstream by the whole-page gutter path.
    """
    if any(w["x0"] <= gx + _BAND_GUTTER_HALF and w["x1"] >= gx - _BAND_GUTTER_HALF
           for w in row_words):
        return False
    left = any((w["x0"] + w["x1"]) / 2 < gx for w in row_words)
    right = any((w["x0"] + w["x1"]) / 2 >= gx for w in row_words)
    return left and right


def _segment_bands(words: list[dict], gx: float) -> list[tuple[bool, float, float, list]]:
    """Group page rows into contiguous y-bands of one class. Returns a list of
    ``(is_full_width, y_top, y_bottom, band_words)`` in top-to-bottom order.

    A single isolated opposite-class row is absorbed (tol=1) so a stray
    gutter-crossing descender or a one-line subhead does not shatter a band.
    Adjacent bands whose y-extents OVERLAP (a tall title glyph reaching into the
    next row) are merged and forced full-width — there is no clean horizontal
    scanline to cut between them, so a column crop would bisect a glyph.
    """
    rows: dict[int, list[dict]] = defaultdict(list)
    for w in words:
        rows[int(round(w["top"] / _LINE_Y_TOLERANCE))].append(w)
    classified: list[tuple[float, float, bool, list]] = []
    for rk in sorted(rows):
        ws = rows[rk]
        y_top = min(w["top"] for w in ws)
        y_bot = max(w["bottom"] for w in ws)
        classified.append((y_top, y_bot, not _row_is_2col(ws, gx), ws))
    if not classified:
        return []
    # Contiguous same-class grouping with single-row tolerance.
    grouped: list[tuple[bool, list]] = []
    cur_fw = classified[0][2]
    run = [classified[0]]
    opp = 0
    for row in classified[1:]:
        if row[2] == cur_fw:
            run.append(row)
            opp = 0
        else:
            opp += 1
            run.append(row)
            if opp > 1:
                keep = run[:-opp]
                if keep:
                    grouped.append((cur_fw, keep))
                run = run[-opp:]
                cur_fw = row[2]
                opp = 0
    if run:
        grouped.append((cur_fw, run))
    bands: list[list] = []
    for fw, rws in grouped:
        y_top = min(r[0] for r in rws)
        y_bot = max(r[1] for r in rws)
        bwords = [w for r in rws for w in r[3]]
        bands.append([fw, y_top, y_bot, bwords])
    # Merge vertically-overlapping adjacent bands (no clean cut) -> full-width.
    merged: list[list] = [bands[0]]
    for b in bands[1:]:
        prev = merged[-1]
        if b[1] <= prev[2]:
            prev[0] = True
            prev[2] = max(prev[2], b[2])
            prev[3] = prev[3] + b[3]
        else:
            merged.append(b)
    return [tuple(b) for b in merged]


def _pdftotext_crop(tmp_path: str, page_index: int, left: float, top: float,
                    right: float, bottom: float, label: str = "banded") -> str | None:
    """One region's pdftotext crop. ``None`` means the crop DID NOT RUN.

    Shared by the banded and the edge-trimmed re-extraction; ``label`` prefixes
    the recorded fallback (``banded_crop_timeout``, ``edge_trimmed_crop_timeout``)
    so each path's failures stay separately countable.

    That third return value is the whole point, and it is the fix for a
    measured defect. This used to return ``""`` for three situations that
    mean different things: a genuinely blank region, a ``pdftotext`` that
    exited non-zero, and a ``subprocess.run`` that raised -- which under
    machine load is the ``timeout=30`` expiring. The caller joined the
    parts, so an expired band vanished and the page came back SHORT with
    every surviving word still in the right order. That is
    indistinguishable from a real word loss:
    ``test_banded_reextraction_is_word_preserving_real_pdf`` failed with
    ``{'and': 17} != {'and': 19}`` on 2026-09-17 during a run that took
    1:00:06 for work that takes 46 s on a quiet machine, and passed on
    both trees afterwards. Machine load became a correctness-shaped
    failure, which is the most expensive kind of flake: it accuses the
    code under test.

    In production the splice's word-multiset guard refused the short page,
    so no wrong text ever shipped -- but the correction was then dropped
    with NO signal of any kind, which is the silent-capability-loss shape
    every other fallback in this module exists to prevent. A failed crop
    is now recorded and abandons the page rather than being averaged into
    it. Gated by ``tests/test_banded_crop_failure_is_not_silent.py``.

    EDGES, not an origin and a size, and in CROP SPACE (`_crop_space_words`).
    pdftotext takes integers, and ``-x int(x) -W int(w)`` put a shared edge at
    ``int(x) + int(w)`` on one side and ``int(x)`` on the other — up to a point
    apart. An interior cut arrives here as an integer (`_column_cut_layout`
    makes it one), so both crops meeting at it receive the SAME x; an outer edge
    is widened to the next integer so no glyph at the page border is shaved.
    """
    import math
    import subprocess

    x0, y0 = max(0, math.floor(left)), max(0, math.floor(top))
    x1, y1 = math.ceil(right), math.ceil(bottom)
    if x1 - x0 <= 1 or y1 - y0 <= 1:
        return ""  # degenerate region, not a failure: nothing to read
    pa = str(page_index + 1)  # pdftotext is 1-indexed
    try:
        proc = subprocess.run(
            [resolve_pdftotext_executable(), "-enc", "UTF-8", "-f", pa, "-l", pa,
             "-x", str(x0), "-y", str(y0),
             "-W", str(x1 - x0), "-H", str(y1 - y0), tmp_path, "-"],
            capture_output=True, timeout=30, encoding="utf-8", errors="replace",
        )
    except subprocess.TimeoutExpired:
        record_fallback(f"{label}_crop_timeout", detail=f"p{pa}")
        return None
    except Exception as exc:
        record_fallback(f"{label}_crop_exception", detail=type(exc).__name__)
        return None
    if proc.returncode != 0:
        # pdftotext's own complaint, not just its exit code: the whole-page
        # column read recorded the stderr text before it came through this
        # helper (register H3f), and an exit code alone does not say why.
        record_fallback(
            f"{label}_crop_nonzero_exit",
            detail=(proc.stderr or "").strip()[:120] or f"rc={proc.returncode}",
        )
        return None
    return (proc.stdout or "").rstrip("\f").strip()


def extract_page_text_banded(layout_doc, page_index: int,
                             pdf_bytes: bytes) -> str:
    """RC-1 Step 2: re-extract a flagged page band-by-band (see module comment).

    Returns the reassembled page text, or "" when the page has no usable column
    gutter / too little text (caller keeps the original page). The result is
    ALWAYS subject to the splice's word-preservation guard, so a banded crop
    that is not a pure reorder is rejected upstream.
    """
    if pdf_bytes is None:
        return ""
    if page_index < 0 or page_index >= len(layout_doc.pages):
        return ""
    page = layout_doc.pages[page_index]
    page_width = float(page.width or 0.0)
    page_height = float(page.height or 0.0)
    if page_width <= 0 or page_height <= 0:
        return ""
    words = _crop_space_words(page)
    if len(words) < _MIN_WORDS_FOR_COLUMN_MODE:
        return ""
    gx = _band_gutter_x(words, page_width)
    if gx is None:
        return ""
    bands = _segment_bands(words, gx)
    if not bands:
        return ""

    # Cut lines: bands are non-overlapping after the merge, so the midpoint of
    # each inter-band gap is a glyph-free scanline. First band starts at the page
    # top, last band runs to the page bottom — every glyph lands in exactly one
    # crop, the precondition for word-preservation. Each interior cut is an
    # INTEGER so the two bands meeting at it receive the same pdftotext edge.
    cuts = [0.0]
    for i in range(len(bands) - 1):
        cuts.append(float(int((bands[i][2] + bands[i + 1][1]) / 2.0)))
    cuts.append(page_height)

    import tempfile

    def _crop(tmp_path: str, left: float, top: float, right: float,
              bottom: float) -> str | None:
        return _pdftotext_crop(tmp_path, page_index, left, top, right, bottom)

    tmp_path = ""
    try:
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(pdf_bytes)
            tmp_path = tmp.name
        parts: list[str] = []
        # A crop that did not run abandons the whole page (see `_crop`): a
        # page assembled from SOME of its bands is a word loss wearing a
        # reorder's clothes, and the splice can only refuse what it can see.
        for i, (fw, _yt, _yb, bwords) in enumerate(bands):
            top, bot = cuts[i], cuts[i + 1]
            did_2col = False
            if not fw and bwords:
                left = [w for w in bwords if (w["x0"] + w["x1"]) / 2 < gx]
                right = [w for w in bwords if (w["x0"] + w["x1"]) / 2 >= gx]
                # Both columns substantial AND no word straddles the gutter strip
                # (else the column crop would split that word).
                straddles = any(
                    w["x0"] <= gx + _BAND_GUTTER_HALF and w["x1"] >= gx - _BAND_GUTTER_HALF
                    for w in bwords
                )
                if (len(left) >= 0.25 * len(bwords)
                        and len(right) >= 0.25 * len(bwords)
                        and not straddles):
                    lt = _crop(tmp_path, 0, top, gx, bot)
                    rt = _crop(tmp_path, gx, top, page_width, bot)
                    if lt is None or rt is None:
                        return ""
                    if lt.strip() and rt.strip():
                        parts.append((lt + "\n" + rt).strip())
                        did_2col = True
            if not did_2col:
                whole = _crop(tmp_path, 0, top, page_width, bot)
                if whole is None:
                    return ""
                parts.append(whole)
    finally:
        # `unlink_temp_pdf` is a no-op on a falsy path, so the `if tmp_path`
        # guard this replaces lives in one place now rather than at each site.
        unlink_temp_pdf(tmp_path)
    return "\n".join(p for p in parts if p.strip())


# ── Edge-trimmed two-column re-extraction ──
#
# The whole-page corrector demands a gutter clear across ~97% of the page's
# text rows, and on a reference page that is defeated by nothing more than the
# page's own furniture: a centred running header, a centred ``References``
# title, a centred footer ("Collabra: Psychology 18"), or a full-width
# how-to-cite block under the last column. Measured 2026-09-23 on the 88
# rotation-flagged pages of a 500-paper random sample: 46 were refused, and on
# ~35 of them every gutter-crossing row sat ABOVE or BELOW the two-column body.
# Worse, where the 97% gate did pass, its tolerance let the cut land inside a
# crossing word ("psychology" -> "ps" + "ychology"), and the word-preservation
# guard — correctly — threw the whole page away.
#
# This path separates the two things the whole-page test conflates. The
# furniture rows are identified geometrically (the rows crossing the gutter),
# may only sit in a band at the top and a band at the bottom, and are read
# full-width; the gutter is then measured on the BODY rows alone, where it must
# be crossed by NO row at all. A row crossing the gutter in the middle of the
# body (a spanning table, a figure, a long URL) makes the page ineligible.
# Full-width text above or below a two-column body is READ in its right place
# (top band first, bottom band last), so this floor only has to say "the page
# is mainly two-column". collabra.251 p12 closes on a 25-row how-to-cite block
# and keeps 38 of 64 rows as body.
_EDGE_MIN_BODY_FRACTION = 0.5
_EDGE_MIN_BODY_ROWS = 15
_EDGE_MAX_TWO_SIDED_FURNITURE = 1

# How far (as a fraction of page width) either side of a detector's midline the
# glyph-free cut may be looked for. The word-centre histogram reports the centre
# of a 5%-of-width bucket run, so the gutter it found can sit most of a bucket
# away from the value it returns: rsos.180914 p1 returns 195.7 for a sidebar
# gutter clear from 197 to 210.
_CUT_SEARCH_FRACTION = 0.08
# A page reached through a detector midline has already passed that detector's
# own word-count and column-balance gates, so the body only has to be more than
# a handful of rows; the reference-page floor above is for pages found by the
# edge-trimmed path alone.
_CUT_MIN_BODY_ROWS = 5
# The smaller side of a cut must hold this share of the body's words (see the
# balance check in `_column_cut_layout` for the measurement that placed it).
_CUT_MIN_SIDE_FRACTION = 0.15
# A row joins an adjacent full-width band only when it sits at most this far
# from it (points): the leading inside one box, not the gap between blocks.
_BAND_JOIN_MAX_GAP = 3.0


def _crop_space_words(page) -> list[dict]:
    """The page's words in the coordinates ``pdftotext -x/-y`` measures in.

    pdfplumber reports geometry in the PDF's user space; pdftotext measures a
    crop from the MediaBox's top-left corner. They agree when the MediaBox
    starts at (0, 0) and are off by its origin otherwise — 9pt on the PDF held
    under 10.1177/0956797611420730, whose ``/MediaBox`` is ``[9 9 594 792]``
    (pdfplumber's top-down ``bbox``: ``(9, -9, 594, 774)``). Measured
    2026-09-25 on four papers against ``pdftotext -bbox``: after this shift
    every matched word's x0 and x1 agree to 0.001pt, so the cut can be placed
    on pdfplumber geometry exactly. Every column crop reads its words here."""
    ox, oy = getattr(page, "origin", None) or (0.0, 0.0)
    words = list(page.words or ())
    if not ox and not oy:
        return words
    return [{**w, "x0": w["x0"] - ox, "x1": w["x1"] - ox,
             "top": w["top"] - oy, "bottom": w["bottom"] - oy} for w in words]


def _column_cut_layout(words: list[dict], page_width: float,
                       hint_x: float | None = None,
                       ) -> tuple[int, int, int, tuple[int, int, int, int] | None] | None:
    """``(cut_x, cut_top, cut_bottom, margin)`` — where to cut a two-column page
    so that NO glyph lies on a cut — or None when there is no such place.

    THE ONE PLACE every column crop gets its geometry (the whole-page read via
    ``_crop_and_extract``, the edge-trimmed read). pdftotext keeps a glyph in a
    crop when the glyph's advance box touches the crop at all (measured
    2026-09-25: a comma spanning x 193.95-195.82 is in a crop ending at 194 and
    in one starting at 195, and in neither ending at 193 or starting at 196), so
    a cut through a glyph duplicates it. Here the vertical cut is an INTEGER x
    that no body word's box reaches (``int(x0) <= x <= int(x1)`` blocks x, so a
    glyph ending exactly on the cut is also kept off it); the rows that cross
    every such x are FURNITURE and are read full width, above or below the
    columns. ``cut_top`` is 0 when nothing sits above the body, ``cut_bottom``
    -1 when nothing sits below. A horizontal cut is safe between rows because
    pdftotext places a glyph in a band by its BASELINE point, not its box
    (measured the same day: a line whose baseline is at 198.65 is in a band
    starting at y=198 and not in one starting at 199).

    ``hint_x`` is a detector's midline. With it, the cut is looked for within
    ``_CUT_SEARCH_FRACTION`` of the page width either side and the gutter
    nearest the hint wins; without it (a reference page reaching the
    edge-trimmed read on its own), the widest gutter in the central band wins
    and must sit within 40-60% of the width.

    Geometry is measured on UPRIGHT text only. A rotated margin watermark
    (Collabra's vertical "Downloaded from http://online.ucpress.edu/..." at
    x~571-577) is one pdfplumber "word" per rotated run, each hundreds of
    points tall, so it would stretch the body's vertical extent over the
    footer and veto a clean cut. It is still extracted — the crops are
    positional — and still counted by the reorder guard. ``margin`` is the
    ``(x_from, x_to, y_from, y_to)`` box holding it clear of every upright
    glyph, or None.

    ``words`` must be in crop space (``_crop_space_words``)."""
    rotated = [w for w in words if not w.get("upright", True)]
    words = [w for w in words if w.get("upright", True)]
    if not words:
        return None
    if hint_x is None:
        lo_i, hi_i = int(page_width * 0.35), int(page_width * 0.65)
    else:
        reach = _CUT_SEARCH_FRACTION * page_width
        lo_i = int(max(page_width * 0.2, hint_x - reach))
        hi_i = int(min(page_width * 0.8, hint_x + reach))
    rows: dict[int, list[dict]] = defaultdict(list)
    for w in words:
        rows[int(round(w["top"] / _LINE_Y_TOLERANCE))].append(w)
    order = sorted(rows)
    min_rows = _EDGE_MIN_BODY_ROWS if hint_x is None else _CUT_MIN_BODY_ROWS
    if len(order) < min_rows:
        return None
    crossings: dict[int, set] = defaultdict(set)
    for rk, ws in rows.items():
        for w in ws:
            x0 = max(lo_i, int(w["x0"]))
            x1 = min(hi_i, int(w["x1"]))
            for x in range(x0, x1 + 1):
                crossings[x].add(rk)
    # Probe a STRIP as wide as the narrowest gutter we accept, not a single x:
    # a centred footer whose inter-word space happens to fall on the gutter
    # ("Collabra:" ends at 294, "Psychology" starts at 296 — collabra.90203
    # p18) crosses no single x there, and would otherwise be classed as body
    # and then veto every strip wide enough to be a gutter.
    strip = int(_MIN_GUTTER_STRIP_WIDTH)
    # (body_len, -distance to hint, start, end) in `order`: the longest body
    # wins, and among equals the strip nearest the detector's midline.
    best: tuple[int, float, int, int] | None = None
    for x in range(lo_i, hi_i - strip + 1):
        cr: set = set()
        for xx in range(x, x + strip + 1):
            cr |= crossings.get(xx, set())
        near = 0.0 if hint_x is None else -abs(x + strip / 2.0 - hint_x)
        # Longest run of consecutive rows none of which crosses x.
        run_s = 0
        for i in range(len(order) + 1):
            if i == len(order) or order[i] in cr:
                cand = (i - run_s, near, run_s, i)
                if best is None or cand[:2] > best[:2]:
                    best = cand
                run_s = i + 1
    if best is None:
        return None
    _, _, s_i, e_i = best

    # A body row sharing a baseline with a furniture row belongs to the
    # furniture: the page number "18" right of a centred "Collabra: Psychology"
    # buckets one row apart from it (collabra.90203 p18) and would otherwise
    # leave no glyph-free scanline between body and footer.
    def _span(i: int) -> tuple[float, float]:
        ws = rows[order[i]]
        return min(w["top"] for w in ws), max(w["bottom"] for w in ws)

    while s_i < e_i and s_i > 0 and _span(s_i)[0] <= max(
            _span(i)[1] for i in range(s_i)):
        s_i += 1
    while e_i > s_i and e_i < len(order) and _span(e_i - 1)[1] >= min(
            _span(i)[0] for i in range(e_i, len(order))):
        e_i -= 1

    # A row that sits against a furniture band and apart from the columns is
    # part of that band, not the last line of a column: collabra.95 p17 closes
    # on a boxed "Editor Decision Letter" whose heading fits inside the left
    # column but whose text line crosses the gutter. The heading is 1.5pt above
    # its text and 40pt below the references, and read as column text it came
    # out after the whole right column, parted from the line it heads. A row
    # joins the band only when its gap to the band is less than half its gap
    # to the column text AND it sits tight against the band (at most
    # `_BAND_JOIN_MAX_GAP`, a line's own leading); ordinary leading keeps a
    # column's last line in the column. The tightness bound stops a cascade:
    # without it collabra.138638 p11, a letter set in short blocks with wide
    # gaps between them, was absorbed block by block until no body was left.
    def _gap(upper: int, lower: int) -> float:
        return _span(lower)[0] - _span(upper)[1]

    def _joins(g_band: float, g_body: float) -> bool:
        g_band = max(g_band, 0.0)
        return g_band <= _BAND_JOIN_MAX_GAP and 2 * g_band < g_body

    while (s_i > 0 and e_i - s_i > 2
           and _joins(_gap(s_i - 1, s_i), _gap(s_i, s_i + 1))):
        s_i += 1
    while (e_i < len(order) and e_i - s_i > 2
           and _joins(_gap(e_i - 1, e_i), _gap(e_i - 2, e_i - 1))):
        e_i -= 1
    body_len = e_i - s_i
    if body_len < min_rows or body_len < _EDGE_MIN_BODY_FRACTION * len(order):
        return None
    body_keys = set(order[s_i:e_i])
    # The gutter measured on the body alone: every x no body row crosses.
    clear = [x for x in range(lo_i, hi_i + 1)
             if not (crossings.get(x, set()) & body_keys)]
    if not clear:
        return None
    runs: list[tuple[int, int]] = []
    r_lo = prev = clear[0]
    for x in clear[1:]:
        if x != prev + 1:
            runs.append((r_lo, prev))
            r_lo = x
        prev = x
    runs.append((r_lo, prev))
    runs = [r for r in runs if r[1] - r[0] >= _MIN_GUTTER_STRIP_WIDTH]
    if not runs:
        return None
    if hint_x is None:
        g_lo, g_hi = max(runs, key=lambda r: r[1] - r[0])
    else:
        g_lo, g_hi = min(runs, key=lambda r: max(r[0] - hint_x, hint_x - r[1], 0.0))
    # An INTEGER inside the run: both crops meeting here get this same x.
    mid = (g_lo + g_hi) // 2
    if hint_x is None and not (0.40 * page_width <= mid <= 0.60 * page_width):
        return None
    # A furniture band is read FULL WIDTH, so it must not hold column text.
    # A header or footer line may have text on both sides of the gutter
    # ("J. Chen et al." ... "Journal of Experimental Social Psychology"), but
    # two such rows in one band mean two-column lines sit on the far side of a
    # full-width row — an internal banner or spanning table, not furniture —
    # and a full-width read of them would ship right-column text beside
    # left-column text with every character intact (raised by the Luna
    # cross-model review, 2026-09-23). FAIL-CLOSED: it can only turn a reorder
    # into a no-op, never rewrite text.
    def _two_sided(rk: int) -> bool:
        ws = rows[rk]
        return (any(w["x1"] <= g_lo for w in ws)
                and any(w["x0"] >= g_hi for w in ws)
                and not any(w["x0"] < g_hi and w["x1"] > g_lo for w in ws))

    if (sum(1 for rk in order[:s_i] if _two_sided(rk)) > _EDGE_MAX_TWO_SIDED_FURNITURE
            or sum(1 for rk in order[e_i:] if _two_sided(rk)) > _EDGE_MAX_TWO_SIDED_FURNITURE):
        return None
    body_words = [w for rk in order[s_i:e_i] for w in rows[rk]]
    left = sum(1 for w in body_words if (w["x0"] + w["x1"]) / 2 < mid)
    # Column balance is the DETECTOR's call when there is one: it has already
    # weighed the whole page, and re-judging the body alone by its 25% bar
    # would second-guess it on a sidebar page — rsos.180914 p1's left sidebar
    # holds 25% of the page's words but less of the body once its "Downloaded
    # from" footer rows are set aside as furniture.
    if hint_x is None and (
            left < _MIN_COLUMN_FRACTION * len(body_words)
            or len(body_words) - left < _MIN_COLUMN_FRACTION * len(body_words)):
        return None
    # ...but a cut with next to nothing on one side is not a column gutter at
    # all, however the detector voted. A detector midline can land beside a
    # one-column page's single ragged line ("Personality and Social
    # Psychology | Bulletin, 44(7)" on an eScholarship cover sheet,
    # 10.1177/0146167218760798 p1) or in the gap between an author photo and
    # its biography (10.1109/access.2024.3421281 p17, which then spliced the
    # biography into the reference list). Counted over EVERY word in the body
    # rows, rotated ones included, so a column that is a rotated table
    # (10.1038/s41467-024-45528-0 p6) still counts as a column. Measured
    # 2026-09-25 over the 150 pages this corrector rewrites in the 601-paper
    # sample: the smaller side held 0.7% and 7.7% of the body's words on the
    # two pages that are not two-column, and at least 21.5% on every other.
    if hint_x is not None:
        top_y = min(w["top"] for w in body_words)
        bot_y = max(w["bottom"] for w in body_words)
        ux0 = min(w["x0"] for w in words)
        ux1 = max(w["x1"] for w in words)
        region = body_words + [
            w for w in rotated
            if top_y <= (w["top"] + w["bottom"]) / 2 <= bot_y
            and w["x1"] >= ux0 and w["x0"] <= ux1]
        n_left = sum(1 for w in region if (w["x0"] + w["x1"]) / 2 < mid)
        if min(n_left, len(region) - n_left) < _CUT_MIN_SIDE_FRACTION * len(region):
            return None
    body_top = min(w["top"] for w in body_words)
    body_bottom = max(w["bottom"] for w in body_words)
    # The cuts must fall in glyph-free space: halfway to the nearest furniture
    # row on each side, or the page edge when there is none.
    above = [w["bottom"] for rk in order[:s_i] for w in rows[rk]]
    below = [w["top"] for rk in order[e_i:] for w in rows[rk]]
    if (above and max(above) >= body_top) or (below and min(below) <= body_bottom):
        return None  # furniture overlaps the body vertically: no clean cut
    cut_top = int((max(above) + body_top) / 2.0) if above else 0
    cut_bot = int((body_bottom + min(below)) / 2.0) if below else -1
    # Rotated margin text runs the full page height, so a horizontal cut
    # splits it — "by guest on 12 March 2024" came back "Ma" + "arch"
    # (collabra.255 p14, collabra.84916 p12) and the word guard refused the
    # page. When it sits wholly in a margin no upright glyph reaches, it gets a
    # crop of its own and the other crops stop short of it. That crop spans
    # only the rows the rotated text occupies, not the page height: on
    # collabra.95 p17 a glyph pdfplumber does not report at all — pdftotext's
    # "	", 720pt of advance from x=68 at y~767, far below the watermark —
    # reached into a full-height margin crop as well as the bottom band and
    # came out twice.
    margin: tuple[int, int, int, int] | None = None
    if rotated:
        ux0 = min(w["x0"] for w in words)
        ux1 = max(w["x1"] for w in words)
        rx0 = min(w["x0"] for w in rotated)
        rx1 = max(w["x1"] for w in rotated)
        ry0 = max(0, math.floor(min(w["top"] for w in rotated)) - 1)
        ry1 = math.ceil(max(w["bottom"] for w in rotated)) + 1
        if rx0 > ux1:
            margin = (int((ux1 + rx0) / 2.0), math.ceil(page_width), ry0, ry1)
        elif rx1 < ux0:
            margin = (0, int((rx1 + ux0) / 2.0), ry0, ry1)
    return mid, cut_top, cut_bot, margin


def _read_column_regions(pdf_bytes: bytes, page_index: int, shape,
                         page_width: float, page_height: float, label: str
                         ) -> tuple[str, str, str, str, str] | None:
    """Crop a page along a ``_column_cut_layout`` shape: ``(top band, left
    body, right body, bottom band, margin)``, each already stripped. None when
    any crop did not run — a page assembled from SOME of its regions is a word
    loss wearing a reorder's clothes."""
    import tempfile

    mid, cut_top, cut_bot, margin = shape
    bottom = page_height if cut_bot < 0 else cut_bot
    x_lo, x_hi = 0.0, page_width
    if margin is not None:
        if margin[0] > mid:
            x_hi = margin[0]
        else:
            x_lo = margin[1]
    regions = [
        (x_lo, 0.0, x_hi, cut_top),               # top band
        (x_lo, cut_top, mid, bottom),             # left body
        (mid, cut_top, x_hi, bottom),             # right body
        (x_lo, bottom, x_hi, page_height),        # bottom band
    ]
    if margin is not None:                        # margin text
        regions.append((margin[0], margin[2], margin[1], margin[3]))
    tmp_path = ""
    try:
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(pdf_bytes)
            tmp_path = tmp.name
        parts: list[str] = []
        for region in regions:
            got = _pdftotext_crop(tmp_path, page_index, *region, label=label)
            if got is None:
                return None
            parts.append(got)
    finally:
        unlink_temp_pdf(tmp_path)
    if margin is None:
        parts.append("")
    return tuple(parts)  # type: ignore[return-value]


def extract_page_text_edge_trimmed(layout_doc, page_index: int,
                                   pdf_bytes: bytes | None) -> str:
    """Top furniture band, left body column, right body column, bottom
    furniture band — or "" when the page does not have that shape. Always
    subject to the splice's reorder guard."""
    if pdf_bytes is None:
        return ""
    if page_index < 0 or page_index >= len(layout_doc.pages):
        return ""
    page = layout_doc.pages[page_index]
    page_width = float(page.width or 0.0)
    page_height = float(page.height or 0.0)
    if page_width <= 0 or page_height <= 0:
        return ""
    words = _crop_space_words(page)
    if len(words) < _MIN_WORDS_FOR_COLUMN_MODE:
        return ""
    shape = _column_cut_layout(words, page_width)
    if shape is None:
        return ""
    parts = _read_column_regions(pdf_bytes, page_index, shape, page_width,
                                 page_height, label="edge_trimmed")
    if parts is None:
        return ""
    top, left, right, bottom, margin = parts
    if not left or not right:
        return ""
    return "\n\n".join(p for p in (top, left, right, bottom, margin) if p)
