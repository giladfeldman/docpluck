""""Cohen" names a family of statistics; only "Cohen's d" is typed d.

Until 2026-11-16 the cohens_d header pattern matched the bare name, so a
"Cohen's h and CI" or "Cohen's w and CI" column was delivered as Cohen's d
(10.1098/rsos.250367 p17 Table 10, measured on the debt-50 branch). An h, w, f
or kappa value now stays an untyped estimate.
"""
from __future__ import annotations

import pytest

from docpluck.tables.flatten import _effect_type_for

D_SPELLINGS = [
    "Cohen's d", "Cohen’s d and CI", "Cohens d", "Cohen d", "Cohen's dz",
    "Cohen's d_av", "Cohen's d (95% CI)", "Cohen's\x00BR\x00d", "d", "dz",
]
OTHER_COHEN = ["Cohen's h and CI", "Cohen's w and CI", "Cohen's f", "Cohen's kappa", "Cohen’s h"]


@pytest.mark.parametrize("header", D_SPELLINGS)
def test_cohens_d_spellings_are_d(header):
    assert _effect_type_for(header) == "cohens_d"


@pytest.mark.parametrize("header", OTHER_COHEN)
def test_other_cohen_statistics_are_not_d(header):
    assert _effect_type_for(header) != "cohens_d"


# The same class beyond Cohen: a header pattern that matches a family or author
# name, a transformed scale, or a neighbouring statistic, so a column is typed
# as a statistic it is not. Found by the Release B consult (Sonnet + Haiku,
# 2026-11-16) and confirmed here; each member failed before its fix.
from docpluck.tables.flatten import _est_kind  # noqa: E402

KEEP = [
    ("Hedges' g", "hedges_g"), ("Hedges’ g (95% CI)", "hedges_g"), ("Hedges g", "hedges_g"),
    ("g", "hedges_g"), ("r", "pearson_r"), ("r [95% CI]", "pearson_r"),
    ("η²", "eta_squared"), ("eta squared", "eta_squared"), ("ηp²", "eta_squared_partial"),
    ("partial η²", "eta_squared_partial"), ("OR", "odds_ratio"), ("Odds ratio (95% CI)", "odds_ratio"),
    ("Mean difference", "mean_difference"), ("MD [95% CI]", "mean_difference"),
]
NOT_THAT = [
    ("Hedges and Olkin estimate", "hedges_g"),   # an author name, no g
    ("Hedges' correction", "hedges_g"),
    ("r²", "pearson_r"), ("r^2", "pearson_r"), ("r_s", "pearson_r"),  # R squared, Spearman
    ("ηG²", "eta_squared"), ("η²G", "eta_squared"), ("generalized η²", "eta_squared"),
    ("generalized eta squared", "eta_squared"),
    ("log OR", "odds_ratio"), ("ln(OR)", "odds_ratio"), ("log odds ratio", "odds_ratio"),
    ("Log-odds ratio [95% CI]", "odds_ratio"),
    ("Standardized mean difference", "mean_difference"),
    ("Standardised mean difference (95% CI)", "mean_difference"),
]


@pytest.mark.parametrize("header,et", KEEP)
def test_statistic_names_still_type(header, et):
    assert _effect_type_for(header) == et


@pytest.mark.parametrize("header,et", NOT_THAT)
def test_neighbouring_statistics_are_not_typed_as_their_relative(header, et):
    assert _effect_type_for(header) != et


@pytest.mark.parametrize("header", ["ηG²", "generalized eta squared", "η²G"])
def test_generalized_eta_never_lands_in_the_eta2_field(header):
    from docpluck.tables.flatten import _effect_key
    assert _effect_key(header, None) != "eta2"


@pytest.mark.parametrize("header", ["log OR [95% CI]", "ln(OR) (95% CI)", "Log odds ratio (95% CI)", "logit OR"])
def test_a_log_odds_column_is_not_given_the_ratio_null(header):
    # a log-odds CI is tested against 0, never 1
    assert _est_kind(header) != "ratio"


def test_a_plain_odds_ratio_keeps_the_ratio_null():
    assert _est_kind("OR [95% CI]") == "ratio"
