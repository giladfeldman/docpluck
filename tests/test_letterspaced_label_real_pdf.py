"""Regression test for D1 — lowercase letter-spaced Elsevier front-matter labels.

The broad-read of the APA corpus (2026-05-15, v2.4.32) found that the three
Elsevier JESP-2009 papers (ar_apa_j_jesp_2009_12_010/011/012) rendered their
front-matter box labels as unintelligible letter-spaced runs:

    a r t i c l e
    i n f o
    a b s t r a c t

pdftotext serializes letter-spaced display typography as single characters
separated by single spaces. The all-caps sibling ``_rejoin_garbled_ocr_headers``
does not fire on lowercase input, so the label leaked verbatim AND the section
taxonomy never recognised ``a b s t r a c t`` — so the Abstract heading was
lost on every paper with this typography.

Cycle 1 (v2.4.33) adds ``_rejoin_letterspaced_lowercase_labels`` (normalize.py
step H0b), which collapses such lines pre-sectioning so the recovered
``abstract`` resolves through the normal taxonomy to ``## Abstract``.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

os.environ.setdefault("DOCPLUCK_DISABLE_CAMELOT", "1")

from docpluck.normalize import _rejoin_letterspaced_lowercase_labels
from docpluck.render import render_pdf_to_markdown

TEST_PDFS = Path(__file__).resolve().parents[1].parent / "PDFextractor" / "test-pdfs"

# A whole line that is >=4 single lowercase letters separated by single spaces.
_LETTERSPACED_LINE_RE = re.compile(r"(?m)^(?:[a-z] ){3,}[a-z]$")

_ELSEVIER_2009 = [
    "ar_apa_j_jesp_2009_12_010",
    "ar_apa_j_jesp_2009_12_011",
    "ar_apa_j_jesp_2009_12_012",
]


# ── Unit tests on the helper ────────────────────────────────────────────

def test_collapses_letterspaced_abstract_label():
    assert _rejoin_letterspaced_lowercase_labels("a b s t r a c t") == "abstract"


def test_collapses_letterspaced_article_and_info():
    src = "a r t i c l e\n\ni n f o"
    assert _rejoin_letterspaced_lowercase_labels(src) == "article\n\ninfo"


def test_preserves_normal_prose():
    prose = "The model predicts that practice should increase self-control."
    assert _rejoin_letterspaced_lowercase_labels(prose) == prose


def test_preserves_leading_whitespace():
    assert _rejoin_letterspaced_lowercase_labels("   a b s t r a c t") == "   abstract"


def test_vowel_guard_rejects_consonant_run():
    # A spaced-out all-consonant run is not a word — must be left untouched.
    src = "b c d f g h"
    assert _rejoin_letterspaced_lowercase_labels(src) == src


def test_ignores_short_runs():
    # Three single letters is below the >=4 threshold.
    assert _rejoin_letterspaced_lowercase_labels("a b c") == "a b c"


# ── Real-PDF regression tests ───────────────────────────────────────────

@pytest.mark.parametrize("stem", _ELSEVIER_2009)
def test_no_letterspaced_lines_in_render(stem):
    pdf = TEST_PDFS / "apa" / f"{stem}.pdf"
    if not pdf.exists():
        pytest.skip(f"fixture missing: {pdf}")
    md = render_pdf_to_markdown(pdf.read_bytes())
    leaks = _LETTERSPACED_LINE_RE.findall(md)
    assert not leaks, f"{stem}: letter-spaced label lines leaked into render: {leaks}"


@pytest.mark.parametrize("stem", _ELSEVIER_2009)
def test_abstract_heading_recovered(stem):
    pdf = TEST_PDFS / "apa" / f"{stem}.pdf"
    if not pdf.exists():
        pytest.skip(f"fixture missing: {pdf}")
    md = render_pdf_to_markdown(pdf.read_bytes())
    assert "## Abstract" in md, (
        f"{stem}: Abstract heading not recovered after letter-spaced "
        f"'a b s t r a c t' label was collapsed"
    )
