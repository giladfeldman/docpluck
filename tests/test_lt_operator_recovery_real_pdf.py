"""Regression test for the '<'-as-backslash glyph corruption (cycle 7, v2.4.39).

The APA Phase-5d sweep found efendic_2022_affect rendered every '<' comparison
operator as a literal backslash: body prose read `p \\ .001` for `p < .001`,
every table p-value cell read `\\.001` for `<.001`, and the legacy Wiley DOI
`13:1<1::AID-BDM333` read `13:1\\1::AID-BDM333`. Diagnosis: a font quirk makes
pdftotext map the '<' glyph to a literal backslash (24 occurrences).

Fix (v2.4.39): `normalize.py::recover_corrupted_lt_operator` (W0c step, also
applied to table cells via `cell_cleaning._html_escape` and to the assembled
markdown via `render_pdf_to_markdown`'s final post-process pass). A literal
backslash never legitimately occurs glued to a numeral in extracted
academic-PDF text, so a backslash immediately followed (optional single space)
by a digit or a '.'-prefixed decimal is unambiguously a corrupted '<'.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

os.environ.setdefault("DOCPLUCK_DISABLE_CAMELOT", "1")

from docpluck.normalize import recover_corrupted_lt_operator
from docpluck.render import render_pdf_to_markdown

TEST_PDFS = Path(__file__).resolve().parents[1].parent / "PDFextractor" / "test-pdfs"

_BS = "\\"


# ── Unit tests on recover_corrupted_lt_operator ─────────────────────────

def test_recovers_bare_decimal_pvalue():
    assert recover_corrupted_lt_operator(_BS + ".001") == "<.001"


def test_recovers_spaced_pvalue():
    assert recover_corrupted_lt_operator("p " + _BS + " .05") == "p < .05"


def test_recovers_backslash_between_digits():
    # Legacy Wiley DOI: 10.1002/(SICI)...13:1<1::AID-BDM333
    assert recover_corrupted_lt_operator("13:1" + _BS + "1::AID-B") == "13:1<1::AID-B"


def test_recovers_bare_integer_comparison():
    assert recover_corrupted_lt_operator("n " + _BS + " 30") == "n < 30"


def test_backslash_before_letter_untouched():
    # The corruption signature is numeric-anchored; a backslash before a
    # letter (a rare path-like artifact) is left alone.
    assert recover_corrupted_lt_operator("C:" + _BS + "x") == "C:" + _BS + "x"


def test_no_backslash_untouched():
    assert recover_corrupted_lt_operator("p < .05 already fine") == "p < .05 already fine"


def test_idempotent():
    once = recover_corrupted_lt_operator(_BS + ".001")
    assert recover_corrupted_lt_operator(once) == once


# ── Real-PDF regression test ────────────────────────────────────────────

def test_efendic_no_backslash_operator_in_render():
    pdf = TEST_PDFS / "apa" / "efendic_2022_affect.pdf"
    if not pdf.exists():
        pytest.skip(f"fixture missing: {pdf}")
    md = render_pdf_to_markdown(pdf.read_bytes())
    # No literal backslash glued to a numeral may survive into the .md.
    residual = re.findall(r"\\\s?\.?\d", md)
    assert not residual, f"corrupted '<'-as-backslash remains: {residual[:5]}"
    # The body p-value must read with a real comparison operator.
    assert "p < .001" in md
