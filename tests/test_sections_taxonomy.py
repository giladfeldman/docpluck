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


from docpluck.sections.taxonomy import lookup_canonical_label


def test_lookup_exact_match():
    assert lookup_canonical_label("Abstract") == SectionLabel.abstract
    assert lookup_canonical_label("References") == SectionLabel.references
    assert lookup_canonical_label("Methods") == SectionLabel.methods


def test_lookup_case_insensitive():
    assert lookup_canonical_label("ABSTRACT") == SectionLabel.abstract
    assert lookup_canonical_label("references") == SectionLabel.references


def test_lookup_whitespace_collapsed():
    assert lookup_canonical_label("  Abstract  ") == SectionLabel.abstract
    assert lookup_canonical_label("Materials  and  Methods") == SectionLabel.methods


def test_lookup_punctuation_stripped():
    assert lookup_canonical_label("References:") == SectionLabel.references
    assert lookup_canonical_label("1. Methods") == SectionLabel.methods
    assert lookup_canonical_label("2.1. Materials and Methods") == SectionLabel.methods


def test_lookup_synonyms():
    assert lookup_canonical_label("Bibliography") == SectionLabel.references
    assert lookup_canonical_label("Works Cited") == SectionLabel.references
    assert lookup_canonical_label("Materials & Methods") == SectionLabel.methods
    assert lookup_canonical_label("Background") == SectionLabel.introduction
    assert lookup_canonical_label("Competing Interests") == SectionLabel.conflict_of_interest
    assert lookup_canonical_label("Disclosure") == SectionLabel.conflict_of_interest
    assert lookup_canonical_label("Supporting Information") == SectionLabel.supplementary


def test_lookup_returns_none_for_unrecognized():
    assert lookup_canonical_label("Frobnicator") is None
    assert lookup_canonical_label("Some Random Heading") is None
    assert lookup_canonical_label("") is None
