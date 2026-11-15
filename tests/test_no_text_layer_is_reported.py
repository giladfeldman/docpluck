"""A PDF with no text layer is reported as a failure, never as an empty paper.

ESCImate 2026-09-07: a 0-character extraction came back with a clean method and
no event. The `_failed` method piece is what consumers' degraded guards read.
"""
from __future__ import annotations

import io

import pytest

from docpluck import extract_pdf, extract_pdf_structured
from docpluck.telemetry import fallback_scope


def _pdf(draw_text: bool, pages: int = 1, blank_page: bool = False) -> bytes:
    canvas = pytest.importorskip("reportlab.pdfgen.canvas")
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    for i in range(pages):
        c.rect(72, 72, 200, 200, fill=1)              # an "image": no text layer
        if draw_text and not (blank_page and i == 1):
            c.drawString(72, 720, f"Body text on page {i + 1} of the test document.")
        c.showPage()
    c.save()
    return buf.getvalue()


def test_image_only_pdf_says_text_layer_failed():
    with fallback_scope() as fb:
        text, method = extract_pdf(_pdf(draw_text=False))
    assert not text.strip()
    assert "+text_layer_failed:no_text_layer" in method
    assert fb.counters.get("no_text_layer") == 1


def test_structured_statuses_say_not_run():
    r = extract_pdf_structured(_pdf(draw_text=False))
    assert r["tables_status"] == "not_run:no_text_layer"
    assert r["figures_status"] == "not_run:no_text_layer"
    assert "text_layer_failed" in r["method"]


def test_normal_pdf_is_untouched_and_a_blank_page_is_only_diagnostic():
    with fallback_scope() as fb:
        text, method = extract_pdf(_pdf(draw_text=True, pages=3, blank_page=True))
    assert "Body text on page 1" in text
    assert "text_layer_failed" not in method
    assert "no_text_layer" not in fb.counters
    assert fb.details.get("pages_without_text") == {"2": 1}
