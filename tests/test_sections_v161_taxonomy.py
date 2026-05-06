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
