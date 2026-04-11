"""Tests for docpluck.extract_html — HTML text extraction with block/inline structure.

These tests exercise the block/inline-aware tree-walk that's the core of
Scimeto's production HTML extractor. The "ChanORCID" bug (merged words from
adjacent inline elements) is specifically regression-tested.
"""
import pytest

pytest.importorskip("bs4", reason="beautifulsoup4 not installed (pip install docpluck[html])")
pytest.importorskip("lxml", reason="lxml not installed (pip install docpluck[html])")

from docpluck import extract_html, html_to_text
from docpluck.extract_html import BLOCK_ELEMENTS, IGNORED_TAGS


# ---------------------------------------------------------------------------
# Block elements produce newlines
# ---------------------------------------------------------------------------

class TestBlockElements:
    def test_paragraphs_separated_by_newline(self):
        text = html_to_text("<p>First</p><p>Second</p>")
        assert "First" in text
        assert "Second" in text
        assert "\n" in text
        assert "FirstSecond" not in text

    def test_headings_produce_newlines(self):
        text = html_to_text("<h1>Title</h1><p>Body</p>")
        assert "Title" in text
        assert "Body" in text
        assert "TitleBody" not in text

    def test_all_heading_levels(self):
        for level in range(1, 7):
            text = html_to_text(f"<h{level}>Heading</h{level}><p>After</p>")
            assert "HeadingAfter" not in text

    def test_div_is_block(self):
        text = html_to_text("<div>Alpha</div><div>Beta</div>")
        assert "AlphaBeta" not in text

    def test_list_items_are_block(self):
        text = html_to_text("<ul><li>Item 1</li><li>Item 2</li></ul>")
        assert "Item 1Item 2" not in text
        assert "Item 1" in text
        assert "Item 2" in text

    def test_table_cells_are_block(self):
        text = html_to_text(
            "<table><tr><td>A</td><td>B</td></tr><tr><td>C</td><td>D</td></tr></table>"
        )
        # Each cell should be separated from the next
        assert "AB" not in text
        assert "CD" not in text

    def test_block_elements_set_includes_common_tags(self):
        for tag in ['p', 'div', 'h1', 'li', 'td', 'table', 'section', 'article']:
            assert tag in BLOCK_ELEMENTS


# ---------------------------------------------------------------------------
# Inline elements get spaces (ChanORCID regression)
# ---------------------------------------------------------------------------

class TestInlineElements:
    def test_chan_orcid_regression(self):
        """The real production bug: adjacent inline elements merged words."""
        text = html_to_text("<a>Chan</a><a>ORCID</a>")
        assert "ChanORCID" not in text
        assert "Chan" in text
        assert "ORCID" in text

    def test_span_elements_get_spaces(self):
        text = html_to_text("<span>Hello</span><span>World</span>")
        assert "HelloWorld" not in text

    def test_inline_within_paragraph(self):
        text = html_to_text("<p>The <em>important</em> result</p>")
        assert "important" in text
        assert "Theimportant" not in text
        assert "importantresult" not in text

    def test_multiple_inline_elements(self):
        text = html_to_text("<p><b>A</b><i>B</i><u>C</u></p>")
        assert "ABC" not in text
        assert "A" in text and "B" in text and "C" in text


# ---------------------------------------------------------------------------
# <br> handling
# ---------------------------------------------------------------------------

class TestBrTag:
    def test_br_produces_newline(self):
        text = html_to_text("<p>Line 1<br>Line 2</p>")
        assert "Line 1" in text
        assert "Line 2" in text
        assert "Line 1Line 2" not in text
        assert "\n" in text

    def test_br_self_closing(self):
        text = html_to_text("<p>A<br/>B</p>")
        assert "AB" not in text

    def test_multiple_brs(self):
        text = html_to_text("<p>A<br><br>B</p>")
        assert "A" in text and "B" in text


# ---------------------------------------------------------------------------
# Ignored tags are fully stripped
# ---------------------------------------------------------------------------

class TestIgnoredTags:
    def test_script_tags_stripped(self):
        text = html_to_text("<p>Before</p><script>alert('x')</script><p>After</p>")
        assert "alert" not in text
        assert "Before" in text
        assert "After" in text

    def test_style_tags_stripped(self):
        text = html_to_text("<style>p { color: red; }</style><p>Content</p>")
        assert "color: red" not in text
        assert "Content" in text

    def test_meta_stripped(self):
        text = html_to_text('<meta charset="utf-8"><p>Body</p>')
        assert "Body" in text

    def test_noscript_stripped(self):
        text = html_to_text("<noscript>No JS</noscript><p>Body</p>")
        assert "No JS" not in text

    def test_svg_stripped(self):
        text = html_to_text('<svg><text>X</text></svg><p>Body</p>')
        assert "Body" in text

    def test_all_ignored_tags_in_set(self):
        expected = {'script', 'style', 'meta', 'link', 'head', 'noscript', 'svg', 'object', 'embed', 'iframe'}
        assert expected <= IGNORED_TAGS


# ---------------------------------------------------------------------------
# Nested structures
# ---------------------------------------------------------------------------

