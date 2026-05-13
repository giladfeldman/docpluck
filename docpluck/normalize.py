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
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class NormalizationLevel(str, Enum):
    none = "none"
    standard = "standard"
    academic = "academic"


NORMALIZATION_VERSION = "1.8.3"


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


def normalize_text(
    text: str,
    level: NormalizationLevel,
    *,
    layout=None,
    table_regions: list[dict] | None = None,
) -> tuple[str, NormalizationReport]:
    """Apply normalization pipeline at the specified level.

    When `layout` is provided (a docpluck.extract_layout.LayoutDoc), the
    F0 step strips footnotes/running-headers/footers using PDF layout info
    and populates report.footnote_spans + report.page_offsets.

    When `table_regions` (a list of ``{"page": int, "bbox": (x0, top, x1, bottom)}``)
    is provided alongside `layout`, F0 will not strip lines whose y-range falls
    inside any table region — preserving table footnotes (e.g. ``Note. *p < .05.``)
    that would otherwise be misclassified as page footnotes.
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

    # ── W0: Publisher-overlay watermark stripping (Request 9) ──────────
    # Runs BEFORE S0 so mid-line watermarks don't leak into body text via
    # downstream whitespace collapse. Patterns are precise (URL+date or
    # known publisher templates) — no false-positive risk on prose.
    before = t
    for _wp in _WATERMARK_PATTERNS:
        t = _wp.sub("", t)
    report._track("W0_watermark_strip", before, t, "watermarks_stripped")

    # ── Standard steps (S1-S9) ──────────────────────────────────────────

    # S0: SMP Mathematical Italic -> ASCII
    before = t
    # Math italic capitals A-Z: U+1D434 - U+1D44D
    for i, letter in enumerate("ABCDEFGHIJKLMNOPQRSTUVWXYZ"):
        t = t.replace(chr(0x1D434 + i), letter)
    # Math italic small a-z: U+1D44E - U+1D467
    for i, letter in enumerate("abcdefghijklmnopqrstuvwxyz"):
        t = t.replace(chr(0x1D44E + i), letter)
    # Math italic Greek
    _greek = {
        0x1D6E2: "A", 0x1D6E4: "G", 0x1D6E5: "D", 0x1D6F4: "S",
        0x1D6F7: "Ph", 0x1D6F8: "Ch", 0x1D6F9: "Ps", 0x1D6FA: "O",
        0x1D6FC: "a", 0x1D6FD: "b", 0x1D6FE: "g", 0x1D6FF: "d",
        0x1D700: "e", 0x1D701: "z", 0x1D702: "n", 0x1D703: "th",
        0x1D707: "m", 0x1D70B: "pi", 0x1D70C: "r", 0x1D70E: "s",
        0x1D711: "ph", 0x1D712: "ch", 0x1D713: "ps",
    }
    for cp, repl in _greek.items():
        t = t.replace(chr(cp), repl)
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

    # S3: Ligature expansion
    before = t
    t = t.replace("\ufb00", "ff")
    t = t.replace("\ufb01", "fi")
    t = t.replace("\ufb02", "fl")
    t = t.replace("\ufb03", "ffi")
    t = t.replace("\ufb04", "ffl")
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

    # S7: Hyphenation repair
    before = t
    t = re.sub(r"([a-z])-\n([a-z])", r"\1\2", t)
    report._track("S7_hyphenation_repair", before, t, "hyphenations_repaired")

    # S8: Mid-sentence line break joining
    before = t
    t = re.sub(r"([a-z,;])\n([a-z])", r"\1 \2", t)
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
    for line in lines:
        stripped = line.strip()
        if 15 <= len(stripped) <= 120:
            line_counts[stripped] = line_counts.get(stripped, 0) + 1
    repeated = {line for line, count in line_counts.items() if count >= 5}
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
    strip_set: set[str] = {s for s, c in four_digit_counts.items() if c >= 3}

    # Pattern B: ≥3 distinct values clustered tightly together.
    if len(four_digit_counts) >= 3:
        values = sorted(int(s) for s in four_digit_counts.keys())
        spread = values[-1] - values[0]
        if spread <= 50:
            # Compute mean of consecutive diffs.
            diffs = [values[i + 1] - values[i] for i in range(len(values) - 1)]
            mean_diff = sum(diffs) / len(diffs)
            if mean_diff <= 3.0:
                # All values in the cluster are page numbers.
                strip_set.update(str(v) for v in values)

    if strip_set:
        t = "\n".join(
            "" if ln.strip() in strip_set else ln
            for ln in t.split("\n")
        )
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
        ]
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
        # (\s | ; ) ] | $) — broadening it to [^0-9a-zA-Z] caused A4 ordering
        # regressions, so we rely on A4 to handle bracket-internal commas.
        before = t
        t = re.sub(
            r"(?<![a-zA-Z,0-9\[\(])(\d),(\d{1,3})(?=\s|[;)\]]|$)",
            r"\1.\2",
            t,
        )
        report._track("A3_decimal_comma_normalization", before, t, "decimal_commas_fixed")

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
        before = t
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
            for pg in _raw_page_numbers:
                pat = re.compile(r"(?<=[a-z])\s+" + re.escape(str(pg)) + r"\s+(?=[a-z])")
                refs_text, c = pat.subn(" ", refs_text)
                r2_count_total += c

            t = t[:r_start] + refs_text + t[r_end:]

        report.steps_applied.append("R2_inline_pgnum_scrub")
        if r2_count_total > 0:
            report.changes_made["inline_pgnum_scrubbed"] = r2_count_total
            report.steps_changed.append("R2_inline_pgnum_scrub")

        report.steps_applied.append("R3_continuation_join")
        if r3_joins_total > 0:
            report.changes_made["ref_continuations_joined"] = r3_joins_total
            report.steps_changed.append("R3_continuation_join")

    return t.strip(), report
