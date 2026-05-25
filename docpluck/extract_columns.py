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


def extract_page_text_columns(layout_doc, page_index: int, column_count: int = 2) -> str:
    """Re-extract a single page's text via column-aware ordering.

    Args:
        layout_doc: LayoutDoc from docpluck.extract_layout.extract_pdf_layout.
        page_index: 0-based page index.
        column_count: Number of columns to detect (currently only 2 supported;
            3-column layouts are rare in academic publishing and need a
            different geometric signal).

    Returns:
        The page text in left-then-right column order. Empty string if the
        column-detection signal is too weak (caller falls back to the
        original page text).
    """
    if column_count != 2:
        return ""  # only 2-column supported in v2.4.75
    if page_index < 0 or page_index >= len(layout_doc.pages):
        return ""
    page = layout_doc.pages[page_index]
    chars = page.chars or ()
    if not chars:
        return ""

    page_width = float(page.width or 0.0)
    if page_width <= 0:
        return ""

    # Step 1: cluster chars into lines by `top` coordinate (round to int for bucketing).
    rows: dict[int, list[dict]] = defaultdict(list)
    for c in chars:
        top_bucket = int(round(c.get("top", 0) / _LINE_Y_TOLERANCE) * _LINE_Y_TOLERANCE)
        rows[top_bucket].append(c)

    # Step 2: for each row, compute its word groups by x. Within a row, chars
    # with x-gap > median-char-width are in different words.
    words_per_line: list[list[dict]] = []
    for top_key in sorted(rows.keys()):
        row_chars = sorted(rows[top_key], key=lambda c: c.get("x0", 0))
        if not row_chars:
            continue
        # Compute median char width for this row.
        widths = [c["x1"] - c["x0"] for c in row_chars if c.get("x1", 0) > c.get("x0", 0)]
        median_w = sorted(widths)[len(widths) // 2] if widths else 5.0
        word_gap = max(median_w * 0.5, 1.0)
        # Group adjacent chars into words.
        words: list[dict] = []
        current: list[dict] = [row_chars[0]]
        for c in row_chars[1:]:
            if c["x0"] - current[-1]["x1"] > word_gap:
                # New word.
                if current:
                    words.append(_chars_to_word(current))
                current = [c]
            else:
                current.append(c)
        if current:
            words.append(_chars_to_word(current))
        for w in words:
            words_per_line.append([w])

    # Step 3: collect all words on the page.
    all_words: list[dict] = []
    for line_words in words_per_line:
        all_words.extend(line_words)
    if len(all_words) < _MIN_WORDS_FOR_COLUMN_MODE:
        return ""

    # Step 4: detect column boundary via x-center histogram. For a 2-column
    # page, the histogram has a clear gap in the middle ~10-30% of page width.
    midline_x = _detect_2col_midline(all_words, page_width)
    if midline_x is None:
        return ""

    # Step 5: partition words into left / right columns.
    left_words = [w for w in all_words if (w["x0"] + w["x1"]) / 2 < midline_x]
    right_words = [w for w in all_words if (w["x0"] + w["x1"]) / 2 >= midline_x]
    if (len(left_words) < len(all_words) * _MIN_COLUMN_FRACTION
        or len(right_words) < len(all_words) * _MIN_COLUMN_FRACTION):
        return ""  # not really a 2-column page

    # Step 6: render each column as text (top-to-bottom, joining adjacent-y
    # words with space, separating distinct lines with newline).
    left_text = _words_to_column_text(left_words)
    right_text = _words_to_column_text(right_words)

    if not left_text.strip() or not right_text.strip():
        return ""

    return left_text + "\n\n" + right_text


def splice_column_corrected_pages(
    raw_text: str,
    layout_doc,
    page_offsets: Iterable[int],
    pages_to_fix: Iterable[int],
) -> str:
    """Splice column-aware re-extracted text into flagged pages of raw_text.

    Args:
        raw_text: Original pdftotext output (form-feed separated pages).
        layout_doc: LayoutDoc.
        page_offsets: Char offsets where each page starts in raw_text.
        pages_to_fix: 1-indexed list of page numbers to rewrite (matching
            NormalizationReport.column_interleave_pages).

    Returns:
        Rewritten raw_text with flagged pages' content replaced. Pages that
        the rewriter couldn't confidently column-detect are left untouched.
    """
    offsets = list(page_offsets)
    pages_set = set(pages_to_fix)
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
            rewritten = extract_page_text_columns(layout_doc, page_idx, column_count=2)
            if rewritten:
                out_parts.append(rewritten)
                cursor = end
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
    if best_run is None:
        return None
    # Require a run of ≥2 contiguous low-density buckets — a single low
    # bucket can be a regular-spacing artifact of a single-column page.
    if best_run[1] - best_run[0] + 1 < 2:
        return None
    # Midline = midpoint of the run.
    midline = (best_run[0] + best_run[1] + 1) / 2 * bucket_width
    return midline


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
