"""Taxonomy enums: SectionLabel, Confidence, DetectedVia."""

from docpluck.sections.taxonomy import SectionLabel, Confidence, DetectedVia


def test_canonical_labels_present():
    expected = {
        "title_block", "abstract", "keywords", "author_note",
        "introduction", "literature_review", "methods", "results",
        "discussion", "general_discussion",
        "acknowledgments", "funding", "conflict_of_interest",
        "data_availability", "author_contributions",
        "references", "appendix", "supplementary",
        "footnotes", "unknown", "study_n_header",
    }
    actual = {label.value for label in SectionLabel}
    assert actual == expected


def test_confidence_levels():
    assert Confidence.high.value == "high"
    assert Confidence.medium.value == "medium"
    assert Confidence.low.value == "low"


def test_detected_via_options():
    assert DetectedVia.heading_match.value == "heading_match"
    assert DetectedVia.markup.value == "markup"
    assert DetectedVia.layout_signal.value == "layout_signal"
    assert DetectedVia.text_pattern_fallback.value == "text_pattern_fallback"
    assert DetectedVia.position_inferred.value == "position_inferred"
