"""A blank result always carries a signal (ESCImate, 2026-11-16 addendum).

Mechanism: an extraction or normalization that yields no text returned "" with a
clean method and no event, so every consumer needed its own blank-text guard.
Members of the class: PDF with no text layer (already flagged as
`no_text_layer`), Word file with no text, HTML page with no text, and a
non-blank text that normalization leaves blank (any length; the step guard in
`_track` only sees texts of 1,000+ characters).
"""
from __future__ import annotations

import io

import pytest

from docpluck.telemetry import fallback_scope

FAILED = "+text_layer_failed:no_text_layer"


def test_a_blank_html_page_is_flagged():
    pytest.importorskip("bs4")
    from docpluck import extract_html
    with fallback_scope() as fb:
        text, method = extract_html(b"<html><body>   </body></html>")
    assert not text.strip()
    assert method == "beautifulsoup" + FAILED
    assert fb.counters.get("no_text_layer") == 1


def test_an_html_page_with_text_is_not_flagged():
    pytest.importorskip("bs4")
    from docpluck import extract_html
    with fallback_scope() as fb:
        _, method = extract_html(b"<html><body><p>Results were clear.</p></body></html>")
    assert method == "beautifulsoup" and "no_text_layer" not in fb.counters


def _docx(paragraphs):
    from docx import Document
    doc = Document()
    for p in paragraphs:
        doc.add_paragraph(p)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def test_a_blank_word_file_is_flagged():
    pytest.importorskip("mammoth")
    pytest.importorskip("docx")
    from docpluck import extract_docx
    with fallback_scope() as fb:
        text, method = extract_docx(_docx(["", "   "]))
    assert not text.strip()
    assert method == "mammoth" + FAILED
    assert fb.counters.get("no_text_layer") == 1


def test_a_word_file_with_text_is_not_flagged():
    pytest.importorskip("mammoth")
    pytest.importorskip("docx")
    from docpluck import extract_docx
    with fallback_scope() as fb:
        _, method = extract_docx(_docx(["Results were clear."]))
    assert method == "mammoth" and "no_text_layer" not in fb.counters


def test_normalization_that_blanks_a_short_text_is_recorded(monkeypatch):
    import docpluck.normalize as n
    monkeypatch.setattr(n, "_normalize_text", lambda text, level, **k: ("", n.NormalizationReport(level="academic", version="t")))
    _, report = n.normalize_text("A short note.", n.NormalizationLevel.academic)
    assert report.fallbacks.get("normalized_text_empty") == 1


def test_a_blank_input_is_not_reported_as_blanked():
    import docpluck.normalize as n
    _, report = n.normalize_text("  \n ", n.NormalizationLevel.academic)
    assert "normalized_text_empty" not in report.fallbacks
