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


def test_author_bio_truncates_references_section():
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
    # The author-bio paragraph must NOT be inside references.
    assert "HERMAN AGUINIS" not in refs.text
    # And it must be SOMEWHERE in the partition (universal coverage).
    all_text = "".join(s.text for s in sections)
    assert all_text == text
    # An unknown span absorbs the bio.
    assert any(
        s.canonical_label == SectionLabel.unknown and "HERMAN AGUINIS" in s.text
        for s in sections
    )


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
