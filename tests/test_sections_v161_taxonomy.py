"""v1.6.1 taxonomy fixes: procedure removal + declaration of competing interest."""

from docpluck.sections.taxonomy import lookup_canonical_label, SectionLabel


# --- Fix 1: procedure/procedures removed from methods canonical set ---

def test_procedure_alone_not_canonical_methods():
    """Procedure on its own is a subsection inside Methods, not a top-level section."""
    assert lookup_canonical_label("Procedure") is None
    assert lookup_canonical_label("Procedures") is None


def test_method_still_canonical():
    assert lookup_canonical_label("Method") == SectionLabel.methods
    assert lookup_canonical_label("Methods") == SectionLabel.methods
    assert lookup_canonical_label("Materials and Methods") == SectionLabel.methods


def test_experimental_procedures_still_canonical():
    """Compound 'experimental procedures' is a real section title."""
    assert lookup_canonical_label("Experimental Procedures") == SectionLabel.methods


# --- Fix 2: declaration of competing interest variants ---

def test_declaration_of_competing_interest_canonical():
    assert lookup_canonical_label("Declaration of Competing Interest") == \
        SectionLabel.conflict_of_interest
    assert lookup_canonical_label("Declaration of Competing Interests") == \
        SectionLabel.conflict_of_interest


def test_existing_conflict_of_interest_variants_still_work():
    """Ensure we didn't break existing variants."""
    assert lookup_canonical_label("Conflict of Interest") == SectionLabel.conflict_of_interest
    assert lookup_canonical_label("Competing Interests") == SectionLabel.conflict_of_interest
    assert lookup_canonical_label("Declaration of Interest") == SectionLabel.conflict_of_interest
    assert lookup_canonical_label("Declaration of Interests") == SectionLabel.conflict_of_interest
    assert lookup_canonical_label("Disclosure") == SectionLabel.conflict_of_interest


# --- Fix 3 (chan_feldman_2025 / chandrashekar_2023): subsection synonyms ---

def test_subsection_methods_synonyms_no_longer_canonical():
    """v1.6.1: Experimental design / Study design are typically subsections of
    Method in APA papers, not top-level methods sections.

    "Methodology" was REINSTATED on 2026-05-08 as canonical after the IEEE
    iteration showed it's the standard top-level methods heading in IEEE /
    technical papers ("II. METHODOLOGY").  False-positive risk in CRediT
    author-contribution tables (where "Methodology" appears as a row label
    followed by a single-char "X" cell) is handled by the table-cell filter
    in annotators/text.py — see test_credit_table_methodology_row_not_emitted.
    """
    assert lookup_canonical_label("Experimental design") is None
    assert lookup_canonical_label("Experimental Design") is None
    assert lookup_canonical_label("Study design") is None
    assert lookup_canonical_label("Study Design") is None
    # Methodology is canonical again — but the table-cell filter rejects the
    # CRediT row variant.  Cf. test_credit_table_methodology_row_not_emitted.
    assert lookup_canonical_label("Methodology") == SectionLabel.methods


def test_method_canonical_methods_still_works():
    assert lookup_canonical_label("Method") == SectionLabel.methods
    assert lookup_canonical_label("Methods") == SectionLabel.methods
    assert lookup_canonical_label("Materials and Methods") == SectionLabel.methods


def test_conclusion_is_separate_canonical_from_discussion():
    """Reinstated 2026-05-08 evening, then split off into its own label
    after Aiyer-Collabra 2024 demonstrated that empirical papers commonly
    have BOTH a Discussion section AND a brief Conclusion wrap-up.  Mapping
    Conclusion to its own label preserves the distinction (rather than
    producing 'discussion_2' for the Conclusion block).

    Combined "Discussion and Conclusion" headings stay as discussion — the
    section is primarily discussion.
    """
    assert lookup_canonical_label("Conclusion") == SectionLabel.conclusion
    assert lookup_canonical_label("Conclusions") == SectionLabel.conclusion
    assert lookup_canonical_label("Concluding remarks") == SectionLabel.conclusion
    assert lookup_canonical_label("Conclusion and Future Work") == SectionLabel.conclusion
    # Discussion-and-Conclusion combined stays discussion.
    assert lookup_canonical_label("Discussion and Conclusion") == SectionLabel.discussion
    assert lookup_canonical_label("Discussion and Conclusions") == SectionLabel.discussion


def test_summary_no_longer_abstract_canonical():
    """v1.6.1 removed Summary, 2026-05-08 evening reinstated for RSOS,
    2026-05-09 reverted: in real-world psychology papers Summary appears
    far more often as a mid-paper subsection ("Summary of Original Studies",
    "Summary and conclusion") than as an abstract heading.  RSOS papers
    that use "1. Summary" as their abstract are handled by Pattern E
    leading-unknown abstract synthesis (the abstract paragraph still gets
    extracted, the heading text just isn't canonically linked)."""
    assert lookup_canonical_label("Summary") is None


def test_abstract_canonical_still_works():
    assert lookup_canonical_label("Abstract") == SectionLabel.abstract
    assert lookup_canonical_label("ABSTRACT") == SectionLabel.abstract
