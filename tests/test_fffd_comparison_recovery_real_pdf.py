"""Regression test for cmsy10 >= / <= glyph recovery (cycle 4, v2.4.57).

On tightly-kerned PDFs that typeset comparison operators with the TeX
Computer Modern math-symbol font (cmsy10), pdftotext AND pdfplumber both
fail to decode the >= / <= glyph and emit U+FFFD. The glyph identity is
destroyed in both engines, so the layout channel cannot recover it --
recovery must be context-based.

Fix (v2.4.57): ``normalize.py::recover_fffd_comparison_operators`` (pipeline
step S5b, sibling of S5a FFFD->eta):

  * Rule 1 -- complement pairing (airtight): a corrupted "<FFFD>N" contrasted
    with a clean "<N" / ">N" of the SAME number N is the set-complement
    (< -> >=, > -> <=). A partition like "(<20/[FFFD]20 mm)" is complementary
    by construction, so this has zero false-positive risk.
  * Rule 2 -- document consensus: a lone "<FFFD>N" with no local complement
    is recovered only when Rule 1 already fired in the document AND every
    recovery agreed on one operator (one PDF == one font == one corruption
    shape). If Rule-1 recoveries disagree, or none fired, a lone FFFD is left
    alone -- the S5a policy for prose FFFD.

Corpus evidence (harness Tier-D baseline): pdfextractor vancouver plos_med_1
(PLOS Medicine, PROSECCO trial) -- 3 prose FFFDs ("age [FFFD]18 years",
"(<20/[FFFD]20 mm)", "<20 mm versus [FFFD]20 mm") reach the rendered .md;
6 more in a linearized fibroid-size-category table.

Non-ASCII codepoints are built with ``chr()`` on purpose -- U+FFFD is a
font-encoding artifact and a literal in source is fragile.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("DOCPLUCK_DISABLE_CAMELOT", "1")

from docpluck.normalize import (
    NormalizationLevel,
    normalize_text,
    recover_fffd_comparison_operators,
)
from docpluck.render import render_pdf_to_markdown

# Vibe/MetaScienceTools -- the docpluck repo's grandparent.
_META = Path(__file__).resolve().parents[2]

FFFD = chr(0xFFFD)   # the replacement character pdftotext emits
GE = chr(0x2265)     # >=
LE = chr(0x2264)     # <=


# -- Rule 1: complement pairing (airtight) -------------------------------

def test_rule1_op_then_fffd_recovers_ge():
    # "<20" partitioned against "[FFFD]20" -> the FFFD is the complement >=.
    assert (
        recover_fffd_comparison_operators("fibroid size (<20/" + FFFD + "20 mm)")
        == "fibroid size (<20/" + GE + "20 mm)"
    )


def test_rule1_op_then_fffd_recovers_le_for_gt():
    # ">N" partitioned against "[FFFD]N" -> the FFFD is the complement <=.
    assert (
        recover_fffd_comparison_operators(">50 vs " + FFFD + "50")
        == ">50 vs " + LE + "50"
    )


def test_rule1_handles_word_separator():
    assert (
        recover_fffd_comparison_operators("<20 mm versus " + FFFD + "20 mm")
        == "<20 mm versus " + GE + "20 mm"
    )


def test_rule1_fffd_then_op_order():
    # The corrupted operator may be written before the clean one.
    assert (
        recover_fffd_comparison_operators(FFFD + "20 or <20 mm")
        == GE + "20 or <20 mm"
    )


def test_rule1_requires_matching_number():
    # "<20" and "[FFFD]30" are different numbers -- not a partition, no pairing.
    text = "between <20 and " + FFFD + "30 units"
    assert recover_fffd_comparison_operators(text) == text


def test_rule1_does_not_pair_across_newline():
    # A "<N" on one line and "[FFFD]N" on another are not one clause.
    text = "<5 mm\n\n" + FFFD + "5 mm"
    assert recover_fffd_comparison_operators(text) == text


# -- Rule 2: document-consensus inference --------------------------------

def test_rule2_lone_fffd_recovered_under_consensus():
    # One airtight Rule-1 pairing establishes >= for the document; the lone
    # "[FFFD]18" then recovers to >=.
    text = "fibroid size (<20/" + FFFD + "20 mm); inclusion was age " + FFFD + "18 years"
    out = recover_fffd_comparison_operators(text)
    assert out == "fibroid size (<20/" + GE + "20 mm); inclusion was age " + GE + "18 years"


def test_rule2_does_not_fire_without_consensus():
    # No Rule-1 pairing anywhere -> no evidence -> the lone FFFD is left alone
    # (the S5a policy: prose FFFD is surfaced for quality scoring, not guessed).
    text = "inclusion was age " + FFFD + "18 years"
    assert recover_fffd_comparison_operators(text) == text


def test_rule2_does_not_fire_on_disagreeing_consensus():
    # Rule 1 yields one >= and one <= -> the document is not unanimous, so a
    # lone FFFD stays corrupt rather than being guessed.
    text = (
        "ages <20 vs " + FFFD + "20, rates >50 vs " + FFFD + "50, "
        "and a lone " + FFFD + "7 cutoff"
    )
    out = recover_fffd_comparison_operators(text)
    assert out.count(FFFD) == 1            # the lone FFFD survived
    assert (FFFD + "7 cutoff") in out


def test_rule2_guard_rejects_letter_or_digit_glued_fffd():
    # A comparison operator is always token-initial. A FFFD welded to a word
    # (corrupt footnote marker) or a digit (corrupt dash) is NOT recovered,
    # even under consensus.
    text = "size (<20/" + FFFD + "20); foot" + FFFD + "3 and range 5" + FFFD + "9"
    out = recover_fffd_comparison_operators(text)
    assert ("foot" + FFFD + "3") in out
    assert ("5" + FFFD + "9") in out
    assert ("<20/" + GE + "20") in out     # the airtight pairing still fired


def test_noop_when_no_fffd():
    clean = "A normal sentence: p < .05, age > 18, no replacement chars."
    assert recover_fffd_comparison_operators(clean) == clean
    assert recover_fffd_comparison_operators("") == ""


# -- S5b pipeline step inside normalize_text -----------------------------

def test_normalize_text_s5b_recovers_and_tracks():
    text = "fibroid size (<20/" + FFFD + "20 mm) was a stratification factor"
    # Render path (preserve_math_glyphs=True) keeps the real >= operator.
    out_render, report = normalize_text(
        text, NormalizationLevel.academic, preserve_math_glyphs=True
    )
    assert "S5b_fffd_comparison_recovery" in report.steps_applied
    assert "S5b_fffd_comparison_recovery" in report.steps_changed
    assert FFFD not in out_render
    assert (GE + "20") in out_render
    # Default (non-render) path: S5b still clears the FFFD; the later A5 step
    # ASCII-folds >= to ">=", consistently with how it folds <=, !=, x.
    out_ascii, _ = normalize_text(text, NormalizationLevel.academic)
    assert FFFD not in out_ascii
    assert ">=20" in out_ascii


def test_normalize_text_s5b_noop_when_no_fffd():
    _out, report = normalize_text(
        "ordinary academic prose with no corrupted glyphs",
        NormalizationLevel.academic,
    )
    assert "S5b_fffd_comparison_recovery" in report.steps_applied
    assert "S5b_fffd_comparison_recovery" not in report.steps_changed


# -- real-PDF regression (public render entry point) ---------------------

def test_plos_med_1_no_fffd_real_pdf():
    """plos_med_1 (PROSECCO trial): pdftotext destroys the cmsy10 >= glyph to
    U+FFFD in 3 body-prose comparisons at v2.4.56. Drives the public render
    entry point; no replacement character may survive to the rendered .md."""
    pdf = _META / "PDFextractor" / "test-pdfs" / "vancouver" / "plos_med_1.pdf"
    if not pdf.exists():
        pytest.skip(f"fixture missing: {pdf}")
    md = render_pdf_to_markdown(pdf.read_bytes())
    assert FFFD not in md, f"{md.count(FFFD)} replacement char(s) remain"
    # The three prose comparisons are recovered to the real >= operator.
    assert ("age " + GE + "18 years") in md
    assert ("<20/" + GE + "20 mm") in md
    assert ("versus " + GE + "20 mm") in md
