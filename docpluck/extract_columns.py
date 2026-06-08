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

from collections import defaultdict
from typing import Iterable


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
        text = _crop_and_extract(pdf_bytes, page_index, midline_x, page_width, page_height)
        if text:
            return text

    # Fallback: word-join approach (no inter-word spacing fix).
    left_words = [w for w in all_words if (w["x0"] + w["x1"]) / 2 < midline_x]
    right_words = [w for w in all_words if (w["x0"] + w["x1"]) / 2 >= midline_x]
    left_text = _words_to_column_text(left_words)
    right_text = _words_to_column_text(right_words)
    if not left_text.strip() or not right_text.strip():
        return ""
    return left_text + "\n\n" + right_text


def _crop_and_extract(pdf_bytes: bytes, page_index: int, midline_x: float,
                       page_width: float, page_height: float) -> str:
    """Crop each column and run pdftotext to preserve proper word spacing.

    pdfplumber's `extract_text()` on tight-kerned PDFs (JAMA Open et al.)
    drops inter-word spaces because the PDF positions characters without
    explicit space chars. pdftotext does its own gap analysis to insert
    spaces correctly. pdftotext supports cropping via `-x -y -W -H` flags:
    we run it twice per flagged page (once per column) and concatenate.

    Returns empty string on any failure — caller falls back to the
    pdfplumber word-join path (which at least preserves column separation
    even when spacing is lost).
    """
    try:
        import os
        import subprocess
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(pdf_bytes)
            tmp_path = tmp.name
        try:
            page_arg = str(page_index + 1)  # pdftotext is 1-indexed
            # Left column: x=0, width=midline_x.
            left_proc = subprocess.run(
                [
                    "pdftotext", "-enc", "UTF-8",
                    "-f", page_arg, "-l", page_arg,
                    "-x", "0", "-y", "0",
                    "-W", str(int(midline_x)),
                    "-H", str(int(page_height)),
                    tmp_path, "-",
                ],
                capture_output=True, timeout=30,
                encoding="utf-8", errors="replace",
            )
            if left_proc.returncode != 0:
                return ""
            right_proc = subprocess.run(
                [
                    "pdftotext", "-enc", "UTF-8",
                    "-f", page_arg, "-l", page_arg,
                    "-x", str(int(midline_x)), "-y", "0",
                    "-W", str(int(page_width - midline_x)),
                    "-H", str(int(page_height)),
                    tmp_path, "-",
                ],
                capture_output=True, timeout=30,
                encoding="utf-8", errors="replace",
            )
            if right_proc.returncode != 0:
                return ""
            left_text = (left_proc.stdout or "").rstrip("\f").strip()
            right_text = (right_proc.stdout or "").rstrip("\f").strip()
            if not left_text or not right_text:
                return ""
            return left_text + "\n\n" + right_text
        finally:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass
    except Exception:
        return ""


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
    from collections import Counter
    import re
    toks = re.findall(r"[^\W\d_]{2,}", text.casefold(), flags=re.UNICODE)
    return Counter(toks)


def splice_column_corrected_pages(
    raw_text: str,
    layout_doc,
    page_offsets: Iterable[int],
    pages_to_fix: Iterable[int],
    pdf_bytes: bytes | None = None,
    gutter_fallback_pages: Iterable[int] | None = None,
    changed_out: list | None = None,
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

    Returns:
        Rewritten raw_text with flagged pages' content replaced. Pages whose
        re-extraction the rewriter couldn't confidently column-detect, or whose
        re-extraction would change the word multiset, are left untouched.
    """
    offsets = list(page_offsets)
    pages_set = set(pages_to_fix)
    gf_pages = set(gutter_fallback_pages or ())
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
            if rewritten:
                original_page = raw_text[start:end]
                # Accept ONLY a pure reorder: identical substantial-word multiset
                # AND a materially different token order (else it's a no-op the
                # original already had right — don't churn whitespace). This guard
                # is unconditional now — it rejects column-crop word SPLITS
                # (jama_open_1 'adults'→'adu') that the old accept-any path shipped.
                same_words = _word_multiset(rewritten) == _word_multiset(original_page)
                reordered = rewritten.split() != original_page.split()
                if same_words and reordered:
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
