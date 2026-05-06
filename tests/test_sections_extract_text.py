"""End-to-end: extract_sections from already-extracted+normalized text."""

from docpluck.sections import (
    extract_sections, SectionedDocument, SectionLabel, SECTIONING_VERSION,
)


SAMPLE = (
    "Some Title\n\nSmith, J.\n\n"
    "Abstract\n\nThis paper investigates X.\n\n"
    "Introduction\n\nIntro text.\n\n"
    "Methods\n\nWe did things.\n\n"
    "Results\n\nWe found stuff.\n\n"
    "Discussion\n\nIt was great.\n\n"
    "References\n\n[1] Doe, J. (2020).\n"
)


def test_returns_sectioned_document():
    doc = extract_sections(text=SAMPLE, source_format="pdf")
    assert isinstance(doc, SectionedDocument)


def test_universal_coverage_invariant():
    doc = extract_sections(text=SAMPLE, source_format="pdf")
    total = sum(s.char_end - s.char_start for s in doc.sections)
    assert total == len(SAMPLE)
    assert "".join(s.text for s in doc.sections) == SAMPLE


def test_canonical_labels_detected():
    doc = extract_sections(text=SAMPLE, source_format="pdf")
    labels = {s.canonical_label for s in doc.sections}
    expected = {
        SectionLabel.abstract, SectionLabel.introduction,
        SectionLabel.methods, SectionLabel.results,
        SectionLabel.discussion, SectionLabel.references,
    }
    assert expected.issubset(labels)


def test_convenience_properties_work():
    doc = extract_sections(text=SAMPLE, source_format="pdf")
    assert doc.abstract is not None
    assert "investigates X" in doc.abstract.text
    assert doc.references is not None
    assert "[1] Doe" in doc.references.text


def test_versioning_recorded():
    doc = extract_sections(text=SAMPLE, source_format="pdf")
    assert doc.sectioning_version == SECTIONING_VERSION
    assert doc.source_format == "pdf"


def test_text_for_filter():
    doc = extract_sections(text=SAMPLE, source_format="pdf")
    out = doc.text_for("abstract", "references")
    assert "investigates X" in out
    assert "[1] Doe" in out
    assert "We did things" not in out


def test_top_level_import():
    from docpluck import extract_sections, SectionedDocument
    assert extract_sections is not None
    assert SectionedDocument is not None
