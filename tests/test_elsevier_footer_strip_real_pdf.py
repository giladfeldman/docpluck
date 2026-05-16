"""Regression test for D4 Elsevier page-1 footer leak (cycle 10, v2.4.42).

The APA Phase-5d sweep found that the Elsevier page-1 footer block —
the corresponding-author e-mail line and the ISSN / front-matter /
copyright line — was extracted by pdftotext at the page boundary and
spliced into the Introduction body:

    ...preliminary research is supportive of the prediction...
    E-mail address: muraven@albany.edu
    0022-1031/$ - see front matter Ó 2009 Elsevier Inc. All rights reserved.
    doi:10.1016/j.jesp.2009.12.011
    However, this prior research has several noteworthy shortcomings...

Fix (v2.4.42): two W0 watermark patterns strip the ISSN/front-matter/
copyright line (anchored on the line-leading journal ISSN `NNNN-NNNX/`)
and the singular `E-mail address:` corresponding-author line. The plural
multi-author `E-mail addresses:` list is intentionally left alone (it
wraps across several lines; a one-line strip would shred it).
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("DOCPLUCK_DISABLE_CAMELOT", "1")

from docpluck.normalize import NormalizationLevel, normalize_text
from docpluck.render import render_pdf_to_markdown

TEST_PDFS = Path(__file__).resolve().parents[1].parent / "PDFextractor" / "test-pdfs"


# ── Contract tests on the W0 watermark strip ────────────────────────────

def _norm(text: str) -> str:
    return normalize_text(text, NormalizationLevel.standard)[0]


def test_strips_issn_front_matter_copyright_line():
    src = (
        "preliminary research is supportive of the prediction.\n"
        "0022-1031/$ - see front matter Ó 2009 Elsevier Inc. All rights reserved.\n"
        "However, this prior research has several shortcomings.\n"
    )
    out = _norm(src)
    assert "0022-1031" not in out
    assert "see front matter" not in out
    assert "preliminary research is supportive" in out
    assert "However, this prior research" in out


def test_strips_issn_copyright_line_modern_form():
    src = "Body sentence here.\n0022-1031/© 2021 Elsevier Inc. All rights reserved.\nNext sentence.\n"
    out = _norm(src)
    assert "0022-1031" not in out
    assert "Body sentence here." in out and "Next sentence." in out


def test_strips_single_corresponding_author_email_line():
    src = "research is supportive of the prediction.\nE-mail address: muraven@albany.edu\nHowever, prior research has shortcomings.\n"
    out = _norm(src)
    assert "muraven@albany.edu" not in out
    assert "E-mail address:" not in out
    assert "research is supportive" in out


def test_keeps_plural_email_address_list():
    # The multi-author "E-mail addresses:" list wraps across lines; a
    # one-line strip would shred it, so it is intentionally NOT matched.
    src = "E-mail addresses: a@x.edu (A. One), b@y.edu (B. Two), c@z.edu\n"
    assert "E-mail addresses:" in _norm(src)


def test_keeps_body_year_range():
    # A body line with a year range (NNNN-NNNN) and no Elsevier/rights
    # keyword must never be mistaken for an ISSN line.
    src = "In 2009-2011/2012 the team replicated the effect across tasks.\n"
    assert "2009-2011" in _norm(src)


# ── Real-PDF regression test ────────────────────────────────────────────

def test_ar_apa_011_elsevier_footer_stripped():
    pdf = TEST_PDFS / "apa" / "ar_apa_j_jesp_2009_12_011.pdf"
    if not pdf.exists():
        pytest.skip(f"fixture missing: {pdf}")
    md = render_pdf_to_markdown(pdf.read_bytes())
    assert "E-mail address: muraven" not in md
    assert "0022-1031/$ - see front matter" not in md
    # Body prose that bracketed the footer must survive intact.
    assert "preliminary research is supportive of the prediction" in md
    assert "this prior research has several noteworthy shortcomings" in md


def test_chen_2021_elsevier_issn_line_stripped():
    pdf = TEST_PDFS / "apa" / "chen_2021_jesp.pdf"
    if not pdf.exists():
        pytest.skip(f"fixture missing: {pdf}")
    md = render_pdf_to_markdown(pdf.read_bytes())
    assert "0022-1031/" not in md
