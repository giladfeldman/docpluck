"""PDF annotator: layout-aware heading detection."""

import io

import pytest

pytest.importorskip("reportlab")
pytest.importorskip("pdfplumber")


def _make_pdf() -> bytes:
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import letter
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    c.setFont("Helvetica-Bold", 16); c.drawString(72, 740, "Abstract")
    c.setFont("Helvetica", 11); c.drawString(72, 720, "This paper investigates X.")
    c.setFont("Helvetica-Bold", 16); c.drawString(72, 690, "Methods")
    c.setFont("Helvetica", 11); c.drawString(72, 670, "We did things.")
    c.setFont("Helvetica-Bold", 16); c.drawString(72, 640, "References")
    c.setFont("Helvetica", 11); c.drawString(72, 620, "[1] Doe, J. (2020).")
    c.showPage(); c.save()
    return buf.getvalue()


def test_pdf_annotator_detects_headings():
    from docpluck.sections.annotators.pdf import annotate_pdf
    text, hints = annotate_pdf(_make_pdf())
    heading_texts = [h.text.strip() for h in hints if h.is_heading_candidate]
    assert "Abstract" in heading_texts
    assert "Methods" in heading_texts
    assert "References" in heading_texts
    for h in hints:
        if h.is_heading_candidate:
            assert h.heading_source == "layout"


def test_pdf_extract_sections_end_to_end():
    from docpluck import extract_sections
    doc = extract_sections(_make_pdf())
    assert doc.source_format == "pdf"
    assert doc.abstract is not None
    assert "investigates X" in doc.abstract.text
    assert doc.methods is not None
    assert "We did things" in doc.methods.text
    assert doc.references is not None
