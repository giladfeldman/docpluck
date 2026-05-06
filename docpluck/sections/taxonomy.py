"""Canonical section labels + heading-text → label map."""

from __future__ import annotations

import re
from enum import Enum


class SectionLabel(str, Enum):
    # Front matter
    title_block = "title_block"
    abstract = "abstract"
    keywords = "keywords"
    author_note = "author_note"
    # Body
    introduction = "introduction"
    literature_review = "literature_review"
    methods = "methods"
    results = "results"
    discussion = "discussion"
    general_discussion = "general_discussion"
    # Back matter
    acknowledgments = "acknowledgments"
    funding = "funding"
    conflict_of_interest = "conflict_of_interest"
    data_availability = "data_availability"
    author_contributions = "author_contributions"
    references = "references"
    appendix = "appendix"
    supplementary = "supplementary"
    # Special
    footnotes = "footnotes"
    unknown = "unknown"
    study_n_header = "study_n_header"


class Confidence(str, Enum):
    high = "high"
    medium = "medium"
    low = "low"


class DetectedVia(str, Enum):
    heading_match = "heading_match"
    markup = "markup"
    layout_signal = "layout_signal"
    text_pattern_fallback = "text_pattern_fallback"
    position_inferred = "position_inferred"


# Heading-text → canonical-label map. Lookup is case-folded,
# whitespace-collapsed, leading-numbering-stripped, trailing-punctuation-stripped.
# Variants per label are grouped in a frozenset for O(1) multi-key lookup.
HEADING_TO_LABEL: dict[frozenset[str], SectionLabel] = {
    # Front matter
    frozenset({"abstract", "summary"}): SectionLabel.abstract,
    frozenset({"keywords", "key words", "keyword"}): SectionLabel.keywords,
    frozenset({"author note", "author's note", "authors' note", "authors note"}):
        SectionLabel.author_note,
    # Body
    frozenset({"introduction", "background", "introduction and background"}):
        SectionLabel.introduction,
    frozenset({"literature review", "review of literature", "related work",
               "theoretical background", "theory"}): SectionLabel.literature_review,
    frozenset({"method", "methods", "materials and methods", "materials & methods",
               "experimental procedures", "methodology", "experimental design",
               "study design"}): SectionLabel.methods,
    frozenset({"results", "results and discussion", "findings",
               "empirical results"}): SectionLabel.results,
    frozenset({"discussion", "general discussion"}): SectionLabel.discussion,
    # General discussion gets its own label only when explicitly named that way.
    frozenset({"general discussion", "overall discussion"}):
        SectionLabel.general_discussion,
    # Back matter
    frozenset({"acknowledgments", "acknowledgements", "acknowledgment",
               "acknowledgement"}): SectionLabel.acknowledgments,
    frozenset({"funding", "funding statement", "funding information",
               "financial support", "grants"}): SectionLabel.funding,
    frozenset({"conflict of interest", "conflicts of interest",
               "competing interests", "competing interest",
               "declaration of interest", "declaration of interests",
               "declaration of competing interest",
               "declaration of competing interests",
               "declarations", "disclosure", "disclosures",
               "competing financial interests"}):
        SectionLabel.conflict_of_interest,
    frozenset({"data availability", "data availability statement",
               "availability of data", "data and materials availability",
               "code availability", "data and code availability"}):
        SectionLabel.data_availability,
    frozenset({"author contributions", "author contribution",
               "contributions", "credit authorship statement",
               "credit author statement"}): SectionLabel.author_contributions,
    frozenset({"references", "bibliography", "works cited", "literature cited",
               "literature", "cited literature", "reference list",
               "list of references", "cited references"}): SectionLabel.references,
    frozenset({"appendix", "appendices", "appendix a", "appendix b",
               "appendix c", "appendix d"}): SectionLabel.appendix,
    frozenset({"supplementary", "supplementary material",
               "supplementary materials", "supplementary information",
               "supporting information", "online supplement",
               "supplemental materials", "supplemental material",
               "online supplementary material"}): SectionLabel.supplementary,
}


# Resolution order matters when a heading appears in multiple frozensets
# (currently only "general discussion" → both discussion and general_discussion).
# We prefer the more specific label.
_PREFERRED_OVER: dict[SectionLabel, SectionLabel] = {
    SectionLabel.general_discussion: SectionLabel.discussion,
}


_NUMBERING_PREFIX = re.compile(r"^\s*(\d+(\.\d+)*\.?)\s+")
_PUNCT_TRAILING = re.compile(r"[\s:.\-–—]+$")
_WHITESPACE = re.compile(r"\s+")


def _normalize_heading(text: str) -> str:
    """Case-fold, strip leading numbering, collapse whitespace, strip
    trailing punctuation. Returns '' for input that becomes empty."""
    s = text.strip().lower()
    s = _NUMBERING_PREFIX.sub("", s)
    s = _PUNCT_TRAILING.sub("", s)
    s = _WHITESPACE.sub(" ", s)
    return s.strip()


def lookup_canonical_label(heading_text: str) -> SectionLabel | None:
    """Map a literal heading string to its canonical SectionLabel, or None."""
    normalized = _normalize_heading(heading_text)
    if not normalized:
        return None
    matches: list[SectionLabel] = []
    for variants, label in HEADING_TO_LABEL.items():
        if normalized in variants:
            matches.append(label)
    if not matches:
        return None
    if len(matches) == 1:
        return matches[0]
    # Multi-match — apply preference order.
    for preferred, less_specific in _PREFERRED_OVER.items():
        if preferred in matches and less_specific in matches:
            return preferred
    return matches[0]
