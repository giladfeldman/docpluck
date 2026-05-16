"""
docpluck.extract_structured — top-level structured PDF extraction.

Per [LESSONS L-006](../LESSONS.md#l-006), this module is pdfplumber-free.
Tables come from Camelot stream flavor; figures and captions are detected
purely from the pdftotext text channel via the regexes in
``docpluck.tables.captions``.

Pipeline:
    1. ``extract_pdf`` → linear pdftotext text + page count.
    2. ``find_caption_matches`` → "Table N" / "Figure N" caption lines on
       each page.
    3. ``extract_tables_camelot`` → cell-bearing tables from each page.
    4. Match each Camelot table to its same-page caption (label, caption text).
    5. Build :class:`Figure` dicts from caption matches that don't pair with
       any table.
    6. Optional placeholder mode replaces caption lines with
       ``[Label: caption]`` markers.
"""

from __future__ import annotations

import os
import re
from typing import Literal, Optional, TypedDict

from .extract import extract_pdf, count_pages
from .figures import Figure
from .tables import Cell, Table
from .tables.camelot_extract import extract_tables_camelot
from .tables.captions import (
    CaptionMatch,
    caption_anchor_is_in_text_reference,
    find_caption_matches,
)
from .tables.render import cells_to_html


TABLE_EXTRACTION_VERSION = "2.1.3"  # v2.1.3: cell-cleaning recovers '<'-as-backslash glyph corruption. v2.1.2: cell-cleaning recovers descending-CI '2'-for-minus corruption. v2.1.1: cell-cleaning recovers (cid:0) corrupted minus signs + strips math-alphanumeric styling. v2.1.0: cell-cleaning pipeline ported from splice spike (multi-row header detection, continuation merging, leader-dot strip, mash-split, group separators, sig-marker attach)

TableTextMode = Literal["raw", "placeholder"]


class StructuredResult(TypedDict):
    text: str
    method: str
    page_count: int
    tables: list[Table]
    figures: list[Figure]
    table_extraction_version: str


