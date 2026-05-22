"""
Normalization Pipeline
=======================
Consolidated from ESCIcheck, MetaESCI, Scimeto/CitationGuard, MetaMisCitations.
Each step is documented, versioned, and independently toggleable.

Levels:
  none     - Raw extracted text, no modifications
  standard - General-purpose cleanup safe for any use
  academic - Standard + academic-specific statistical expression repair
"""

import re
import unicodedata
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class NormalizationLevel(str, Enum):
    none = "none"
    standard = "standard"
    academic = "academic"


NORMALIZATION_VERSION = "1.9.20"


# ── Mathematical Alphanumeric Symbols de-styling (shared, v2.4.34) ──────────
# The SMP block U+1D400-U+1D7FF holds styled (italic / bold / bold-italic /
# script / fraktur / double-struck / sans-serif / sans-bold / monospace)
# Latin letters, Greek letters and digits. Every codepoint in it is a
# compatibility character whose NFKC decomposition is its plain base form:
# 𝐴->A, 𝜂->η, 𝛽->β, 𝟎->0. Greek MUST stay Greek — mapping it to ASCII Latin
# (the pre-v2.4.34 bug: 𝜂->"n", 𝛽->"b") silently corrupts statistical
# symbols (η² rendered as "n2"). CLAUDE.md hard rule 4: only U+2212->hyphen
# is a sanctioned Unicode->ASCII conversion. Shared by normalize_text's S0
# step (text/body channel) and tables/cell_cleaning (layout channel) so math
# styling is stripped consistently across every output view.
_MATH_ALNUM_RE = re.compile(r"[\U0001D400-\U0001D7FF]")


def destyle_math_alphanumeric(text: str) -> str:
    """Strip Mathematical-Alphanumeric styling to the plain base letter/digit.

    NFKC-normalises each U+1D400-U+1D7FF codepoint (Greek stays Greek, Latin
    stays Latin, digits stay digits). No-op when the text holds no such char.
    """
    if not text or not _MATH_ALNUM_RE.search(text):
        return text
    return _MATH_ALNUM_RE.sub(
        lambda m: unicodedata.normalize("NFKC", m.group()), text
    )


# ── Request 9 (Scimeto, 2026-04-27): Reference-list normalization ──────────
# Three artifact classes that survive S0–A6 and silently corrupt bibliographies:
#   W0 — Publisher-overlay watermarks glued mid-line (Royal Society "Downloaded
#        from..." overlay, Wiley/Elsevier "Provided by..." stamps, etc.)
#   R2 — Page-number digits that pdftotext glued between two body words inside
#        a reference (e.g. "psychological 41 science." in ref 17).
#   R3 — Continuation lines from a wrapped reference that didn't get rejoined,
#        so the journal/volume tail looks like an orphan paragraph.
#   A7 — DOIs broken across a line ("doi:10.\n1007/s10683-...").
# Pretest (51-PDF corpus): W0 fires on RSOS-family PDFs; R2 catches the silent
# corruption case; R3 fixes 1–142 continuations per PDF; A7 fixes long DOIs.

_WATERMARK_PATTERNS = [
    # 2026-05-09: relaxed to allow optional intermediate phrase between the
    # URL and the "on <date>" tail.  Collabra Psychology renders the watermark
    # as "Downloaded from <url> by guest on <date>"; the previous pattern
    # required `<url> on <date>` with nothing in between and missed it on
    # every Collabra paper.
    re.compile(
        # v2.3.0: extended the "by <phrase>" tail from `\w+` (one word, fits
        # "by guest") to any non-newline-bounded phrase, so it catches
        # institutional download stamps like
        #   "Downloaded from <url> by University of Innsbruck (Universitat
        #    Innsbruck) user on 16 March 2026"
        # found on every page of ar_royal_society_rsos_140072 (verified by
        # ``scripts/verify_corpus.py``). The trailing "on <day> <month>
        # <year>" anchor prevents runaway captures into body prose.
        r"Downloaded\s+from\s+https?://[^\s]+(?:\s+by\s+[^\n]+?)?"
        r"\s+on\s+\d{1,2}\s+\w+\s+\d{4}",
        re.IGNORECASE,
    ),
    re.compile(r"Provided\s+by\s+[\w\s.,&-]+\s+on\s+\d{4}-\d{2}-\d{2}", re.IGNORECASE),
    re.compile(r"This\s+article\s+is\s+protected\s+by\s+copyright\.[^\n]*", re.IGNORECASE),
    # RSOS running-footer artifact glued onto body text:
    # "41royalsocietypublishing.org/journal/rsos R. Soc. Open Sci. 12: 250979"
    re.compile(r"\d+\s*royalsocietypublishing\.org/journal/\w+\s+R\.\s*Soc\.\s*Open\s*Sci\.\s*\d+:\s*\d+"),
    # Issue H — Publisher copyright stamp on its own line. Format:
    #   "© 2009 Elsevier Inc. All rights reserved."
    #   "Ó 2009 Elsevier Inc. All rights reserved."  (pdftotext sometimes flattens © → Ó)
    #   "© 2020 Springer Nature Limited. All rights reserved."
    #   "© 2021 The Author(s). Published by Wiley..."  (do NOT match — no "rights reserved")
    # We anchor to start-of-line and require ALL of: © or Ó, a 4-digit year,
    # then "All rights reserved" (case-insensitive). The intervening publisher
    # name is bounded to a single line. Trailing period optional. Also strip
    # the trailing newline so we don't leave a blank line behind.
    re.compile(
        r"(?im)^\s*[©Ó]\s*\d{4}[^\n]*?All\s+rights\s+reserved\.?\s*\n?",
    ),
    # Issue K (cycle 10, D4) — Elsevier page-1 ISSN / front-matter / copyright
    # line. pdftotext extracts it at the page-1 footer and downstream
    # paragraph-rejoin splices it into the Introduction body. Formats:
    #   "0022-1031/$ - see front matter Ó 2009 Elsevier Inc. All rights reserved."
    #   "0022-1031/© 2021 Elsevier Inc. All rights reserved."
    # The Issue-H pattern above only fires when the line STARTS with ©/Ó;
    # these lines start with the journal ISSN. The line-leading ISSN
    # `NNNN-NNNX/` is the anchor — academic body prose and references never
    # begin with it — and we additionally require an Elsevier/front-matter/
    # rights-reserved keyword so a coincidental digit run can never match.
    re.compile(
        r"(?im)^\s*\d{4}-\d{3}[\dX]/[^\n]*?"
        r"(?:see\s+front\s+matter|Elsevier|All\s+rights\s+reserved)[^\n]*\n?",
    ),
    # Issue L (cycle 10, D4) — Elsevier single-author corresponding-author
    # e-mail footer line, e.g. "E-mail address: muraven@albany.edu". This is
    # page-1 footer metadata that pdftotext splices mid-Introduction. Only
    # the SINGULAR "E-mail address:" form is matched — it is a single short
    # line (one corresponding author). The plural "E-mail addresses:" form is
    # a long multi-author list that pdftotext wraps across several lines, so
    # it is intentionally left alone (a one-line strip would shred it).
    re.compile(
        r"(?im)^\s*E-mail\s+address:\s*\S*@\S+[^\n]*\n?",
    ),
    # Issue I — Two-column running header that pdftotext extracts at page
    # boundaries.  Format:
    #   "M. Muraven / Journal of Experimental Social Psychology 46 (2010) 465-468"
    #   "J. Smith / Cognitive Psychology 12 (2020) 100-120"
    # Anchored to its own line; recognized by the trailing "<vol> (<year>) <pages>"
    # signature.  We require at least one initial-then-surname before the slash
    # and one Capitalized word after.  The page range may use a hyphen or en-dash.
    re.compile(
        r"(?m)^\s*[A-Z]\.\s*(?:[A-Z]\.\s*)?[A-Z][\w'\-]+"
        r"(?:\s*(?:and|&|,)\s*[A-Z]\.\s*(?:[A-Z]\.\s*)?[A-Z][\w'\-]+)*"
        r"\s*/\s*"
        r"[A-Z][^/\n]{2,80}?"
        r"\s+\d+\s*\(\d{4}\)\s+\d+\s*[-–]\s*\d+\s*\n?",
    ),
    # 2026-05-09: Author-equal-contribution footnote line.
    # Collabra/IRSP and other open-access journals print a footnote at the
    # bottom of page 1 of the form:
    #   "a Surname, Surname, ... are equal-contribution first authors b email@..."
    # pdftotext extracts this in reading order, often interleaved between
    # the abstract and the introduction body.  The pattern requires:
    #   - leading lowercase letter + space (footnote marker "a ")
    #   - a list of capitalized surnames (3+ tokens, comma-separated)
    #   - the literal phrase "equal" + "contribution" OR "equal contribution"
    #     OR "joint first authors" anywhere in the line
    # The "equal contribution" phrase is the discriminator that distinguishes
    # this from genuine prose body lines that happen to start with a lowercase
    # letter (rare but possible).
    re.compile(
        r"(?m)^\s*[a-z]\s+"
        r"(?:[A-Z][\w-]+,\s+(?:and\s+)?){2,15}"
        r"[A-Z][\w-]+"
        r"\s+(?:are\s+)?(?:equal[ -]?contribution|joint\s+first\s+author)"
        r"[^\n]*\n?",
    ),
    # Issue J — Creative Commons / open-access license footer sentences that
    # publishers append to abstract paragraphs.  These are NOT abstract content;
    # they're licensing metadata.  Examples:
    #   "Copyright: © 2022. The authors license this article under the terms of
    #    the Creative Commons Attribution 3.0 License."
    #   "The authors license this article under the terms of the Creative
    #    Commons Attribution 4.0 International License."
    # The match starts at the optional "Copyright:..." prefix or at "The authors
    # license...", and runs to the first "License" closer.  We use lazy
    # `[^\n]*?` because the license version may contain a period ("4.0", "3.0")
    # that a `[^\n.]` class would reject.
    re.compile(
        r"(?:Copyright[: ]\s*[©Ó]?\s*\d{4}\.?\s+)?"
        r"The authors? licen[cs]e this article under the terms of the\s+"
        r"Creative\s+Commons[^\n]*?License\.?",
    ),
    # v2.4.37 (D4): Cambridge University Press per-page running footer.
    # pdftotext emits "https://doi.org/10.1017/<id> Published online by
    # Cambridge University Press" once per page; downstream paragraph-rejoin
    # then splices it MID-SENTENCE into body prose ("...individuals usually
    # fail to <footer> notice the absence..."). Not line-anchored — matches
    # whether the footer stands alone or is glued inline (pdftotext version
    # skew, memory feedback_pdftotext_version_skew). "Published online by
    # Cambridge University Press" is unambiguous platform boilerplate (book
    # citations read "Cambridge: Cambridge University Press"). Generic across
    # every Cambridge UP journal.
    re.compile(
        r"(?:https?://doi\.org/\S+\s+)?"
        r"Published\s+online\s+by\s+Cambridge\s+University\s+Press",
        re.IGNORECASE,
    ),
    # v2.4.37 (D4): Cambridge / JDM open-access licence boilerplate sentence.
    # The copyright block "© The Author(s), <year>. Published by Cambridge
    # University Press on behalf of ... European Association for Decision
    # Making. This is an Open Access article, distributed under the terms of
    # the Creative Commons Attribution licence (...), which permits ...
    # properly cited." gets serialized into the Introduction body. The "© ..."
    # head is caught by the page-footer strip; this removes the trailing
    # open-access sentence (with any dangling "...Association for Decision
    # Making." lead-in). [\s\S] spans the pdftotext line wrap inside it.
    re.compile(
        # Optional bare "Association for Decision Making." lead-in (the tail
        # of the publisher name, left behind when the "© ... European" head
        # is stripped by the page-footer pass). Literal only — must NOT reach
        # backward across legitimate body prose.
        r"(?:Association for Decision Making\.\s*)?"
        r"This is an Open Access article,[\s\S]{0,60}?"
        r"distributed under the terms of the\s+Creative\s+Commons"
        r"[\s\S]{0,240}?properly cited\.",
        re.IGNORECASE,
    ),
]

_REFS_HEADER = re.compile(
    r"^\s*(References?|Bibliography|Works\s+Cited|Literature\s+Cited)\s*$",
    re.MULTILINE | re.IGNORECASE,
)
_REFS_END = re.compile(
    r"\n\s*(Acknowledg|Funding|Author\s+contribution|Supplementary|Appendix|"
    r"Conflict\s+of\s+interest|Competing\s+interest|Notes|Data\s+availability|"
    r"Ethics\s+statement|Author's?\s+(note|disclosure))\b",
    re.IGNORECASE,
)
_REF_START_VANCOUVER = re.compile(r"^\d{1,3}\.\s+[A-Z]")
_REF_START_IEEE = re.compile(r"^\[\d+\]\s+[A-Z]")
_REF_START_APA = re.compile(r"^[A-Z][a-z]+(?:-[A-Z][a-z]+)?,\s+[A-Z]\.")


def _find_references_spans(text: str) -> list[tuple[int, int]]:
    """Return all (start, end) spans for References / Bibliography sections.

    A header qualifies only if followed within 5k chars by ≥3 ref-like
    patterns — guards against false positives from in-text "References"
    mentions or section-heading repetitions. Returns spans in document
    order. Multiple bibliographies (main + supplementary) all qualify and
    are returned separately, each ending at the next non-bibliography
    section heading.
    """
    spans: list[tuple[int, int]] = []
    for m in _REFS_HEADER.finditer(text):
        start = m.end()
        window = text[start:start + 5000]
        ref_starts = (
            len(re.findall(r"\b\d{1,3}\.\s+[A-Z]", window))
            + len(re.findall(r"\n\[\d+\]\s+[A-Z]", window))
            + len(re.findall(r"\n[A-Z][a-z]+(?:-[A-Z][a-z]+)?,\s+[A-Z]\.", window))
        )
        if ref_starts >= 3:
            end_m = _REFS_END.search(text, start)
            end = end_m.start() if end_m else len(text)
            # Skip if this span overlaps the previous span (next-header
            # qualifying within an already-claimed bibliography region).
            if spans and start < spans[-1][1]:
                continue
            spans.append((start, end))
    return spans


def _body_size(layout) -> float:
    """Return the most common font size by character count in the body zone.

    Excludes spans in the top 5% and bottom 15% of each page to avoid
    headers and footnotes skewing the result.
    """
    from collections import Counter
    counter: Counter[float] = Counter()
    for page in layout.pages:
        h = page.height
        y_lo = h * 0.15   # exclude bottom 15% (footnote zone)
        y_hi = h * 0.95   # exclude top 5% (running header zone)
        for span in page.spans:
            if span.y0 < y_lo or span.y0 > y_hi:
                continue
            counter[round(span.font_size, 1)] += len(span.text)
    if not counter:
        return 11.0
    return max(counter.items(), key=lambda kv: kv[1])[0]


def _body_y_band(page, body_size: float) -> tuple[float, float]:
    """Return (y_min, y_max) of the body-text band on this page."""
    body_spans = [s for s in page.spans if abs(s.font_size - body_size) <= 1.0]
    if not body_spans:
        return 0.0, page.height
    y_min = min(s.y0 for s in body_spans)
    y_max = max(s.y1 for s in body_spans)
    return y_min, y_max


def _detect_repeating_lines(layout, *, position: str) -> set[str]:
    """Return text lines that appear at the top (or bottom) of >=50% of pages."""
    if len(layout.pages) < 2:
        return set()
    counts: dict[str, int] = {}
    for page in layout.pages:
        if not page.spans:
            continue
        y_sorted = sorted(page.spans, key=lambda s: s.y0)
        if position == "top":
            candidates = [y_sorted[-1].text.strip()] if y_sorted else []
        else:
            candidates = [y_sorted[0].text.strip()] if y_sorted else []
        for c in candidates:
            if c:
                counts[c] = counts.get(c, 0) + 1
    threshold = len(layout.pages) // 2 + 1
    return {line for line, n in counts.items() if n >= threshold}


def _f0_strip_running_and_footnotes(
    raw_text: str, layout, table_regions: list[dict] | None = None,
) -> tuple[str, list[tuple[int, int]]]:
    """Strip running headers/footers and footnotes using layout info.

    Returns (post_strip_text_with_appendix, footnote_spans_in_raw_text).
    """
    from .extract_layout import LayoutDoc

    if not isinstance(layout, LayoutDoc) or not layout.pages:
        return raw_text, []

    body_size = _body_size(layout)

    # Pre-index table regions by 1-indexed page number for fast lookup.
    regions_by_page: dict[int, list[tuple[float, float, float, float]]] = {}
    if table_regions:
        for r in table_regions:
            page = int(r.get("page", 0))
            bbox = r.get("bbox")
            if page < 1 or not bbox or len(bbox) != 4:
                continue
            regions_by_page.setdefault(page, []).append(tuple(bbox))  # type: ignore[arg-type]

    def _span_in_table_region(span_y0: float, span_y1: float, span_x0: float,
                              span_x1: float, page_1based: int) -> bool:
        for rx0, rtop, rx1, rbot in regions_by_page.get(page_1based, ()):
            # Span y-range overlaps region y-range AND x-range overlaps region x-range.
            if span_y1 < rtop or span_y0 > rbot:
                continue
            if span_x1 < rx0 or span_x0 > rx1:
                continue
            return True
        return False

    page_text_chunks: list[str] = []
    footnote_chunks: list[str] = []
    footnote_raw_spans: list[tuple[int, int]] = []

    repeating_header_lines = _detect_repeating_lines(layout, position="top")
    repeating_footer_lines = _detect_repeating_lines(layout, position="bottom")

    for page in layout.pages:
        body_y_min, body_y_max = _body_y_band(page, body_size)
        keep_lines: list[str] = []
        page_footnotes: list[str] = []

        for span in page.spans:
            line_text = span.text.strip()
            if not line_text:
                continue

            is_header = (
                line_text in repeating_header_lines
                or span.y0 > body_y_max + 30
            )
            is_footer = (
                line_text in repeating_footer_lines
                and span.y0 < body_y_min - 30
            )
            is_footnote = (
                span.y0 < body_y_min - 30
                and span.font_size < body_size * 0.92
                and not is_footer
                and not _span_in_table_region(
                    span.y0, span.y1, span.x0, span.x1, page.page_index + 1,
                )
            )

            if is_header or is_footer:
                continue
            if is_footnote:
                page_footnotes.append(line_text)
                page_start = layout.page_offsets[page.page_index]
                idx = raw_text.find(line_text, page_start)
                if idx >= 0:
                    footnote_raw_spans.append((idx, idx + len(line_text)))
                continue

            keep_lines.append(line_text)

        page_text_chunks.append("\n".join(keep_lines))
        if page_footnotes:
            footnote_chunks.append("\n".join(page_footnotes))

    body = "\n\f".join(page_text_chunks)
    if footnote_chunks:
        appendix = "\n\f\f\n" + "\n\n".join(footnote_chunks)
    else:
        appendix = ""
    return body + appendix, footnote_raw_spans


