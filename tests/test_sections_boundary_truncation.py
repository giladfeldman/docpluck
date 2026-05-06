"""Partitioner truncates a span when boundary pattern fires inside it."""

from docpluck.sections.blocks import BlockHint
from docpluck.sections.core import partition_into_sections
from docpluck.sections.taxonomy import SectionLabel


def _hint(text, start, end):
    return BlockHint(
        text=text, char_start=start, char_end=end,
        page=None, is_heading_candidate=True,
        heading_strength="strong", heading_source="text_pattern",
    )


def test_author_bio_inside_references_not_truncated():
    """v1.6.1: References are exempt from boundary truncation, so an
    author-bio paragraph that follows the reference list stays inside
    the references section rather than being split into an unknown tail."""
    text = (
        "Pre.\n\n"
        "References\n\n"
        "[1] Doe, J. (2020). Title. Journal, 1(1), 1-10.\n"
        "[2] Smith, A. (2021). Other. Journal, 2(2), 11-20.\n\n"
        "HERMAN AGUINIS is the senior chair of management at GWU.\n"
        "He has published widely on research methods.\n"
    )
    refs_idx = text.index("References")
    sections = partition_into_sections(
        text, [_hint("References", refs_idx, refs_idx + 10)],
        source_format="pdf",
    )
    refs = next(s for s in sections if s.canonical_label == SectionLabel.references)
    # References runs to end-of-text; the author-bio is inside it (not truncated).
    assert "HERMAN AGUINIS" in refs.text
    assert refs.char_end == len(text)
    # Universal coverage is preserved.
    all_text = "".join(s.text for s in sections)
    assert all_text == text


def test_corresponding_author_truncates():
    text = (
        "Pre.\n\nMethods\n\nProcedures used.\n\n"
        "Corresponding author: jane@example.org\nDept of X, U of Y.\n"
    )
    methods_idx = text.index("Methods")
    sections = partition_into_sections(
        text, [_hint("Methods", methods_idx, methods_idx + 7)],
        source_format="pdf",
    )
    methods = next(s for s in sections if s.canonical_label == SectionLabel.methods)
    assert "jane@example.org" not in methods.text


def test_no_boundary_means_section_extends_to_eof():
    text = "Pre.\n\nAbstract\n\nThis is the abstract content with no trailing bio.\n"
    abs_idx = text.index("Abstract")
    sections = partition_into_sections(
        text, [_hint("Abstract", abs_idx, abs_idx + 8)],
        source_format="pdf",
    )
    abstract = next(s for s in sections if s.canonical_label == SectionLabel.abstract)
    assert "This is the abstract content" in abstract.text
    assert abstract.char_end == len(text)


def test_references_section_not_truncated_by_boundary_patterns():
    """References + Appendix + Supplementary are exempt from boundary
    truncation (v1.6.1 — they legitimately run to end-of-doc)."""
    from docpluck.sections.blocks import BlockHint
    from docpluck.sections.core import partition_into_sections

    # These lines START with patterns that fire is_section_boundary():
    #   "ORCID: ..."  → matches ^ORCID\s*:
    #   "HERMAN AGUINIS is ..."  → matches ^[A-Z]{2,}...is\s
    # They are legitimate reference-list content but would trigger
    # truncation for non-exempt sections.
    text = (
        "References\n"
        "Smith, J. (2020). A paper. Journal, 1(1), 1-10.\n"
        "ORCID: 0000-0002-1234-5678\n"  # boundary-pattern bait (start of line)
        "Jones, K. (2021). Another paper. Journal, 2(2), 11-20.\n"
        "HERMAN AGUINIS is a professor at GWU.\n"  # author-bio boundary bait
    )
    refs_start = 0
    hint = BlockHint(
        text="References", char_start=refs_start,
        char_end=refs_start + len("References"), page=1,
        is_heading_candidate=True, heading_strength="strong",
        heading_source="layout",
    )
    sections = partition_into_sections(text, [hint], source_format="pdf")
    refs = next(s for s in sections if s.label == "references")
    assert refs.char_end == len(text), \
        f"References should span to end-of-text, got char_end={refs.char_end} of {len(text)}"
    assert "Smith" in refs.text
    assert "Jones" in refs.text
    assert "HERMAN AGUINIS" in refs.text
