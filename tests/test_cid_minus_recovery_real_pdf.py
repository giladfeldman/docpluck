"""Regression test for the (cid:0) corrupted-minus-sign defect (cycle 4, v2.4.36).

The APA Phase-5d sweep found that ziano_2021_joep and chen_2021_jesp rendered
negative numbers in their statistical tables as ``(cid:0) 0.23`` instead of
``-0.23``. Diagnosis: the values come from the Camelot layout channel, whose
text layer is pdfminer; pdfminer emits ``(cid:N)`` for a font glyph it cannot
map to Unicode. For these PDFs the unmapped glyph is the U+2212 minus sign,
always printed directly before a number. ``(cid:0)`` is never legitimate text.

Fix (v2.4.36): `tables/cell_cleaning._html_escape` recovers ``(cid:0)`` (with
optional following space) immediately before a digit to an ASCII hyphen.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

os.environ.setdefault("DOCPLUCK_DISABLE_CAMELOT", "1")

from docpluck.render import render_pdf_to_markdown
from docpluck.tables.cell_cleaning import _html_escape

TEST_PDFS = Path(__file__).resolve().parents[1].parent / "PDFextractor" / "test-pdfs"


# ── Unit tests on _html_escape (cell strings observed verbatim in the PDFs) ──

def test_recovers_cid0_before_decimal():
    assert _html_escape("(cid:0) 0.23") == "-0.23"


def test_recovers_cid0_before_integer():
    assert _html_escape("(cid:0) 31") == "-31"


def test_recovers_cid0_inside_ci_bracket():
    # Verbatim ziano Table 2 cell.
    assert _html_escape("[(cid:0) 0.108,") == "[-0.108,"


def test_recovers_cid0_with_no_space():
    assert _html_escape("(cid:0)5") == "-5"


def test_leaves_cid0_not_before_digit():
    # No observed case, but the rule must be digit-anchored — a (cid:0) not
    # before a number is not a recoverable minus and is left alone.
    assert _html_escape("(cid:0) abc") == "(cid:0) abc"


def test_plain_cell_untouched():
    assert _html_escape("0.45") == "0.45"
    assert _html_escape("-0.45") == "-0.45"


# ── Real-PDF regression test ────────────────────────────────────────────

@pytest.mark.parametrize("stem", ["ziano_2021_joep", "chen_2021_jesp"])
def test_no_cid_marker_in_render(stem):
    pdf = TEST_PDFS / "apa" / f"{stem}.pdf"
    if not pdf.exists():
        pytest.skip(f"fixture missing: {pdf}")
    md = render_pdf_to_markdown(pdf.read_bytes())
    leaks = re.findall(r"\(cid:\d+\)", md)
    assert not leaks, f"{stem}: unmapped-glyph (cid:N) markers leaked: {leaks[:5]}"