def extract_pdf_structured(
    pdf_bytes: bytes,
    *,
    thorough: bool = False,
    table_text_mode: TableTextMode = "raw",
) -> StructuredResult:
    """Extract text + structured tables + figures from a PDF.

    Args:
        pdf_bytes: Raw PDF bytes.
        thorough: Currently unused — Camelot scans every page by default.
            Retained for backwards-compatible call signature.
        table_text_mode: ``"raw"`` (default; text identical to ``extract_pdf``)
            or ``"placeholder"`` (caption lines for tables/figures are replaced
            with ``[Label: caption]`` markers).

    Returns:
        StructuredResult dict.
    """
    raw_text, base_method = extract_pdf(pdf_bytes)
    page_count = count_pages(pdf_bytes)

    if raw_text.startswith("ERROR:"):
        return {
            "text": raw_text,
            "method": base_method,
            "page_count": page_count,
            "tables": [],
            "figures": [],
            "table_extraction_version": TABLE_EXTRACTION_VERSION,
        }

    method_pieces = [base_method]
    if thorough:
        method_pieces.append("thorough")
    # Preprocess: pdftotext sometimes splits captions like "Table 1: X" into
    # "T\n\n1: X". Join these so the caption regex matches consistently.
    # We work on a SHADOW string for caption detection only — raw_text returned
    # to callers is unmodified.
    rejoined = _join_split_captions(raw_text)
    page_offsets = _page_offsets(rejoined)
    captions_all = find_caption_matches(rejoined, page_offsets)
    # Dedupe by (kind, number). A body-text reference like
    # "… we summarised the effects in Figure 10." can line-wrap so the
    # "Figure 10." token lands at a line start and false-matches the
    # caption regex — and it often sits EARLIER in the document than the
    # real caption. Keeping the first occurrence then renders body prose
    # as the caption (FIG-3b: chan_feldman Figure 10). So when a
    # (kind, number) has multiple anchors, prefer one that is NOT an
    # in-text reference. Falls back to first-in-document-order when every
    # anchor looks like a reference (no real caption captured) — i.e. no
    # regression vs. the old "keep first" behavior in that case.
    by_key: dict[tuple[str, int], list[CaptionMatch]] = {}
    for c in captions_all:
        by_key.setdefault((c.kind, c.number), []).append(c)
    captions: list[CaptionMatch] = []
    for group in by_key.values():
        if len(group) == 1:
            captions.append(group[0])
            continue
        real = [
            c for c in group
            if not caption_anchor_is_in_text_reference(rejoined, c)
        ]
        captions.append(real[0] if real else group[0])
    captions.sort(key=lambda c: c.char_start)
    # The captions' char_start/char_end refer to `rejoined`, not raw_text. For
    # placeholder mode we need positions in raw_text — build a translation map.
    # Since the rejoin only deletes whitespace runs, char positions in rejoined
    # are <= positions in raw_text. We translate by re-finding the caption line
    # in raw_text on demand.

    tables: list[Table] = []
    figures: list[Figure] = []

    # v2.3.0 Bug 4 fix: build a fast lookup from caption to the char_start
    # of the next caption (any kind) so _extract_caption_text can bound
    # the caption snippet at the next-caption boundary. Prevents the
    # gratitude-paper Figure 1 caption from concatenating Figure 2's
    # caption and the results-section F-stat prose.
    sorted_caps = sorted(captions, key=lambda c: c.char_start)
    next_boundary_by_id: dict[int, Optional[int]] = {}
    for i, c in enumerate(sorted_caps):
        nb = sorted_caps[i + 1].char_start if i + 1 < len(sorted_caps) else None
        next_boundary_by_id[id(c)] = nb

    # ---- Tables (Camelot) ----
    camelot_disabled = os.environ.get("DOCPLUCK_DISABLE_CAMELOT", "0") == "1"
    camelot_tables: list[Table] = []
    if not camelot_disabled:
        try:
            camelot_tables = extract_tables_camelot(pdf_bytes)
            if camelot_tables:
                method_pieces.append("camelot_stream")
        except Exception:
            method_pieces.append("camelot_failed")
            camelot_tables = []

    # Match Camelot tables to "Table N" caption lines on the same page.
    used_caption_ids: set[int] = set()
    table_captions = [c for c in captions if c.kind == "table"]

    # Filter Camelot's output to tables that have a same-page caption.
    # This anchors detection to caption signal (matching the pre-pdfplumber-removal
    # behavior of docpluck) and drops false-positive Camelot detections like
    # bibliographies or address blocks. Tables without captions are rare in APA
    # corpus and the existing tests are calibrated against caption-anchored counts.
    pages_with_table_caption = {c.page for c in table_captions}
    for ct in camelot_tables:
        if (ct.get("page") or 0) not in pages_with_table_caption:
            continue
        match = _find_caption_for_table(ct, table_captions, raw_text, used_caption_ids)
        if match is not None:
            used_caption_ids.add(id(match))
            ct["label"] = match.label
            ct["caption"] = _extract_caption_text(
                rejoined, match, next_boundary_by_id.get(id(match))
            )
            tables.append(ct)

    # If a table caption had no Camelot match, emit an "isolated" Table dict so
    # downstream consumers still see something at that page.
    for cap in table_captions:
        if id(cap) in used_caption_ids:
            continue
        tables.append(
            _isolated_table_from_caption(
                cap, rejoined, next_boundary_by_id.get(id(cap))
            )
        )

    # ---- Figures ----
    for cap in captions:
        if cap.kind != "figure":
            continue
        figures.append(
            _figure_from_caption(cap, rejoined, next_boundary_by_id.get(id(cap)))
        )

    # ---- Placeholder mode ----
    text_out = (
        _apply_placeholder(raw_text, captions)
        if table_text_mode == "placeholder"
        else raw_text
    )

    # Sort tables/figures by page for stable output.
    tables.sort(key=lambda t: (t.get("page") or 0, t.get("label") or ""))
    figures.sort(key=lambda f: (f.get("page") or 0, f.get("label") or ""))

    return {
        "text": text_out,
        "method": "+".join(method_pieces),
        "page_count": page_count,
        "tables": tables,
        "figures": figures,
        "table_extraction_version": TABLE_EXTRACTION_VERSION,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _page_offsets(raw_text: str) -> list[int]:
    """Char offset where each 1-indexed page starts in raw_text. raw_text uses
    ``\\f`` (form feed) as page separator (pdftotext default)."""
    offsets = [0]
    for i, ch in enumerate(raw_text):
        if ch == "\f":
            offsets.append(i + 1)
    return offsets


_SPLIT_CAPTION_RE = re.compile(
    r"^(T|Table|Fig\.?|Figure)\s*\n\s*\n\s*(\d+(?:\.\d+)?)([\s.:\-—–]+)",
    re.MULTILINE | re.IGNORECASE,
)
_T_PREFIX_RE = re.compile(
    r"^T\s+(\d+(?:\.\d+)?)([\s.:\-—–])",
    re.MULTILINE,
)
_FIG_PREFIX_RE = re.compile(
    r"^Fig\.?\s+(\d+(?:\.\d+)?)([\s.:\-—–])",
    re.MULTILINE | re.IGNORECASE,
)


def _join_split_captions(text: str) -> str:
    """Rejoin captions pdftotext split across paragraphs.

    Patterns:
      - "T\\n\\n1: foo" → "Table 1: foo"
      - "Fig.\\n\\n2: bar" → "Figure 2: bar"
      - bare "T 1:" prefix → "Table 1:" (after the rejoin above)
    """
    text = _SPLIT_CAPTION_RE.sub(r"\1 \2\3", text)
    text = _T_PREFIX_RE.sub(r"Table \1\2", text)
    text = _FIG_PREFIX_RE.sub(r"Figure \1\2", text)
    return text


def _find_caption_for_table(
    camelot_table: Table,
    captions: list[CaptionMatch],
    raw_text: str,
    used_caption_ids: set[int],
) -> Optional[CaptionMatch]:
    """Pick the best ``Table N:`` caption on the same page as the camelot table.

    Strategy: among unused captions on the same page, prefer the one whose
    caption-line tokens appear most densely in the table's raw_text. If no
    captions are on the same page, return None.
    """
    page = camelot_table.get("page") or 0
    same_page = [c for c in captions if c.page == page and id(c) not in used_caption_ids]
    if not same_page:
        return None
    if len(same_page) == 1:
        return same_page[0]
    # Score each caption by token overlap with the camelot table content
    table_text = (camelot_table.get("raw_text") or "").lower()
    table_tokens = set(re.findall(r"[a-z]{3,}|\d+(?:\.\d+)?", table_text))
    best: Optional[tuple[int, int, CaptionMatch]] = None
    for c in same_page:
        cap_tokens = set(re.findall(r"[a-z]{3,}|\d+(?:\.\d+)?", c.line_text.lower()))
        score = len(cap_tokens & table_tokens)
        candidate = (-score, c.char_start, c)
        if best is None or candidate < best:
            best = candidate
    if best is None:
        return None
    return best[2]


def _extract_caption_text(
    raw_text: str,
    cap: CaptionMatch,
    next_boundary: Optional[int] = None,
) -> str:
    """Pull the full caption (label + description) starting at the caption line.

    Captions are often line-wrapped by pdftotext, so a single ``\\n\\n``
    boundary can sit MID-SENTENCE. Walk past such breaks until we find one
    where the preceding text ends with a real sentence terminator
    (``.``/``!``/``?``) or we hit a hard cap.

    v2.3.0 Bug 4 fix (handoff 2026-05-11): caller may pass
    ``next_boundary`` — the char position of the next caption / next
    section heading — to cap extraction. Without it, a caption that
    didn't end in a sentence terminator would greedily extend into the
    next figure's caption or unrelated body prose (the gratitude-paper
    Figure 1 / Figure 2 / F-stat-prose concatenation bug). The
    effective hard cap is ``min(cap.char_end + 800, next_boundary,
    len(raw_text))``.
    """
    start = cap.char_start
    # Hard cap — never read more than 800 chars from caption start. The
    # 800 figure is the handoff's "guard against runaway captions" upper
    # bound; before v2.3.0 this was 600, but raising it to 800 with the
    # next_boundary cap is strictly safer since next_boundary now bounds
    # the typical case.
    hard_end = min(cap.char_end + 800, len(raw_text))
    if next_boundary is not None and next_boundary > cap.char_end:
        hard_end = min(hard_end, next_boundary)
    # v2.4.25: page-break (form feed) is a hard caption boundary — academic
    # figure/table captions never span pages, so anything past the next \f
    # is guaranteed to be either a running header, next-page body prose, or
    # a different figure. Cap hard_end at the next \f to prevent the
    # paragraph-walk below from absorbing post-pagebreak content.
    pagebreak = raw_text.find("\f", cap.char_end, hard_end)
    if pagebreak != -1:
        hard_end = pagebreak
    pos = cap.char_end
    # FIG-4 (v2.4.52): track whether the walk stopped at a real ``\n\n``
    # paragraph break (a complete caption paragraph) vs. ran to the 800-char
    # hard cap / next_boundary / pagebreak (a runaway that absorbed body
    # prose). The figure-caption overflow trim below only applies to the
    # runaway case — a caption that overflows 400 chars but ended at a clean
    # paragraph break is a LEGITIMATE long caption (a label + a long Note).
    stopped_at_break = False
    while pos < hard_end:
        nxt = raw_text.find("\n\n", pos)
        if nxt == -1 or nxt >= hard_end:
            break
        # Check the text just before this paragraph break.
        prev = raw_text[max(start, nxt - 40):nxt].rstrip()
        # If it ends with a sentence terminator OR is empty/very short, stop.
        if not prev or len(prev.split()) < 2:
            hard_end = nxt
            stopped_at_break = True
            break
        if re.search(r"[.!?][\"'\)\]]?$", prev):
            # Cycle 15n (v2.4.31): the paragraph-walk's sentence-terminator
            # bail is too aggressive when the *only* thing consumed so far
            # is the caption's own label (e.g. just "FIGURE 1." on its own
            # line, followed by "\n\n" and then the real description). The
            # caption regex anchors at MULTILINE ``^`` and `\s*` can absorb
            # the leading newline, so for IEEE/PMC-style captions where
            # the ALL-CAPS label sits alone on a line before a blank break
            # before the title-case description, char_start lands at the
            # blank line and char_end == char_start. The walk then bails
            # on prev="FIGURE 1." (a terminator), truncating the caption
            # to the duplicate-label placeholder ``Figure 1. FIGURE 1.``.
            # Fix: if the accumulated text from start..nxt is just a
            # label-only stretch (no real description), keep walking.
            if _accumulated_is_label_only(raw_text[start:nxt]):
                pos = nxt + 2
                continue
            hard_end = nxt
            stopped_at_break = True
            break
        # FIG-2 (v2.4.48): the caption ends without a ``.!?`` terminator but
        # is nonetheless COMPLETE — an APA period-less Title-Case figure
        # title, or a trailing significance legend (``*** p < .001``). The
        # ``\n\n`` legitimately ends it; without this the walk absorbs the
        # following body prose.
        if cap.kind == "figure" and _caption_is_complete_without_terminator(
            raw_text[start:nxt], cap.label
        ):
            hard_end = nxt
            stopped_at_break = True
            break
        # Otherwise the caption continues — skip past this break and keep going.
        pos = nxt + 2
    # Cycle 15f-1 (v2.4.32, G4b): for TABLE captions, the paragraph-walk
    # above has no sentence terminator to stop at when the table title
    # lacks a trailing period (common in AOM / management journals:
    # "Table 1. Most Cited Sources in Organizational Behavior Textbooks").
    # It walks straight through the linearized cell content until the
    # 400-char hard cap, so the caption field becomes 400 chars of cell
    # garbage. Trim the raw caption region at the start of the cell run
    # (>=3 consecutive header-like short lines) before flattening.
    if cap.kind == "table":
        region = raw_text[start:hard_end]
        trimmed = _trim_table_caption_at_cell_region(region)
        if len(trimmed) < len(region):
            hard_end = start + len(trimmed)
    snippet = raw_text[start:hard_end].replace("\n", " ").strip()
    # v2.3.0 soft-hyphen rejoin (per `docs/HANDOFF_2026-05-11_visual_review_findings.md`
    # "Soft-hyphen artifacts in captions" — chen.pdf showed `Sup­ plementary`).
    # Captions don't flow through ``normalize_text``, so apply the same
    # rejoin here. ``­`` followed by any whitespace = word-wrap artifact
    # → drop both. Orphan ``­`` is also invisible by Unicode and gets
    # dropped.
    snippet = re.sub("­\\s+", "", snippet)
    snippet = snippet.replace("­", "")
    # Collapse runs of any whitespace (including U+2002 EN SPACE, etc.) to a
    # single space; many APA PDFs use unusual spaces between label and caption.
    snippet = re.sub(r"\s+", " ", snippet)
    # Strip leading orphan punctuation that can occur when the rejoin produced
    # a partial caption (e.g., "Table 1. : Studies 1b and 3...").
    snippet = re.sub(r"^[\s.:\-—–]+", "", snippet)
    # Re-prefix the label if stripping ate it.
    if cap.label and not snippet.startswith(cap.label):
        snippet = f"{cap.label}. {snippet}".strip()
    # v2.4.25: strip a duplicate ALL-CAPS label that pdftotext often
    # captures alongside the title-case caption label (AOM / IEEE PMC
    # patterns: "Figure 1. FIGURE 1 Theoretical Framework …", "Figure 2.
    # FIGURE 2. Continuous-time …"). Keep title-case label, drop the
    # ALL-CAPS one.
    snippet = _strip_duplicate_uppercase_label(snippet, cap.label)
    # Cycle 15n (v2.4.31): when the paragraph-walk above absorbs a
    # cross-page running header that pdftotext placed BETWEEN the
    # caption's label line and the description (PMC reprint pattern:
    # ``FIGURE 4.\n\nAuthor Manuscript\n\nTwo options …``), the
    # running header survives into the snippet as a leading prefix
    # after the label. Strip a sequence of "Author Manuscript " (one
    # or more occurrences) that sits between the label and the
    # description.
    snippet = _strip_leading_pmc_running_header(snippet)
    # v2.4.4: trim chart-data appendage from figure captions (axis-tick
    # sequences, raw bar-chart values pdftotext joined inline into the
    # caption paragraph). For tables the appendage is usually the next-
    # row continuation so skip — the caption hard-cap at 400 below
    # bounds it.
    if cap.kind == "figure":
        snippet = _trim_caption_at_chart_data(snippet)
        # v2.4.25: trim journal/running-header tails and inline section-
        # heading body-prose absorption. Only applied to figures —
        # tables hit different post-cell patterns and are already bounded
        # by the next caption / Camelot cell merge.
        snippet = _trim_caption_at_running_header_tail(snippet)
        snippet = _trim_caption_at_body_prose_boundary(snippet)
    if len(snippet) > 400:
        # Figure captions: an overflow is over-absorbed body prose — walk
        # back to the last real sentence terminator so the caption ends
        # cleanly instead of being cut mid-word with an ellipsis. Tables
        # keep the mid-word cap (their overflow is linearized cell text
        # already bounded by ``_trim_table_caption_at_cell_region``).
        #
        # FIG-4 (v2.4.52): only a RUNAWAY figure caption — the walk found
        # no ``\n\n`` and ran to the 800-char hard cap — is over-absorbed
        # body prose. A caption that overflows 400 chars but whose walk
        # stopped at a real ``\n\n`` paragraph break is a LEGITIMATE long
        # caption (a label + a long Note, e.g. efendic Figure 1 at ~430
        # chars); pdftotext's own paragraph boundary bounds it, so it is
        # kept whole rather than truncated at the last pre-400 terminator.
        if cap.kind == "figure":
            if not stopped_at_break:
                snippet = _trim_overflowing_figure_caption(snippet)
        else:
            snippet = snippet[:400].rsplit(" ", 1)[0] + "…"
    return snippet


# v2.4.4: shared chart-data trim, duplicated logic from
# ``docpluck.figures.detect._trim_caption_at_chart_data`` so this module
# doesn't import from ``figures.detect`` (which has its own layout-channel
# dependencies). Two signatures of pdftotext-joined chart data:
#   1. Run of 6+ consecutive digits — flowchart counts, row IDs.
#   2. Run of 5+ short (1–4 digit) numeric tokens separated only by
#      whitespace — axis-tick label sequences.
_CHART_DATA_DIGIT_RUN_RE_STRUCT = re.compile(r"\b\d{6,}\b")
_CHART_DATA_TICK_RUN_RE_STRUCT = re.compile(r"(?:\b\d{1,4}\b[ \t]+){5,}")

# v2.4.28 (cycle 13): two new signatures added for amj_1 flow-chart and
# axis-tick patterns the original two regexes don't catch:
#
#   3. **Axis-tick pair**: 2+ occurrences of `\d\s+\d` (a single-digit
#      token followed by another single-digit token, separated only by
#      whitespace). amj_1 Figures 2-7 emit chart axis ticks as
#      `7 6 Employee Creativity 5 4 Bottom-up Flow 3 Lateral Flow 2 1`
#      after pdftotext flattens them inline with the caption. The
#      existing 5+ numeric-token signature doesn't fire because the
#      digits are interrupted by Title-Case words.
#
#   4. **Numbered flow-chart nodes**: 3+ occurrences of
#      `\d+\.\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,4}` (a numbered prefix
#      followed by a Title-Case noun phrase, 2-5 words). amj_1 Figure 1
#      embeds flow-chart node labels as `1. Bottom-up Feedback Flow 2.
#      Top-down Feedback Flow 3. Lateral Feedback Flow`.
#
# Both require 2+ matches (axis-tick) / 3+ matches (numbered list) in
# close proximity (< 80 chars between matches) so a single legit "in
# Study 1" or numbered list item in a real caption doesn't false-fire.
# Match either two adjacent single-digit tokens (``7 6``) or two
# single-digit tokens separated by 1-4 Title-Case words
# (``7 Meta-Processes 6``, ``5 Bottom-up Flow 4``). The Title-Case
# variant catches axis ticks that pdftotext interleaved with their
# axis labels, common in amj_1 Figure 5-7.
_AXIS_TICK_PAIR_RE = re.compile(
    r"\b\d\s+(?:[A-Z][\w\-]+(?:\s+[A-Z][\w\-]+){0,3}\s+)?\d\b"
)
# Allow hyphenated Title-Case words ("Bottom-up", "Top-down") in the
# numbered-node pattern by treating ``[A-Z][\w\-]*`` as the "word"
# unit. Both anchor word AND continuation words must be Title-Case.
_NUMBERED_CHART_NODE_RE = re.compile(
    r"\b\d+\.\s+[A-Z][a-z]+(?:-[a-z]+)?(?:\s+[A-Z][a-z]+(?:-[a-z]+)?){1,4}"
)


def _find_chart_data_cluster(
    caption: str, pattern: re.Pattern, min_matches: int, max_gap: int = 80
) -> int | None:
    """Find the start position of the first chart-data cluster.

    A cluster is ``min_matches`` consecutive matches of ``pattern``
    where each pair of adjacent matches is within ``max_gap`` chars of
    each other. Returns the start position of the FIRST match in the
    cluster, or None if no cluster meets the threshold.

    Matches at position < 20 are excluded so the ``Figure N.`` /
    ``Table N.`` label prefix can't itself become the first match
    of a numbered-list cluster.

    This is the discriminator that prevents false-positives on legit
    captions that happen to contain ONE numbered list item or ONE
    "Study 1" — only clusters of repeated patterns trigger the trim.
    """
    matches = [m for m in pattern.finditer(caption) if m.start() >= 20]
    if len(matches) < min_matches:
        return None
    # Sliding window: find any min_matches consecutive matches within
    # max_gap chars of each other.
    for i in range(len(matches) - min_matches + 1):
        window = matches[i:i + min_matches]
        gaps = [
            window[j + 1].start() - window[j].end()
            for j in range(len(window) - 1)
        ]
        if all(g <= max_gap for g in gaps):
            return window[0].start()
    return None


def _trim_caption_at_chart_data(caption: str) -> str:
    """Truncate a caption when it transitions from prose to chart-data.

    Conservative: only fires when caption ≥ 150 chars AND the surviving
    trimmed text is ≥ 40 chars. Four regex signatures catch
    complementary chart-data patterns; the earliest match wins.

    v2.4.28 (cycle 13): added axis-tick-pair clusters
    (``\\d \\d ... \\d \\d`` interleaved with Title Case words, common
    in amj_1 Figures 2-7) and numbered flow-chart node clusters
    (``1. Bottom-up Foo 2. Top-down Foo``, common in amj_1 Figure 1).
    Both require 2+ / 3+ matches in close proximity so a single legit
    "in Study 1" or numbered list item doesn't false-fire.
    """
    if not caption or len(caption) < 150:
        return caption
    candidates: list[int] = []
    m1 = _CHART_DATA_DIGIT_RUN_RE_STRUCT.search(caption)
    if m1 is not None:
        candidates.append(m1.start())
    m2 = _CHART_DATA_TICK_RUN_RE_STRUCT.search(caption)
    if m2 is not None:
        candidates.append(m2.start())
    c3 = _find_chart_data_cluster(caption, _AXIS_TICK_PAIR_RE, min_matches=2, max_gap=100)
    if c3 is not None:
        candidates.append(c3)
    c4 = _find_chart_data_cluster(caption, _NUMBERED_CHART_NODE_RE, min_matches=3, max_gap=100)
    if c4 is not None:
        candidates.append(c4)
    if not candidates:
        return caption
    cut = min(candidates)
    while cut > 0 and not caption[cut - 1].isspace():
        cut -= 1
    trimmed = caption[:cut].rstrip(" ,;:")
    if len(trimmed) < 40:
        return caption
    return trimmed


# v2.4.25 (cycle 10): three new figure-caption trim functions for
# defects surfaced by the cycle-9 handoff (item A) + broad-read of
# amj_1 / ieee_access_2 figure captions. All three target
# ``_extract_caption_text``'s output AFTER the paragraph-walk has
# settled — they fix things the walk can't (it operates on \n\n
# boundaries; these patterns sit inside a single rejoined paragraph).


_DUPLICATE_UPPER_LABEL_RE = re.compile(
    r"^(?P<label>Figure|Table)\s+(?P<num>\d+(?:\.\d+)?)\.\s+"
    r"(?:FIGURE|TABLE)\s+(?P=num)\.?\s+",
    re.IGNORECASE,
)


# Cycle 15n (v2.4.31): label-only fullmatch — accumulated caption text that
# contains nothing more than the caption's own label (and possibly a
# duplicate ALL-CAPS form). When the paragraph-walk in
# ``_extract_caption_text`` is about to bail at a sentence-terminator but
# the accumulated snippet is just label-only, the walk should keep going
# so it can reach the actual description in the next paragraph.
_LABEL_ONLY_FULLMATCH_RE = re.compile(
    r"\s*(?:figure|fig\.?|table)\s+\d+(?:\.\d+)?\.?"
    r"(?:\s+(?:figure|fig\.?|table)\s+\d+(?:\.\d+)?\.?)?\s*",
    re.IGNORECASE | re.DOTALL,
)


# Cycle 15f-1 (v2.4.32, G4b): conjunction / article words that, when a
# short line ends with one, signal the line is a wrapped title
# continuation rather than a table column header.
_TITLE_WRAP_TAIL_WORDS = frozenset({
    "and", "or", "of", "the", "for", "in", "on", "to", "a", "an",
    "with", "by", "from", "&",
})


def _is_table_header_like_short_line(line: str) -> bool:
    """True if ``line`` looks like a table column header or linearized
    cell token rather than a caption title (or a wrapped title line).

    Header / cell tokens from pdftotext linearization are short, start
    with an uppercase letter or a digit, and are not grammatical
    continuations of a title. Lowercase-leading short lines
    (``by condition``) and lines ending in a conjunction/article
    (``Means and SDs for the``) are title wraps, not headers.
    """
    s = line.strip()
    if not s:
        return False
    words = s.split()
    # Column headers / linearized cell tokens are short — almost always
    # <=3 words ("Academic Rank", "Number of Citations", "Impact Factor").
    # A 4+-word capitalised line is far more likely a wrapped title line
    # ("General Management (GM) Textbooks") — keep it out so the cell-run
    # detector can't cut a real title.
    if len(words) > 3 or len(s) > 35:
        return False
    # Lowercase-leading short line → grammatical title continuation.
    if s[0].islower():
        return False
    # Ends with a conjunction/article → title wrap, not a standalone header.
    if words[-1].lower() in _TITLE_WRAP_TAIL_WORDS:
        return False
    return True


def _trim_table_caption_at_cell_region(region: str) -> str:
    """Trim a raw TABLE caption region at the start of linearized cell content.

    pdftotext linearizes a table's cells as a run of short one-per-line
    tokens. When the caption title has no sentence terminator, the
    paragraph-walk in :func:`_extract_caption_text` absorbs all of them.

    Detect the cell region as the first run of >=3 consecutive
    ``_is_table_header_like_short_line`` non-blank lines, and cut there.
    The label line plus at least one title line are always preserved
    (the run can only start at the 3rd non-blank line or later), so a
    short single-word title (``Correlations``) is never truncated.

    ``region`` is the raw caption text with newlines intact. Returns the
    region truncated to label + title line(s) — or unchanged if no cell
    run is found (the existing 400-char hard cap still applies).
    """
    lines = region.split("\n")
    nonblank = [(i, ln) for i, ln in enumerate(lines) if ln.strip()]
    if len(nonblank) < 5:
        # Too few lines to confidently locate a cell run — leave as-is.
        return region
    first = nonblank[0][1].strip()
    label_only = bool(re.fullmatch(r"(?:TABLE|Table)\s+\d+\.?", first))
    first_terminated = bool(re.search(r"[.!?][\"'\)\]]?$", first))
    # Primary rule: when the FIRST line already carries title text AND
    # ends with a sentence terminator ("Table 6. Study 2 descriptive
    # statistics."), the title sentence is complete on line 0. Everything
    # after is either a table note (belongs in the `footnote` field, not
    # `caption`) or linearized cell content — cut it all. This reliably
    # handles captions whose column headers are multi-word phrases that
    # the cell-run heuristic below would miss.
    if not label_only and first_terminated:
        return lines[nonblank[0][0]] if nonblank[0][0] == 0 else "\n".join(
            lines[: nonblank[0][0] + 1]
        )
    # Fallback rule: nonblank[0] is just a bare label ("TABLE 13") or an
    # unterminated title that may wrap. Locate the linearized cell region
    # as the first run of >=3 consecutive header-like short lines, and cut
    # there. nonblank[1] (the title or its first wrapped line) is always
    # protected — the run can only start at the 3rd non-blank line.
    for j in range(2, len(nonblank) - 2):
        window = nonblank[j:j + 3]
        if all(_is_table_header_like_short_line(ln) for _, ln in window):
            cut_line_idx = window[0][0]
            return "\n".join(lines[:cut_line_idx])
    return region


def _accumulated_is_label_only(text: str) -> bool:
    """True when ``text`` is just a Table/Figure label (optionally followed
    by a duplicate ALL-CAPS or title-case form of the same label) with no
    description content. Used by ``_extract_caption_text``'s paragraph-walk
    to decide whether a `.`-terminated short fragment is a real caption or
    just the label sitting on its own line.

    Examples that return True:
        "FIGURE 1."
        "Figure 1.\\n\\nFIGURE 1."
        "Figure 1. FIGURE 1."

    Examples that return False:
        "Figure 1. Petri nets model formalism elements."
        "Author Manuscript"  (would also be rejected by the prev-words check)
    """
    if not text:
        return False
    return bool(_LABEL_ONLY_FULLMATCH_RE.fullmatch(text))


# A significance-legend tail — ``* p < .05, ** p < .01, *** p < .001`` and
# kin. When a caption's accumulated text ends with one of these, the caption
# is complete: a significance legend is conventionally the LAST element of a
# figure/table caption, so a ``\n\n`` after it ends the caption.
_SIG_LEGEND_TAIL_RE = re.compile(
    r"[*†‡]{1,4}\s*p\s*[<>=≤≥]\s*\.?\d+\s*$", re.IGNORECASE
)

# Lowercase function words that may appear inside an APA Title-Case figure
# title without breaking it. A title is "complete" when every other word is
# capitalized (or a digit-led token); a lowercase *content* word means the
# accumulated text is body prose, not a title.
_TITLE_FUNCTION_WORDS = frozenset(
    "a an and as at between by for from in into of on or than that the to "
    "via vs with within over under per".split()
)


def _caption_is_complete_without_terminator(accumulated: str, label: str) -> bool:
    """True when ``accumulated`` (the caption text walked so far) is a
    COMPLETE caption even though it does not end with ``.``/``!``/``?``.

    Two period-less shapes occur in the academic-PDF corpus and both must
    end the ``_extract_caption_text`` paragraph-walk at the next ``\\n\\n``:

      1. **Significance legend** — ``… *** p < .001``. The legend is
         conventionally the caption's final element (chandrashekar Figs
         1/3).
      2. **APA Title-Case figure title** — ``The Interaction Between Change
         in … Non-Manipulated Attribute`` — every content word capitalized,
         joined by lowercase function words, no terminal period (efendic
         Figs 4/5). APA 7 figure titles are period-less Title-Case phrases.

    Without this, the walk sails past the ``\\n\\n`` that legitimately ends
    such a caption (its terminator check only recognizes ``.!?``) and
    absorbs the following body prose.
    """
    flat = re.sub(r"\s+", " ", accumulated).strip()
    # Strip the label prefix case-INsensitively — pdftotext may emit the
    # label ALL-CAPS (``FIGURE 15.``) while ``cap.label`` is title-case.
    m_label = _CAPTION_LABEL_PREFIX_RE.match(flat)
    if m_label:
        flat = flat[m_label.end():]
    elif label and flat.startswith(label):
        flat = flat[len(label):].lstrip(" .:")
    # Strip a leading PMC ``Author Manuscript`` running header (one or more
    # repeats) that pdftotext interleaves between the label and the real
    # description — otherwise ``Author Manuscript Author Manuscript`` reads
    # as a 4-word Title-Case "title" and the walk stops on the header.
    flat = re.sub(
        r"^(?:Author\s+Manuscript\s*)+", "", flat, flags=re.IGNORECASE
    ).strip()
    if not flat:
        return False
    if _SIG_LEGEND_TAIL_RE.search(flat):
        return True
    # APA Title-Case title: >= 4 words, no lowercase content word.
    words = flat.split()
    if len(words) < 4:
        return False
    for w in words:
        core = w.strip("(),.;:!?\"'—–-/").strip()
        if not core:
            continue
        if core.lower() in _TITLE_FUNCTION_WORDS:
            continue
        if core[0].isupper() or core[0].isdigit():
            continue
        return False  # a lowercase content word — this is prose, not a title
    return True


# Cycle 15n (v2.4.31): PMC running header that pdftotext interleaves
# between a figure caption's label line and its description. Pattern
# observed in ieee_access_2 (37 figures): after the title-case label
# ``Figure N.`` the snippet has ``Author Manuscript`` (one or more
# repeats) before the description. Anchored to require the label as
# a prefix so it can't false-fire on body prose that happens to start
# with the phrase.
_PMC_LEADING_HEADER_RE = re.compile(
    r"^(?P<label>(?:Figure|Fig\.?|Table)\s+\d+(?:\.\d+)?\.)\s+"
    r"(?:Author\s+Manuscript\s+)+",
    re.IGNORECASE,
)


def _strip_leading_pmc_running_header(snippet: str) -> str:
    """Strip a PMC ``Author Manuscript`` running header that sits
    between the caption label and the description, after duplicate-
    label collapse has run.

    Examples:
        ``Figure 4. Author Manuscript Two options …`` → ``Figure 4. Two options …``
        ``Figure 5. Author Manuscript Author Manuscript Comparison …``
            → ``Figure 5. Comparison …``
    """
    if not snippet:
        return snippet
    return _PMC_LEADING_HEADER_RE.sub(lambda m: f"{m.group('label')} ", snippet, count=1)


def _strip_duplicate_uppercase_label(snippet: str, label: str) -> str:
    """Strip a redundant ALL-CAPS "FIGURE N" / "TABLE N" that follows the
    title-case label.

    Example:
        "Figure 1. FIGURE 1 Theoretical Framework …" → "Figure 1. Theoretical Framework …"
        "Figure 2. FIGURE 2. Continuous-time …"      → "Figure 2. Continuous-time …"

    The duplicate occurs in many AOM and IEEE / PMC reprints where the
    PDF embeds the ALL-CAPS label as a graphics overlay alongside the
    title-case caption text. pdftotext returns both.
    """
    if not snippet or not label:
        return snippet
    return _DUPLICATE_UPPER_LABEL_RE.sub(
        lambda m: f"{m.group('label')} {m.group('num')}. ", snippet, count=1
    )


# Running-header tail signatures. Each is anchored at end-of-snippet
# (`\s*$`) so they can't accidentally chop the middle of a legit caption.
# Three families covered:
#   A. Author-running-header — e.g. "14 Q. XIAO ET AL."  (T&F / APA journals)
#   B. Same-surname dyad     — e.g. "2020 Kim and Kim 599" (AOM / Wiley)
#   C. PMC reprint footer    — e.g. "IEEE Access. Author manuscript;
#                                    available in PMC 2026 February 25."
_TAIL_AUTHOR_ETAL_RE = re.compile(
    r"\s+\d+\s+[A-Z]\.\s+(?:[A-Z]\.?\s+)?[A-Z]{2,}"
    r"(?:\s+(?:AND|&)\s+[A-Z][A-Z'\-]+)?"
    r"\s+ET\s+AL\.?\s*$"
)
_TAIL_DYAD_PAGE_RE = re.compile(
    r"\s+\d{4}\s+(?P<a>[A-Z][a-z]+)\s+and\s+(?P=a)\s+\d{1,4}\s*$"
)
_TAIL_PMC_REPRINT_RE = re.compile(
    r"\s+[A-Z][\w\s]+?\.\s+Author manuscript;\s+available in PMC[^.]*?\.?\s*$",
    re.IGNORECASE,
)


def _trim_caption_at_running_header_tail(snippet: str) -> str:
    """Strip a trailing running-header / journal-reprint footer that
    pdftotext absorbed at the end of a figure caption.

    Walks the three known tail signatures and removes the matched span.
    Then back-tracks to the last sentence-ending period so a body-prose
    run that preceded the running header (between the legit caption and
    the page-break) is also dropped.
    """
    if not snippet:
        return snippet
    for pat in (_TAIL_PMC_REPRINT_RE, _TAIL_AUTHOR_ETAL_RE, _TAIL_DYAD_PAGE_RE):
        m = pat.search(snippet)
        if m is None:
            continue
        trimmed = snippet[: m.start()].rstrip()
        # If the trimmed prefix still has body-prose tail (no sentence
        # terminator at end), walk back to the last ". " boundary.
        if trimmed and not re.search(r"[.!?][\"'\)\]]?$", trimmed):
            last_period = trimmed.rfind(". ")
            if last_period > 0:
                trimmed = trimmed[: last_period + 1]
        snippet = trimmed
        break
    return snippet


# Body-prose absorption: a caption sentence terminated by a period,
# followed by a Title-Case noun phrase (1-3 lowercase words after the
# capital lead) and then a Capital-starting clause with no intervening
# period. This is the inline-section-heading-then-body-prose pattern
# (e.g. "Study 1 interaction plots. Exploratory analysis To examine
# whether …"). The 2nd Capital word distinguishes body prose from a
# legit caption continuation like "Note. Bars represent SE." (which has
# no further Capital-starting word in the tail).
_BODY_PROSE_BOUNDARY_RE = re.compile(
    r"\s+([A-Z][a-z]+(?:\s+[a-z]+){0,3})\s+([A-Z][a-z]+)\b"
)

# Lowercase opener keywords that legitimately introduce a caption's 2nd
# / 3rd sentence; if the tail starts with one of these we treat it as
# caption-continuation and skip the trim at this boundary.
_CAPTION_CONTINUATION_OPENERS = (
    "note", "notes", "source", "sources", "bars", "error",
    "asterisks", "numbers", "values", "data", "see",
    "n =", "n=", "p <", "p<", "*p", "**p", "***p",
    "panel", "panels",
)

# FIG-3a (v2.4.49): label words whose trailing period terminates a
# caption-NOTE LABEL, not a sentence. ``Note. t-values are partial`` is a
# legitimate caption note whose content starts lowercase — the period
# after ``Note`` is a label separator, so the body-prose-boundary walk
# must treat these the same as a non-terminal abbreviation and never trim
# the note content away.
_CAPTION_LABEL_WORDS = frozenset({"note", "notes", "source", "sources"})

# FIG-3a (v2.4.49): a caption tail that is itself a significance legend
# (``ns p>.05, * p<.05, ** p<.01``). It legitimately continues the
# caption even though it starts with a lowercase ``ns`` / asterisk run,
# so the lowercase-tail trim below must recognize and keep it. ``∗`` is
# U+2217 ASTERISK OPERATOR — APA PDFs use it instead of ASCII ``*``.
_SIGNIFICANCE_LEGEND_TAIL_RE = re.compile(
    r"^\s*(?:n\.?s\.?|[*∗•·°†‡⁎]+)?\s*p\s*[<>=]", re.IGNORECASE
)


def _trim_caption_at_body_prose_boundary(snippet: str) -> str:
    """Trim a figure caption at the first sentence boundary where the
    tail looks like inline-section-heading-then-body-prose rather than
    a caption continuation.

    Triggered by the cycle-9 handoff item A: pdftotext occasionally
    flattens "Figure N. <short caption>.\\n<inline section heading>
    <body sentence>" into a single rejoined paragraph, so the
    paragraph-walk in :func:`_extract_caption_text` can't separate
    them. This function walks every ``. `` boundary after position 20
    (so "Figure N." isn't trimmed) and stops at the first one whose
    tail matches :data:`_BODY_PROSE_BOUNDARY_RE` AND doesn't start with
    a caption-continuation opener.

    Also requires a body-prose corroboration signal in the tail
    (parenthesized year, first-person pronoun, subordinating
    conjunction, or "participants") to reduce false positives on legit
    multi-sentence captions.

    FIG-3a (v2.4.49): a second, simpler boundary signature is added — a
    ``. `` terminator followed by a *lowercase-initial* word. A figure
    caption's own sentences always start capitalized, so a lowercase
    continuation is absorbed body prose (a wrapped citation fragment
    such as ``and Linos, 2022).`` or a body sentence pdftotext welded on
    with a single ``\\n``). This branch is guarded against three legit
    lowercase continuations: a non-terminal abbreviation before the
    period (``vs.``/``e.g.``), a caption-NOTE label before it
    (``Note. t-values …``), and a significance-legend tail
    (``ns p>.05, * p<.05 …``).
    """
    if not snippet or len(snippet) < 60:
        return snippet
    pos = snippet.find(". ", 20)
    while pos != -1:
        tail = snippet[pos + 2:]
        if not tail:
            break
        tail_lower = tail.lower()
        if any(tail_lower.startswith(k) for k in _CAPTION_CONTINUATION_OPENERS):
            pos = snippet.find(". ", pos + 2)
            continue
        # FIG-3a: a lowercase-initial tail is absorbed body prose unless
        # the period is a non-terminator (abbreviation / note label) or
        # the tail is a lowercase-led significance legend.
        if tail[:1].islower():
            prev = re.search(r"([A-Za-z.]+)$", snippet[: pos + 1])
            prev_tok = prev.group(1).rstrip(".").lower() if prev else ""
            if (
                prev_tok not in _CAPTION_NON_TERMINAL_ABBREV
                and prev_tok not in _CAPTION_LABEL_WORDS
                and _SIGNIFICANCE_LEGEND_TAIL_RE.match(tail) is None
            ):
                return snippet[: pos + 1]
        m = _BODY_PROSE_BOUNDARY_RE.match(" " + tail)
        if m is not None and _looks_like_body_prose(tail):
            return snippet[: pos + 1]
        pos = snippet.find(". ", pos + 2)
    return snippet


_BODY_PROSE_SIGNAL_RE = re.compile(
    r"\(\d{4}\)"                       # year citation
    r"|\b(?:we|our|us)\s+(?:examined|tested|observed|investigated|analyzed|compared|explored|performed|found|present|aimed|sought|conducted)\b"
    r"|\bparticipants?\b"
    r"|\bwhether\b"
    r"|\bbecause\b"
    r"|\bin\s+order\s+to\b"
    r"|\bto\s+(?:examine|test|observe|investigate|analyze|compare|explore|describe|determine|assess|evaluate)\b",
    re.IGNORECASE,
)


def _looks_like_body_prose(tail: str) -> bool:
    """Corroborate the body-prose boundary signature with a content signal.

    Requires one of: parenthesized year citation, first-person verb
    phrase, "participants", subordinating conjunction, or an infinitive
    of intent. Caption continuations rarely contain any of these.
    """
    return _BODY_PROSE_SIGNAL_RE.search(tail) is not None


# Abbreviations whose trailing period is NOT a sentence terminator. Used
# by the figure-caption overflow walk-back so it doesn't cut a caption
# mid-clause at "vs.", "e.g.", an author initial, etc.
_CAPTION_NON_TERMINAL_ABBREV = frozenset({
    "vs", "e.g", "i.e", "cf", "fig", "figs", "no", "nos", "eq", "eqs",
    "al", "etc", "dr", "mr", "mrs", "ms", "prof", "ca", "approx",
    "ref", "refs", "ed", "eds", "vol", "pp", "sd", "se", "ns",
})

# A sentence-terminator followed by whitespace or end-of-string:
# ``.``/``!``/``?`` with an optional closing bracket/quote. ``m.start()``
# lands on the terminator char itself.
_CAPTION_SENTENCE_END_RE = re.compile(r"[.!?][\"'\)\]]?(?=\s|$)")

# The label prefix of a caption (``Figure 12.`` / ``Fig. 3`` / ``Table 1.``).
# Used to ensure the overflow walk-back keeps real description content and
# doesn't collapse the caption to just its label.
_CAPTION_LABEL_PREFIX_RE = re.compile(
    r"(?:figure|fig\.?|table)\s+\d+(?:\.\d+)?\.?\s*", re.IGNORECASE
)


def _trim_overflowing_figure_caption(snippet: str, limit: int = 400) -> str:
    """Trim a figure caption that overflows the hard cap back to its last
    real sentence terminator instead of hard-truncating mid-word.

    A figure caption longer than ``limit`` chars (after every targeted
    trim above has already run) is, in the academic-PDF corpus, always a
    caption that absorbed following body prose — no legitimate figure
    caption in the 17-paper APA test corpus exceeds ~360 chars. The old
    behavior (``snippet[:400].rsplit(" ", 1)[0] + "…"``) cut the caption
    mid-word and appended an ellipsis, leaving the user a caption ending
    in a fragment. This walks the cap window back to the last genuine
    sentence terminator (skipping abbreviations like ``vs.`` and author
    initials) so the caption ends cleanly on a real sentence boundary.

    Keyed purely on the structural signature (caption overflow + sentence
    boundary), not on paper identity. Falls back to the mid-word cap only
    when no usable terminator exists past the label.
    """
    head = snippet[:limit]
    label = _CAPTION_LABEL_PREFIX_RE.match(head)
    label_end = label.end() if label else 0
    best = -1
    for m in _CAPTION_SENTENCE_END_RE.finditer(head):
        word = re.search(r"([A-Za-z.]+)$", head[: m.start() + 1])
        tok = word.group(1).rstrip(".").lower() if word else ""
        if tok in _CAPTION_NON_TERMINAL_ABBREV:
            continue
        if len(tok) == 1 and tok.isalpha():  # author initial, e.g. "J."
            continue
        best = m.start() + 1  # keep through the terminator char
    # The terminator must sit past the label, so the surviving caption
    # retains real description content (not just ``Figure N.``).
    if best > label_end:
        return snippet[:best].rstrip()
    return snippet[:limit].rsplit(" ", 1)[0] + "…"


def _isolated_table_from_caption(
    cap: CaptionMatch,
    raw_text: str,
    next_boundary: Optional[int] = None,
) -> Table:
    """Build an isolated (cellless) Table dict for a caption with no Camelot match.

    v2.4.12: populate ``raw_text`` with the body text following the caption.
    pdftotext linearizes table cells into the body as a vertical run of
    short lines (column headers, then values, then more rows). Even
    though we can't reconstruct the grid (Camelot failed and we run in
    pdfplumber-free mode here), surfacing the raw cell content under the
    caption is much better than the previous "no cells or raw text
    extracted" banner — the user sees the table's information, just as
    a flat list rather than a structured grid.
    """
    cap_text = _extract_caption_text(raw_text, cap, next_boundary)
    body_text = _extract_table_body_text(raw_text, cap, next_boundary)
    return {
        "id": f"t{cap.number}",
        "label": cap.label,
        "page": cap.page,
        "bbox": (0.0, 0.0, 0.0, 0.0),
        "caption": cap_text,
        "footnote": None,
        "kind": "isolated",
        "rendering": "isolated",
        "confidence": None,
        "n_rows": None,
        "n_cols": None,
        "header_rows": None,
        "cells": [],
        "html": None,
        "raw_text": body_text,
    }


# Common English stopwords used by `_line_is_body_prose` to discriminate
# table cells (mostly noun fragments / numbers / short labels) from running
# body prose (rich in articles, prepositions, conjunctions). Kept small and
# stable — the goal is signal, not coverage.
_BODY_PROSE_STOPWORDS = frozenset({
    "the", "of", "and", "in", "to", "that", "this", "with", "as", "for",
    "we", "was", "were", "be", "is", "are", "an", "by", "on", "from",
    "their", "have", "has", "had", "but", "not", "or", "which", "these",
    "our", "its", "than", "at", "such", "between", "would", "could",
    "however", "therefore", "thus", "while", "when",
})


def _line_is_body_prose(line: str) -> bool:
    """True if ``line`` looks like body prose rather than table cell content.

    Table cells from pdftotext linearization are typically short fragments
    (column header, numeric value, "Mean (SD)"). Table notes start with
    ``Note:`` or ``Notes:``. Body prose paragraphs that bleed past the
    table boundary are long, sentence-shaped, and stopword-dense.

    Guarded against measurement-scale items (e.g. ``"The offender has
    apologised?" (1 = Strongly disagree to 5 = Strongly agree) (Source:
    McCullough et al., 1997)``) which can be quite long but ARE table
    cells in instrument-description tables.
    """
    s = line.strip()
    if len(s) < 80:
        return False
    # Table notes / footnotes are legitimate trailing content.
    if re.match(r"^(Note[s.:]?\s|a\s*Note\b)", s):
        return False
    # Strong "this is a table cell" signals — keep:
    #   - measurement-scale anchor like "(1 = ... to 5 = ...)"
    #   - parenthetical source attribution "(Source: ...)"
    #   - quoted instrument items (curly or straight double quotes
    #     enclosing 8+ chars — survey prompts, condition descriptions)
    if re.search(r"\(\d+\s*=", s):
        return False
    if re.search(r"\(Source[:\s]", s, re.IGNORECASE):
        return False
    # Quoted instrument items: keep only when DOUBLE-quoted content is
    # substantial (multiple runs OR ≥40 chars total). Use double-quote
    # delimiters only — single curly quotes (‘ ’) double as apostrophes
    # in academic text and a too-loose pattern would match across whole
    # paragraphs (e.g. "Kruger‘s (1999) findings, ... section in the OSF"
    # — 400 chars of body prose between an apostrophe and a quote-mark).
    # Cap each run at 160 chars so a stray unmatched double-quote can't
    # eat a runaway sentence either.
    quoted_runs = re.findall(r"[“”\"](.{4,160}?)[“”\"]", s)
    if quoted_runs and (
        len(quoted_runs) >= 2 or sum(len(q) for q in quoted_runs) >= 40
    ):
        return False
    words = re.findall(r"[A-Za-z']+", s.lower())
    if len(words) < 12:
        return False
    stopwords_hit = sum(1 for w in words if w in _BODY_PROSE_STOPWORDS)
    return stopwords_hit >= 4


def _extract_table_body_text(
    raw_text: str,
    cap: CaptionMatch,
    next_boundary: Optional[int] = None,
) -> str:
    """Pull the text following a Table caption (intended for use when
    Camelot failed to extract cells). Returns the cell content as a flat
    string — column headers, values, group labels, etc., all linearized
    by pdftotext.

    Bounds (v2.4.14 — tightened to stop body-prose bleed; handoff
    2026-05-13 Defect B):
      * Start at the end of the caption's snippet.
      * Walk line-by-line and STOP at the first of:
          - form-feed (``\\x0c`` page boundary),
          - a body-prose-looking line (``_line_is_body_prose``),
          - 1500 chars from body_start (hard cap, down from 3000),
          - ``next_boundary`` (next caption).
      * Trim trailing heading-like short lines (they're part of the next
        section, not this table).

    Both poppler (single ``\\n`` paragraph breaks) and Xpdf (``\\n\\n``)
    text channels are supported: the line-by-line walk doesn't depend on
    paragraph delimiters being doubled.
    """
    # Walk past the caption's tail to find body_start. The caption sentence
    # may continue across one or more wrapped lines; stop at the first
    # paragraph-break following a sentence terminator.
    pos = cap.char_end
    cap_tail_end = min(cap.char_end + 800, len(raw_text))
    if next_boundary is not None and next_boundary > cap.char_end:
        cap_tail_end = min(cap_tail_end, next_boundary)
    while pos < cap_tail_end:
        # Prefer \n\n (Xpdf paragraph break) when present, otherwise treat
        # a single \n as a candidate break (poppler).
        nxt2 = raw_text.find("\n\n", pos)
        nxt1 = raw_text.find("\n", pos)
        if nxt2 != -1 and nxt2 < cap_tail_end:
            nxt = nxt2
            step = 2
        elif nxt1 != -1 and nxt1 < cap_tail_end:
            nxt = nxt1
            step = 1
        else:
            pos = cap_tail_end
            break
        prev = raw_text[max(cap.char_start, nxt - 40):nxt].rstrip()
        if not prev or len(prev.split()) < 2 or re.search(
            r"[.!?][\"'\)\]]?$", prev
        ):
            pos = nxt + step
            break
        pos = nxt + step
    body_start = pos
    body_end_hard = min(body_start + 1500, len(raw_text))
    if next_boundary is not None and next_boundary > body_start:
        body_end_hard = min(body_end_hard, next_boundary)
    region = raw_text[body_start:body_end_hard]

    # Hard stop at page boundary — table cell flow doesn't survive a
    # form-feed in pdftotext output; whatever's on the next page is
    # the next page's running header / body, not this table's cells.
    ff = region.find("\x0c")
    if ff != -1:
        region = region[:ff]

    # Line-by-line walk; stop at first body-prose-looking line.
    kept: list[str] = []
    for ln in region.split("\n"):
        if _line_is_body_prose(ln):
            break
        kept.append(ln)

    # Trim trailing heading-like short lines that don't belong to this table
    # (the start of the next section). Two patterns are trimmed:
    #   * Title-Case headings without a sentence terminator
    #     (e.g. "Experimental design", "Discussion")
    #   * Numbered section headings like "3.2.3 H2: Relationship ..."
    #     even when they end with a period (their structure betrays them).
    while kept:
        last = kept[-1].strip()
        if not last:
            kept.pop()
            continue
        is_numbered_heading = bool(
            re.match(r"^\d+(?:\.\d+){1,3}\s+[A-Z]", last)
        ) and len(last) < 200
        is_titlecase_heading = (
            10 < len(last) < 50
            and not last.endswith((".", "!", "?", ":"))
            and last[0].isupper()
            and not last[0].isdigit()
            and len(last.split()) <= 6
        )
        if is_numbered_heading or is_titlecase_heading:
            kept.pop()
            continue
        break

    snippet = "\n".join(kept)
    snippet = snippet.replace("\x0c", "")
    snippet = re.sub(r"­\s+", "", snippet)
    snippet = snippet.replace("­", "")
    cleaned_lines: list[str] = []
    for ln in snippet.split("\n"):
        s = re.sub(r"[ \t]+", " ", ln).strip()
        if s:
            cleaned_lines.append(s)
    return "\n".join(cleaned_lines).strip()


def _figure_from_caption(
    cap: CaptionMatch,
    raw_text: str,
    next_boundary: Optional[int] = None,
) -> Figure:
    """Build a Figure dict from a caption match. bbox is unknown (zeros)."""
    return {
        "id": f"f{cap.number}",
        "label": cap.label,
        "page": cap.page,
        "bbox": (0.0, 0.0, 0.0, 0.0),
        "caption": _extract_caption_text(raw_text, cap, next_boundary),
    }


def _apply_placeholder(raw_text: str, captions: list[CaptionMatch]) -> str:
    """Replace each caption's line with ``[Label: caption]`` marker.

    Without pdfplumber we don't know the exact bbox of the table region; we
    mark only the caption line itself. The marker is shorter than the caption
    line so total text length doesn't grow.
    """
    if not captions:
        return raw_text
    items = sorted(
        ((c.char_start, c.char_end, c) for c in captions),
        key=lambda item: item[0],
        reverse=True,
    )
    # v2.3.0 Bug 4: bound each caption's snippet at the next caption's start.
    by_start = sorted(captions, key=lambda c: c.char_start)
    next_boundary_by_id: dict[int, Optional[int]] = {}
    for i, c in enumerate(by_start):
        next_boundary_by_id[id(c)] = (
            by_start[i + 1].char_start if i + 1 < len(by_start) else None
        )
    out = raw_text
    for start, end, cap in items:
        snippet = _extract_caption_text(raw_text, cap, next_boundary_by_id.get(id(cap)))
        # Build "[Label: caption]" marker. Use the snippet (already cleaned).
        if cap.label and cap.label in snippet:
            desc = snippet[len(cap.label):].lstrip(" .:—–-,")
        else:
            desc = snippet
        marker = f"[{cap.label}: {desc[:120]}]" if desc else f"[{cap.label}]"
        out = out[:start] + marker + out[end:]
    return out


__all__ = [
    "TABLE_EXTRACTION_VERSION",
    "TableTextMode",
    "StructuredResult",
    "extract_pdf_structured",
]
