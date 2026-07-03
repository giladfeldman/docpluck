"""Taxonomy enums: SectionLabel, Confidence, DetectedVia."""

from docpluck.sections.taxonomy import SectionLabel, Confidence, DetectedVia


def test_canonical_labels_present():
    expected = {
        "title_block", "abstract", "keywords", "author_note",
        "introduction", "literature_review", "methods", "results",
        "discussion", "general_discussion", "conclusion",
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
    assert lookup_canonical_label("General Discussion") == SectionLabel.general_discussion


def test_lookup_returns_none_for_unrecognized():
    assert lookup_canonical_label("Frobnicator") is None
    assert lookup_canonical_label("Some Random Heading") is None
    assert lookup_canonical_label("") is None


# ── v2.4.105: Sage / APA back-matter heading variants (ip_feldman cluster C2) ─
# These render as body text (not `##`) because they were missing from the
# taxonomy — in Sage replication reports they immediately precede their
# paragraph with no blank line, so only canonical-heading recognition (not the
# line-isolated fallback) can promote them.


def test_declaration_of_conflicting_interests_recognized():
    assert (
        lookup_canonical_label("Declaration of Conflicting Interests")
        == SectionLabel.conflict_of_interest
    )
    assert (
        lookup_canonical_label("Declaration of Conflicting Interest")
        == SectionLabel.conflict_of_interest
    )


def test_authorship_declaration_recognized():
    assert (
        lookup_canonical_label("Authorship Declaration")
        == SectionLabel.author_contributions
    )


def test_orcid_ids_heading_recognized_but_not_inline_orcid():
    # The plural heading form is canonical.
    assert lookup_canonical_label("ORCID iDs") == SectionLabel.author_note
    # A bare / singular / inline ORCID must NOT be canonical — it would
    # false-match a line-leading identifier ("ORCID: 0000-…").
    assert lookup_canonical_label("ORCID iD") is None
    assert lookup_canonical_label("ORCID: 0000-0002-1305-0547") is None