def _detect_recurring_page_numbers(raw_text: str) -> set[int]:
    """Return integers that appeared as standalone-line page numbers ≥2 times.

    Threshold ≥2 (not ≥3) — short articles only repeat the page header on a
    handful of pages, so we'd miss real artifacts (e.g. RSOS p.41 in
    Li&Feldman appears only twice as standalone). Combined with the lowercase-
    surround guard in R2, ≥2 is safe.
    """
    counts: dict[int, int] = {}
    for line in raw_text.split("\n"):
        s = line.strip()
        # ASCII-only digit check: `str.isdigit()` matches Unicode superscripts
        # (², ³) which would crash int() — guard with isascii() first.
        if 1 <= len(s) <= 3 and s.isascii() and s.isdigit():
            n = int(s)
            if 1 <= n <= 999:
                counts[n] = counts.get(n, 0) + 1
    return {n for n, c in counts.items() if c >= 2}


# v2.4.17 (NORMALIZATION_VERSION 1.8.5): R2 noun-exception list.
#
# R2 strips inline digits in references span when the digit value also appears
# as a standalone line elsewhere in the doc (treated as a page-number leak).
# BUT some PDFs have many standalone-digit lines that aren't page numbers
# (table cell values, footnote markers, etc.) — those falsely contaminate
# the candidate set.
#
# Confirmed at v2.4.16: amle_1 has "20" as a standalone line 4+ times (Yes/No
# table cell values), causing R2 to strip "20" from the legitimate reference
# title "The first 20 years of Organizational Research Methods" → "The first
# years of …". Same for "40" in "The Journal of Management's first 40 years"
# → "first years".
#
# Fix: a negative-lookahead exception list. If the digit is followed by a
# whitespace-then-noun-class word (years, days, hours, percent, participants,
# people, etc.), the digit is part of a body phrase, NOT a page-number leak —
# do not strip.
_R2_BODY_NOUN_PATTERN = re.compile(
    r"(?:years?|days?|months?|weeks?|hours?|minutes?|seconds?|"
    r"percent|cents?|dollars?|pounds?|kilograms?|kg|grams?|cm|mm|m|km|"
    r"miles?|inches?|feet|points?|times?|samples?|individuals?|"
    r"participants?|subjects?|respondents?|cases?|trials?|studies?|"
    r"articles?|papers?|books?|chapters?|sources?|authors?|"
    r"countries?|nations?|institutions?|universities?|firms?|"
    r"companies?|organizations?|teams?|groups?|hospitals?|schools?|"
    r"records?|entries?|observations?|measurements?|events?|incidents?|"
    r"people|persons?|adults?|children|students?|patients?|workers?|"
    r"employees?|managers?|leaders?|followers?|users?|members?|"
    r"votes?|comments?|ratings?|reviews?|posts?|tweets?|messages?|"
    r"items?|conditions?|variables?|categories?|topics?|themes?)\b",
    re.IGNORECASE,
)


def _r2_is_body_phrase(digit_str: str, refs_text: str, match_pos: int) -> bool:
    """Return True if the digit at ``match_pos`` is part of a body phrase
    (e.g. "20 years", "1,675 participants") and should NOT be stripped by R2.

    Heuristic: check the 30-char window AFTER the matched digit for a
    body-noun keyword (years, participants, etc.). If found, the digit is
    almost certainly part of legitimate body prose, not a page-number leak.
    """
    # Window starts after the digit + at least one space.
    window_start = match_pos + len(digit_str)
    window = refs_text[window_start:window_start + 60]
    return bool(_R2_BODY_NOUN_PATTERN.search(window))


def _looks_like_ref_start(line: str) -> bool:
    return bool(
        _REF_START_VANCOUVER.match(line)
        or _REF_START_IEEE.match(line)
        or _REF_START_APA.match(line)
    )


# ── H0 / T0 / P0 / H1 : document-shape strips (NORMALIZATION_VERSION 1.8.0) ──
# Ported from docs/superpowers/plans/spot-checks/splice-spike/splice_spike.py
# (iter-20, iter-25, iter-26, iter-27). These run BEFORE the unicode/whitespace
# steps so the line-level regexes match raw pdftotext output.

# H0: explicit publisher / journal / repository banner lines that appear in the
# document header zone. A line is dropped ONLY if it matches an explicit
# pattern — anything else (titles, authors, affiliations, unknown text) stays.
_HEADER_BANNER_PATTERNS: list[re.Pattern[str]] = [
    # Bare URL line (publisher landing page).
    re.compile(r"^(?:https?://)?(?:www\.)?\S+\.(?:com|org|edu|gov|net|fr|uk|jp|cn|de|ch|nl)(?:/\S*)?$"),
    # NCBI / HHS / PMC manuscript banner (3-line block).
    re.compile(r"^HHS Public Access$"),
    re.compile(r"^Author manuscript$"),
    re.compile(r"^Published in final edited form as:.*$"),
    # Royal Society Open Science masthead.
    re.compile(r"^Cite this article:.*$"),
    re.compile(r"^Subject (?:Category|Areas):.*$"),
    re.compile(r"^Author for correspondence:.*$"),
    re.compile(r"^Received:\s+\d{1,2}\s+\w+\s+\d{4}.*$"),
    re.compile(r"^Accepted:\s+\d{1,2}\s+\w+\s+\d{4}.*$"),
    # Elsevier / ScienceDirect masthead.
    re.compile(r"^Contents lists available at\s+\S+.*$"),
    re.compile(r"^journal homepage:.*$", re.IGNORECASE),
    # Tandfonline / Taylor & Francis masthead.
    re.compile(r"^ISSN:\s*\S+.*$"),
    re.compile(r"^To cite this article:.*$"),
    re.compile(r"^To link to this article:.*$"),
    re.compile(r"^View supplementary material.*$"),
    re.compile(r"^Full Terms.*Conditions of access.*$"),
    # arXiv preprint banner.
    re.compile(r"^arXiv:\d+\.\d+(?:v\d+)?\s+\[[\w\.-]+\]\s+\d{1,2}\s+\w+\s+\d{4}\s*$"),
    # Article-type / category single-word labels.
    re.compile(r"^Article$"),
    re.compile(r"^ARTICLE$"),
    re.compile(r"^Research$"),
    re.compile(r"^Empirical Research Paper$"),
    re.compile(r"^Original (?:Investigation|Article|Research)(?:\s*\|\s*.+)?$"),
    re.compile(r"^Article\s+type[:.]\s*.*$", re.IGNORECASE),
    # AOM "r Academy of Management ..." masthead.
    re.compile(r"^r\s+Academy of Management\s+\S.*\d{4},.*$"),
    # SAGE / generic journal volume + page-range banner.
    re.compile(
        r"^[A-Z][A-Za-z &\-‐-―]{4,60}\s+\d{4},\s+Vol\.\s+\d+(?:\(\d+\))?[\s,].+$"
    ),
    # Chicago / Demography / similar: "Journal Name. YYYY Month DD; Vol(Iss): pages. doi:..."
    re.compile(
        r"^[A-Z][A-Za-z &]{3,40}\.\s+\d{4}.*\d+[:;].+doi:.*$"
    ),
    # SAGE / Cambridge / generic: "British Journal of Political Science (YYYY), Vol, pages doi:..."
    re.compile(
        r"^[A-Z][A-Za-z &]{4,60}\s+\(\d{4}\),\s+\d+,\s+\d+.{0,200}$"
    ),
    # Mangled DOI lines from publishers that overlay two PDF text runs.
    # v2.4.8: removed `^` anchor — PSPB / SAGE banners place the corrupted
    # DOI mid-line after the journal name, so the whole line is publisher
    # banner gibberish; "Dhtt" only appears in this specific corruption.
    re.compile(r".*Dhtt[Oo]ps[Ii]://.*$"),
    # Manuscript-ID gibberish like "1253268 ASRXXX10.1177/00031224241253268..."
    re.compile(r"^\d{6,}\s+[A-Z]{2,}[A-Z0-9]*\d+\.\d{4,}/.+$"),
    # Generic journal-citation banner with DOI suffix.
    re.compile(r"^[A-Z][A-Za-z\-]+,\s+\d{4},\s+vol(?:ume)?\s+\d+.*https?://doi\.org/.*$", re.IGNORECASE),
    # ScienceDirect issue line: "Journal Name 96 (2021) 104154 Contents lists..."
    re.compile(r"^[A-Z][A-Za-z &]+\s+\d+\s+\(\d{4}\)\s+\d+(?:\s+Contents.*)?$"),
    # Standalone Digital Object Identifier line.
    re.compile(r"^Digital Object Identifier\s+10\.\d+/.+$"),
    # Curated bare journal-name lines (small-font running banner above title).
    re.compile(r"^Journal of Economic Psychology$"),
    re.compile(r"^Cognition and Emotion$"),
    re.compile(
        r"^Journal of Experimental Social Psychology"
        r"(?:\s+\d+(?:\s*\(\d{4}\))?\s+\d+[‐-―\-]\d+)?$"
    ),
    # Judgment and Decision Making cite-line banner.
    re.compile(
        r"^[A-Z][A-Za-z]+(?:\s+[A-Za-z]+){1,8},\s+"
        r"Vol\.\s+\d+,\s+No\.\s+\d+,\s+\w+\s+\d{4},\s+pp\.\s+\d+[‐-―\-]\d+\s*$"
    ),
    # Oxford-journals: "Social Forces, 2025, 104, 224–249".
    re.compile(
        r"^[A-Z][A-Za-z]+(?:\s+[A-Za-z]+){0,3},\s+\d{4},\s+\d+,\s+\d+[‐-―\-]\d+\s*$"
    ),
    # Oxford-journals supplementary doi banner.
    re.compile(r"^https?://doi\.org/\S+\s+Advance access.*$"),
]


def _strip_document_header_banners(text: str) -> str:
    """H0: drop publisher/journal/repo banner lines in the document header zone.

    Header zone = everything before the first ``##`` heading, capped at the
    first 30 lines. (In the library pipeline ``##`` headings have not been
    added yet, so the 30-line cap is what applies.) Lines are dropped only on
    explicit pattern match; title / author / affiliation lines (which never
    match any banner pattern) are preserved verbatim.
    """
    if not text:
        return text
    lines = text.split("\n")
    header_end = len(lines)
    cap = min(len(lines), 30)
    for idx in range(cap):
        if lines[idx].lstrip().startswith("##"):
            header_end = idx
            break
    else:
        header_end = cap

    out_lines: list[str] = []
    dropped_any = False
    for idx, line in enumerate(lines):
        if idx < header_end:
            stripped = line.strip()
            if stripped and any(
                p.match(stripped) for p in _HEADER_BANNER_PATTERNS
            ):
                dropped_any = True
                continue
        out_lines.append(line)

    if not dropped_any:
        return text

    cleaned = "\n".join(out_lines)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    if cleaned.startswith("\n"):
        cleaned = cleaned.lstrip("\n")
    return cleaned


# T0: TOC dot-leader strip — Nature Supplementary PDFs render their TOC with
# runs of ``___`` (pdftotext's encoding of dot-leader filler characters).
_TOC_DOT_LEADER_RE = re.compile(r"_{3,}")
_PURE_TOC_LEADER_RE = re.compile(r"^\s*_{3,}\s*\d{0,4}\s*$")
_TOC_HEADING_RE = re.compile(
    r"^\s*(?:Table\s+of\s+Contents|List\s+of\s+(?:Supplementary\s+)?(?:Figures?|Tables?))\s*$",
    re.IGNORECASE,
)


def _strip_toc_dot_leader_block(text: str) -> str:
    """T0: drop TOC paragraphs with dot-leader page-number trails.

    Scope is limited to the first ~100 lines of the document (TOCs live near
    the top). Drops paragraphs that contain ``_{3,}`` runs or explicit TOC
    label lines. Also drops a ``## Heading`` whose immediate next paragraph is
    a TOC dot-leader paragraph (misparsed TOC entry promoted to a false
    heading) — this second rule fires only when section-detection has already
    introduced headings, which in the library pipeline happens later, so it
    is effectively a no-op here. Kept for parity with the spike behavior in
    case ``normalize_text`` is ever called on already-rendered markdown.
    """
    if not text:
        return text
    head_zone = text[:8000]
    if "_" not in head_zone and not re.search(
        r"\b(?:Table\s+of\s+Contents|List\s+of\s+(?:Supplementary\s+)?(?:Figures?|Tables?))\b",
        head_zone,
        re.IGNORECASE,
    ):
        return text
    parts = re.split(r"(\n\n+)", text)
    n = len(parts)

    cum_lines = 0
    last_para_idx_in_zone = -1
    for i in range(0, n, 2):
        if cum_lines >= 100:
            break
        last_para_idx_in_zone = i
        cum_lines += parts[i].count("\n") + 1
        if i + 1 < n:
            cum_lines += parts[i + 1].count("\n")

    drop_idx: set[int] = set()
    for i in range(0, last_para_idx_in_zone + 1, 2):
        para = parts[i]
        para_s = para.strip()
        if not para_s:
            continue
        is_toc = (
            _TOC_DOT_LEADER_RE.search(para)
            or _TOC_HEADING_RE.match(para_s)
        )
        if is_toc:
            drop_idx.add(i)
            if i >= 2 and parts[i - 2].strip().startswith("## "):
                drop_idx.add(i - 2)

    if not drop_idx:
        return text

    kept: list[str] = []
    for i in range(0, n, 2):
        if i in drop_idx:
            continue
        kept.append(parts[i])

    while kept and not kept[0].strip():
        kept.pop(0)
    cleaned = "\n\n".join(kept)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned


