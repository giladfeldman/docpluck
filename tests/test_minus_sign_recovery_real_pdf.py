"""Regression test for the '2'-for-U+2212 minus-sign corruption (cycle 6, v2.4.38).

The APA Phase-5d sweep found efendic_2022_affect rendered every negative
statistic with the U+2212 minus sign turned into the digit '2': the abstract
read `r = 2.74 [20.92, 20.30]` for `r = −.74 [−0.92, −0.30]`, and every CI in
the body and tables was likewise sign-corrupted (29 confidence intervals).
Diagnosis: a font quirk makes pdftotext map U+2212 to '2'.

Fix (v2.4.38): `normalize.py::recover_corrupted_minus_signs` (W0b step, also
applied to table cells via `cell_cleaning._html_escape`). Two self-gating,
context-safe rules:
  - descending CI bracket `[A, B]` (A > B is impossible) recovered when the
    leading '2' of a decimal bound reads as '−' and the interval becomes
    ascending;
  - `r = 2.<digits>` — a Pearson r cannot exceed 1.
An ascending CI / a plausible correlation is never touched.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

os.environ.setdefault("DOCPLUCK_DISABLE_CAMELOT", "1")

from docpluck.normalize import (
    recover_corrupted_minus_signs,
    recover_minus_via_ci_pairing,
)
from docpluck.render import render_pdf_to_markdown

TEST_PDFS = Path(__file__).resolve().parents[1].parent / "PDFextractor" / "test-pdfs"

_CORRUPT_CI_RE = re.compile(r"\[2\d?\.\d+, ?2?\d?\.\d+\]")


# ── Unit tests on recover_corrupted_minus_signs ─────────────────────────

def test_recovers_descending_ci_both_bounds():
    assert recover_corrupted_minus_signs("[20.92, 20.30]") == "[-0.92, -0.30]"


def test_recovers_descending_ci_one_bound():
    # Lower bound corrupt, upper bound genuinely positive.
    assert recover_corrupted_minus_signs("[20.08, 0.35]") == "[-0.08, 0.35]"


def test_recovers_descending_ci_above_one():
    assert recover_corrupted_minus_signs("[21.27, 21.03]") == "[-1.27, -1.03]"


def test_ascending_ci_untouched():
    # A genuine ascending interval — must NOT be converted.
    assert recover_corrupted_minus_signs("[2.42, 2.69]") == "[2.42, 2.69]"
    assert recover_corrupted_minus_signs("[0.22, 0.75]") == "[0.22, 0.75]"


def test_already_negative_ci_untouched():
    assert recover_corrupted_minus_signs("[-0.92, -0.30]") == "[-0.92, -0.30]"


def test_integer_bracket_untouched():
    # Citation list or integer pair — no decimal bound, never converted.
    assert recover_corrupted_minus_signs("[25, 3]") == "[25, 3]"


def test_recovers_implausible_correlation():
    assert recover_corrupted_minus_signs("r = 2.74") == "r = -.74"
    assert recover_corrupted_minus_signs("r(10) = 2.87") == "r(10) = -.87"


def test_plausible_correlation_untouched():
    assert recover_corrupted_minus_signs("r = 0.74") == "r = 0.74"


# ── Unit tests on recover_minus_via_ci_pairing (cycle 8, v2.4.40) ───────
# A standalone '2X.XX' point estimate (no bracket of its own) is recovered
# only when the SAME record carries a CI it must lie inside — a structural
# invariant of statistics. A genuine literal 2X.XX is never touched.

def test_ci_pairing_recovers_table_row_estimate():
    row = "<tr><td>Intercept</td><td>20.26</td><td>0.10</td><td>[-0.45, -0.06]</td></tr>"
    assert "<td>-0.26</td>" in recover_minus_via_ci_pairing(row)


def test_ci_pairing_recovers_above_one():
    row = "<tr><td>PMA</td><td>21.15</td><td>0.06</td><td>[-1.27, -1.03]</td></tr>"
    assert "<td>-1.15</td>" in recover_minus_via_ci_pairing(row)


def test_ci_pairing_recovers_body_line():
    line = "High only mediation: Mposterior = 20.54, SD=0.04, CI = [-0.61, -0.47];"
    assert "Mposterior = -0.54" in recover_minus_via_ci_pairing(line)


def test_ci_pairing_leaves_positive_estimate():
    row = "<tr><td>Attribute</td><td>0.55</td><td>0.06</td><td>[0.43, 0.67]</td></tr>"
    assert recover_minus_via_ci_pairing(row) == row


def test_ci_pairing_leaves_literal_mean_inside_its_ci():
    # A genuine mean (e.g. age 23.45) sitting INSIDE its own CI must never be
    # "recovered" — the literal value is consistent with the bracket.
    row = "<tr><td>Age</td><td>23.45</td><td>[22.10, 24.80]</td></tr>"
    assert recover_minus_via_ci_pairing(row) == row


def test_ci_pairing_leaves_token_without_bracket():
    # No CI in the record — genuinely ambiguous, must not be touched.
    assert recover_minus_via_ci_pairing("Mchange = 20.14, (0.05)") == "Mchange = 20.14, (0.05)"


def test_ci_pairing_leaves_token_outside_any_ci():
    # 25.0 de-corrupts to -5.0 which is not inside [2.0, 3.0]; untouched.
    assert recover_minus_via_ci_pairing("value 25.0 CI [2.0, 3.0]") == "value 25.0 CI [2.0, 3.0]"


# ── Real-PDF regression test ────────────────────────────────────────────

def test_efendic_no_corrupt_minus_in_render():
    pdf = TEST_PDFS / "apa" / "efendic_2022_affect.pdf"
    if not pdf.exists():
        pytest.skip(f"fixture missing: {pdf}")
    md = render_pdf_to_markdown(pdf.read_bytes())
    bad_cis = _CORRUPT_CI_RE.findall(md)
    assert not bad_cis, f"corrupt (descending '2'-prefixed) CIs remain: {bad_cis[:5]}"
    assert not re.search(r"\br = 2\.\d", md), "'r = 2.X' corrupted correlation remains"
    # The headline abstract effect size must read correctly.
    assert "r = -.74" in md


def test_efendic_table_point_estimates_recovered_via_ci():
    """Every negative B-coefficient that pairs with a CI must read as a
    recovered negative, not the corrupted '2X.XX' literal. Mode-agnostic:
    tables emit as <td> HTML (Camelot) or as unstructured-table lines, and
    the CI-pairing recovery reaches the point estimate in either mode."""
    pdf = TEST_PDFS / "apa" / "efendic_2022_affect.pdf"
    if not pdf.exists():
        pytest.skip(f"fixture missing: {pdf}")
    md = render_pdf_to_markdown(pdf.read_bytes())
    # Mediation estimate recovered in body prose (confirmed vs AI gold).
    assert "Mposterior = -0.54" in md
    # Distinctive corrupt point-estimate forms must be gone (recovered).
    assert "21.34" not in md  # Table 3, Direction x Attribute -> -1.34
    assert "21.05" not in md  # Table 4, PMA -> -1.05
    # Idempotence: the render already applies the CI-pairing recovery, so a
    # second pass must be a no-op -- proving no CI-paired corrupt estimate
    # survived. (The body `Mchange` / contrast-coding residuals carry no CI
    # and are documented escalations -- the pass leaves them untouched.)
    assert recover_minus_via_ci_pairing(md) == md
