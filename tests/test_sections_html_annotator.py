"""HTML annotator: <h1>-<h6> heading detection."""

import pytest

bs4 = pytest.importorskip("bs4")

from docpluck.sections.annotators.html import annotate_html


SAMPLE_HTML = """<html><body>
<h1>Some Title</h1>
<p>Author, J.</p>
<h2>Abstract</h2>
<p>This paper investigates X.</p>
<h2>Methods</h2>
<p>We did things.</p>
<h2>References</h2>
<p>[1] Doe, J. (2020).</p>
</body></html>"""


def test_annotate_html_returns_hints_with_text_offsets():
    text, hints = annotate_html(SAMPLE_HTML.encode("utf-8"))
    assert isinstance(text, str)
    for h in hints:
        assert text[h.char_start:h.char_end] == h.text


def test_annotate_html_detects_h1_h2_as_strong():
    _, hints = annotate_html(SAMPLE_HTML.encode("utf-8"))
    headings = [h for h in hints if h.is_heading_candidate]
    heading_texts = [h.text for h in headings]
    assert "Some Title" in heading_texts
    assert "Abstract" in heading_texts
    assert "Methods" in heading_texts
    assert "References" in heading_texts
    for h in headings:
        assert h.heading_strength == "strong"
        assert h.heading_source == "markup"


def test_annotate_html_h4_h6_are_weak():
    html = b"<html><body><h4>Subsubsection</h4><p>x</p></body></html>"
    _, hints = annotate_html(html)
    headings = [h for h in hints if h.is_heading_candidate]
    assert len(headings) == 1
    assert headings[0].heading_strength == "weak"


def test_extract_sections_from_html_bytes():
    from docpluck import extract_sections
    doc = extract_sections(SAMPLE_HTML.encode("utf-8"))
    assert doc.source_format == "html"
    assert doc.abstract is not None
    assert "investigates X" in doc.abstract.text
    assert doc.references is not None
