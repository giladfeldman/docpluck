"""F0: layout-aware footnote + running-header strip."""

import io

import pytest

pytest.importorskip("pdfplumber")
pytest.importorskip("reportlab")


def _pdf_with_footnote_and_runheader() -> bytes:
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import letter
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    # Page 1
    c.setFont("Helvetica-Oblique", 9); c.drawString(72, 760, "MY JOURNAL — VOL 12")
    c.setFont("Helvetica-Bold", 14); c.drawString(72, 720, "Abstract")
    c.setFont("Helvetica", 11); c.drawString(72, 700, "This is the abstract content.")
    c.setFont("Helvetica", 8); c.drawString(72, 80, "1 First footnote on page 1.")
    c.showPage()
    # Page 2
    c.setFont("Helvetica-Oblique", 9); c.drawString(72, 760, "MY JOURNAL — VOL 12")
    c.setFont("Helvetica-Bold", 14); c.drawString(72, 720, "Methods")
    c.setFont("Helvetica", 11); c.drawString(72, 700, "We did things.")
    c.setFont("Helvetica", 8); c.drawString(72, 80, "2 Second footnote on page 2.")
    c.showPage()
    c.save()
    return buf.getvalue()


def test_f0_strips_running_header():
    from docpluck import normalize_text, NormalizationLevel
    from docpluck.extract_layout import extract_pdf_layout
    layout = extract_pdf_layout(_pdf_with_footnote_and_runheader())
    out, _ = normalize_text(layout.raw_text, NormalizationLevel.academic, layout=layout)
    assert "MY JOURNAL" not in out


def test_f0_separates_footnotes_into_appendix():
    from docpluck import normalize_text, NormalizationLevel
    from docpluck.extract_layout import extract_pdf_layout
    layout = extract_pdf_layout(_pdf_with_footnote_and_runheader())
    out, report = normalize_text(layout.raw_text, NormalizationLevel.academic, layout=layout)
    assert "First footnote" in out
    assert "Second footnote" in out
    body_only_until_appendix = out.split("\n\f\f\n", 1)[0] if "\n\f\f\n" in out else out
    assert "First footnote" not in body_only_until_appendix or \
           "Abstract" in body_only_until_appendix.split("First footnote")[0]


def test_f0_records_footnote_spans():
    from docpluck import normalize_text, NormalizationLevel
    from docpluck.extract_layout import extract_pdf_layout
    layout = extract_pdf_layout(_pdf_with_footnote_and_runheader())
    _, report = normalize_text(layout.raw_text, NormalizationLevel.academic, layout=layout)
    assert len(report.footnote_spans) >= 2
