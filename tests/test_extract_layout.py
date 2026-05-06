"""Layout-aware PDF extraction via pdfplumber."""

import io
import os
import shutil

import pytest


def _build_synthetic_pdf() -> bytes:
    """Build a 1-page PDF with a heading and body using reportlab (fallback)
    or skip if not available. We just need any valid PDF for the smoke test."""
    rl = pytest.importorskip("reportlab")
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import letter
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    c.setFont("Helvetica-Bold", 18)
    c.drawString(72, 720, "Methods")
    c.setFont("Helvetica", 11)
    c.drawString(72, 700, "We did things.")
    c.showPage()
    c.save()
    return buf.getvalue()


def test_layout_doc_shape():
    from docpluck.extract_layout import extract_pdf_layout, LayoutDoc, PageLayout, TextSpan
    pdf = _build_synthetic_pdf()
    layout = extract_pdf_layout(pdf)
    assert isinstance(layout, LayoutDoc)
    assert isinstance(layout.raw_text, str)
    assert len(layout.pages) == 1
    page = layout.pages[0]
    assert isinstance(page, PageLayout)
    assert all(isinstance(s, TextSpan) for s in page.spans)
    # Body text should be present.
    assert "We did things" in layout.raw_text


def test_layout_extract_includes_font_sizes():
    from docpluck.extract_layout import extract_pdf_layout
    layout = extract_pdf_layout(_build_synthetic_pdf())
    sizes = {round(s.font_size, 1) for p in layout.pages for s in p.spans}
    # Heading is 18pt, body is 11pt — both should appear.
    assert any(abs(s - 18.0) < 0.5 for s in sizes)
    assert any(abs(s - 11.0) < 0.5 for s in sizes)
