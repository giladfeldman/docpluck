"""A4 turns braces into brackets only when the braces hold a confidence interval.

Both shapes measured on rasterized pages, 2026-10-14:

* 10.1038/s41562-026-02417-4 p35 prints a SET, "multiplied by a shift factor
  d ∈ {1, 2}" (also "(d ∈ {0, 1, 2})"). A4 rewrote it to "d ∈ [1, 2]", an interval:
  the paper's two scenarios became a continuum.
* 10.1016/j.jesp.2011.08.004 p8 (p93) prints a CI in braces, "the bias-corrected and
  accelerated confidence interval was {−.18, −.01}". That is the delimiter
  harmonization A4 exists for, and it stays.

The interval reading needs the words that say so (`CI`, `C.I.`, `confidence
interval`) just before the brace, the same context A4a already requires.
"""
from __future__ import annotations

from docpluck import NormalizationLevel, normalize_text


def _norm(text: str) -> str:
    return normalize_text(text, NormalizationLevel.academic)[0]


def test_set_notation_passes_through():
    out = _norm("multiplied by a shift factor d ∈ {1, 2}. Fig. S10 illustrates")
    assert "{1, 2}" in out and "[1, 2]" not in out, out
    out = _norm("ground-truth partworth utility (d ∈ {0, 1, 2}). The top row")
    assert "{0, 1, 2}" in out, out


def test_braced_confidence_interval_is_harmonized():
    out = _norm("The bias-corrected and accelerated confidence interval was {−.18, −.01}. Thus,")
    assert "[-.18, -.01]" in out, out
    out = _norm("the indirect effect, 95% CI {0.12, 0.40}, was positive")
    assert "[0.12, 0.40]" in out, out


def test_unlabelled_two_number_braces_pass_through():
    out = _norm("the thresholds were {2.5, 3.5} in both conditions")
    assert "{2.5, 3.5}" in out, out
