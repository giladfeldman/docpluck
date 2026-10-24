"""Body-scope text: the document text without its bibliography.

``extract_pdf`` + ``normalize_text`` return the WHOLE document: title block,
body, back matter and the reference list. A consumer that wants only what the
authors wrote as running text (for text comparison, readability, search or
language models) had to cut the bibliography out itself. This module does it:

* :func:`extract_pdf_body` runs the layout-aware text path (``extract_pdf`` +
  ``extract_pdf_layout`` + ``normalize_text(layout=...)``, which already strips
  running heads and moves footnotes out of the body) and removes the reference
  list.
* :func:`body_scope_text` does the removal on text you already have.

Additive: nothing else in docpluck calls this module, so every existing output
is unchanged.

What is removed: every section the sectioner labels ``references`` (a headed
bibliography, a German ``Literatur`` list, or an unheaded numbered list of
reference entries). Nothing else: dropping all front and back matter was
measured to cost more body text than it saved.

The guard: a references section ends where its entry-shaped lines end. When a
paper's linearised text places body paragraphs after the bibliography heading
(reference numbers printed in a separate column, a two-column page read out of
order), those paragraphs are kept, and reported in
``BodyScopeReport.kept_after_references``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .normalize import NormalizationLevel, NormalizationReport

BODY_SCOPE_VERSION = "1.0.0"

# The separator ``normalize_text(layout=...)`` puts between the body and the
# footnote appendix it moved out of the body.
_FOOTNOTE_APPENDIX_SEP = "\n\f\f\n"

# A references section whose entry-shaped lines stop and are followed by this
# many characters of non-entry text has ended; the rest is kept as body.
_NON_ENTRY_RUN_CHARS = 1200
# Lines this short directly after the last entry are its wrapped continuation.
_CONTINUATION_MAX_CHARS = 120


@dataclass(frozen=True)
class RemovedSpan:
    """One span cut out of the text. Offsets index the text that was passed in
    (for :func:`extract_pdf_body`, the layout-aware body text)."""

    label: str
    char_start: int
    char_end: int
    heading_text: str | None


@dataclass(frozen=True)
class BodyScopeReport:
    removed: tuple[RemovedSpan, ...] = ()
    # Text inside a ``references`` section that the guard kept because it is
    # not entry-shaped (body paragraphs linearised after the heading).
    kept_after_references: tuple[tuple[int, int], ...] = ()
    references_found: bool = False
    source_chars: int = 0
    body_scope_version: str = BODY_SCOPE_VERSION
    # Filled by extract_pdf_body only.
    footnote_texts: tuple[str, ...] = ()
    normalization: NormalizationReport | None = field(default=None, repr=False)


# A short line after the last entry that starts a figure or table caption, or
# is the PMC "Author Manuscript" stamp, is not the entry's wrapped tail.
_NOT_A_CONTINUATION = re.compile(r"(?i)(?:fig(?:ure)?\b|table\b|author manuscript\b)")
_CAPTION_LABEL = re.compile(r"(?:Table|Fig\.?|Figure)[ \t]*[A-Z]?\d")
_LINK = re.compile(r"(?i)\bdoi\b|https?://|\b10\.\d{4,9}/|\[PubMed|\bPMID\b")
# A journal volume-and-pages tail: "12(3), 45-67", "98:110-114", "12, 1-10".
_VOLUME_PAGES = re.compile(r"\b\d{1,4}[ \t]?\(\d{1,4}\)[,:]?[ \t]?e?\d+|\b\d{1,4}[,:][ \t]?e?\d{1,6}[-–]\d{1,6}\b")


def _is_entry_line(line: str) -> bool:
    """A line that belongs to a reference list: a numbered entry, an
    author-and-year line, a wrapped author list (three or more "Surname AB,"
    names), an identifier line (DOI, URL, PubMed id), or a journal
    volume-and-pages tail."""
    from .sections._reference_entries import (
        _AUTHOR, _NUMBERED_ENTRY, looks_like_reference_entry,
    )

    return (
        bool(_NUMBERED_ENTRY.match(line))
        or looks_like_reference_entry(line)
        or len(_AUTHOR.findall(line)) >= 3
        or bool(_LINK.search(line))
        or bool(_VOLUME_PAGES.search(line))
    )


def reference_list_end(text: str, start: int, end: int) -> int:
    """Where the reference list that occupies ``text[start:end]`` really ends.

    Walks the lines; the list ends after the last entry-shaped line (plus its
    short wrapped continuation lines) that is followed by at least
    ``_NON_ENTRY_RUN_CHARS`` of non-entry text, or at ``end``.
    """
    pos = start
    last_entry_end = None  # end offset of the last entry-shaped line seen
    non_entry_since = None  # offset where the current non-entry run began
    while pos < end:
        nl = text.find("\n", pos, end)
        line_end = end if nl < 0 else nl + 1
        line = text[pos:line_end].strip()
        if line:
            if _is_entry_line(line):
                last_entry_end = line_end
                non_entry_since = None
            elif last_entry_end is not None:
                if non_entry_since is None:
                    if (len(line) <= _CONTINUATION_MAX_CHARS and pos == last_entry_end
                            and not _NOT_A_CONTINUATION.match(line)):
                        # wrapped continuation of the entry just before
                        last_entry_end = line_end
                    else:
                        non_entry_since = pos
                if non_entry_since is not None and line_end - non_entry_since >= _NON_ENTRY_RUN_CHARS:
                    return _before_trailing_caption(text, start, non_entry_since)
        elif last_entry_end is not None and non_entry_since is None and pos == last_entry_end:
            last_entry_end = line_end  # blank line after an entry
        pos = line_end
    return _before_trailing_caption(text, start, end)


def _before_trailing_caption(text: str, start: int, stop: int) -> int:
    """Pull ``stop`` back to the first figure/table caption line that follows
    the last entry-shaped line: a caption printed after the bibliography is
    body content, however short (a table title is well under the 1200-char
    run the main rule needs)."""
    last_entry_end = start
    pos = start
    lines = []
    while pos < stop:
        nl = text.find("\n", pos, stop)
        line_end = stop if nl < 0 else nl + 1
        line = text[pos:line_end].strip()
        if line:
            lines.append((pos, line))
            if _is_entry_line(line):
                last_entry_end = line_end
        pos = line_end
    for p, line in lines:
        if p >= last_entry_end and _CAPTION_LABEL.match(line):
            return p
    return stop


# A run of reference entries outside the references section counts only when it
# holds at least this many author-and-year entries.
_MIN_RUN_ENTRIES = 3
# Non-entry text a run may hold between two entries (wrapped titles).
_RUN_GAP_CHARS = 600


def _reference_runs(text: str, start: int, end: int) -> list[tuple[int, int]]:
    """Runs of reference entries inside ``text[start:end]``.

    A run starts at an author-and-year (or numbered) entry line and continues
    over entry-shaped lines, their short wrapped tails and blank lines; any
    other line ends it. Runs with fewer than ``_MIN_RUN_ENTRIES`` author-and-year
    entries are not returned. Only called on text AFTER the first references
    heading, where a stretch of entries is the bibliography continuing.
    """
    from .sections._reference_entries import _NUMBERED_ENTRY, looks_like_reference_entry

    runs: list[tuple[int, int]] = []
    run_start = None
    run_end = None
    n_entries = 0
    pending = 0
    pos = start
    while pos < end:
        nl = text.find("\n", pos, end)
        line_end = end if nl < 0 else nl + 1
        line = text[pos:line_end].strip()
        is_head = bool(line) and (
            bool(_NUMBERED_ENTRY.match(line)) or looks_like_reference_entry(line)
        )
        if is_head:
            if run_start is None:
                run_start, n_entries = pos, 0
            n_entries += 1
            run_end = line_end
            pending = 0
        elif run_start is not None:
            if not line:
                pass
            elif _is_entry_line(line) or (
                len(line) <= _CONTINUATION_MAX_CHARS and not _NOT_A_CONTINUATION.match(line)
            ):
                run_end = line_end
                pending = 0
            else:
                # A long line with no entry shape: an entry's wrapped title, or
                # the body resuming. The run survives it only if entries resume
                # within _RUN_GAP_CHARS.
                pending += len(line)
                if pending >= _RUN_GAP_CHARS or _NOT_A_CONTINUATION.match(line):
                    if n_entries >= _MIN_RUN_ENTRIES:
                        runs.append((run_start, run_end))
                    run_start = None
        pos = line_end
    if run_start is not None and n_entries >= _MIN_RUN_ENTRIES:
        runs.append((run_start, run_end))
    return runs


def body_scope_text(text: str) -> tuple[str, BodyScopeReport]:
    """Remove the reference list(s) from ``text``.

    ``text`` should be normalized text (``normalize_text`` output, with or
    without ``layout=``); the footnote appendix that ``layout=`` adds after
    ``"\\n\\f\\f\\n"`` is dropped first, since footnotes are not body text.
    Returns ``(body, report)``; ``report.removed`` holds every span taken out.
    """
    if _FOOTNOTE_APPENDIX_SEP in text:
        text = text.split(_FOOTNOTE_APPENDIX_SEP, 1)[0]
    from .sections import SectionLabel, extract_sections

    doc = extract_sections(text=text, source_format="pdf")
    removed: list[RemovedSpan] = []
    kept: list[tuple[int, int]] = []
    first_refs = None
    for s in doc.sections:
        if s.canonical_label is not SectionLabel.references:
            if first_refs is not None:
                # The bibliography continues under a heading the column order
                # dropped into it ("Disclosure" printed beside the list).
                for a, b in _reference_runs(text, s.char_start, s.char_end):
                    removed.append(RemovedSpan("references_continued", a, b, None))
            continue
        if first_refs is None:
            first_refs = s.char_start
        stop = reference_list_end(text, s.char_start, s.char_end)
        removed.append(RemovedSpan(s.label, s.char_start, stop, s.heading_text))
        if stop < s.char_end:
            kept.append((stop, s.char_end))
            for a, b in _reference_runs(text, stop, s.char_end):
                removed.append(RemovedSpan("references_continued", a, b, None))
    removed.sort(key=lambda r: r.char_start)
    pieces: list[str] = []
    pos = 0
    for r in removed:
        pieces.append(text[pos:r.char_start])
        pos = r.char_end
    pieces.append(text[pos:])
    body = "".join(pieces)
    return body, BodyScopeReport(
        removed=tuple(removed),
        kept_after_references=tuple(kept),
        references_found=bool(removed),
        source_chars=len(text),
    )


def extract_pdf_body(
    pdf_bytes: bytes,
    level: NormalizationLevel = NormalizationLevel.academic,
) -> tuple[str, BodyScopeReport]:
    """Body-scope text of a PDF: layout-aware normalized text, footnotes moved
    out, reference list removed.

    Returns ``(body, report)``. ``report.footnote_texts`` carries the footnotes
    the layout pass separated; ``report.normalization`` the full
    ``NormalizationReport``. Requires pdfplumber (``docpluck[all]``) for the
    layout pass; without it the text is normalized without ``layout=``, so
    running heads and footnotes stay in, and that is recorded as the
    ``body_scope_no_layout`` fallback.
    """
    from .extract import extract_pdf
    from .normalize import normalize_text
    from .telemetry import record_fallback

    raw, _method = extract_pdf(pdf_bytes)
    layout = None
    try:
        from .extract_layout import extract_pdf_layout

        layout = extract_pdf_layout(pdf_bytes)
    except Exception as exc:  # pdfplumber missing or the layout pass failed
        record_fallback("body_scope_no_layout", detail=type(exc).__name__)
    if layout is not None:
        normalized, nreport = normalize_text(raw, level, layout=layout)
    else:
        normalized, nreport = normalize_text(raw, level)
    body, report = body_scope_text(normalized)
    return body, BodyScopeReport(
        removed=report.removed,
        kept_after_references=report.kept_after_references,
        references_found=report.references_found,
        source_chars=report.source_chars,
        footnote_texts=tuple(getattr(nreport, "footnote_texts", ()) or ()),
        normalization=nreport,
    )


__all__ = [
    "BODY_SCOPE_VERSION",
    "BodyScopeReport",
    "RemovedSpan",
    "body_scope_text",
    "extract_pdf_body",
    "reference_list_end",
]