class TestNesting:
    def test_nested_block_in_block(self):
        text = html_to_text("<div><p>Inner</p></div>")
        assert "Inner" in text

    def test_nested_inline_in_block(self):
        text = html_to_text("<p>The <span>quick <em>brown</em> fox</span> jumps</p>")
        for word in ("quick", "brown", "fox", "jumps"):
            assert word in text
        assert "quickbrown" not in text
        assert "brownfox" not in text

    def test_deeply_nested(self):
        text = html_to_text("<div><div><div><p><span>Deep</span></p></div></div></div>")
        assert "Deep" in text


# ---------------------------------------------------------------------------
# Empty / edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_empty_html(self):
        assert html_to_text("") == ""

    def test_empty_body(self):
        assert html_to_text("<html><body></body></html>") == ""

    def test_only_whitespace(self):
        assert html_to_text("   \n\t  ") == ""

    def test_only_ignored_tags(self):
        assert html_to_text("<script>x</script><style>y</style>") == ""

    def test_malformed_html_does_not_crash(self):
        # lxml is lenient — these should not raise
        assert html_to_text("<p>Unclosed") is not None
        assert html_to_text("<p><b>Mismatched</p></b>") is not None
        assert html_to_text("<<<>>>") is not None


# ---------------------------------------------------------------------------
# Whitespace normalization
# ---------------------------------------------------------------------------

class TestWhitespaceNormalization:
    def test_collapse_multiple_spaces(self):
        text = html_to_text("<p>Hello    world</p>")
        assert "    " not in text
        assert "Hello world" in text

    def test_nbsp_normalized_to_space(self):
        text = html_to_text("<p>p\u00a0=\u00a00.05</p>")
        assert "\u00a0" not in text
        assert "p = 0.05" in text

    def test_thin_space_normalized(self):
        text = html_to_text("<p>1\u2009000</p>")  # U+2009 THIN SPACE
        assert "\u2009" not in text

    def test_bom_handled(self):
        text = html_to_text("\ufeff<p>Content</p>")
        assert "\ufeff" not in text
        assert "Content" in text

    def test_crlf_normalized(self):
        text = html_to_text("<p>Line 1</p>\r\n<p>Line 2</p>")
        assert "\r" not in text

    def test_triple_newlines_collapsed(self):
        text = html_to_text("<p>A</p><p></p><p></p><p></p><p>B</p>")
        assert "\n\n\n" not in text

    def test_leading_trailing_whitespace_stripped(self):
        text = html_to_text("   <p>Content</p>   ")
        assert text == "Content"


# ---------------------------------------------------------------------------
# HTML entities
# ---------------------------------------------------------------------------

class TestHtmlEntities:
    def test_ampersand_entity(self):
        text = html_to_text("<p>Smith &amp; Jones</p>")
        assert "Smith & Jones" in text

    def test_less_than_entity(self):
        text = html_to_text("<p>p &lt; 0.001</p>")
        assert "p < 0.001" in text

    def test_minus_entity(self):
        text = html_to_text("<p>r = &minus;0.5</p>")
        assert "\u2212" in text or "-" in text  # Unicode minus or ASCII

    def test_unicode_entities(self):
        text = html_to_text("<p>&eta;&sup2; = 0.15</p>")
        assert "\u03b7" in text  # eta character present


# ---------------------------------------------------------------------------
# Entry point: extract_html(bytes) -> (text, method)
# ---------------------------------------------------------------------------

class TestExtractHtml:
    def test_returns_tuple(self):
        result = extract_html(b"<p>Hello</p>")
        assert isinstance(result, tuple)
        assert len(result) == 2
        text, method = result
        assert isinstance(text, str)
        assert isinstance(method, str)

    def test_method_is_beautifulsoup(self):
        _, method = extract_html(b"<p>Hello</p>")
        assert method == "beautifulsoup"

    def test_utf8_decoding(self):
        text, _ = extract_html("<p>café \u03b7\u00b2</p>".encode("utf-8"))
        assert "café" in text
        assert "\u03b7" in text

    def test_invalid_encoding_does_not_crash(self):
        # Invalid UTF-8 bytes should be replaced, not raise
        text, _ = extract_html(b"<p>\xff\xfe Content</p>")
        assert "Content" in text


# ---------------------------------------------------------------------------
# Academic HTML patterns
# ---------------------------------------------------------------------------

class TestAcademicPatterns:
    def test_statistical_values_preserved(self):
        html = "<p>The effect was significant, <em>F</em>(1, 30) = 4.42, <em>p</em> = .043.</p>"
        text = html_to_text(html)
        assert "F" in text
        assert "(1, 30)" in text
        assert "4.42" in text
        assert ".043" in text

    def test_confidence_intervals(self):
        html = "<p>95% CI [0.12, 0.48]</p>"
        text = html_to_text(html)
        assert "95% CI" in text
        assert "[0.12, 0.48]" in text

    def test_article_structure(self):
        html = """
        <article>
            <h1>Title of the Paper</h1>
            <section class="abstract">
                <h2>Abstract</h2>
                <p>We conducted a study on X.</p>
            </section>
            <section>
                <h2>Results</h2>
                <p>The mean was <em>M</em> = 3.42, <em>SD</em> = 0.89.</p>
            </section>
        </article>
        """
        text = html_to_text(html)
        assert "Title of the Paper" in text
        assert "Abstract" in text
        assert "Results" in text
        assert "M" in text
        assert "3.42" in text
        assert "0.89" in text
