"""normalize_text(text, level, layout=...) accepts an optional LayoutDoc."""

import io

import pytest

pytest.importorskip("pdfplumber")
pytest.importorskip("reportlab")


def _make_pdf() -> bytes:
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import letter
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    c.setFont("Helvetica", 11); c.drawString(72, 720, "Body line one.")
    c.showPage()
    c.setFont("Helvetica", 11); c.drawString(72, 720, "Body line two.")
    c.showPage()
    c.save()
    return buf.getvalue()


def test_layout_param_optional_and_default_unchanged():
    from docpluck import normalize_text, NormalizationLevel
    out, _ = normalize_text("Body line one.\fBody line two.", NormalizationLevel.standard)
    assert "Body line one" in out


def test_layout_param_populates_page_offsets():
    from docpluck import normalize_text, NormalizationLevel
    from docpluck.extract_layout import extract_pdf_layout
    layout = extract_pdf_layout(_make_pdf())
    out, report = normalize_text(layout.raw_text, NormalizationLevel.standard, layout=layout)
    assert len(report.page_offsets) == 2
    assert report.page_offsets[0] >= 0
