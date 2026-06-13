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


# --- x-gap space reinsertion (feedback_pdfplumber_extract_words_unreliable) ---
#
# Regression for the v2.4.86 fix: on tight-kerned PDFs pdfplumber's char stream
# drops the inter-word space glyph, so span text built with a naive "".join was
# glued ("CNSSpectrums") — catastrophically (token_f1 ~0.00) corrupting the F0
# layout body channel. _join_chars_with_spaces reinserts spaces from the x-gap.

def _char(text, x0, x1, size=10.0):
    return {"text": text, "x0": x0, "x1": x1, "size": size}


def test_join_chars_inserts_space_on_word_gap():
    from docpluck.extract_layout import _join_chars_with_spaces
    # "CNS" then a word-sized gap then "Spectrums": x1=18 -> x0=22 (gap 4 > 2.0).
    line = [
        _char("C", 0, 6), _char("N", 6, 12), _char("S", 12, 18),
        _char("S", 22, 28), _char("p", 28, 34), _char("e", 34, 40),
    ]
    assert _join_chars_with_spaces(line) == "CNS Spe"


def test_join_chars_no_space_within_word():
    from docpluck.extract_layout import _join_chars_with_spaces
    # Tight kerning (gap ~0.5 << 0.20*10) must NOT split a word.
    line = [_char("w", 0, 6), _char("o", 6.5, 12), _char("r", 12.3, 18),
            _char("d", 18.2, 24)]
    assert _join_chars_with_spaces(line) == "word"


def test_join_chars_no_double_space():
    from docpluck.extract_layout import _join_chars_with_spaces
    # An explicit space glyph already present must not be doubled by the gap.
    line = [_char("a", 0, 6), _char(" ", 6, 9), _char("b", 30, 36)]
    assert _join_chars_with_spaces(line) == "a b"


def test_synthetic_span_text_preserves_word_spaces():
    """Normal (loosely-kerned) text must keep its spaces in span.text — the fix
    must not under- or over-insert on a well-behaved PDF."""
    from docpluck.extract_layout import extract_pdf_layout
    layout = extract_pdf_layout(_build_synthetic_pdf())
    span_text = " ".join(s.text for p in layout.pages for s in p.spans)
    assert "We did things" in span_text
    assert "Wedidthings" not in span_text
