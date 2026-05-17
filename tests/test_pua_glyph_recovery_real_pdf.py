"""Regression test for Adobe-Symbol-font PUA glyph recovery (cycle 1, v2.4.54).

Some PDF / DOCX producers embed the Adobe "Symbol" font with no ToUnicode
CMap, so pdftotext / mammoth surface each glyph as a Private-Use-Area
codepoint U+F000+<symbol-byte> -- beta reads as U+F062, chi as U+F063,
bullet as U+F0B7. A PUA codepoint is never a legitimate character in
extracted academic text; it carries no Unicode identity, it is purely a
font-encoding artifact.

Fix (v2.4.54): ``normalize.py::recover_pua_glyphs`` maps the Adobe Symbol
StandardEncoding (U+F020-F0FF) back to real Unicode. It is the SINGLE shared
helper for all three text channels -- the body channel's W0e step
(``normalize_text``), ``cell_cleaning._html_escape`` (Camelot table cells) and
the ``render_pdf_to_markdown`` post-process (captions, fences, raw_text
fallbacks) -- so no Symbol-PUA glyph reaches any output view.

Corpus evidence (harness Tier-D baseline at v2.4.53):
  - escicheck Xiao-etal-2024 Monin&Miller : U+F063 x2 (chi), U+F0B7 x2 (bullet)
  - docxtests BH1988_manuscript           : U+F062 x2 (beta)

Non-ASCII codepoints are built with ``chr()`` on purpose: a literal
Private-Use glyph is invisible and does not survive copy/paste.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

os.environ.setdefault("DOCPLUCK_DISABLE_CAMELOT", "1")

from docpluck.normalize import (
    NormalizationLevel,
    normalize_text,
    recover_pua_glyphs,
)
from docpluck.render import render_pdf_to_markdown
from docpluck.tables.cell_cleaning import _html_escape

# Vibe/MetaScienceTools -- the docpluck repo's grandparent.
_META = Path(__file__).resolve().parents[2]
_ESCICHECK_PDFS = _META / "ESCIcheckapp" / "testpdfs"
_DOCX_TESTS = _META / "ESCIcheckapp" / "docxtests"

# Symbol-font PUA block -- none of these may survive to a user-facing view.
_SYMBOL_PUA_RE = re.compile("[" + chr(0xF020) + "-" + chr(0xF0FF) + "]")

PUA_BETA = chr(0xF062)
PUA_CHI = chr(0xF063)
PUA_BULLET = chr(0xF0B7)
GREEK_BETA = chr(0x3B2)
GREEK_CHI = chr(0x3C7)
BULLET = chr(0x2022)


# -- unit tests on recover_pua_glyphs ------------------------------------

def test_recovers_symbol_beta():
    assert recover_pua_glyphs(PUA_BETA + " = .17") == GREEK_BETA + " = .17"


def test_recovers_symbol_chi():
    # chi-squared test statistic (the superscript 2 linearizes as a digit).
    assert recover_pua_glyphs(PUA_CHI + "2(1) = 0.34") == GREEK_CHI + "2(1) = 0.34"


def test_recovers_symbol_bullet():
    assert recover_pua_glyphs(PUA_BULLET + " item one") == BULLET + " item one"


def test_recovers_full_lowercase_greek_block():
    """The Symbol 0x61-0x7A lowercase-Greek block maps to real Greek.

    Verified by codepoint so a literal-Greek typo in this test cannot mask a
    wrong table entry. Order is the Symbol typist mnemonic (a->alpha,
    b->beta, c->chi, ...)."""
    expected = [
        0x3B1, 0x3B2, 0x3C7, 0x3B4, 0x3B5, 0x3C6, 0x3B3, 0x3B7, 0x3B9,
        0x3D5, 0x3BA, 0x3BB, 0x3BC, 0x3BD, 0x3BF, 0x3C0, 0x3B8, 0x3C1,
        0x3C3, 0x3C4, 0x3C5, 0x3D6, 0x3C9, 0x3BE, 0x3C8, 0x3B6,
    ]
    got = recover_pua_glyphs("".join(chr(0xF000 + b) for b in range(0x61, 0x7B)))
    assert [ord(c) for c in got] == expected
    assert not _SYMBOL_PUA_RE.search(got)


def test_noop_on_clean_text():
    clean = "A normal sentence: p < .05, beta = .17, no PUA codepoints here."
    assert recover_pua_glyphs(clean) == clean
    assert recover_pua_glyphs("") == ""


def test_unmapped_pua_left_untouched():
    # A PUA codepoint outside the Symbol block is never guessed.
    assert recover_pua_glyphs(chr(0xE123)) == chr(0xE123)


# -- channel 2: Camelot table-cell cleaning ------------------------------

def test_cell_cleaning_channel_recovers_pua():
    """_html_escape is the Camelot-cell channel -- it bypasses normalize_text."""
    out = _html_escape(PUA_BETA + " = .17")
    assert GREEK_BETA in out
    assert not _SYMBOL_PUA_RE.search(out)


# -- channel 1: normalize_text body channel (W0e step) -------------------

def test_normalize_text_w0e_recovers_pua():
    out, report = normalize_text(
        "the standardized " + PUA_BETA + " coefficient", NormalizationLevel.academic
    )
    assert "W0e_pua_glyph_recovery" in report.steps_applied
    assert "W0e_pua_glyph_recovery" in report.steps_changed
    assert not _SYMBOL_PUA_RE.search(out)


def test_normalize_text_w0e_noop_when_no_pua():
    _out, report = normalize_text(
        "ordinary academic prose, no symbol font", NormalizationLevel.academic
    )
    # The step always runs (recorded in steps_applied) but changes nothing.
    assert "W0e_pua_glyph_recovery" in report.steps_applied
    assert "W0e_pua_glyph_recovery" not in report.steps_changed


# -- real-PDF / real-DOCX regression (all channels, public entry point) --

def test_xiao_monin_miller_no_symbol_pua_real_pdf():
    """escicheck Xiao-etal-2024: chi and bullet glyphs reach the rendered .md
    as Symbol-PUA codepoints at v2.4.53. Drives the public render entry."""
    pdf = _ESCICHECK_PDFS / (
        "Xiao-etal-2024-IRSP-Monin&Miller2001-replication-extensions-preprint-v9.pdf"
    )
    if not pdf.exists():
        pytest.skip(f"fixture missing: {pdf}")
    md = render_pdf_to_markdown(pdf.read_bytes())
    leftover = _SYMBOL_PUA_RE.findall(md)
    assert not leftover, f"Symbol-PUA glyphs remain: {[hex(ord(c)) for c in leftover]}"
    # The chi-squared test statistic is recovered to real Greek (render keeps it).
    assert GREEK_CHI in md


def test_bh1988_no_symbol_pua_real_docx():
    """docxtests BH1988: the beta regression coefficient reaches the normalized
    DOCX view as U+F062 at v2.4.53. Drives extract_docx + normalize_text, the
    pipeline the service runs to build the DOCX `normalized` view."""
    pytest.importorskip("mammoth")
    from docpluck.extract_docx import extract_docx

    docx = _DOCX_TESTS / "BH1988_manuscript.docx"
    if not docx.exists():
        pytest.skip(f"fixture missing: {docx}")
    text, _method = extract_docx(docx.read_bytes())
    normalized, report = normalize_text(text, NormalizationLevel.academic)
    leftover = _SYMBOL_PUA_RE.findall(normalized)
    assert not leftover, f"Symbol-PUA glyphs remain: {[hex(ord(c)) for c in leftover]}"
    assert "W0e_pua_glyph_recovery" in report.steps_changed


# -- cycle 3 (v2.4.56): CMEX10 extensible matrix-bracket pieces ----------

# The whole Private Use Area -- the harness Tier-D `glyph` check fails on any.
_PUA_RE = re.compile("[" + chr(0xE000) + "-" + chr(0xF8FF) + "]")


def test_recovers_cmex_extensible_brackets():
    """CMEX10 extensible square-bracket pieces U+F8EE-F8FB map to the Unicode
    Miscellaneous-Technical bracket-piece block U+23A1-23A6 (left
    upper/extension/lower corner, then right). Confirmed by glyph geometry on
    ieee_access_10 (left column F8EE/EF/F0, right column F8F9/FA/FB)."""
    for pua, want in [
        (0xF8EE, 0x23A1), (0xF8EF, 0x23A2), (0xF8F0, 0x23A3),
        (0xF8F9, 0x23A4), (0xF8FA, 0x23A5), (0xF8FB, 0x23A6),
    ]:
        got = recover_pua_glyphs(chr(pua))
        assert len(got) == 1 and ord(got) == want, (
            f"U+{pua:04X} -> U+{ord(got):04X}, want U+{want:04X}"
        )


def test_ieee_access_10_no_pua_real_pdf():
    """ieee_access_10: a matrix typeset with CMEX10 extensible square brackets
    reaches the rendered .md as U+F8EE-F8FB PUA codepoints at v2.4.55. Drives
    the public render entry; no PUA codepoint may survive."""
    pdf = _META / "PDFextractor" / "test-pdfs" / "ieee" / "ieee_access_10.pdf"
    if not pdf.exists():
        pytest.skip(f"fixture missing: {pdf}")
    md = render_pdf_to_markdown(pdf.read_bytes())
    leftover = _PUA_RE.findall(md)
    assert not leftover, (
        f"PUA codepoints remain: {sorted({hex(ord(c)) for c in leftover})}"
    )
