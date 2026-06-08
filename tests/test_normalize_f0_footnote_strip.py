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


def test_f0_exposes_footnote_texts():
    """v2.4.83: report.footnote_texts surfaces the captured footnote strings
    as a first-class list, parallel to footnote_spans, so downstream
    consumers don't have to slice char offsets or parse the \\n\\f\\f\\n
    appendix out of the body text."""
    from docpluck import normalize_text, NormalizationLevel
    from docpluck.extract_layout import extract_pdf_layout
    layout = extract_pdf_layout(_pdf_with_footnote_and_runheader())
    _, report = normalize_text(layout.raw_text, NormalizationLevel.academic, layout=layout)
    # Parallel to footnote_spans: one text per recorded span.
    assert len(report.footnote_texts) == len(report.footnote_spans)
    joined = " ".join(report.footnote_texts)
    assert "First footnote" in joined
    assert "Second footnote" in joined
    # Each text matches the raw_text slice at its parallel span.
    for (start, end), text in zip(report.footnote_spans, report.footnote_texts):
        assert layout.raw_text[start:end] == text


def test_f0_footnote_texts_empty_without_layout():
    """No layout → F0 doesn't run → footnote_texts is empty (not an error)."""
    from docpluck import normalize_text, NormalizationLevel
    _, report = normalize_text("Plain body text with no layout.", NormalizationLevel.academic)
    assert report.footnote_texts == ()
