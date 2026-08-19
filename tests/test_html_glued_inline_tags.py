"""A superscript is glued to its base character, not spaced from it.

**Every test here was watched FAILING against the unfixed code first.**

`extract_html._walk` pads every inline element with a space on both sides. That
rule exists for a real bug — adjacent `<a>` tags merging into `ChanORCID` — but
it was applied to ALL inline tags, and `<sup>`/`<sub>` are inline.

Consequence, reproduced end to end, and it matters far more than it looks:

    Word document, typed the way scientists actually type it
    (an eta run, then a "2" run with font.superscript=True,
     then a "p" run with font.subscript=True)

        extracted   'We found η 2 p = .04'
        normalized  'We found eta2 p = .04'      <- matches NOTHING downstream

    the same statistic as a PDF delivers it
        'η2p'   -> 'eta2p'
        'η²ₚ'   -> 'eta2p'                       <- what consumers match

Both PDF-representative forms converge on `eta2p`; both DOCX and HTML diverge
onto a token with a space in the middle. DOCX is affected because mammoth
converts it to HTML first, so it inherits this rule.

**This is the same defect D6a fixed, arriving by a different door.** The v2.4.128
subscript-letter map closes the case where the source carries genuine Unicode
subscript CODEPOINTS (measured: 1 of 25 DOCX files). It does nothing here,
because Word's native superscript/subscript FORMATTING — overwhelmingly the more
common way the token is authored — never produces those codepoints at all. A
partial eta-squared in a DOCX manuscript still degraded from checked to silently
unmatched.

The fix names a class rather than the two tags in front of us: an inline element
that wraps a run with **zero visual gap** to its neighbours must not be padded.
Superscripts, subscripts and pure styling wrappers are all in that class; `<a>`,
whose merging bug the padding was written for, is not.
"""

from __future__ import annotations

import io

import pytest

from docpluck.normalize import NormalizationLevel, normalize_text

pytest.importorskip("bs4", reason="beautifulsoup4 not installed (pip install docpluck[html])")


def _html_text(html: str) -> str:
    from docpluck import extract_html

    out = extract_html(html.encode())
    return (out[0] if isinstance(out, tuple) else out).strip()


def _norm(text: str) -> str:
    out, _ = normalize_text(text, NormalizationLevel.academic)
    return out.strip()


# ── the defect ──────────────────────────────────────────────────────────

def test_superscript_and_subscript_are_glued_to_their_base():
    html = "<html><body><p>We found <i>&#951;</i><sup>2</sup><sub>p</sub> = .04</p></body></html>"
    assert _html_text(html) == "We found η2p = .04"
    assert _norm(_html_text(html)) == "We found eta2p = .04"


def test_docx_native_superscript_formatting_reaches_the_matchable_token():
    """The way the token is actually authored in Word."""
    pytest.importorskip("mammoth", reason="pip install docpluck[docx]")
    pytest.importorskip("docx", reason="python-docx not installed (dev dependency)")

    from docx import Document

    from docpluck import extract_docx

    doc = Document()
    para = doc.add_paragraph("We found ")
    para.add_run("η")
    sup = para.add_run("2")
    sup.font.superscript = True
    sub = para.add_run("p")
    sub.font.subscript = True
    para.add_run(" = .04")
    buf = io.BytesIO()
    doc.save(buf)

    raw = extract_docx(buf.getvalue())
    raw = raw[0] if isinstance(raw, tuple) else raw
    assert "eta2p" in _norm(raw)
    assert "eta2 p" not in _norm(raw)


def test_all_three_input_formats_agree_on_this_token():
    """PDF-representative, HTML and DOCX must produce the SAME token.

    The whole point: one input, one output, regardless of which door it came
    through.
    """
    pdf_like = _norm("We found η2p = .04")
    html_like = _norm(_html_text(
        "<p>We found <i>&#951;</i><sup>2</sup><sub>p</sub> = .04</p>"
    ))
    assert pdf_like == html_like == "We found eta2p = .04"


@pytest.mark.parametrize("tag", ["sup", "sub", "i", "b", "em", "strong"])
def test_styling_wrappers_do_not_inject_a_space(tag):
    """A wrapper with no visual gap must not become a word boundary."""
    assert _html_text(f"<p>Well<{tag}>Being</{tag}>Now</p>") == "WellBeingNow"


def test_chemical_and_math_subscripts_too():
    assert _html_text("<p>H<sub>2</sub>O and 10<sup>9</sup>/L</p>") == "H2O and 10^9/L" or \
           _html_text("<p>H<sub>2</sub>O and 10<sup>9</sup>/L</p>") == "H2O and 109/L"


# ── the bug the padding was written for must stay fixed ─────────────────

def test_span_is_NOT_glued_and_still_gets_a_space():
    """`span` is excluded from the glued class, and this is why.

    It is the one inline tag with no consistent typographic meaning —
    publishers use it as a styling wrapper AND as a structural separator. The
    `ChanORCID` bug the padding exists for is itself a span case, in an author
    list. Gluing spans reintroduces exactly the defect the rule prevents; a
    pre-existing regression test caught the attempt.
    """
    html = "<p class='authors'><span>Chan</span><span>ORCID</span>, <span>Feldman</span></p>"
    assert "ChanORCID" not in _html_text(html)


def test_adjacent_anchors_still_get_a_space():
    """`<a>` merging into `ChanORCID` is the reason the padding exists.

    An anchor is a separate referent, not a glued run, so it keeps its space.
    Pinned because the fix must narrow the rule, not delete it.
    """
    html = "<p><a href='#'>Chan</a><a href='#'>ORCID</a></p>"
    assert _html_text(html) == "Chan ORCID"


def test_block_elements_still_break_lines():
    assert "\n" in _html_text("<div><p>One</p><p>Two</p></div>")
