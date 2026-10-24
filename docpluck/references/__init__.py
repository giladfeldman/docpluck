"""docpluck.references -- bibliography entries and in-text citation linking.

Public API (re-exported from ``docpluck``):

* :func:`parse_reference` -- one printed entry string -> :class:`Reference`.
* :func:`parse_references` -- a references section's text -> entries, split and parsed.
* :func:`extract_references` -- a document -> its bibliography.
* :func:`link_citations` -- text + entries -> :class:`Citation` list.
* :func:`extract_citations` -- a document -> :class:`CitationAnalysis` (entries,
  citations, uncited entries, orphan citations, duplicate entries).

Deterministic, pure-Python heuristics over docpluck's own sectioned text; no
model and no external service. The bibliography is the document's
``references`` section(s) as :func:`docpluck.extract_sections` finds them; when
no section is labelled ``references``, the text after the last line that reads
as a references heading is used.
"""

from __future__ import annotations

import re
from typing import Literal

from .link import duplicate_groups, link_citations
from .parse import parse_reference
from .split import densest_entry_run, entry_density, split_entries
from .types import Citation, CitationAnalysis, CitationKind, Reference, ReferenceAuthor, ReferenceStyle

#: Bump when entry splitting, field parsing or citation linking changes output.
REFERENCES_VERSION = "1.0.0"

__all__ = [
    "REFERENCES_VERSION",
    "Citation",
    "CitationAnalysis",
    "CitationKind",
    "Reference",
    "ReferenceAuthor",
    "ReferenceStyle",
    "extract_citations",
    "extract_references",
    "link_citations",
    "parse_reference",
    "parse_references",
]


def parse_references(text: str, *, offset: int = 0) -> tuple[Reference, ...]:
    """Split a references section's text into entries and parse each.

    ``offset`` is added to every entry's ``char_start`` / ``char_end`` (pass the
    section's own start to get offsets into the whole document's text).
    """
    out = []
    for i, e in enumerate(split_entries(text), start=1):
        rid = str(e.number) if e.number is not None else f"r{i}"
        out.append(parse_reference(e.text, reference_id=rid, number=e.number,
                                   char_start=offset + e.char_start, char_end=offset + e.char_end))
    return tuple(out)


#: Section labels that never follow a bibliography in a real paper. A section
#: with one of these labels that starts inside a reference list -- a lone
#: "Methods." line wrapped out of "Behavior Research Methods." reads as a heading
#: -- is absorbed back into the list when its own text is entry-shaped.
_SPURIOUS_AFTER_REFERENCES = {
    "introduction", "literature_review", "methods", "results", "discussion",
    "general_discussion", "conclusion", "study_n_header", "abstract", "keywords", "unknown",
}


#: a references heading on its own line ("References", "6. References"), or run
#: into the first entry on the same line ("References Adams, Jimi, and ...")
_REF_HEADING_LINE = re.compile(
    r"(?m)^[ \t\f]*(?:\d{1,2}\.?[ \t]+)?"
    r"(?:References?(?:\s+Cited)?|REFERENCES?|Bibliography|BIBLIOGRAPHY|Literature\s+Cited|Works\s+Cited)"
    r"(?:[ \t]*:?[ \t]*$|[ \t]+(?=[A-Za-z][\w'’\-]*,))"
)


def _label(section) -> str:
    return getattr(section.canonical_label, "value", section.canonical_label)


