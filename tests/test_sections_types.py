"""Section + SectionedDocument dataclasses."""

import pytest

from docpluck.sections.types import Section, SectionedDocument
from docpluck.sections.taxonomy import SectionLabel, Confidence, DetectedVia


def _mk(label, text, start, end, canonical=None, pages=()):
    return Section(
        label=label,
        canonical_label=canonical or SectionLabel(label),
        text=text,
        char_start=start,
        char_end=end,
        pages=pages,
        confidence=Confidence.high,
        detected_via=DetectedVia.heading_match,
        heading_text=None,
    )


def test_section_is_frozen():
    s = _mk("abstract", "hi", 0, 2)
    with pytest.raises(Exception):
        s.text = "changed"


def test_sectioned_document_get_returns_first():
    a = _mk("methods", "m1", 0, 2)
    b = _mk("methods_2", "m2", 5, 7, canonical=SectionLabel.methods)
    doc = SectionedDocument(
        sections=(a, b), normalized_text="m1   m2",
        sectioning_version="1.0.0", source_format="pdf",
    )
    assert doc.get("methods") is a
    assert doc.get("methods_2") is b


def test_sectioned_document_all_returns_all_in_order():
    a = _mk("methods", "m1", 0, 2)
    b = _mk("methods_2", "m2", 5, 7, canonical=SectionLabel.methods)
    doc = SectionedDocument(
        sections=(a, b), normalized_text="m1   m2",
        sectioning_version="1.0.0", source_format="pdf",
    )
    assert doc.all("methods") == (a, b)


def test_sectioned_document_text_for():
    abstract = _mk("abstract", "ABSTRACT", 0, 8)
    refs = _mk("references", "REFS", 9, 13)
    doc = SectionedDocument(
        sections=(abstract, refs), normalized_text="ABSTRACT REFS",
        sectioning_version="1.0.0", source_format="pdf",
    )
    assert doc.text_for("abstract", "references") == "ABSTRACT\n\nREFS"
    assert doc.text_for("references", "abstract") == "ABSTRACT\n\nREFS"  # always document order
    assert doc.text_for("methods") == ""


def test_sectioned_document_property_accessors():
    abstract = _mk("abstract", "ABSTRACT", 0, 8)
    refs = _mk("references", "REFS", 9, 13)
    doc = SectionedDocument(
        sections=(abstract, refs), normalized_text="ABSTRACT REFS",
        sectioning_version="1.0.0", source_format="pdf",
    )
    assert doc.abstract is abstract
    assert doc.references is refs
    assert doc.methods is None
    assert doc.results is None
    assert doc.introduction is None
    assert doc.discussion is None


def test_section_subheadings_default_empty():
    from docpluck.sections.types import Section
    from docpluck.sections.taxonomy import SectionLabel, Confidence, DetectedVia
    s = Section(
        label="methods",
        canonical_label=SectionLabel.methods,
        text="body",
        char_start=0,
        char_end=4,
        pages=(),
        confidence=Confidence.high,
        detected_via=DetectedVia.heading_match,
        heading_text="Method",
    )
    assert s.subheadings == ()


def test_section_subheadings_set_value():
    from docpluck.sections.types import Section
    from docpluck.sections.taxonomy import SectionLabel, Confidence, DetectedVia
    s = Section(
        label="methods",
        canonical_label=SectionLabel.methods,
        text="body",
        char_start=0,
        char_end=4,
        pages=(),
        confidence=Confidence.high,
        detected_via=DetectedVia.heading_match,
        heading_text="Method",
        subheadings=("Participants", "Procedure"),
    )
    assert s.subheadings == ("Participants", "Procedure")
