"""Canonical section labels + heading-text → label map."""

from __future__ import annotations

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
