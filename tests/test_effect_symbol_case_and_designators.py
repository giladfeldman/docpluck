"""A column header's own effect symbol is read case-exact and never as a
designator letter (consult round 2, Sonnet + Haiku seats, 2026-11-13).

* "Vitamin D (95% CI)", "Study d [95% CI]", "panel (d)", "(a) (b) (c) (d)"
  typed Cohen's d; "R [95% CI]" typed Pearson r; "Mean or median" an odds ratio.
* "HR (bpm) [95% CI]" (heart rate) was given est_kind "ratio".
All failed on v2.4.160 (f7a9bbd). Headers are invented.
"""
from __future__ import annotations

import pytest

from docpluck.tables.flatten import _effect_type_for, _est_kind, _vocab_effect_type


@pytest.mark.parametrize("header", [
    "Vitamin D (95% CI)", "Study d [95% CI]", "Results for panel (d)",
    "Panels (a) (b) (c) (d)", "Experiment D estimate", "Model 2d", "Estimate^d",
])
def test_designator_or_capital_letter_is_not_cohens_d(header):
    assert _effect_type_for(header) != "cohens_d"
    assert _vocab_effect_type(header) != "cohens_d"


@pytest.mark.parametrize("header, et", [
    ("d [95% CI]", "cohens_d"), ("Cohen's d (95% CI)", "cohens_d"), ("dz", "cohens_d"),
    ("Between-group d [95% CI]", "cohens_d"), ("Hedges' g", "hedges_g"), ("g [95% CI]", "hedges_g"),
    ("r [95% CI]", "pearson_r"), ("OR [95% CI]", "odds_ratio"), ("MD (95% CI)", "mean_difference"),
])
def test_printed_symbol_still_types(header, et):
    assert _effect_type_for(header) == et


@pytest.mark.parametrize("header", ["R [95% CI]", "Mean or median [95% CI]", "md"])
def test_wrong_case_symbol_does_not_type(header):
    assert _effect_type_for(header) not in ("pearson_r", "odds_ratio", "mean_difference")


@pytest.mark.parametrize("header", ["HR (bpm) [95% CI]", "RR (breaths/min)", "HR, beats per minute"])
def test_unit_header_is_not_a_ratio(header):
    assert _est_kind(header) is None


def test_difference_with_a_unit_stays_a_difference():
    assert _est_kind("Mean difference (ms) [95% CI]") == "difference"
    assert _est_kind("HR [95% CI]") == "ratio"
