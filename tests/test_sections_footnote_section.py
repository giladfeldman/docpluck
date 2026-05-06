"""Footnotes appear as their own section, not inside abstract/methods."""

import io

import pytest

pytest.importorskip("pdfplumber")
pytest.importorskip("reportlab")


def _pdf_with_footnote_in_abstract() -> bytes:
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import letter
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    c.setFont("Helvetica-Bold", 14); c.drawString(72, 720, "Abstract")
    c.setFont("Helvetica", 11); c.drawString(72, 700, "Body of abstract.")
    c.setFont("Helvetica-Bold", 14); c.drawString(72, 660, "Methods")
    c.setFont("Helvetica", 11); c.drawString(72, 640, "We did things.")
    c.setFont("Helvetica", 8); c.drawString(72, 80, "1 This is the footnote.")
    c.showPage(); c.save()
    return buf.getvalue()


def test_footnote_in_separate_section():
    from docpluck import extract_sections
    doc = extract_sections(_pdf_with_footnote_in_abstract())
    fn = doc.get("footnotes")
    assert fn is not None, "Expected a 'footnotes' section to be present."
    assert "footnote" in fn.text.lower()
    if doc.abstract is not None:
        assert "footnote" not in doc.abstract.text.lower()