# P0: page-footer / running-header LINES anywhere in the document. Curated
# patterns only — each must match a single COMPLETE line.
_PAGE_FOOTER_LINE_PATTERNS: list[re.Pattern[str]] = [
    # Bare page number: "Page 1", "Page 27".
    re.compile(r"^Page\s+\d+\s*$"),
    # Page-N-of-M with date prefix: "October 27, 2023 1/13".
    re.compile(
        r"^(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s*20\d{2}\s+\d+/\d+\s*$"
    ),
    # Bare "(continued)" page-break marker.
    re.compile(r"^\([Cc]ontinued\)\s*$"),
    # Affiliation footnote markers like "aETH Zurich".
    re.compile(r"^[a-z][A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)*\s*$"),
    # "Corresponding Author:" lines.
    re.compile(r"^Corresponding\s+[Aa]uthor[s]?:.*$"),
    # "Author for correspondence:" Royal Society style.
    re.compile(r"^Author\s+for\s+correspondence:.*$", re.IGNORECASE),
    # Email/phone metadata lines.
    re.compile(r"^E-?mail(?:s)?:\s*\S+@.+$", re.IGNORECASE),
    re.compile(r"^Tel(?:\.|ephone)?:\s*\S.*$", re.IGNORECASE),
    re.compile(r"^Fax:\s*\S.*$", re.IGNORECASE),
    # Bare email line (one or more emails separated by whitespace/punct).
    re.compile(
        r"^[\w.+-]+@[\w.-]+\.[a-zA-Z]{2,6}(?:[\s,;]+[\w.+-]+@[\w.-]+\.[a-zA-Z]{2,6})*\s*$"
    ),
    # JAMA running header line.
    re.compile(
        r"^JAMA\s+Network\s+Open\.\s+20\d{2};\d+\(\d+\):e\d+\.\s*doi:10\.\d+/.+$"
    ),
    # JAMA category banner.
    re.compile(r"^JAMA\s+Network\s+Open\s+\|\s+\S.*$"),
    # Compound license + citation footer.
    re.compile(
        r"^Open\s+Access\.\s+This is an open access article.*doi:10\.\d+/.+$"
    ),
    # Standalone copyright line "© 20YY ...".
    re.compile(r"^©\s*20\d{2}\b.*$"),
    re.compile(r"^\(c\)\s*20\d{2}\b.*$", re.IGNORECASE),
    # JAMA sidebar pointer.
    re.compile(
        r"^Author affiliations and article information are listed at the end of (?:this article|the article)\.?\s*$"
    ),
    # JAMA visual-abstract sidebar.
    re.compile(r"^\+\s*Visual Abstract.*Supplemental content\s*$"),
    re.compile(r"^\+\s*Supplemental content\s*$"),
    # Compound copyright-footer.
    re.compile(
        r"^Received:\s+[\w ,]+\d{4}\.\s+(?:Revised:.*Accepted:.*"
        r"|Accepted:.*)\s*©.*$"
    ),
    # Parenthesized cite-line: "(Received DD Month YYYY; revised...)".
    re.compile(
        r"^\(Received\s+\d{1,2}\s+\w+\s+\d{4};\s+(?:revised|accepted).*\)\s*$",
        re.IGNORECASE,
    ),
    # Standalone open-access license footers.
    re.compile(
        r"^©\s+The Author\(s\)[,\s]+\d{4}\..*Cambridge University Press.*$",
        re.IGNORECASE,
    ),
    re.compile(
        r"^©\s+The Author\(s\)[,\s]+\d{4}\..*Published by .*$",
        re.IGNORECASE,
    ),
    re.compile(r"^This is an open access article distributed under.*$", re.IGNORECASE),
    # PMC supplementary-material footer.
    re.compile(
        r"^ELECTRONIC SUPPLEMENTARY MATERIAL\b.*$",
        re.IGNORECASE,
    ),
    # Running-header lines with "| <page>" or "<page> Author et al.".
    re.compile(r"^\S(?:[^|\n]{2,80})\|\s*\d{1,4}\s*$"),
    re.compile(r"^\d{1,4}\s+[A-ZÀ-ÿ][^\n]{1,60}\s+et al\.?\s*$"),
    # v2.4.6: "Q. XIAO ET AL." style running header — surname journal abbrev
    # used by CRSP, JESP, and many other 2-column journals. Accepts:
    #   "Q. XIAO ET AL."         single initial + surname
    #   "Q.M. XIAO ET AL."       two initials with internal period
    #   "Q. M. XIAO ET AL"       two initials with space (no trailing dot)
    # All-caps surname required (lowercase letters appear in regular prose
    # like "Most participants in the experimental condition were …").
    re.compile(
        r"^[A-Z]\.(?:\s*[A-Z]\.?)?\s+[A-Z]{2,}\s+ET\s+AL\.?\s*$"
    ),
    # v2.4.23 (NORMALIZATION_VERSION 1.8.8): prod-pdftotext-skew patterns.
    # Xpdf 4.00 (local Win) and poppler 25.03 (Railway Linux) emit
    # different line-break placements. P0 line patterns only match
    # COMPLETE single lines (anchored `^…$`). Prod's poppler often splits
    # what Xpdf serializes as a single line into multiple lines, so the
    # previous P0 patterns miss the strip on prod. Surfaced by v2.4.16
    # Phase 8 Tier 3 byte-diff (xiao_2021_crsp T2 vs T3 had +4897 bytes
    # of front-matter junk retained on prod).
    #
    # Strategy: add patterns for the specific front-matter junk lines
    # that prod's poppler emits as standalone lines (where Xpdf merged
    # them into longer banner lines). Conservative — each pattern matches
    # a complete line on its own.
    re.compile(r"^Submit your article to this journal\s*$", re.IGNORECASE),
    re.compile(r"^ARTICLE HISTORY\s*$"),
    re.compile(r"^Published online:?\s+\d{1,2}\s+\w+\s+\d{4}\.?\s*$", re.IGNORECASE),
    re.compile(r"^View related articles?\s*$", re.IGNORECASE),
    re.compile(r"^View Crossmark data\s*$", re.IGNORECASE),
    re.compile(r"^Citing articles?:\s+\d+\s+View citing articles?\s*$", re.IGNORECASE),
    re.compile(r"^Full Terms\s+&?\s+Conditions of access and use\.?\s*$", re.IGNORECASE),
    # Bare "Received DD Month YYYY" line (T&F masthead split by poppler)
    re.compile(r"^Received\s+\d{1,2}\s+\w+\s+\d{4}\s*$"),
    re.compile(r"^Accepted\s+\d{1,2}\s+\w+\s+\d{4}\s*$"),
    re.compile(r"^Revised\s+\d{1,2}\s+\w+\s+\d{4}\s*$"),

    # v2.4.19: same-surname two-author running header:
    #   "Kim and Kim" (Yeun Joon Kim & Junha Kim — amj_1, 14 occurrences)
    #   "Smith and Smith" / "Lee and Lee" (any X-and-X co-author pattern)
    # Anchored on `(\w+) and (?:that same word)` — distinct from prose
    # "John and Mary" (different names). Conservative: same surname only.
    re.compile(r"^(?P<surname>[A-Z][a-z]+) and (?P=surname)\s*$"),
    # v2.4.19: bare month-name page marker (AOM, ASA, T&F volume headers):
    #   "April" (amj_1: AOM April 2020 issue, 14 occurrences)
    #   "March" / "October" / etc.
    # Page-marker month names appear ALONE on a line as the issue indicator.
    # Body prose never uses a month name alone on a line.
    re.compile(
        r"^(?:January|February|March|April|May|June|July|August|"
        r"September|October|November|December)\s*$"
    ),
    # v2.4.16: bare uppercase running header with lowercase "et al." tail:
    #   "RECKELL et al."
    #   "SMITH et al"
    #   "VAN DER WAL et al."   (preceded by space-separated prefix tokens)
    # Distinct from the variants above (which require initials prefix or
    # all-caps ET AL). Appears as its own paragraph in IEEE / 2-column
    # journals between Abstract and Introduction and at every page break.
    # Globally safe: an all-caps surname + lowercase et al. on a line by
    # itself is unambiguously a running header — in-paragraph citations
    # never appear without parens / year.
    re.compile(
        r"^[A-Z]{2,}(?:\s+[A-Z]{2,}){0,3}\s+et\s+al\.?\s*$"
    ),
    # v2.4.16: Taylor & Francis "Supplemental data for this article …"
    # sidebar boilerplate. Exact-phrase pattern — safe globally.
    re.compile(
        r"^Supplemental\s+data\s+for\s+this\s+article\s+can\s+be\s+"
        r"accessed\s+(?:here|online|via)\.?\s*$",
        re.IGNORECASE,
    ),
    # v2.4.16: truncated affiliation that ends at "University of" with no
    # place name on the same line. Distinct from the full form
    # "Department of X, University of Y" (P0 already strips that via the
    # earlier pattern on line ~651) because of the trailing ``$`` after
    # "University of" — nothing follows on the line.
    re.compile(
        r"^Department\s+of\s+[A-Z][A-Za-z]+"
        r"(?:\s+and\s+[A-Z][A-Za-z\s]+?)?,\s*University\s+of\s*$"
    ),
    # v2.4.6: contact-line footer used by Taylor & Francis (CRSP, etc.):
    #   "CONTACT Gilad Feldman gfeldman@hku.hk; giladfel@gmail.com …"
    # The `CONTACT` keyword + name + email is distinctive enough to anchor
    # safely. Optional trailing affiliation / region tokens.
    re.compile(
        r"^CONTACT\s+[A-Z][\w'’-]+(?:\s+[A-Z][\w'’-]+)+\s+\S+@\S+.*$"
    ),
    # v2.4.6: prefixed author-contribution / corresponding-author footnotes
    # used by Collabra, eLife, PLOS, etc.:
    #   "a Contributed equally, joint first author"
    #   "b Contributed equally, joint first author"
    #   "c Corresponding Author: <name>, <affiliation>"
    re.compile(
        r"^[a-z]\s+(?:Contributed\s+equally|Corresponding\s+Author)\b.*$"
    ),
    # v2.4.6: standalone affiliation lines that recur on bottom of every
    # page in 2-column journals — "Department of <field>, University of
    # <place>, <region>".
    re.compile(
        r"^Department\s+of\s+[A-Z][A-Za-z]+(?:\s+and\s+[A-Z][A-Za-z]+)?,\s+"
        r"University\s+of\s+[A-Z][A-Za-z]+(?:\s+Kong)?,\s+.{2,80}$"
    ),
    # v2.4.7: journal-footer URLs and volume markers that recur on every
    # page in Nature / Sci Rep / Royal Society OA journals — pdftotext
    # extracts them as standalone lines that leak into body prose.
    re.compile(r"^rsos\.royalsocietypublishing\.org\s*$"),
    re.compile(r"^www\.nature\.com/(?:naturecommunications|scientificreports)\s*$"),
    re.compile(r"^Vol\.:\(\d{10,}\)\s*$"),  # "Vol.:(0123456789)" Springer marker
    # v2.4.7: standalone ORCID URL lines.
    re.compile(r"^https?://orcid\.org/\d{4}-\d{4}-\d{4}-[0-9X]{4}\s*$"),
    # v2.4.8: Academy of Management copyright footer (recurs on every AOM
    # journal — AMC, AMD, AMJ, AMLE, AMP, Annals; 9 papers in corpus).
    re.compile(
        r"^Copyright\s+of\s+the\s+Academy\s+of\s+Management,.*rights\s+reserved\.?.*$",
        re.IGNORECASE,
    ),
    # v2.4.8: ARTICLE HISTORY title + date block (chan_feldman + xiao).
    # The block leaks as a single pdftotext line in T&F two-column layouts.
    re.compile(
        r"^ARTICLE\s+HISTORY\s+Received\s+\d{1,2}\s+\w+\s+\d{4}"
        r"(?:\s+Revised\s+\d{1,2}\s+\w+\s+\d{4})?"
        r"\s+Accepted\s+\d{1,2}\s+\w+\s+\d{4}\s*$"
    ),
    # v2.4.8: Standalone "Open Access" line that BMC / PMC journals stamp
    # at the top of each page. Bare two-word marker — anchored to top of
    # line, requires nothing else.
    re.compile(r"^Open\s+Access\s*$"),
    # v2.4.8: Elsevier (JESP, JEP) compound footer with DOI + dates +
    # copyright + "All rights reserved." on a single line. Distinctive
    # enough to anchor on `Received\s+\d{1,2}\s+\w+\s+\d{4};` near the
    # start.
    re.compile(
        r"^(?:https?://doi\.org/\S+\s+)?Received\s+\d{1,2}\s+\w+\s+\d{4};"
        r".*(?:©|All\s+rights\s+reserved\.?).*$"
    ),
]


# v2.4.8: garbled OCR headers — "ACK NOW L EDGEM EN TS", "DATA AVA IL A
# BILIT Y STATEM ENT" etc. (brjpsych_1 + similar). The pdftotext extraction
# collapses letter-spaced display text by inserting spaces between groups
# of letters; the resulting line is unintelligible but has a distinctive
# signature: ≥4 capital-letter clusters separated by single spaces, total
# alpha characters ≥ 12.
_GARBLED_OCR_HEADER_RE = re.compile(
    r"^(?:[A-Z]{1,4}\s+){3,}[A-Z]{1,4}(?:\s+[A-Z]{1,4}){0,8}\s*$"
)


def _rejoin_garbled_ocr_headers(text: str) -> str:
    """Re-knit letter-spaced display-typography headers.

    pdftotext renders display-typography acknowledgments / data-availability
    headers (where the PDF uses letter-spacing for emphasis) as:

        ACK NOW L EDGEM EN TS

    which is unparseable as either prose or a heading. This pass detects
    such lines (≥ 4 capital-letter clusters separated by single spaces) and
    collapses them by removing the spaces, recovering ``ACKNOWLEDGMENTS``.

    Conservative trigger: the entire line must consist of all-caps token
    groups separated by single spaces, with each token ≤ 4 chars and ≥ 4
    tokens. Real all-caps headings like ``CONCLUSIONS AND RELEVANCE`` have
    longer tokens (≥ 5 chars) and pass through unchanged.
    """
    if not text:
        return text
    lines = text.split("\n")
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or len(stripped) < 12:
            continue
        if not _GARBLED_OCR_HEADER_RE.match(stripped):
            continue
        # Compact: remove all whitespace between caps.
        compact = re.sub(r"\s+", "", stripped)
        if len(compact) < 8:
            continue
        # Preserve leading whitespace; replace rest.
        lead = line[: len(line) - len(line.lstrip())]
        lines[i] = lead + compact
    return "\n".join(lines)


# v2.4.33 (NORMALIZATION_VERSION 1.9.1): lowercase letter-spaced display
# labels. Elsevier-family journals (e.g. JESP 2009-era FlashReports) letter-
# space the front-matter box labels "article info" and "abstract" for
# typographic emphasis. pdftotext serializes each as a run of single
# lowercase characters separated by single spaces, one label per line:
#       a r t i c l e
#       i n f o
#       a b s t r a c t
# The all-caps sibling _rejoin_garbled_ocr_headers does not fire (its regex
# requires capital-letter clusters). Left uncollapsed, "a b s t r a c t" is
# never recognised by the section taxonomy, so the Abstract section heading
# is lost on every paper with this typography. This pass collapses such
# lines; the recovered "abstract" then resolves through the normal section
# taxonomy ({"abstract"} -> SectionLabel.abstract) exactly like a paper that
# printed the label without letter-spacing.
_LETTERSPACED_LABEL_RE = re.compile(r"^(?:[a-z] ){3,}[a-z]$")


def _rejoin_letterspaced_lowercase_labels(text: str) -> str:
    """H0b: collapse lowercase letter-spaced display labels (Elsevier).

    Sibling of _rejoin_garbled_ocr_headers (which handles the all-caps
    variant at render time); this lowercase variant must run pre-sectioning
    so a recovered "abstract" label can be promoted to the Abstract heading.

    Conservative trigger: the ENTIRE line must be >=4 single lowercase
    letters separated by single spaces, and the collapsed form must contain
    a vowel (rejects spaced-out consonant runs / variable lists).
    """
    if not text:
        return text
    lines = text.split("\n")
    changed = False
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or not _LETTERSPACED_LABEL_RE.match(stripped):
            continue
        compact = stripped.replace(" ", "")
        if not any(v in compact for v in "aeiou"):
            continue
        lead = line[: len(line) - len(line.lstrip())]
        lines[i] = lead + compact
        changed = True
    return "\n".join(lines) if changed else text


# Cycle 9b (v2.4.61) / 14 (v2.4.66) — context discriminator used by S9
# Pattern A to protect table sample-size values from being stripped as
# page numbers. Cycle 14 added `<>=%` so lines like `<.001` (p-value),
# `S<= 10000`, `>= 0.05` are detected as table-cell content, not prose.
_NUMERIC_ONLY_LINE_RE = re.compile(r"^[\d\s.,()+\-*∗;:<>=%]+$")


def _is_numeric_only_line(line: str) -> bool:
    """True if the (stripped) line contains only digits + common stat-table
    punctuation (decimal point, comma, parens, asterisks/sig-stars, minus,
    plus, semicolon, colon, whitespace) AND has at least one digit. Used as
    a "this line is a table cell, not prose" signal."""
    s = line.strip()
    if not s:
        return False
    if not _NUMERIC_ONLY_LINE_RE.match(s):
        return False
    return any(c.isdigit() for c in s)


def _is_in_numeric_block(lines: list[str], idx: int) -> bool:
    """True if the line at ``idx`` sits in a vertical block of numeric-only
    lines — its nearest non-blank neighbor above OR below is itself
    numeric-only. Used by S9 to distinguish per-page markers (isolated in
    prose) from table cells (in a column of other numeric values)."""
    for direction in (-1, +1):
        i = idx + direction
        while 0 <= i < len(lines) and not lines[i].strip():
            i += direction
        if 0 <= i < len(lines) and _is_numeric_only_line(lines[i]):
            return True
    return False


def _strip_page_footer_lines(text: str) -> str:
    """P0: drop page-footer / running-header lines anywhere in the document.

    Curated patterns only. Line is dropped on explicit match; everything else
    is preserved. CHEAP variant of F1 — does not stitch sentence halves that
    spanned the page break, just removes the junk between them.
    """
    if not text:
        return text
    out_lines: list[str] = []
    dropped_any = False
    for line in text.split("\n"):
        stripped = line.strip()
        if stripped and any(
            p.match(stripped) for p in _PAGE_FOOTER_LINE_PATTERNS
        ):
            dropped_any = True
            continue
        out_lines.append(line)
    if not dropped_any:
        return text
    cleaned = "\n".join(out_lines)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned


# ── P1 (v2.4.16 / NORMALIZATION_VERSION 1.8.4) ──────────────────────────
# Front-matter metadata-leak paragraph strip.
#
# pdftotext's reading-order serialization linearizes a two-column article by
# emitting the article's left-column (Abstract → Introduction body) and then
# the right-column / inter-column metadata (corresponding-author block,
# acknowledgments footnote, supplemental-data sidebar, "A previous version
# of this article was presented…" note, IEEE/CC license blob, running
# headers like "RECKELL et al."). Those metadata fragments end up as
# standalone single-line paragraphs INLINED between body paragraphs of the
# Introduction — visible to a human reader but invisible to char-ratio /
# Jaccard verifiers (the tokens are present, just in the wrong section).
#
# Confirmed leak instances at v2.4.15 (broad-read 2026-05-13):
#   xiao_2021_crsp (APA / T&F): "Supplemental data for this article…",
#       "Department of Psychology, University of" (truncated affiliation).
#   amj_1 (AOM):                "We wish to thank our editor Jill Perry-Smith
#       and three anonymous reviewers… Correspondence concerning this article
#       should be addressed to…" (one long pdftotext-serialized line).
#   amle_1 (AOM):               "We thank Steven Charlier… reviewers for
#       offering highly constructive feedback…", "A previous version of this
#       article was presented at the Management Education and Development…".
#   ieee_access_2 (IEEE):       "This work is licensed under a Creative
#       Commons Attribution 4.0 License… CONFLICT OF INTEREST…",
#       "RECKELL et al." (bare running header).
#
# Strategy: paragraph-level strip (\n\n-bounded) with two safety gates:
#   1. Pattern must match the START of the paragraph — anchored, not
#      free-floating.
#   2. Position gate: paragraph must begin in the first ``max(8000,
#      len(text) // 6)`` characters of the document. This protects the
#      legitimate Acknowledgments / Funding / Affiliations sections that
#      live at the end (e.g. xiao's `## Acknowledgments / We thank Siu Kit
#      Yeung…` at ~25% of doc, amle_1's affiliations block at ~90%).
#
# Two pattern groups:
#   - ``_FRONTMATTER_LEAK_PARA_PATTERNS`` — multi-sentence acknowledgments
#     / previous-version / license blocks. Anchored on a distinctive
#     opening phrase. The pattern allows the paragraph to be of any length
#     up to ``_FRONTMATTER_LEAK_MAX_PARA_CHARS``.
#   - ``_FRONTMATTER_LEAK_LINE_PATTERNS`` — short single-line orphan
#     fragments (running headers, truncated affiliations, supplemental-
#     data sidebars). These are ultra-specific patterns that match a full
#     bounded line.
_FRONTMATTER_LEAK_MAX_PARA_CHARS = 1500

_FRONTMATTER_LEAK_PARA_PATTERNS: list[re.Pattern[str]] = [
    # Acknowledgments footnote serialized as a paragraph:
    #   "We wish to thank our editor Jill Perry-Smith and three anonymous
    #    reviewers for their insightful and constructive feedback. We also
    #    thank Angelo DeNisi, Matthew Feinberg…"
    # Anchor: starts with "We thank" or "We wish to thank" AND the
    # paragraph contains at least one of (reviewers|editor|feedback|
    # comments|suggestions|insights|helpful) within the first 300 chars.
    # The keyword guard rejects body prose that legitimately starts with
    # "We thank participants for…".
    re.compile(
        r"^We\s+(?:wish\s+to\s+)?thank\s+[A-Z].{0,300}?\b"
        r"(?:reviewers?|editor|feedback|comments?|suggestions?|insights?|helpful)\b",
        re.IGNORECASE | re.DOTALL,
    ),
    # "A previous version of this article was presented/published at…"
    # (AOM, T&F, Sage — anywhere a conference / proceedings note leaks).
    re.compile(
        r"^A\s+previous\s+version\s+of\s+this\s+article\s+was\s+"
        r"(?:presented|published)\b",
        re.IGNORECASE,
    ),
    # IEEE / Creative Commons license block. The full block typically chains
    # "This work is licensed under… Corresponding author: <name>… CONFLICT
    # OF INTEREST…". Anchoring on the opening is enough.
    re.compile(
        r"^This\s+work\s+is\s+licensed\s+under\s+(?:a\s+|the\s+)?"
        r"Creative\s+Commons\b",
        re.IGNORECASE,
    ),
    # APA-style standalone corresponding-author paragraph (when not already
    # caught by P0's "CONTACT <name>" single-line rule because the
    # serialization put it on its own bounded paragraph rather than a one-
    # line "Corresponding Author:" header).
    re.compile(
        r"^Correspondence\s+concerning\s+this\s+article\s+should\s+be\s+"
        r"addressed\s+to\b",
        re.IGNORECASE,
    ),
]

# Note: the three "globally safe" LINE patterns originally drafted here
# (Supplemental-data sidebar, truncated affiliation, bare uppercase running
# header) were promoted into P0's ``_PAGE_FOOTER_LINE_PATTERNS`` in
# v2.4.16 once it became clear that the running-header variant recurs at
# every page break (e.g. ieee_access_2 emits ``RECKELL et al.`` between
# Abstract / Introduction AND again at ~18% of the doc, past P1's position
# gate). P0 is the correct home for those patterns — they have zero
# false-positive risk in the body. P1 keeps only the multi-sentence
# paragraph-level patterns that DO carry false-positive risk in the late
# Acknowledgments section and need the position gate.
_FRONTMATTER_LEAK_LINE_PATTERNS: list[re.Pattern[str]] = []