def _references_spans(doc) -> list[tuple[int, int]]:
    sections = list(doc.sections)
    spans: list[tuple[int, int]] = []
    i = 0
    while i < len(sections):
        s = sections[i]
        if _label(s) != "references":
            i += 1
            continue
        start, end = s.char_start, s.char_end
        j = i + 1
        while j < len(sections) and _label(sections[j]) in _SPURIOUS_AFTER_REFERENCES \
                and entry_density(sections[j].text) >= 0.5:
            end = sections[j].char_end
            j += 1
        spans.append((start, end))
        i = j
    text = doc.normalized_text
    found = sum(len(split_entries(text[a:b])) for a, b in spans)
    if found >= 3:
        return spans
    # No references section, or one that holds (almost) nothing -- the list was
    # filed under another section or read out of place. Try (a) the text after
    # the last references heading, up to the end of the section holding it, and
    # (b) the longest run of entry-opening lines; keep whichever holds more.
    best, best_n = spans, found
    candidates = []

    def section_end(pos: int, extra: int = 0) -> int:
        for k, s in enumerate(sections):
            if s.char_start <= pos < s.char_end:
                return sections[min(k + extra, len(sections) - 1)].char_end
        return len(text)

    for h in _REF_HEADING_LINE.finditer(text):
        # to the end of the section holding the heading, or of the next one when
        # the heading closes its section (the list was filed under the next)
        candidates.append((h.end(), section_end(h.start())))
        candidates.append((h.end(), section_end(h.start(), 1)))
    for a, _b in spans:
        candidates.append((a, section_end(a, 1)))
    run = densest_entry_run(text)
    if run is not None:
        candidates.append(run)
    for a, b in candidates:
        n = len(split_entries(text[a:b]))
        if n > best_n:
            best, best_n = [(a, b)], n
    return best


def _from_document(file_bytes, text, source_format, normalization_level):
    from ..sections import extract_sections

    kwargs = {}
    if normalization_level is not None:
        kwargs["normalization_level"] = normalization_level
    if file_bytes is not None:
        doc = extract_sections(file_bytes=file_bytes, source_format=source_format, **kwargs)
    else:
        if text is None:
            raise ValueError("pass file_bytes or text")
        doc = extract_sections(text=text, source_format=source_format or "pdf", **kwargs)
    spans = _references_spans(doc)
    refs: list[Reference] = []
    seen: set[str] = set()
    for a, b in spans:
        for r in parse_references(doc.normalized_text[a:b], offset=a):
            if r.reference_id in seen:  # a second numbered list (supplementary)
                from dataclasses import replace
                k = 2
                while f"{r.reference_id}#{k}" in seen:
                    k += 1
                r = replace(r, reference_id=f"{r.reference_id}#{k}")
            seen.add(r.reference_id)
            refs.append(r)
    return doc, spans, tuple(refs)


def extract_references(
    file_bytes: bytes | None = None,
    *,
    text: str | None = None,
    source_format: Literal["pdf", "docx", "html"] | None = None,
    normalization_level=None,
) -> tuple[Reference, ...]:
    """Return the document's bibliography as parsed :class:`Reference` entries.

    Pass ``file_bytes`` (PDF, DOCX or HTML) or already-extracted ``text``.
    Offsets index the document's normalized text (``extract_sections(...).normalized_text``).
    """
    return _from_document(file_bytes, text, source_format, normalization_level)[2]


def extract_citations(
    file_bytes: bytes | None = None,
    *,
    text: str | None = None,
    source_format: Literal["pdf", "docx", "html"] | None = None,
    normalization_level=None,
) -> CitationAnalysis:
    """Bibliography, in-text citations and their links for one document."""
    doc, spans, refs = _from_document(file_bytes, text, source_format, normalization_level)
    body = doc.normalized_text
    citations = link_citations(body, refs, exclude_spans=spans) if refs else ()
    cited = {rid for c in citations for rid in c.reference_ids}
    style: ReferenceStyle | None = None
    if refs:
        style = "numbered" if sum(r.number is not None for r in refs) >= len(refs) / 2 else "author_year"
    return CitationAnalysis(
        references=refs,
        citations=citations,
        style=style,
        uncited_reference_ids=tuple(r.reference_id for r in refs if r.reference_id not in cited),
        orphan_citations=tuple(c.marker_text for c in citations if not c.reference_ids),
        duplicate_reference_groups=duplicate_groups(refs),
        text=body,
        references_version=REFERENCES_VERSION,
    )
