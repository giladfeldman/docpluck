"""Unit-corpus assertions across synthetic fixtures."""

import pytest

pytest.importorskip("reportlab")
pytest.importorskip("pdfplumber")

from docpluck import extract_sections
from docpluck.sections import SectionLabel
from tests.fixtures.sections import builders


def _assert_universal_coverage(doc):
    total = sum(s.char_end - s.char_start for s in doc.sections)
    # The footnotes appendix uses a sentinel; subtract it from coverage check.
    sentinel_count = doc.normalized_text.count("\n\f\f\n")
    assert total + sentinel_count * len("\n\f\f\n") >= len(doc.normalized_text) - 1


def test_apa_single_study_pdf():
    doc = extract_sections(builders.build_apa_single_study_pdf())
    _assert_universal_coverage(doc)
    expected = {
        SectionLabel.abstract, SectionLabel.introduction, SectionLabel.methods,
        SectionLabel.results, SectionLabel.discussion, SectionLabel.references,
    }
    actual = {s.canonical_label for s in doc.sections}
    assert expected.issubset(actual)


def test_apa_multi_study_pdf():
    doc = extract_sections(builders.build_apa_multi_study_pdf())
    _assert_universal_coverage(doc)
    methods = doc.all("methods")
    results = doc.all("results")
    assert len(methods) >= 2
    assert len(results) >= 2
    labels = [s.label for s in doc.sections]
    assert "methods" in labels and "methods_2" in labels


def test_html_real_headings():
    pytest.importorskip("bs4")
    doc = extract_sections(builders.build_html_with_real_headings())
    expected = {SectionLabel.abstract, SectionLabel.methods, SectionLabel.references}
    actual = {s.canonical_label for s in doc.sections}
    assert expected.issubset(actual)


def test_docx_real_headings():
    pytest.importorskip("mammoth")
    pytest.importorskip("docx")
    doc = extract_sections(builders.build_docx_with_real_headings())
    expected = {SectionLabel.abstract, SectionLabel.methods, SectionLabel.references}
    actual = {s.canonical_label for s in doc.sections}
    assert expected.issubset(actual)
