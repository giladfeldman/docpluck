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
