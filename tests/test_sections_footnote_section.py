"""Footnote section behavior across PDF path versions.

v1.6.1 note: The PDF path now uses extract_pdf (pdftotext) + normalize_text(academic)
WITHOUT layout/F0. The F0 step (which stripped footnotes and appended them as a
separate section) is no longer run. Footnote text remains inline in the normalized
text and no 'footnotes' section is emitted. The old test is kept below but updated
to document the new behavior.
"""

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
    """v1.6.1: PDF path no longer runs F0 (layout-based footnote stripping),
    so no 'footnotes' section is emitted. Footnote text stays inline in the
    body section that contains it. This test documents the new behavior."""
    from docpluck import extract_sections
    doc = extract_sections(_pdf_with_footnote_in_abstract())
    # No separate footnotes section in the new path.
    fn = doc.get("footnotes")
    assert fn is None, (
        "v1.6.1 PDF path does not emit a 'footnotes' section; "
        "footnote text remains inline."
    )
    # Abstract and Methods should still be detected.
    assert doc.abstract is not None or any(
        s.canonical_label.value == "abstract" for s in doc.sections
    ), "Abstract section should be detected."