def _strip_frontmatter_metadata_leaks(text: str) -> str:
    """P1: strip orphan front-matter metadata lines.

    Targets standalone single-line paragraphs that pdftotext serializes
    mid-Introduction via right-column reading order:
      - acknowledgments footnote on one long line ("We wish to thank …
        reviewers …")
      - "A previous version of this article was presented at …" note
      - IEEE / Creative Commons license blob
      - "Correspondence concerning this article should be addressed to …"
      - "Supplemental data for this article can be accessed here."
      - Truncated affiliation ending at "University of" (no place name)
      - Bare "RECKELL et al." style running header

    Operates at the LINE level (not paragraph level) because pdftotext often
    emits the leak with only a single ``\\n`` separator from the body
    paragraph above it — the paragraph-level (``\\n\\n``-bounded) view
    would absorb the leak into the body paragraph and miss it.

    Position-gated to the first ``max(8000, len(text) // 6)`` characters of
    the document so the legitimate Acknowledgments / Funding /
    Affiliations sections at the END are preserved unchanged.

    Cross-paper coverage (confirmed at v2.4.15): xiao_2021_crsp, amj_1,
    amle_1, ieee_access_2. See LESSONS / NORMALIZATION_VERSION 1.8.4
    history for the discovery context.
    """
    if not text or len(text) < 200:
        return text

    cutoff = max(8000, len(text) // 6)
    # Snap the cutoff to a line boundary so we don't bisect a line.
    nl = text.rfind("\n", 0, cutoff)
    split = (nl + 1) if nl != -1 else cutoff
    front, back = text[:split], text[split:]

    out_lines: list[str] = []
    dropped = False
    for line in front.split("\n"):
        stripped = line.strip()
        if not stripped:
            out_lines.append(line)
            continue
        if len(stripped) > _FRONTMATTER_LEAK_MAX_PARA_CHARS:
            out_lines.append(line)
            continue
        matched = (
            any(p.match(stripped) for p in _FRONTMATTER_LEAK_LINE_PATTERNS)
            or any(p.match(stripped) for p in _FRONTMATTER_LEAK_PARA_PATTERNS)
        )
        if matched:
            dropped = True
            continue
        out_lines.append(line)

    if not dropped:
        return text

    cleaned = "\n".join(out_lines) + back
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned


# v2.4.20 (NORMALIZATION_VERSION 1.8.7): rejoin pdftotext-space-broken
# compound words.
#
# Soft-hyphenation artifact: PDFs use Unicode soft-hyphen (U+00AD) or
# letter-spacing for line-break-aware hyphenation. pdftotext removes the
# soft-hyphen but leaves a single SPACE between the two halves. Example:
# the word "experiments" in xiao_2021_crsp's abstract renders as
# "experi ments" — visible as a typo to a human reader and breaks every
# downstream NLP / search / citation-extraction tool that relies on word
# tokens.
#
# Note: S7 (hyphenation repair) handles `\\nword-\\nword2` → `\\nwordword2`
# but ONLY when the hyphen is still present (the line-break-then-hyphen
# pattern). pdftotext's space-broken form has no hyphen — different bug,
# different fix.
#
# Strategy: curated list of (prefix, suffix-set) pairs where the joined
# form is unambiguously a single English word. The pairs were sourced
# from xiao_2021_crsp Phase 5d AI verify (2026-05-14): experi/ments,
# addi/tion, discre/pancies, con/ducted, con/cerning, con/fined,
# presenta/tion, ques/tionnaires, experi/ences. Expanded with sibling
# pairs in the same morphological family.
#
# Conservative: every (prefix, suffix) listed produces a single valid
# English word when joined. Rejecting body context: the patterns require
# both halves to be lowercase and at word boundaries. Phrases like
# "they were experi ments" → "they were experiments" — the surrounding
# context is fine.
_DEHYPHEN_REJOIN_PAIRS: list[tuple[str, str]] = [
    (r"experi",  r"(?:ments?|mental|mentally|ences?|enced|mentation)"),
    (r"addi",    r"(?:tions?|tionally|tive|tives)"),
    (r"discre",  r"(?:pancy|pancies|tion|tionary)"),
    (r"con",     r"(?:cerning|ducted|ducting|fined|firmed|sequently|"
                 r"sistent|sistently|cluded|sists|sisted|siderable|"
                 r"siderably|trolled|trolling|fronted|fronting|firmation)"),
    (r"ques",    r"(?:tion|tions|tionnaire|tionnaires|tioned|tioning)"),
    (r"presenta", r"(?:tion|tions|tional)"),
    (r"discus",  r"(?:sion|sions|sed)"),
    (r"informa", r"(?:tion|tions|tive|tional)"),
    (r"differ",  r"(?:ence|ences|ent|ently|ential|entiate|entiated)"),
    (r"repli",   r"(?:cation|cations|cate|cates|cated|cating)"),
    (r"refer",   r"(?:ence|ences|ential|enced|encing)"),
    (r"identi",  r"(?:fied|fies|fy|fication)"),
    (r"specifi", r"(?:cation|cations|cally|ed)"),
    (r"reliabi", r"(?:lity|lities)"),
    (r"genera",  r"(?:tion|tions|lly|lize|lized|lization)"),
    (r"explana", r"(?:tion|tions|tory)"),
    (r"transla", r"(?:tion|tions|ted|ting)"),
    (r"observa", r"(?:tion|tions|tional)"),
    (r"opera",   r"(?:tion|tions|tional|tionalize|tionalized)"),
    (r"varia",   r"(?:tion|tions|ble|bles|bility)"),
    (r"correla", r"(?:tion|tions|ted|ting|tional)"),
    (r"applica", r"(?:tion|tions|ble|bility)"),
    (r"interpre", r"(?:tation|tations|t|ted|ting|tive)"),
]

_DEHYPHEN_PATTERNS: list[re.Pattern[str]] = [
    re.compile(rf"\b{p}\s+{s}\b")
    for p, s in _DEHYPHEN_REJOIN_PAIRS
]


def _rejoin_space_broken_compounds(text: str) -> str:
    """S7a: rejoin pdftotext-broken compound words.

    Applies the curated (prefix, suffix) regex list. Each pattern is
    ``\\bprefix\\s+suffix\\b`` — the ``\\s+`` separator matches a space, a
    tab, OR a newline, because pdftotext breaks these compounds two ways:
    ``experi ments`` (soft hyphen dropped, a space left) and
    ``repli\\ncations`` (line-wrapped — no hyphen, or a soft hyphen that S6
    has already stripped). The whole separating run is removed, so the
    compound rejoins regardless of separator. Stripping only the literal
    space (the pre-v2.4.58 behavior) left newline-separated compounds
    un-joined until a second pipeline pass — that broke idempotency, since
    S8 converts the mid-word newline to a space only AFTER this step runs.
    Idempotent and pipeline-order-independent.
    """
    if not text:
        return text
    for pat in _DEHYPHEN_PATTERNS:
        text = pat.sub(lambda m: re.sub(r"\s+", "", m.group(0)), text)
    return text


def _fix_hyphenated_line_breaks(text: str) -> str:
    """H1: join lines split mid-word at a hyphen by pdftotext column wrap.

    Conservative: always keeps the hyphen, only removes the newline. Both
    real compounds (``Meta-\\nProcesses`` → ``Meta-Processes``) and line-wrap
    artifacts (``socio-\\neconomic`` → ``socio-economic``) end up as valid
    hyphenated forms.

    Skips ``<table>`` blocks, fenced code, markdown headings, hyphens after
    non-alpha characters (date ranges), and continuation lines starting with
    non-alpha (markers, brackets).
    """
    lines = text.split("\n")
    in_table = False
    in_fence = False
    i = 0
    while i < len(lines):
        line = lines[i]
        ls = line.strip()
        if ls.startswith("```"):
            in_fence = not in_fence
            i += 1
            continue
        if not in_fence:
            if "<table" in ls:
                in_table = True
            if "</table>" in ls:
                in_table = False
                i += 1
                continue
        if in_fence or in_table:
            i += 1
            continue
        if ls.startswith("#"):
            i += 1
            continue
        if (
            i + 1 < len(lines)
            and len(line) >= 3
            and line.endswith("-")
            and line[-2].isalpha()
        ):
            next_line = lines[i + 1]
            ns = next_line.strip()
            if ns and ns[0].isalpha():
                lines[i] = line + ns
                del lines[i + 1]
                continue
        i += 1
    return "\n".join(lines)


@dataclass
class NormalizationReport:
    level: str
    version: str = NORMALIZATION_VERSION
    steps_applied: list[str] = field(default_factory=list)
    steps_changed: list[str] = field(default_factory=list)
    changes_made: dict[str, int] = field(default_factory=dict)
    footnote_spans: tuple[tuple[int, int], ...] = ()  # pre-strip char offsets
    page_offsets: tuple[int, ...] = ()                 # post-strip body page offsets

    def _track(self, step_code: str, before: str, after: str, metric_name: str):
        # ``steps_applied`` records every step that ran (kept for backward
        # compatibility with tests and diagnostics that want to see the full
        # pipeline order). ``steps_changed`` records only steps that actually
        # modified the text — this is the field diagnostics should prefer
        # when they want to know what the pipeline *did* on a given input.
        # See MetaESCI request D7.2.
        self.steps_applied.append(step_code)
        if before != after:
            self.steps_changed.append(step_code)
            diff = len(before) - len(after)
            if diff != 0:
                self.changes_made[metric_name] = abs(diff)

    def to_dict(self) -> dict:
        return {
            "level": self.level,
            "version": self.version,
            "steps_applied": self.steps_applied,
            "steps_changed": self.steps_changed,
            "changes_made": self.changes_made,
            "footnote_spans": [list(s) for s in self.footnote_spans],
            "page_offsets": list(self.page_offsets),
        }


# v2.4.38 (NORMALIZATION_VERSION 1.9.4): recover U+2212 minus signs that
# pdftotext maps to the digit '2' on certain fonts (e.g. efendic_2022 — every
# confidence interval reads "[20.92, 20.30]" for "[−0.92, −0.30]", every
# "r = 2.74" for "r = −.74"). Two self-gating, context-safe signatures:
#   Rule 1 — a bracketed numeric pair "[A, B]" DESCENDING as written (A > B,
#   impossible for a CI / range) that becomes a valid ASCENDING interval once
#   the leading '2' of a decimal-bearing bound is read as '−'. Integer-only
#   brackets (citation lists like "[25, 3]") never convert.
#   Rule 2 — "r = 2.<digits>": a Pearson r cannot exceed 1, so any
#   "r = 2.something" is a corrupted "r = −.something".
# An ascending CI or a plausible correlation is never touched.
_BRACKET_PAIR_RE = re.compile(r"\[\s*(-?\d*\.?\d+)\s*,\s*(-?\d*\.?\d+)\s*\]")
_CORRUPT_R_RE = re.compile(r"(\br\s*(?:\(\s*\d+\s*\)\s*)?=\s*)2(\.\d+)")


def recover_corrupted_minus_signs(text: str) -> str:
    """W0b: recover pdftotext '2'-for-U+2212 minus-sign corruption."""
    if not text:
        return text

    def _conv(tok: str) -> str:
        # A '2'-prefixed decimal token reads as a negative: 20.92 -> -0.92.
        if tok.startswith("2") and "." in tok:
            return "-" + tok[1:]
        return tok

    def _fix_bracket(m: "re.Match[str]") -> str:
        a_str, b_str = m.group(1), m.group(2)
        try:
            a, b = float(a_str), float(b_str)
        except ValueError:
            return m.group(0)
        if a <= b:
            return m.group(0)  # ascending — genuine interval, leave it
        a2_str, b2_str = _conv(a_str), _conv(b_str)
        if a2_str == a_str and b2_str == b_str:
            return m.group(0)  # nothing convertible (e.g. integer bracket)
        try:
            if float(a2_str) <= float(b2_str):
                return f"[{a2_str}, {b2_str}]"
        except ValueError:
            pass
        return m.group(0)

    t = _BRACKET_PAIR_RE.sub(_fix_bracket, text)
    t = _CORRUPT_R_RE.sub(r"\1-\2", t)
    return t


# v2.4.39 (NORMALIZATION_VERSION 1.9.5): recover the '<' comparison operator
# that pdftotext maps to a backslash '\' on certain fonts (e.g. efendic_2022 —
# every "p < .001" reads "p \ .001", every table p-value cell "<.001" reads
# "\.001", the legacy Wiley DOI "13:1<1::AID-…" reads "13:1\1::AID-…"). A
# literal backslash never legitimately occurs glued to a numeral in extracted
# academic-PDF text — '\' is not a prose character and the renderer adds no
# markdown escapes — so a backslash immediately followed (optional single
# space) by a digit or a '.'-prefixed decimal is unambiguously a corrupted
# '<'. The space, if any, is preserved so "p \ .05" -> "p < .05".
_CORRUPT_LT_RE = re.compile(r"\\(\s?)(?=\.?\d)")


def recover_corrupted_lt_operator(text: str) -> str:
    """W0c: recover pdftotext '<'-as-backslash glyph corruption."""
    if not text or "\\" not in text:
        return text
    return _CORRUPT_LT_RE.sub(r"<\1", text)


# v2.4.40 (NORMALIZATION_VERSION 1.9.6): recover standalone '2'-for-U+2212
# minus corruption on point-estimate tokens/cells that the bracket-pair rule
# (recover_corrupted_minus_signs) cannot reach because they carry no bracket
# of their own. The discriminator is a structural invariant of statistics,
# not a heuristic: a point estimate ALWAYS lies inside its own reported
# confidence interval. So when a token reads "2X.XX" and the SAME record (a
# table row <tr>…</tr>, or a single text line) carries a CI bracket [lo, hi]
# such that the de-corrupted value -X.XX falls inside [lo, hi] while the
# literal 2X.XX falls outside, the token is unambiguously a corrupted
# negative. A genuine literal 2X.XX is never "recovered": that would require
# a stats record whose estimate sits outside the CI it is paired with — which
# does not occur. efendic_2022 Tables 2-5 every negative B-coefficient cell +
# the Mposterior mediation estimates are recovered this way; the bracketed
# CIs themselves are already handled upstream by recover_corrupted_minus_signs.
_CI_PAIR_BRACKET_RE = re.compile(r"\[\s*(-?\d*\.?\d+)\s*,\s*(-?\d*\.?\d+)\s*\]")
# A corrupted negative point estimate: a leading '2' (the mis-mapped minus)
# glued to a small decimal of the form D.DD — one integer digit, then the
# fraction. Not preceded by a digit/dot (so we never match inside 120.26),
# AND not preceded by a literal minus (so we never re-recover an already-
# recovered `-2.68`, which would yield `--.68`). Cycle 10 (v2.4.62) — the
# missing `-` in the lookbehind was the cause of `normalize_text` non-
# idempotence on ip-feldman 2025 (the value first recovers correctly as
# `-2.68`, then pass 2 re-fires and corrupts it to `--.68`).
_CORRUPT_NEG_TOKEN_RE = re.compile(r"(?<![\d.\-])2(\d?\.\d+)\b")
_TABLE_ROW_RE = re.compile(r"<tr\b.*?</tr>", re.DOTALL | re.IGNORECASE)


# Cycle 11 (v2.4.63) / 12 (v2.4.64) — proximity gate for the CI-pairing recovery.
#
# In stat reporting a BARE bracket `[lo, hi]` attaches to the IMMEDIATELY-
# preceding point estimate; a LABELED bracket `CI = [lo, hi]` or
# `95% CI [lo, hi]` can attach to ANY earlier point estimate on the same
# row (the SD/SE/df-pair tokens in between are descriptive of the same
# estimate). The cycle 11 proximity gate treated both as needing strict
# adjacency, which broke efendic's body-line recovery
#   `Mposterior = 20.54, SD=0.04, CI = [-0.61, -0.47]`
# where `, SD=` falsely tripped the "new stat label" sentence-break check.
#
# Cycle 12 fix: discriminate LABELED vs BARE brackets.
#   - LABELED bracket (`CI =`/`95% CI`/`CI:` immediately precedes `[`):
#     pairs with any candidate token in its record (the old wide rule).
#   - BARE bracket: pairs ONLY with candidates within 30 chars + no
#     sentence break (period/semicolon + space — NOT comma + new label,
#     because stat-row labels are comma-separated by convention).
#
# This keeps the majumder fix (bare bracket far from `2.01`) AND
# preserves efendic-style labeled CIs that pair across SD/SE annotations.
_CI_PAIR_MAX_GAP = 30
# Bare-bracket sentence break: only period/semicolon + space.  A comma is
# NOT a break because stat rows are comma-separated.  The majumder false-
# positive is now caught by the per-bracket proximity check (the bare
# bracket sits ~50 chars after `2.01` — beyond _CI_PAIR_MAX_GAP).
_SENTENCE_BREAK_RE = re.compile(r"[.;]\s")
# A bracket is "labeled" when prefixed by `CI`, `95 % CI`, or similar
# directly before the opening `[`. Allow optional whitespace and an `=` /
# `:` between the label and the bracket.
_CI_LABEL_PREFIX_RE = re.compile(r"(?:\bCI|\b\d+\s*%\s*CI)\s*[=:]?\s*$", re.IGNORECASE)
# Cycle 13 (v2.4.65) — even a LABELED CI cannot reach back ACROSS an
# independent-test-statistic label. The discriminator: between the
# candidate token and the labeled bracket, allow ONLY variance-family
# labels (SD, SE, M, Mdn, Var, CI, 95% CI itself, %), reject anything
# that introduces a NEW estimate (t, F, p, d, g, η, χ, r, R², β, OR, RR,
# HR, B, Z, Q).
#
# Why: `Mposterior = 20.54, SD=0.04, CI = [-0.61, -0.47]` (efendic) has
# only SD between the candidate and the CI — same estimate, paired OK.
# `M = 5.37, SD = 2.01, t(1827) = 1.83, p tukey = .067, d = 0.09, 95% CI
# [-0.006, 0.18]` (majumder) has t, p, d — three independent estimates —
# between `2.01` and the CI; the CI is for `d`, not `2.01`. Reject.
_INDEPENDENT_STAT_BETWEEN_RE = re.compile(
    r"(?:^|[,;\s])\s*"
    r"(?:t|F|d|g|R|R²|β|γ|B|OR|RR|HR|H|Q|Z|f|n|η|χ|η²|χ²|r|"
    r"p\s+tukey|p\s+holm|p\s+bonf(?:erroni)?|p\s+adj|"
    r"\bp(?:\s*[=<>]))"
    r"\s*[=(\(]",
)


def _recover_minus_in_record(record: str) -> str:
    """Recover '2X.XX' tokens in a single record (a table row or a text line)
    by pairing each with a CI bracket present in the same record."""
    # Each entry: (lo, hi, (bs, be), is_labeled). `is_labeled` is True when
    # the bracket is prefixed by `CI`/`95% CI`/etc. — see cycle 12 notes
    # at _CI_LABEL_PREFIX_RE.
    brackets: list[tuple[float, float, tuple[int, int], bool]] = []
    for m in _CI_PAIR_BRACKET_RE.finditer(record):
        try:
            lo, hi = float(m.group(1)), float(m.group(2))
        except ValueError:
            continue
        if lo > hi:
            continue  # not a well-formed interval
        # Look back ≤8 chars for a `CI` / `95 % CI` label.
        bs, be = m.span()
        prefix = record[max(0, bs - 8): bs]
        is_labeled = bool(_CI_LABEL_PREFIX_RE.search(prefix))
        brackets.append((lo, hi, (bs, be), is_labeled))
    if not brackets:
        return record

    def _sub(m: "re.Match[str]") -> str:
        # Never touch a token that lies inside a bracket span (a CI bound).
        for _lo, _hi, (bs, be), _lab in brackets:
            if bs <= m.start() < be:
                return m.group(0)
        frac = m.group(1)
        try:
            literal = float("2" + frac)
            recovered = float("-" + frac)
        except ValueError:
            return m.group(0)
        # Cycle 12: pick the NEAREST bracket whose pairing rules accept this
        # token. LABELED brackets accept any candidate in the record (legacy
        # wide rule — efendic body line `Mposterior = 20.54, SD=0.04,
        # CI = [-0.61, -0.47]` is the canonical case). BARE brackets only
        # accept the immediately-preceding stat (within 30 chars, no
        # sentence break) — this is what blocks the majumder false-positive
        # `M = 5.37, SD = 2.01, t = ..., d = 0.09 [-1.86, 0.04]`.
        token_end = m.end()
        nearest = None
        nearest_dist = None
        for lo, hi, (bs, be), is_labeled in brackets:
            if bs < token_end:
                continue
            gap = bs - token_end
            intervening = record[token_end:bs]
            if is_labeled:
                # Labeled bracket: relaxed proximity, but still reject if
                # an independent-stat label intervenes. The label gates the
                # pairing to the variance-family (SD/SE/M/CI/%) of the
                # SAME estimate. See _INDEPENDENT_STAT_BETWEEN_RE notes.
                if _INDEPENDENT_STAT_BETWEEN_RE.search(intervening):
                    continue
            else:
                if gap > _CI_PAIR_MAX_GAP:
                    continue
                if _SENTENCE_BREAK_RE.search(intervening):
                    continue
            if nearest_dist is None or gap < nearest_dist:
                nearest = (lo, hi)
                nearest_dist = gap
        if nearest is None:
            return m.group(0)
        lo, hi = nearest
        in_recovered = (lo - 0.005) <= recovered <= (hi + 0.005)
        in_literal = (lo - 0.005) <= literal <= (hi + 0.005)
        if in_recovered and not in_literal:
            return "-" + frac
        return m.group(0)

    return _CORRUPT_NEG_TOKEN_RE.sub(_sub, record)


def recover_minus_via_ci_pairing(text: str) -> str:
    """W0d: recover standalone '2'-for-minus corruption via point-estimate ∈ CI.

    Operates on whole records — a ``<tr>…</tr>`` table row, or a single text
    line — so a corrupted ``2X.XX`` point estimate can be checked against the
    confidence interval reported alongside it. See the module comment above
    ``_CI_PAIR_BRACKET_RE`` for the invariant this relies on.
    """
    if not text or "2" not in text:
        return text
    text = _TABLE_ROW_RE.sub(lambda m: _recover_minus_in_record(m.group(0)), text)
    out = []
    for line in text.split("\n"):
        if "[" in line and "2" in line:
            out.append(_recover_minus_in_record(line))
        else:
            out.append(line)
    return "\n".join(out)


# v2.4.44 (NORMALIZATION_VERSION 1.9.8): decompose Latin typographic
# ligatures (ﬀ ﬁ ﬂ ﬃ ﬄ ﬅ ﬆ, U+FB00-FB06). pdftotext preserves these
# presentation-form glyphs verbatim, so words render as "conﬁdent" /
# "inﬂuence" — broken for search, word matching, and any downstream NLP.
# An explicit ASCII table is used (not a scoped NFKC pass): NFKC of U+FB05
# yields "ſt" with a non-ASCII LONG S, and meta-science output must stay
# ASCII. This is the SINGLE shared helper for all THREE text channels — the
# S3 body step (normalize_text, below), table-cell cleaning, and the render
# post-process. Table cells and figure/table captions bypass normalize_text
# entirely, so a body-only fix leaves them showing raw ligature glyphs.
_LIGATURE_MAP = {
    "ﬀ": "ff", "ﬁ": "fi", "ﬂ": "fl",
    "ﬃ": "ffi", "ﬄ": "ffl", "ﬅ": "st", "ﬆ": "st",
}
_LIGATURE_RE = re.compile("[ﬀ-ﬆ]")


def decompose_ligatures(text: str) -> str:
    """Decompose Latin typographic ligatures (U+FB00-FB06) to ASCII."""
    if not text:
        return text
    return _LIGATURE_RE.sub(lambda m: _LIGATURE_MAP[m.group(0)], text)


# ── PUA glyph recovery — Adobe Symbol font (shared, v2.4.54) ───────────────
# Some PDF/DOCX producers embed the Adobe "Symbol" font with no ToUnicode
# CMap, so pdftotext / mammoth surface each glyph as a Private-Use-Area
# codepoint U+F000+<symbol-byte> — β reads as U+F062, χ as U+F063, • as
# U+F0B7 (e.g. efendic-style "χ²(1) = 0.34" arriving as a raw  2(1)).
# A PUA codepoint is never a legitimate character in extracted academic text
# — it carries no Unicode identity, it is purely a font-encoding artifact —
# so mapping the Adobe Symbol StandardEncoding (a fixed, decades-stable
# standard) back to real Unicode is a zero-false-positive, fully general
# recovery keyed on the structural signature "codepoint in the Symbol-font
# PUA block U+F020-F0FF". Greek stays Greek (CLAUDE.md hard rule 4 — the A5
# step transliterates β→"beta" for ASCII-form callers; the rendered .md keeps
# β). SHARED by all three text channels: normalize_text's W0e step (body),
# tables/cell_cleaning (Camelot layout channel) and the render post-process
# (caption / fenced-table / raw-text surfaces), so no Symbol-PUA glyph
# reaches any output view. The lowercase-Greek block follows the Symbol
# typist mnemonic — key 'b'→β, 'c'→χ, 'd'→δ, 'h'→η, 'm'→μ, 'p'→π, 's'→σ …
_SYMBOL_BYTE_TO_CHAR: dict[int, str] = {
    # ASCII-shared punctuation + digits (Symbol shares these positions)
    0x20: " ", 0x21: "!", 0x23: "#", 0x25: "%", 0x26: "&", 0x28: "(",
    0x29: ")", 0x2B: "+", 0x2C: ",", 0x2E: ".", 0x2F: "/",
    0x30: "0", 0x31: "1", 0x32: "2", 0x33: "3", 0x34: "4",
    0x35: "5", 0x36: "6", 0x37: "7", 0x38: "8", 0x39: "9",
    0x3A: ":", 0x3B: ";", 0x3C: "<", 0x3D: "=", 0x3E: ">", 0x3F: "?",
    0x5B: "[", 0x5D: "]", 0x5F: "_", 0x7B: "{", 0x7C: "|", 0x7D: "}",
    # uppercase Greek (0x41-0x5A)
    0x41: "Α", 0x42: "Β", 0x43: "Χ", 0x44: "Δ", 0x45: "Ε", 0x46: "Φ",
    0x47: "Γ", 0x48: "Η", 0x49: "Ι", 0x4A: "ϑ", 0x4B: "Κ", 0x4C: "Λ",
    0x4D: "Μ", 0x4E: "Ν", 0x4F: "Ο", 0x50: "Π", 0x51: "Θ", 0x52: "Ρ",
    0x53: "Σ", 0x54: "Τ", 0x55: "Υ", 0x56: "ς", 0x57: "Ω", 0x58: "Ξ",
    0x59: "Ψ", 0x5A: "Ζ",
    # lowercase Greek (0x61-0x7A)
    0x61: "α", 0x62: "β", 0x63: "χ", 0x64: "δ", 0x65: "ε", 0x66: "φ",
    0x67: "γ", 0x68: "η", 0x69: "ι", 0x6A: "ϕ", 0x6B: "κ", 0x6C: "λ",
    0x6D: "μ", 0x6E: "ν", 0x6F: "ο", 0x70: "π", 0x71: "θ", 0x72: "ρ",
    0x73: "σ", 0x74: "τ", 0x75: "υ", 0x76: "ϖ", 0x77: "ω", 0x78: "ξ",
    0x79: "ψ", 0x7A: "ζ",
    # math operators / relations
    0x22: "∀", 0x24: "∃", 0x27: "∋", 0x2A: "∗", 0x2D: "−",
    0x40: "≅", 0x5C: "∴", 0x5E: "⊥", 0x60: "‾", 0x7E: "∼",
    0xA1: "ϒ", 0xA2: "′", 0xA3: "≤", 0xA4: "⁄", 0xA5: "∞", 0xA6: "ƒ",
    0xA7: "♣", 0xA8: "♦", 0xA9: "♥", 0xAA: "♠",
    0xAB: "↔", 0xAC: "←", 0xAD: "↑", 0xAE: "→", 0xAF: "↓",
    0xB0: "°", 0xB1: "±", 0xB2: "″", 0xB3: "≥", 0xB4: "×", 0xB5: "∝",
    0xB6: "∂", 0xB7: "•", 0xB8: "÷", 0xB9: "≠", 0xBA: "≡", 0xBB: "≈",
    0xBC: "…", 0xBF: "↵",
    0xC0: "ℵ", 0xC1: "ℑ", 0xC2: "ℜ", 0xC3: "℘", 0xC4: "⊗", 0xC5: "⊕",
    0xC6: "∅", 0xC7: "∩", 0xC8: "∪", 0xC9: "⊃", 0xCA: "⊇", 0xCB: "⊄",
    0xCC: "⊂", 0xCD: "⊆", 0xCE: "∈", 0xCF: "∉",
    0xD0: "∠", 0xD1: "∇", 0xD2: "®", 0xD3: "©", 0xD4: "™", 0xD5: "∏",
    0xD6: "√", 0xD7: "⋅", 0xD8: "¬", 0xD9: "∧", 0xDA: "∨", 0xDB: "⇔",
    0xDC: "⇐", 0xDD: "⇑", 0xDE: "⇒", 0xDF: "⇓", 0xE0: "◊",
    0xE2: "®", 0xE3: "©", 0xE4: "™", 0xE5: "∑",
    # extensible bracket / paren / brace / integral pieces
    0xE1: "⟨", 0xE6: "⎛", 0xE7: "⎜", 0xE8: "⎝", 0xE9: "⎡", 0xEA: "⎢",
    0xEB: "⎣", 0xEC: "⎧", 0xED: "⎨", 0xEE: "⎩", 0xEF: "⎪", 0xF1: "⟩",
    0xF2: "∫", 0xF3: "⌠", 0xF5: "⌡", 0xF6: "⎞", 0xF7: "⎟", 0xF8: "⎠",
    0xF9: "⎤", 0xFA: "⎥", 0xFB: "⎦", 0xFC: "⎫", 0xFD: "⎬", 0xFE: "⎭",
}
_SYMBOL_PUA_MAP: dict[str, str] = {
    chr(0xF000 + _b): _c for _b, _c in _SYMBOL_BYTE_TO_CHAR.items()
}
# CMEX10 / Computer-Modern extensible square-bracket pieces. pdftotext and
# pdfplumber both surface these as U+F8EE-F8FB PUA codepoints (font
# *+CMEX10, the TeX math-extension font); glyph geometry confirms the
# assignment -- the left column F8EE/F8EF/F8F0 are the upper-corner /
# extension / lower-corner of a tall left square bracket, F8F9/F8FA/F8FB
# the right -- so they map to the Unicode Miscellaneous-Technical
# bracket-piece block U+23A1-U+23A6.
_SYMBOL_PUA_MAP.update({
    chr(0xF8EE): chr(0x23A1), chr(0xF8EF): chr(0x23A2), chr(0xF8F0): chr(0x23A3),
    chr(0xF8F9): chr(0x23A4), chr(0xF8FA): chr(0x23A5), chr(0xF8FB): chr(0x23A6),
})
# Symbol-font PUA block U+F020-F0FF plus the CMEX extensible-bracket pieces.
_SYMBOL_PUA_RE = re.compile(
    "[" + chr(0xF020) + "-" + chr(0xF0FF) + chr(0xF8EE) + "-" + chr(0xF8FB) + "]"
)


def recover_pua_glyphs(text: str) -> str:
    """Recover Adobe-Symbol-font glyphs surfaced as Private-Use codepoints.

    pdftotext / mammoth emit a Symbol-font glyph that has no ToUnicode CMap as
    ``U+F000 + <symbol-byte>`` (β→U+F062, χ→U+F063, •→U+F0B7). Each is mapped
    back to real Unicode via the fixed Adobe Symbol StandardEncoding. A PUA
    codepoint at an unassigned Symbol position — or outside the Symbol block —
    is left untouched, never guessed. No-op when the text holds no
    Symbol-block PUA codepoint.
    """
    if not text or not _SYMBOL_PUA_RE.search(text):
        return text
    return _SYMBOL_PUA_RE.sub(
        lambda m: _SYMBOL_PUA_MAP.get(m.group(0), m.group(0)), text
    )


# v2.4.57 (NORMALIZATION_VERSION 1.9.11): recover the cmsy10 (TeX Computer
# Modern math-symbol font) >= / <= comparison glyphs that pdftotext AND
# pdfplumber both destroy to U+FFFD on tightly-kerned PDFs. The glyph identity
# is gone from BOTH engines, so the layout channel cannot recover it --
# recovery is context-based. Sibling of S5a (FFFD->eta).
#
# Rule 1 -- complement pairing: a corrupted "<FFFD>N" contrasted with a clean
# "<N" / ">N" of the SAME number N is a set-partition (every value is either
# <N or >=N, resp. >N or <=N). The same-number constraint is enforced by a
# regex backreference, so a non-matching pair simply does not match. The
# separator class excludes digits/newlines/FFFD so the two operands stay in
# one clause. (?!\d) anchors the trailing number so "<20...[FFFD]200" cannot
# match a prefix.
_FFFD_OP_THEN_RE = re.compile(
    r"([<>])(\s*)(\d+)([^\d�\n]{0,18}?)�(\s*)\3(?!\d)"
)
_FFFD_RE_THEN_OP = re.compile(
    r"�(\s*)(\d+)([^\d�\n]{0,18}?)([<>])(\s*)\2(?!\d)"
)
# Rule 2 -- a lone "<FFFD>N": FFFD token-initial (not glued to a letter or
# digit -- a comparison operator is always set off by space/paren/slash/line
# start, never welded to a word or another number) immediately before a digit.
_FFFD_LONE_RE = re.compile(r"(?<![A-Za-z0-9])�(\s*\d)")
_FFFD_COMPLEMENT = {"<": "≥", ">": "≤"}


def recover_fffd_comparison_operators(text: str) -> str:
    """Recover cmsy10 >= / <= glyphs that pdftotext destroyed to U+FFFD.

    Rule 1 -- complement pairing (airtight): a corrupted ``<FFFD>N`` in a
    partition contrast with a clean ``<N`` / ``>N`` of the same number N is the
    set-complement (``<`` -> ``>=``, ``>`` -> ``<=``). Zero false-positive
    risk -- a partition like ``(<20/[FFFD]20 mm)`` is complementary by
    construction.

    Rule 2 -- document consensus: a lone ``<FFFD>N`` with no local complement
    is recovered only when Rule 1 has already fired in this document AND every
    recovery agreed on one operator. One PDF == one font == one corruption
    shape, so an airtight unanimous mapping generalises to a lone occurrence.
    If Rule-1 recoveries disagree, or none fired, a lone FFFD is left alone for
    the caller's quality scoring to flag (the S5a policy for prose FFFD).

    No-op when the text holds no U+FFFD.
    """
    if not text or "�" not in text:
        return text

    def _op_then(m: "re.Match[str]") -> str:
        op, ws1, num, sep, ws2 = m.groups()
        return f"{op}{ws1}{num}{sep}{_FFFD_COMPLEMENT[op]}{ws2}{num}"

    def _re_then(m: "re.Match[str]") -> str:
        ws1, num, sep, op, ws2 = m.groups()
        return f"{_FFFD_COMPLEMENT[op]}{ws1}{num}{sep}{op}{ws2}{num}"

    before = text
    text = _FFFD_OP_THEN_RE.sub(_op_then, text)
    text = _FFFD_RE_THEN_OP.sub(_re_then, text)
    # Rule 2 fires only on a unanimous, evidence-based consensus.
    n_ge = text.count("≥") - before.count("≥")
    n_le = text.count("≤") - before.count("≤")
    if n_ge > 0 and n_le == 0:
        text = _FFFD_LONE_RE.sub(lambda m: "≥" + m.group(1), text)
    elif n_le > 0 and n_ge == 0:
        text = _FFFD_LONE_RE.sub(lambda m: "≤" + m.group(1), text)
    return text


def normalize_text(
    text: str,
    level: NormalizationLevel,
    *,
    layout=None,
    table_regions: list[dict] | None = None,
    preserve_math_glyphs: bool = False,
) -> tuple[str, NormalizationReport]:
    """Apply normalization pipeline at the specified level.

    When `layout` is provided (a docpluck.extract_layout.LayoutDoc), the
    F0 step strips footnotes/running-headers/footers using PDF layout info
    and populates report.footnote_spans + report.page_offsets.

    When `table_regions` (a list of ``{"page": int, "bbox": (x0, top, x1, bottom)}``)
    is provided alongside `layout`, F0 will not strip lines whose y-range falls
    inside any table region — preserving table footnotes (e.g. ``Note. *p < .05.``)
    that would otherwise be misclassified as page footnotes.

    When `preserve_math_glyphs=True` (default False), the A5 step that
    transliterates Greek letters (β→"beta", δ→"delta", η²→"eta2", etc.) and
    math operators (×→"x", ≥→">=", ²→"2", ₀→"0", etc.) is SKIPPED. This is
    the correct setting for the rendered-markdown user output: every glyph
    that appears in the source PDF is preserved verbatim in the .md (subject
    only to U+2212→hyphen per CLAUDE.md L004 — the single documented
    Unicode→ASCII conversion). Default False preserves backward-compatible
    behavior for callers that depend on ASCII-form stat tokens (D5 audit
    suite, statistical pattern matching). Established 2026-05-14 from the
    Phase-5d AI-gold audit (TRIAGE_2026-05-14_phase_5d_gold_audit.md G2/G7/G12/G21).
    """
    if level == NormalizationLevel.none:
        report = NormalizationReport(level="none")
        if layout is not None:
            report.page_offsets = layout.page_offsets
        return text, report

    report = NormalizationReport(level=level.value)
    if layout is not None:
        report.page_offsets = layout.page_offsets
    t = text

    # ── NFC composition (Cycle 15c, G15 — combining-char split fix) ───
    # pdftotext sometimes emits author names with combining accents in NFD
    # decomposed form ("Förster", "Potočnik") or with a stray space
    # between base and combining mark ("Fö rster" → "Fö rster").
    # NFC composition recombines them into precomposed code points (Förster,
    # Potočnik). Safe to run at the top of the pipeline because all downstream
    # regex patterns operate on precomposed glyphs.
    import unicodedata
    # First squash any space between a base letter and an immediately-following
    # combining diacritic (the "Fö rster" → "Förster" case observed in amj_1
    # v2.4.28 audit). This relies on pdftotext's specific corruption pattern.
    t = re.sub(r"([A-Za-z])\s+([̀-ͯ])", r"\1\2", t)
    # Then NFC-compose to merge base+combining into precomposed (Fö → Förster
    # only works if Fö is precomposed; NFC handles the Potočnik case).
    t = unicodedata.normalize("NFC", t)

    # Snapshot raw page-number set before any mutation — R2 needs lines that
    # match `^\s*\d+\s*$` in the original extraction.
    _raw_page_numbers = _detect_recurring_page_numbers(text)

    # ── F0: Layout-aware running-header/footer + footnote strip ─────────
    # Requires a LayoutDoc from extract_pdf_layout. When present, strips
    # repeating running headers/footers and moves footnotes to an appendix
    # section after "\n\f\f\n". Populates report.footnote_spans.
    if layout is not None:
        t, footnote_spans = _f0_strip_running_and_footnotes(t, layout, table_regions=table_regions)
        report.footnote_spans = tuple(footnote_spans)
        report.steps_applied.append("F0")
        if footnote_spans:
            report.steps_changed.append("F0")

    # ── H0: document-header banner-line strip (NORMALIZATION_VERSION 1.8.0) ─
    # Note: H1 (hyphen-broken-word rejoin) is NOT applied here — the library's
    # S7 step below already removes column-wrap hyphens. H1 lives in
    # docpluck/render.py, where it runs on already-rendered markdown to
    # re-knit real compound words (e.g. Meta-Processes) split across caption
    # line wraps after S7 has handled the common case.
    before = t
    t = _strip_document_header_banners(t)
    report._track("H0_header_banner_strip", before, t, "header_banners_stripped")

    # ── T0: TOC dot-leader paragraph strip (NORMALIZATION_VERSION 1.8.0) ────
    before = t
    t = _strip_toc_dot_leader_block(t)
    report._track("T0_toc_dot_leader_strip", before, t, "toc_paragraphs_stripped")

    # ── P0: page-footer / running-header line strip (NORMALIZATION_VERSION 1.8.0) ─
    before = t
    t = _strip_page_footer_lines(t)
    report._track("P0_page_footer_strip", before, t, "page_footer_lines_stripped")

    # ── P1: front-matter metadata-leak paragraph strip (NORMALIZATION_VERSION 1.8.4) ─
    # Drops orphan acknowledgments / license / "previous version" / supplemental
    # -data / truncated-affiliation / bare-running-header paragraphs that
    # pdftotext serializes mid-Introduction via right-column reading order.
    # Position-gated to the first ~16% of the document so the legitimate
    # Acknowledgments / Funding / Affiliations sections at the END are
    # preserved. See _strip_frontmatter_metadata_leaks docstring for the
    # cross-publisher pattern coverage.
    before = t
    t = _strip_frontmatter_metadata_leaks(t)
    report._track("P1_frontmatter_metadata_leak_strip", before, t, "frontmatter_leaks_stripped")

    # ── H0b: lowercase letter-spaced display-label collapse (NORMALIZATION_VERSION 1.9.1) ─
    # Elsevier letter-spaced "a r t i c l e / i n f o / a b s t r a c t" box
    # labels. Runs pre-sectioning so the recovered "abstract" heads its section.
    before = t
    t = _rejoin_letterspaced_lowercase_labels(t)
    report._track("H0b_letterspaced_label_collapse", before, t, "letterspaced_labels_collapsed")

    # ── W0: Publisher-overlay watermark stripping (Request 9) ──────────
    # Runs BEFORE S0 so mid-line watermarks don't leak into body text via
    # downstream whitespace collapse. Patterns are precise (URL+date or
    # known publisher templates) — no false-positive risk on prose.
    before = t
    for _wp in _WATERMARK_PATTERNS:
        t = _wp.sub("", t)
    report._track("W0_watermark_strip", before, t, "watermarks_stripped")

    # ── W0b: recover '2'-for-U+2212 minus-sign corruption ──────────────
    before = t
    t = recover_corrupted_minus_signs(t)
    report._track("W0b_minus_sign_recovery", before, t, "minus_signs_recovered")

    # ── W0c: recover '<'-as-backslash glyph corruption ─────────────────
    before = t
    t = recover_corrupted_lt_operator(t)
    report._track("W0c_lt_operator_recovery", before, t, "lt_operators_recovered")

    # ── W0d: recover standalone '2'-for-minus via point-estimate ∈ CI ──
    before = t
    t = recover_minus_via_ci_pairing(t)
    report._track("W0d_minus_ci_pairing", before, t, "minus_signs_recovered")

    # ── W0e: recover Adobe-Symbol-font glyphs surfaced as PUA codepoints ─
    # pdftotext/mammoth emit a Symbol-font glyph with no ToUnicode CMap as a
    # U+F0xx Private-Use codepoint (β→U+F062, χ→U+F063, •→U+F0B7). The fixed
    # Adobe Symbol StandardEncoding maps each back to real Unicode. No-op on
    # text with no Symbol-block PUA codepoint.
    before = t
    t = recover_pua_glyphs(t)
    report._track("W0e_pua_glyph_recovery", before, t, "pua_glyphs_recovered")

    # ── Standard steps (S1-S9) ──────────────────────────────────────────

    # S0: Mathematical Alphanumeric Symbols (U+1D400-U+1D7FF) de-styling.
    # NFKC strips the math styling to the plain base letter/digit; Greek
    # stays Greek (see destyle_math_alphanumeric). Replaces pre-v2.4.34
    # hand-rolled loops that were (a) incomplete — only italic Latin + a
    # partial italic-Greek dict, so bold / sans / script variants and
    # ι/κ/λ/ν/ξ/τ/υ/ω leaked through — and (b) mapped math-italic Greek to
    # ASCII Latin (𝜂->"n", 𝛽->"b"), corrupting statistical symbols.
    before = t
    t = destyle_math_alphanumeric(t)
    if t != before:
        report._track("S0_smp_to_ascii", before, t, "smp_chars_converted")

    # S1: Encoding validation
    before = t
    t = t.replace("\x00", "")
    t = t.replace("\r\n", "\n").replace("\r", "\n")
    if t != before:
        report._track("S1_encoding_validation", before, t, "encoding_fixes")
    else:
        report.steps_applied.append("S1_encoding_validation")

    # S2: Accent recombination
    before = t
    _accent_maps = {
        "\u00B4": {"a": "\u00e1", "e": "\u00e9", "i": "\u00ed", "o": "\u00f3", "u": "\u00fa",
                    "A": "\u00c1", "E": "\u00c9", "I": "\u00cd", "O": "\u00d3", "U": "\u00da"},
        "\u02C6": {"a": "\u00e2", "e": "\u00ea", "i": "\u00ee", "o": "\u00f4", "u": "\u00fb"},
        "\u00A8": {"a": "\u00e4", "e": "\u00eb", "i": "\u00ef", "o": "\u00f6", "u": "\u00fc"},
        "\u0060": {"a": "\u00e0", "e": "\u00e8", "i": "\u00ec", "o": "\u00f2", "u": "\u00f9"},
    }
    for accent, mapping in _accent_maps.items():
        for vowel, combined in mapping.items():
            t = t.replace(vowel + accent, combined)
            t = t.replace(accent + vowel, combined)
    report._track("S2_accent_recombination", before, t, "accents_recombined")

    # S3: Ligature expansion \u2014 body channel. Calls the shared
    # decompose_ligatures helper (full U+FB00-FB06 block, incl. \ufb05/\ufb06\u2192st) so the
    # body, table-cell, and render-post-process channels stay in lockstep.
    before = t
    t = decompose_ligatures(t)
    report._track("S3_ligature_expansion", before, t, "ligatures_expanded")

    # S4: Quote normalization
    before = t
    t = re.sub(r"[\u201C\u201D\u201E\u201F\u2033\u2036]", '"', t)
    t = re.sub(r"[\u2018\u2019\u201A\u201B\u2032\u2035]", "'", t)
    report._track("S4_quote_normalization", before, t, "quotes_normalized")

    # S5: Dash and minus normalization
    before = t
    t = t.replace("\u2212", "-")   # Unicode MINUS SIGN (critical for stats)
    t = t.replace("\u2013", "-")   # en-dash
    t = t.replace("\u2014", "--")  # em-dash
    t = t.replace("\u2010", "-")   # Unicode hyphen
    t = t.replace("\u2011", "-")   # non-breaking hyphen
    report._track("S5_dash_normalization", before, t, "dashes_normalized")

    # S5a: Context-aware U+FFFD -> eta recovery (ESCImate Request 1.2)
    # pdftotext occasionally emits U+FFFD in place of Greek eta. The pdfplumber
    # SMP fallback catches most; this is second-line defense when both engines
    # drop the character. CONTEXT-AWARE — only rewrites U+FFFD when followed by
    # a statistical "eta-squared" pattern (eta^2 = .NNN). Generic encoding-fail
    # FFFDs in prose are left alone for the caller's quality scoring to flag.
    before = t
    _fffd_before = t.count("\ufffd")
    # Core pattern: FFFD followed by (optional space) (superscript-2 or digit 2) = number
    t = re.sub(
        r"\ufffd(\s*(?:\u00B2|2)\s*=\s*-?\.?\d)",
        r"eta\1",
        t,
    )
    # Partial-eta subscript variant: FFFD_p^2 = .04
    t = re.sub(
        r"\ufffd(_?p\u00B2\s*=\s*-?\.?\d)",
        r"eta\1",
        t,
    )
    _fffd_after = t.count("\ufffd")
    _fffd_recovered = _fffd_before - _fffd_after
    report.steps_applied.append("S5a_fffd_context_recovery")
    if _fffd_recovered > 0:
        report.changes_made["fffd_context_recovered"] = _fffd_recovered
        report.steps_changed.append("S5a_fffd_context_recovery")

    # S5b: Context-aware U+FFFD -> comparison-operator (>= / <=) recovery.
    # pdftotext AND pdfplumber destroy the cmsy10 (TeX Computer Modern
    # math-symbol font) >= / <= glyphs to U+FFFD on tightly-kerned PDFs -- the
    # layout channel cannot recover it (the glyph identity is gone from both
    # engines), so recover_fffd_comparison_operators rebuilds it from context:
    # airtight complement pairing ("<N" partitioned against "[FFFD]N"), then a
    # document-consensus rule for a lone "[FFFD]N". Sibling of S5a.
    before = t
    _fffd_cmp_before = t.count("�")
    t = recover_fffd_comparison_operators(t)
    _fffd_cmp_recovered = _fffd_cmp_before - t.count("�")
    report.steps_applied.append("S5b_fffd_comparison_recovery")
    if _fffd_cmp_recovered > 0:
        report.changes_made["fffd_comparison_recovered"] = _fffd_cmp_recovered
        report.steps_changed.append("S5b_fffd_comparison_recovery")

    # S6: Whitespace and invisible character normalization
    before = t
    t = t.replace("\u00AD", "")    # soft hyphen (invisible, breaks search — 14/50 test PDFs)
    t = t.replace("\u00A0", " ")   # NBSP
    t = t.replace("\u2002", " ")   # en space
    t = t.replace("\u2003", " ")   # em space
    t = t.replace("\u2004", " ")   # three-per-em space
    t = t.replace("\u2005", " ")   # four-per-em space
    t = t.replace("\u2006", " ")   # six-per-em space
    t = t.replace("\u2007", " ")   # figure space
    t = t.replace("\u2008", " ")   # punctuation space
    t = t.replace("\u2009", " ")   # thin space
    t = t.replace("\u200A", " ")   # hair space
    t = t.replace("\u200B", "")    # zero-width space
    t = t.replace("\u200C", "")    # zero-width non-joiner
    t = t.replace("\u200D", "")    # zero-width joiner
    t = t.replace("\u202F", " ")   # narrow no-break space
    t = t.replace("\u205F", " ")   # medium mathematical space
    t = t.replace("\u3000", " ")   # ideographic space
    t = t.replace("\uFEFF", "")    # BOM / zero-width no-break space
    # Full-width ASCII → ASCII (U+FF01-FF5E → U+0021-007E)
    chars = list(t)
    for i, c in enumerate(chars):
        cp = ord(c)
        if 0xFF01 <= cp <= 0xFF5E:
            chars[i] = chr(cp - 0xFEE0)
    t = "".join(chars)
    t = re.sub(r"[ \t]{2,}", " ", t)
    report._track("S6_whitespace_normalization", before, t, "whitespace_normalized")

    # S7: Hyphenation repair. The trailing letter is matched as a lookahead so a
    # run of consecutive `word-\nword-\nword` breaks all join in one pass — a
    # `re.sub` of `(g1)-\n(g2)` consumes g2 and resumes after it, missing the
    # `g2-\ng3` join (an N-break chain takes N passes to fully repair, breaking
    # normalize_text idempotency).
    before = t
    t = re.sub(r"([a-z])-\n(?=[a-z])", r"\1", t)
    report._track("S7_hyphenation_repair", before, t, "hyphenations_repaired")

    # S7a (v2.4.20, NORMALIZATION_VERSION 1.8.7): space-broken-compound
    # rejoin. See _rejoin_space_broken_compounds docstring + the pair
    # list defined above for the curated cases (experi/ments,
    # con/ducted, presenta/tion, ques/tionnaires, etc.).
    before = t
    t = _rejoin_space_broken_compounds(t)
    report._track("S7a_space_broken_compound_rejoin", before, t,
                  "space_broken_compounds_rejoined")

    # S8: Mid-sentence line break joining. Two fixes packaged here, both
    # idempotency-driven:
    # 1) Trailing char is a lookahead (not a captured group) so a run of N
    #    consecutive joinable lines fully merges in one pass — `re.sub(g1\ng2)`
    #    used to consume g2 and resume past it, missing every other adjacency
    #    in a chained run (an N-line paragraph needed log2(N)+1 passes).
    # 2) The trailing class includes lowercase Greek (U+03B1-03C9). pdftotext
    #    surfaces Greek letters as their actual Unicode glyph; the A5 academic
    #    step transliterates them to ASCII names (`σ`→`sigma`) LATER in the
    #    pipeline. So a `,\nσ²(ξ)` line break used to escape S8 on pass 1
    #    (Greek not in `[a-z]`), A5 then turned it into `,\nsigma2(xi)`, and
    #    only the NEXT normalize pass joined it — breaking idempotency.
    before = t
    t = re.sub(r"([a-z,;])\n(?=[a-zα-ω])", r"\1 ", t)
    report._track("S8_line_break_joining", before, t, "line_breaks_joined")

    # For academic level: join stat line breaks BEFORE stripping page numbers,
    # because standalone numbers like "484" on their own line might be stat values
    # that got split from "p =\n484". S9 would strip them as page numbers.
    if level == NormalizationLevel.academic:
        before = t
        # Basic stat line break: `p\n<`, `p\n=`, `p\n>` → `p <` etc.
        t = re.sub(r"([pP])\s*\n\s*([=<>])", r"\1 \2", t)

        # A1-extended (2026-04-11, v1.3.1): column-bleed BETWEEN `p` and the
        # operator. Pattern observed in PSPB papers: `p\n\n01\n\n01\n\n= .28`
        # where "01", "11" etc. are short column-bleed fragments on their own
        # lines. Must run before the simple `p =\n digit` rule below, otherwise
        # the first fragment gets interpreted as the value.
        t = re.sub(
            r"([pP])\s*\n(?:\s*\d{1,3}\s*\n){1,4}\s*([<=>])",
            r"\1 \2",
            t,
        )
        # Same pattern with column-bleed BETWEEN operator and value:
        # `p =\n01\n11\n.28` → `p = .28`. Must run before the simple
        # `p =\n digit` rule below to avoid eating the first fragment.
        t = re.sub(
            r"([pP]\s*[<=>])\s*\n(?:\s*\d{1,3}\s*\n){1,4}\s*([-.\d])",
            r"\1 \2",
            t,
        )

        # Simple: p =\n digit → p = digit (must run AFTER column-bleed rules)
        t = re.sub(r"([pP]\s*[=<>])\s*\n\s*(\d)", r"\1 \2", t)
        t = re.sub(r"(OR|CI|RR)\s*\n\s*(\d)", r"\1 \2", t)
        t = re.sub(r"(95\s*%)\s*\n\s*(CI)", r"\1 \2", t)
        t = re.sub(r"([=<>])\s*\n\s*([-\d.])", r"\1 \2", t)
        # Column-boundary garbage: skip letter-starting text (1-20 chars) between
        # p= and a valid p-value on the next line.  Two independent safety guards:
        # Guard 1 — garbage must start with [a-zA-Z] (real stat content starts with
        #   digits/dots, column-bleed garbage starts with word fragments).
        # Guard 2 — next-line value must match 0?\.\d+ (valid p-value format;
        #   rejects section numbers like 8.3, page numbers like 1024, footnotes).
        # See MetaESCI D5 audit (2026-04-12): old [^\n]{1,20} ate real p-values.
        t = re.sub(r"(p\s*[<=>]\s*)[a-zA-Z][^\n]{0,19}\n\s*(0?\.\d+)", r"\1\2", t)
        # Rejoin test stat → p-value across line break: "t(23) = 2.34,\n p < .001"
        t = re.sub(r"([,;])\s*\n\s*(p\s*[<=>])", r"\1 \2", t)
        # Rejoin effect size → CI across line break: "d = 0.45,\n 95% CI"
        t = re.sub(r"([,;])\s*\n\s*(\d+%\s*CI)", r"\1 \2", t)
        report._track("A1_stat_linebreak_repair", before, t, "stats_repaired")

    # S9: Header/footer removal
    before = t
    lines = t.split("\n")
    line_counts: dict[str, int] = {}
    line_positions: dict[str, list[int]] = {}
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if 15 <= len(stripped) <= 120:
            line_counts[stripped] = line_counts.get(stripped, 0) + 1
            line_positions.setdefault(stripped, []).append(idx)
    # Cycle 14 (v2.4.66) — minimum-gap discriminator.
    # A repeated line that appears ≥5 times is a candidate header/footer.
    # The old rule stripped every candidate; this false-positives on
    # TABLE ROW LABELS that repeat across columns of a regression table
    # (socius-3 `Intend vs. Later` ×5, majumder `eta2p = .001, ⸸` ×9,
    # collabra-rnr `Identifiability` ×5, social-forces-1 `Emotional
    # neglect` ×5 — all cluster within a small region).
    #
    # The MINIMUM GAP between consecutive occurrences cleanly separates
    # the two classes:
    #   - Table labels cluster in adjacent rows → min_gap ≤ 14 (range
    #     3-14 across 4 corpus cases).
    #   - Running headers appear once per page → min_gap ≥ 25 (range
    #     25-100 across multiple corpus papers).
    # Threshold at min_gap ≥ 20 separates the two with margin on both
    # sides. The range-coverage approach was abandoned because doc length
    # is too variable — short docs can have running-header range only
    # 65-72% (below the natural 90% mark seen in long docs), causing
    # idempotence drift when pass 2 has a shorter input.
    repeated: set[str] = set()
    for s, count in line_counts.items():
        if count < 5:
            continue
        positions = line_positions[s]
        gaps = [positions[i + 1] - positions[i] for i in range(len(positions) - 1)]
        if not gaps:
            continue
        # Two paths qualify a repeated line as a header/footer:
        #   - min_gap ≥ 20: cleanly-spaced running header (one per page).
        #   - count ≥ 20: super-frequently-repeated watermark / sidebar /
        #     PMC-style "Author Manuscript" boilerplate that repeats multiple
        #     times per page (consecutive occurrences yield min_gap = 1).
        # Both forms are publisher boilerplate, never body content.
        if min(gaps) >= 20 or count >= 20:
            repeated.add(s)
    if repeated:
        lines = [l for l in lines if l.strip() not in repeated]
        t = "\n".join(lines)
    # Strip standalone page numbers — 1-3 digit unconditionally.
    t = re.sub(r"^\s*\d{1,3}\s*$", "", t, flags=re.MULTILINE)
    # v2.4.3/v2.4.5: 4-digit page numbers (continuous-pagination journals like
    # PSPB where volume runs page numbers into the 1000s, e.g.
    # ``efendic_2022_affect`` with pages 1174-1185). Two patterns fire:
    #
    #   (A) RECURRING (v2.4.3) — same value appears ≥3 times. Catches PDFs
    #       where every page repeats the same volume number on its own line
    #       (rare for true page numbers, but happens for volume markers).
    #
    #   (B) SEQUENTIAL (v2.4.5) — ≥3 distinct standalone 4-digit values in
    #       the doc AND they cluster within a 50-page range (max - min ≤ 50)
    #       AND the average per-page gap is small (mean diff ≤ 3). This is
    #       the canonical continuous-pagination signature: page numbers
    #       monotonically increasing across the article. The conservative
    #       gates protect table cells (where 4-digit values would have
    #       larger spreads and irregular gaps).
    four_digit_counts: dict[str, int] = {}
    for ln in t.split("\n"):
        s = ln.strip()
        if len(s) == 4 and s.isascii() and s.isdigit() and 1000 <= int(s) <= 9999:
            four_digit_counts[s] = four_digit_counts.get(s, 0) + 1

    # Pattern A: same value recurs ≥3 times.
    # Cycle 14 (v2.4.66) — exclude citation-year range (1900-2100). A
    # 4-digit value that repeats ≥3 times is most-often a citation year
    # ("House, R. J. 1971" cited in multiple table rows or the references
    # section), not a page number. Page numbers in the citation-year
    # range are extremely rare; corrupting a citation year by stripping
    # it is common and harmful (amle-1 had `1971` stripped under the old
    # rule).
    strip_set: set[str] = {
        s for s, c in four_digit_counts.items()
        if c >= 3 and not (1900 <= int(s) <= 2100)
    }

    # Pattern B: ≥3 distinct values clustered tightly together.
    #
    # v2.4.11: scan for the densest sub-cluster instead of computing global
    # spread. chan_feldman_2025_cogemo has page numbers 1228-1249 (21 values,
    # tight) PLUS year mentions like 1997 and 2023 in inline citations. The
    # old check `spread = max - min` saw the global span 1228-2023 (795
    # chars) and rejected the cluster outright. Now we slide a 50-window
    # across the sorted values, find the run with ≥3 values + mean diff ≤3,
    # and strip those.
    if len(four_digit_counts) >= 3:
        values = sorted(int(s) for s in four_digit_counts.keys())
        # Greedy clustering: walk sorted values, extend a cluster while the
        # next value is within 5 of the previous one. Pick the longest run
        # with ≥3 values that spans ≤50 and mean-diff ≤3.
        clusters: list[list[int]] = [[values[0]]]
        for v in values[1:]:
            if v - clusters[-1][-1] <= 5:
                clusters[-1].append(v)
            else:
                clusters.append([v])
        for cluster in clusters:
            if len(cluster) < 3:
                continue
            spread = cluster[-1] - cluster[0]
            if spread > 50:
                continue
            diffs = [cluster[i + 1] - cluster[i] for i in range(len(cluster) - 1)]
            mean_diff = sum(diffs) / len(diffs)
            if mean_diff <= 3.0:
                strip_set.update(str(v) for v in cluster)

    # Cycle 9b (v2.4.61 / NORMALIZATION_VERSION 1.9.15) — per-occurrence
    # gating to protect table sample-size values.
    #
    # The previous "strip every occurrence in strip_set" rule was a corpus-
    # level false-positive: A3 (academic level) strips thousands-separator
    # commas in N contexts (`Observations: 7,182` → `Observations: 7182`),
    # and pdftotext sometimes lands the bare N on its own line (right-aligned
    # in a regression table). chandrashekar 2020 has 4 regression columns
    # citing the SAME N=7182 → 4 standalone `7182` lines → Pattern A flags
    # `7182` as a page number → all 4 get stripped on pass 2 (pass 1 hasn't
    # seen A3 yet, so the line still reads `7,182` and S9 doesn't flag it;
    # this is what causes the non-idempotence). Stripping table N is real
    # production text loss.
    #
    # Discriminator: a per-page marker (page number / volume number) sits
    # ISOLATED — surrounded by prose, blank lines, or section headings. A
    # table cell value sits in a VERTICAL BLOCK of other numeric values
    # (other table cells in the same column). So: keep the line if EITHER
    # its nearest non-blank neighbor above OR below is numeric-only.
    if strip_set:
        lines = t.split("\n")
        new_lines: list[str] = []
        for idx, ln in enumerate(lines):
            if ln.strip() not in strip_set:
                new_lines.append(ln)
                continue
            if _is_in_numeric_block(lines, idx):
                # Table-like context: keep. (Cycle 9b — clears chandrashekar
                # `7182`, aiyer `1118`/`1265`, and ~7 sibling regression-
                # table papers from the non-idempotent set.)
                new_lines.append(ln)
            else:
                new_lines.append("")
        t = "\n".join(new_lines)
    report._track("S9_header_footer_removal", before, t, "headers_removed")

    # Limit consecutive newlines
    t = re.sub(r"\n{3,}", "\n\n", t)

    # ── Academic steps (A2-A5) ─────────────────────────────────────────
    # Note: A1 already ran above (before S9) to prevent number stripping

    if level == NormalizationLevel.academic:

        # A2: Dropped decimal repair (p > 1.0 -> p = 0.xxx)
        #
        # Changed 2026-04-11 (v1.3.1): accept val >= 1.0 (not > 1.0) so that
        # `p = 01` and `p = 10` (both evaluating to 1.0 or 10.0) get repaired.
        # The `\d{2,3}` prefix in the regex already guarantees we never touch
        # single-digit values like `p = 1`, so this widening is safe.
        #
        # Changed 2026-04-11: lookahead accepts `.` only when not followed by
        # another digit — so `p = 01.` (sentence-ending period) matches but
        # `p = 15.8` (legitimate decimal) does not.
        before = t

        def _fix_dropped_decimal(m):
            val = float(m.group(2))
            if val >= 1.0 and val < 1000:
                return f"{m.group(1)}.{m.group(2)}"
            return m.group(0)

        # Fix p-values and effect sizes with dropped leading "0."
        _A2_LOOKAHEAD = r"(?=\s|[,;)\]]|\.(?!\d)|$)"
        t = re.sub(r"([pP]\s*[=]\s*)(\d{2,3})" + _A2_LOOKAHEAD, _fix_dropped_decimal, t)
        t = re.sub(r"(\b[dDgG]\s*[=]\s*)(\d{2,3})" + _A2_LOOKAHEAD, _fix_dropped_decimal, t)
        report._track("A2_dropped_decimal_repair", before, t, "decimals_fixed")

        # A3a: Protect thousands separators in N-context integers (ESCImate Request 1.1)
        # Problem: A3 converts "0,05" -> "0.05" (European decimal commas). The same
        # rule corrupts "N = 1,182" -> "N = 1.182" which downstream parses as a
        # sample size of 1.182 people. This step strips commas from ONLY the
        # matched integer token in sample-size contexts, so A3 sees the already-
        # clean integer and leaves it alone.
        #
        # Runs in academic level because A3 itself is academic-only; in standard
        # level the commas are preserved by default (no A3 to corrupt them).
        before = t
        _thousands_count = [0]

        def _strip_commas_integer(m):
            _thousands_count[0] += 1
            groups = list(m.groups())
            # The integer token is always the second capture group below
            groups[1] = groups[1].replace(",", "")
            return "".join(g for g in groups if g is not None)

        _N_PROTECT_PATTERNS = [
            # N = 1,182 / n = 2,443 / N=(1,234,567)
            re.compile(r"(\b[Nn]\s*=\s*\(?\s*)(\d{1,3}(?:,\d{3})+)(\s*\)?)"),
            # df = 1,197 (rare — df large enough to need thousands separator)
            re.compile(r"(\bdf\s*=\s*)(\d{1,3}(?:,\d{3})+)(\b)"),
            # "sample size of 2,443"
            re.compile(r"(\bsample\s+size\s+of\s+)(\d{1,3}(?:,\d{3})+)(\b)", re.IGNORECASE),
            # "total of 2,443 participants"
            re.compile(r"(\btotal\s+of\s+)(\d{1,3}(?:,\d{3})+)(\s+participants)", re.IGNORECASE),
            # v2.4.17 widening (NORMALIZATION_VERSION 1.8.5): generic body-integer
            # with thousands-separator. The original 4 patterns above only protect
            # narrow syntactic contexts (`N =`, `df =`, "sample size of", "total
            # of … participants"). Real academic prose uses thousands-separated
            # integers in many more constructions:
            #     "1,001 participants"           (xiao_2021_crsp)
            #     "4,200 followers"              (amj_1)
            #     "3,000 hours"                  (amle_1)
            #     "7,445 sources, 33,719 articles, 32,981 authors"   (amle_1)
            #     "5,792 people"
            #     "1,675 entries"
            #     "1,842 records"
            # Without this widening, A3 (decimal-comma normalization) corrupts
            # these to "1.001 participants", "4.200 followers", etc., destroying
            # the meaning of sample sizes and count statistics. Confirmed via
            # v2.4.16 Phase 5d AI verify across xiao + amj_1 + amle_1.
            #
            # Guards (four independent):
            #   1. Integer must start with [1-9] (rejects `0,001` decimal form
            #      — a European-decimal pattern A3 is supposed to fix).
            #   2. Integer must have exactly `\d{1,3}(?:,\d{3})+` structure
            #      (requires comma-thousands-separator; "0,05" → 1 digit after
            #      comma, won't match; "1,5" → 1 digit, won't match; "1,500" →
            #      3 digits, matches).
            #   3. Followed by a lookahead boundary `\s|[,;.)\]:]|$` (must not
            #      be in mid-citation context like "Smith, 1992" — that has
            #      no comma between digits).
            #   4. NEGATIVE LOOKBEHIND `(?<![A-Z][\(\[])` blocks the
            #      degrees-of-freedom stat-bracket context "F[7,140]",
            #      "F(7,140)", "t(1,197)", "chi2(2,42)" — those are stat
            #      df brackets, not thousands-separators. A3b handles them
            #      separately (bracket-to-paren harmonization). Without this
            #      guard, stripping the comma from "7,140" inside "F[7,140]"
            #      destroys the df pair and A3b can no longer harmonize.
            #
            # Effect: strips the comma from "1,001" → "1001" BEFORE A3 runs,
            # so A3 sees the plain integer and leaves it alone. Reader sees
            # "1001 participants" instead of "1.001 participants" — same
            # meaning, no thousands-separator (acceptable; consistent with
            # Methods sections that often use comma-free format).
            re.compile(
                r"(?<![A-Z][\(\[])(\b)([1-9]\d{0,2}(?:,\d{3})+)(?=[\s,;.)\]:]|$)"
            ),
        ]
        if preserve_math_glyphs:
            # Render path: count matches for telemetry but DO NOT strip commas.
            # Thousands separators (`7,445`, `33,719`, etc.) are source glyphs
            # the rendered .md must preserve. A3 below is also gated to skip
            # in preserve mode so it doesn't corrupt these into decimals.
            for pattern in _N_PROTECT_PATTERNS:
                _thousands_count[0] += len(pattern.findall(t))
        else:
            for pattern in _N_PROTECT_PATTERNS:
                t = pattern.sub(_strip_commas_integer, t)
        report.steps_applied.append("A3a_thousands_separator_protect")
        if _thousands_count[0] > 0:
            report.changes_made["thousands_separators_preserved"] = _thousands_count[0]
            report.steps_changed.append("A3a_thousands_separator_protect")

        # A3: Decimal comma normalization (European locale)
        #
        # Leading lookbehind (?<![a-zA-Z,0-9\[\(]) prevents four classes of
        # false positive:
        #
        # 1. Author affiliation superscripts — "Braunstein1,3" or "Wagner1,3,4"
        #    where the 1/3/4 are citation markers, not decimals. The letter
        #    before "1" (Braunstein) and the comma before "3" (Wagner middle)
        #    block those matches. Cross-ported from effectcheck/R/parse.R:189.
        #
        # 2. Multi-value CI content — "[0.45,0.89]" where A4 later fixes the
        #    comma-separated pair. The digit before the comma (4) would
        #    otherwise let A3 corrupt "5,089" -> "5.089" because the trailing
        #    "]" matches the lookahead. Excluding digits from the lookbehind
        #    blocks this.
        #
        # 3. Existing well-formed decimal lists like "0.5,0.8,1.2" where A3
        #    should leave the commas alone (they're separators, not decimals).
        #
        # 4. Statistical df brackets — "F[2,42]", "F(2,42)", "t(1,197)" where
        #    pdftotext produces the tight-no-space df form. Without excluding
        #    "[" and "(" from the lookbehind, A3 corrupts "F[2,42]=13.689"
        #    into "F[2.42]=13.689", which effectcheck's parser then fails to
        #    match. Regression discovered via MetaESCI D2 lost-source repro
        #    (10.15626/mp.2019.1723, 2026-04-11). The A3a step above handles
        #    N=/df= thousands separators before A3 runs, so excluding "(" here
        #    does not affect that path.
        #
        # The trailing lookahead keeps the original restrictive character set
        # (\s | ; ) ] | $). Broadening it to [^0-9a-zA-Z] caused A4 ordering
        # regressions historically.
        #
        # v2.4.17 (NORMALIZATION_VERSION 1.8.5): minor extension — add
        # `\.(?!\d)` to the lookahead so sentence-ending decimals like
        # "d = 0,87." get normalized to "d = 0.87." Same pattern A2 already
        # uses safely (line 1466 ``_A2_LOOKAHEAD``). The `(?!\d)` guard
        # blocks the thousands-separated-decimal case "1,234.567" — that
        # still doesn't match because the next char after the comma group
        # is `.` followed by a digit. Validated against the existing A3 +
        # A4 regression suite.
        before = t
        if not preserve_math_glyphs:
            t = re.sub(
                r"(?<![a-zA-Z,0-9\[\(])(\d),(\d{1,3})(?=\s|[;)\]]|\.(?!\d)|$)",
                r"\1.\2",
                t,
            )
        # In preserve mode, A3 is SKIPPED so the rendered .md keeps European-
        # decimal comma form ("d = 0,87") AND thousands-separator form
        # ("7,445 sources") exactly as printed. Downstream stat extraction
        # that wants ENG decimal can normalize on its own.
        report._track("A3_decimal_comma_normalization", before, t, "decimal_commas_fixed")

        # A3c: Leading-zero decimal recovery (cycle 14, HANDOFF_2026-05-14
        # deferred item D, NORMALIZATION_VERSION 1.8.9).
        #
        # A3's lookbehind ``(?<![a-zA-Z,0-9\[\(])`` blocks legitimate
        # European-decimal p-values inside parens or brackets, e.g.
        # ``(0,003)``, ``[0,05]``, ``(p < 0,001)`` with the parenthesis
        # directly preceding the integer. This exclusion exists to
        # protect statistical-df forms like ``F(2,42)`` and citation
        # superscripts. But the leading-zero form ``0,XX[X[X]]`` is
        # unambiguous: degrees-of-freedom never use 0 as the first df
        # value, and citation superscripts never start with 0.
        #
        # Rule: convert ``0,(\d{2,4})`` (zero + comma + 2-4 digits)
        # regardless of lookbehind, as long as it's at a word boundary
        # and followed by a non-digit terminator. Single-digit-after-
        # comma cases like ``[0,5]`` are skipped — they're typically
        # range expressions like ``[0,5]`` meaning ``[0, 5]``, not a
        # decimal.
        before = t
        if not preserve_math_glyphs:
            t = re.sub(
                r"\b0,(\d{2,4})(?=[\s)\];,.:]|$)",
                r"0.\1",
                t,
            )
        # In preserve mode, A3c is SKIPPED so the rendered .md keeps the
        # European-decimal form ("0,003") exactly as printed.
        report._track("A3c_leading_zero_decimal_recovery", before, t, "leading_zero_decimals_fixed")

        # A3b: Statistical df-bracket harmonization (MetaESCI D2, 2026-04-11)
        #
        # Some PDFs encode F/t/chi2 degrees-of-freedom with square brackets
        # instead of parentheses — e.g. pdftotext produces "F[2,42]= 13.689"
        # from 10.15626/mp.2019.1723 where the paper visually uses parens.
        # effectcheck's parse.R only matches `F\s*\(`, so these rows are
        # silently dropped. Convert the bracket form to canonical parens
        # when the bracket follows a short stat identifier AND is followed
        # by `=` (the assignment to a numeric value). The `=` lookahead is
        # the load-bearing constraint — it blocks false positives on
        # `ref[1,2]`, `fig[1,2]`, `eq[1,2]` which look structurally
        # identical but are citation/figure/equation references, not stats.
        before = t
        t = re.sub(
            r"(\b[A-Za-z][A-Za-z0-9]{0,3})\[(\s*\d+(?:\.\d+)?\s*,\s*\d+(?:\.\d+)?\s*)\](?=\s*=)",
            r"\1(\2)",
            t,
        )
        report._track("A3b_stat_bracket_to_paren", before, t, "stat_brackets_fixed")

        # A4: CI delimiter harmonization
        before = t
        # Semicolons → commas inside square brackets and parens
        t = re.sub(r"\[(\s*[-+]?\d*\.?\d+)\s*;\s*([-+]?\d*\.?\d+\s*)\]", r"[\1, \2]", t)
        t = re.sub(r"\((\s*[-+]?\d*\.?\d+)\s*;\s*([-+]?\d*\.?\d+\s*)\)", r"(\1, \2)", t)
        # Curly braces → square brackets
        t = re.sub(r"\{\s*([-+]?\d*\.?\d+)\s*[,;]\s*([-+]?\d*\.?\d+)\s*\}", r"[\1, \2]", t)
        # Normalize spacing inside brackets and parens
        t = re.sub(r"\[\s*([-+]?\d*\.?\d+)\s*,\s*([-+]?\d*\.?\d+)\s*\]", r"[\1, \2]", t)
        t = re.sub(r"\(\s*([-+]?\d*\.?\d+)\s*,\s*([-+]?\d*\.?\d+)\s*\)", r"(\1, \2)", t)
        report._track("A4_ci_delimiter_harmonization", before, t, "ci_delimiters_fixed")

        # A5: Math symbol and Greek letter normalization
        # When preserve_math_glyphs=True (render path), this block is SKIPPED
        # so the rendered .md preserves source glyphs (\u03B2, \u03B4, \u03C7\u00B2, \u03B7\u00B2, \u00B2, \u2080, etc.)
        # exactly as printed. Default False preserves backward-compatible
        # behavior for stat-extraction callers (D5 audit, regex matching).
        # See CLAUDE.md ground-truth rule + memory feedback_ground_truth_is_ai_not_pdftotext.
        before = t
        if preserve_math_glyphs:
            # Skip A5 entirely \u2014 preserve source glyphs.
            report._track("A5_skipped_preserve_math_glyphs", before, t, "preserved")
        else:
            t = t.replace("\u00D7", "x")     # multiplication sign
            t = t.replace("\u2264", "<=")     # less-than-or-equal
            t = t.replace("\u2265", ">=")     # greater-than-or-equal
            t = t.replace("\u2260", "!=")     # not-equal

            # Greek statistical letters → ASCII (for downstream regex matching)
            # Order matters: multi-char sequences before single chars
            t = t.replace("\u03B7\u00B2", "eta2")    # η² → eta2
            t = t.replace("\u03B7\u00B2", "eta2")    # η² variant
            t = t.replace("\u03C7\u00B2", "chi2")    # χ² → chi2
            t = t.replace("\u03C9\u00B2", "omega2")  # ω² → omega2
            t = re.sub(r"\u03B7\s*2", "eta2", t)     # η 2 → eta2 (space variant)
            t = re.sub(r"\u03C7\s*2", "chi2", t)     # χ 2 → chi2
            t = re.sub(r"\u03C9\s*2", "omega2", t)   # ω 2 → omega2
            t = t.replace("\u03B7", "eta")            # η → eta
            t = t.replace("\u03C7", "chi")            # χ → chi
            t = t.replace("\u03C9", "omega")          # ω → omega
            t = t.replace("\u03B1", "alpha")          # α → alpha
            t = t.replace("\u03B2", "beta")           # β → beta
            t = t.replace("\u03B4", "delta")          # δ → delta
            t = t.replace("\u03C3", "sigma")          # σ → sigma
            t = t.replace("\u03C6", "phi")            # φ → phi
            t = t.replace("\u03BC", "mu")             # μ → mu

            # Superscript digits → regular digits (² → 2, ³ → 3, etc.)
            t = t.replace("\u00B2", "2")   # ²
            t = t.replace("\u00B3", "3")   # ³
            t = t.replace("\u00B9", "1")   # ¹
            t = t.replace("\u2070", "0")   # ⁰
            t = t.replace("\u2074", "4")   # ⁴
            t = t.replace("\u2075", "5")   # ⁵
            t = t.replace("\u2076", "6")   # ⁶
            t = t.replace("\u2077", "7")   # ⁷
            t = t.replace("\u2078", "8")   # ⁸
            t = t.replace("\u2079", "9")   # ⁹

            # Subscript digits → regular digits
            t = t.replace("\u2080", "0")   # ₀
            t = t.replace("\u2081", "1")   # ₁
            t = t.replace("\u2082", "2")   # ₂
            t = t.replace("\u2083", "3")   # ₃
            t = t.replace("\u2084", "4")   # ₄
            t = t.replace("\u2085", "5")   # ₅
            t = t.replace("\u2086", "6")   # ₆
            t = t.replace("\u2087", "7")   # ₇
            t = t.replace("\u2088", "8")   # ₈
            t = t.replace("\u2089", "9")   # ₉

            report._track("A5_math_symbol_normalization", before, t, "math_symbols_normalized")

        # A6: Footnote marker removal after statistical values
        # "p < .001¹" → "p < .001", "95% CI [0.1, 0.5]²" → "95% CI [0.1, 0.5]"
        # Only remove isolated superscript/subscript digits that follow stat-adjacent chars
        # Note: A5 already converted ² → 2, so we look for isolated digits after ] ) or stat values
        # This catches remaining Unicode superscripts that A5 missed
        before = t
        t = re.sub(
            r"([\d\]\)])[\u00B9\u00B2\u00B3\u2070\u2074-\u2079\u2080-\u2089](?=\s|[,;.\)]|$)",
            r"\1", t
        )
        report._track("A6_footnote_removal", before, t, "footnotes_removed")

        # ── A7: DOI cross-line repair (Request 9, document-wide) ─────────
        # pdftotext sometimes wraps long DOIs across a line, e.g.
        # "(doi:10.\n1007/s10683-020-09663-x)". Rejoin them. The `doi:` prefix
        # in the lookbehind chain is load-bearing — without it the rule
        # would damage decimals at line ends in normal prose.
        before = t
        t = re.sub(r"(doi:\s*\S*?\d)\.\s*\n\s*(\d)", r"\1.\2", t, flags=re.IGNORECASE)
        report._track("A7_doi_rejoin", before, t, "doi_rejoined")

        # ── R2 + R3: References-section repairs (Request 9) ──────────────
        # R2 scrubs page-number digits glued mid-reference (silent corruption
        # of titles). R3 joins continuation lines so each reference is on a
        # single logical line. Bounded to detected references spans; iterate
        # right-to-left so prior span offsets remain valid after edits.
        _refs_spans = _find_references_spans(t)
        r2_count_total = 0
        r3_joins_total = 0
        for r_start, r_end in reversed(_refs_spans):
            refs_text = t[r_start:r_end]

            # R3 first: continuation join must run before R2 because R2's
            # lowercase-surround guard relies on the page-number being
            # surrounded by content from the SAME logical line.
            before_r3 = refs_text
            lines = refs_text.split("\n")
            joined: list[str] = []
            for line in lines:
                stripped = line.strip()
                if not stripped:
                    joined.append("")
                    continue
                if joined and joined[-1] and not _looks_like_ref_start(stripped):
                    joined[-1] = joined[-1].rstrip() + " " + stripped
                else:
                    joined.append(stripped)
            refs_text = "\n".join(joined)
            r3_joins_total += before_r3.count("\n") - refs_text.count("\n")

            # R2: scrub orphan page-number digits that appear surrounded by
            # lowercase letters (so we don't touch volume numbers, page
            # ranges with hyphens, or year boundaries).
            #
            # v2.4.17 (NORMALIZATION_VERSION 1.8.5): body-noun exception
            # list. Some PDFs (e.g. amle_1) have many standalone-digit lines
            # that are table cell values, NOT page numbers — those falsely
            # contaminate ``_raw_page_numbers``. Guard against false-positive
            # strips on legitimate body phrases like "first 20 years",
            # "1,675 participants", "3,000 hours" by checking the 30-char
            # window after the matched digit for a body-noun keyword
            # (years/days/participants/etc.). If a body noun follows, the
            # digit is part of prose — leave it alone. See
            # ``_R2_BODY_NOUN_PATTERN`` and ``_r2_is_body_phrase``.
            for pg in _raw_page_numbers:
                pat = re.compile(r"(?<=[a-z])(\s+)" + re.escape(str(pg)) + r"(\s+)(?=[a-z])")
                # Use a sub-callable so we can inspect each match individually
                # and skip body-phrase contexts (see ``_r2_is_body_phrase`` —
                # v2.4.17 guard against false-positive strips on legitimate
                # body phrases like "first 20 years"). Track strip count
                # explicitly because ``subn`` counts both preserved and
                # stripped matches.
                pg_str = str(pg)
                _r2_strip_count = [0]
                _captured_refs = refs_text  # closure: read original text
                def _r2_repl(m, _pg=pg_str, _refs=_captured_refs, _c=_r2_strip_count):
                    if _r2_is_body_phrase(_pg, _refs, m.start() + len(m.group(1))):
                        return m.group(0)  # preserve — body phrase
                    _c[0] += 1
                    return " "
                refs_text = pat.sub(_r2_repl, refs_text)
                r2_count_total += _r2_strip_count[0]

            t = t[:r_start] + refs_text + t[r_end:]

        report.steps_applied.append("R2_inline_pgnum_scrub")
        if r2_count_total > 0:
            report.changes_made["inline_pgnum_scrubbed"] = r2_count_total
            report.steps_changed.append("R2_inline_pgnum_scrub")

        report.steps_applied.append("R3_continuation_join")
        if r3_joins_total > 0:
            report.changes_made["ref_continuations_joined"] = r3_joins_total
            report.steps_changed.append("R3_continuation_join")

    # ── Late line-join re-application on stabilized line positions ──────
    # S9 strips repeated header/footer lines via ``"\n".join`` over a filtered
    # list — when an intermediate line is dropped, the two surrounding lines
    # become adjacent with a single `\n` between them. If those neighbours are
    # body prose, stats, or hyphenated word parts, the join produces a fresh
    # line-break boundary that S7/S8/A1 already ran past. R2/R3 reference
    # continuation joins can also shift line positions late. Same idempotency
    # pattern as H0r: re-apply the line-join patterns now, on the stabilized
    # line positions, so a second normalize pass finds nothing to do.
    # (run 9 cycle 8 — JOIN bucket.)
    before = t
    # S7r: hyphenation
    t = re.sub(r"([a-z])-\n(?=[a-z])", r"\1", t)
    # S8r: general prose line-break (Greek-aware as in S8)
    t = re.sub(r"([a-z,;])\n(?=[a-zα-ω])", r"\1 ", t)
    if level == NormalizationLevel.academic:
        # A1r: re-apply the stat line-break patterns (same as the A1 block
        # above, in lookahead form so a chained run converges in one pass).
        # The whitespace-around-newline class is `[ \t]*` (horizontal only),
        # NOT `\s*` — `\s*` would match `\n` too and so cross a `\n\n`
        # paragraph break. After S9 strips column-bleed fragments (e.g. the
        # `01\n02\n03\n04\n05` between `p` and `= .05`), the residue is
        # `p\n\n= .05`, a paragraph break — the test_column_bleed
        # _too_many_fragments_ignored contract requires that be LEFT alone.
        # Single-line-removal by S9 / R3 leaves a *single* `\n` between
        # neighbours (`"\n".join` of a filtered list), which is exactly what
        # the strict `[ \t]*\n[ \t]*` boundary matches and joins.
        t = re.sub(r"([pP])[ \t]*\n[ \t]*(?=[=<>])", r"\1 ", t)
        t = re.sub(r"([pP]\s*[=<>])[ \t]*\n[ \t]*(?=\d)", r"\1 ", t)
        t = re.sub(r"(OR|CI|RR)[ \t]*\n[ \t]*(?=\d)", r"\1 ", t)
        t = re.sub(r"(95\s*%)[ \t]*\n[ \t]*(?=CI)", r"\1 ", t)
        t = re.sub(r"([=<>])[ \t]*\n[ \t]*(?=[-\d.])", r"\1 ", t)
        t = re.sub(r"([,;])[ \t]*\n[ \t]*(?=p\s*[<=>])", r"\1 ", t)
        t = re.sub(r"([,;])[ \t]*\n[ \t]*(?=\d+%\s*CI)", r"\1 ", t)
        # Cycle 12 (v2.4.64) — cross-paragraph stat-continuation join.
        # A1 (which uses `\s*` and so crosses paragraph breaks) runs BEFORE
        # S9 strips header/footer lines. So a stat row like
        #   `r(1798) = -0.27,\n\n472\n\nJournal of Decision Making, ...\n\n95% CI [-0.31, ...]`
        # has so much intervening junk that A1's lookahead fails on pass 1;
        # only after S9 strips the junk (producing `,\n\n95% CI`) can the
        # join happen, and that's pass 2. The two patterns below are the
        # paragraph-crossing variants of the comma-to-stat-continuation
        # patterns above — restricted to the high-confidence prefixes
        # `\d+% CI` and `p [<=>]` because no real paragraph STARTS with
        # those tokens (test_column_bleed_too_many_fragments_ignored is
        # unaffected — its input has no leading `,`/`;`).
        # Clears korbmacher (2 papers) from the non-idempotent set.
        t = re.sub(r"([,;])\s*\n\s*\n\s*(?=\d+%\s*CI)", r"\1 ", t)
        t = re.sub(r"([,;])\s*\n\s*\n\s*(?=p\s*[<=>])", r"\1 ", t)
        # Cycle 13 (v2.4.65) — same shape, applied to `=/<>` → digit/dot
        # continuations. li-feldman-fox has `p =\n\n\x0cFox et al. (2005)...
        # \n\n38\n\n.25, OR = .96, 95%CI [.90, 1.03])` where A1's
        # `([=<>])\s*\n\s*([-\d.])` pattern fails on pass 1 (the journal-
        # header text isn't `\s`); S9 strips the header + page number,
        # leaving `p =\n\n.25` — but A1 is over. Pass 2 joins on the
        # cleaned form. The lookahead `(?=[-\d.])` is the load-bearing
        # constraint — real paragraphs rarely START with a leading dot
        # or `-digit`.
        t = re.sub(r"([=<>])\s*\n\s*\n\s*(?=[-.]?\d)", r"\1 ", t)
    report._track("LateJoin_line_break_rejoin", before, t, "late_line_joins")

    # ── H0r: header-banner re-strip on stabilized line positions ─────────
    # The early H0 (top of the pipeline) scans only the first 30 lines of
    # RAW pdftotext output. Un-cleaned front-matter noise can push a real
    # banner line (e.g. a bare publisher/DOI URL) past that 30-line cap, so
    # H0 misses it on the first pass. P0/P1/S9/A1/A7/R3 then strip that
    # noise and shift lines up — the banner lands inside the header zone
    # only AFTER the pipeline has run. Re-running H0 here, to a fixed point
    # on the final line positions, makes normalize_text idempotent: a second
    # normalize pass finds the header already clean. (run 9 cycle 7 — fixes
    # the test_normalization_idempotent regression.)
    before = t
    while True:
        _restripped = _strip_document_header_banners(t)
        if _restripped == t:
            break
        t = _restripped
    report._track("H0r_header_banner_restrip", before, t, "header_banners_restripped")

    # ── Final blank-line collapse ────────────────────────────────────────
    # S9 enforces `re.sub(r"\n{3,}", "\n\n", t)` once near the top of the
    # pipeline. Later steps that REMOVE non-blank content can leave blank
    # gaps that S9's earlier collapse no longer reaches:
    #
    #   - R3 (refs-section continuation join) walks the refs span line by
    #     line. A bare form-feed `\x0c` (pdftotext page-break) between two
    #     blank lines becomes `"".strip() == ""` and is preserved as a blank
    #     entry; R3 outputs three consecutive blank entries surrounded by
    #     `"\n".join(...)` — `\n\n\n\n`. Pass 1 leaves this; pass 2's S9
    #     collapses it, producing the bibliography-shift non-idempotence
    #     (cycle 12 — 5 papers: chan-etal, horsham, lee-feldman,
    #     li-feldman-mental, + 1 incidental).
    #   - Same pattern for any late strip step that empties a line without
    #     re-collapsing.
    #
    # Add the collapse here so the function is idempotent regardless of
    # which late step produced the blank-line run.
    t = re.sub(r"\n{3,}", "\n\n", t)

    # ── P1r: front-matter metadata-leak re-strip on stabilized lines ─────
    # Same shape as H0r and P0r. P1's `_strip_frontmatter_metadata_leaks`
    # matches an acknowledgment-style line by ANCHORED prefix + a keyword
    # check within the first 300 chars (e.g. `^We\s+thank...reviewers|
    # editor|feedback|comments|suggestions|insights|helpful`). pdftotext
    # often line-wraps the acknowledgment before the keyword fires (e.g.
    # `We thank the target article's authors - Prof. Craig Fox and Prof.
    # Rebecca Ratner, for being very` — the raw line stops before
    # `helpful`). S7/S8 join the continuation; the joined line now contains
    # the keyword, but P1 has already run by then. Pass 2's P1 catches the
    # joined form and strips — non-idempotence + a missed production strip.
    #
    # Re-running here on the post-LateJoin line positions catches every
    # form (the original short line where the keyword was already in
    # window, AND the post-join long line where it's only in window after
    # the join).
    #
    # Cycle 13 (v2.4.65) — clears li-feldman-fox + amp-1 + annals-2 +
    # xiao-poc-epley (4 acknowledgment-block papers) from the
    # non-idempotent set.
    before = t
    while True:
        _restripped = _strip_frontmatter_metadata_leaks(t)
        if _restripped == t:
            break
        t = _restripped
    report._track("P1r_frontmatter_leak_restrip", before, t, "frontmatter_leaks_restripped")

    # ── P0r: page-footer-line re-strip on stabilized line positions ──────
    # Same shape as H0r, applied to P0's anchored ^...$ patterns. P0 runs
    # near the top of the pipeline, where some P0-targeted lines are still
    # SPLIT across two pdftotext rows (e.g. JAMA's
    # `Author affiliations and article information are\nlisted at the end
    # of this article.` — the `^...$` anchors fail because the line is two
    # rows). S7/S8 + the LateJoin block above merge the rows into a single
    # line, but P0 has already run by then. P0r re-applies P0 on the joined
    # line positions and catches the now-single-line forms.
    #
    # Idempotent by construction: _strip_page_footer_lines is a no-op when
    # no pattern matches, so the fixed-point loop converges in 1-2 passes.
    # (run 9 cycle 9 — clears the 10 JAMA `jama_open_*` papers from the
    # 40-paper non-idempotent set; same H0r-pattern generalized.)
    before = t
    while True:
        _restripped = _strip_page_footer_lines(t)
        if _restripped == t:
            break
        t = _restripped
    report._track("P0r_page_footer_restrip", before, t, "page_footer_lines_restripped")

    return t.strip(), report
