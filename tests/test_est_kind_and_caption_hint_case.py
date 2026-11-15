"""`est_kind` names a generic estimate's null, and a caption letter
no longer types a column (found 2026-11-13).

* `est_kind`: "ratio" (null 1) or "difference" (null 0) when the column header
  names the measure; absent otherwise -- never a guessed null.
* The table-wide hint read `\\bd\\b` and `\\bOR\\b` case-insensitively over the
  caption: "Odds ratios for vitamin D" typed an "Estimate [95% CI]" column as
  Cohen's d. Case-exact symbols there now. Failed on v2.4.159.
"""
from __future__ import annotations

import pytest

from docpluck.tables.flatten import flatten_tables_for_paper


def _rows(header: str, cell: str, caption: str = "Results"):
    rows = [["Predictor", header, "p"], ["Age", cell, ".007"]]
    cells = [{"r": r, "c": c, "text": t, "is_header": r == 0}
             for r, row in enumerate(rows) for c, t in enumerate(row)]
    table = {"id": "t1", "label": "Table 1", "caption": caption, "page": 1,
             "cells": cells, "n_rows": 2, "n_cols": 3, "caption_status": "matched"}
    return [r["fields"] for r in flatten_tables_for_paper([table])]


@pytest.mark.parametrize("header, kind", [
    ("OR [95% CI]", "ratio"),
    ("HR (95% CI)", "ratio"),
    ("Odds ratio [95% CI]", "ratio"),
    ("MD [95% CI]", "difference"),
    ("Mean difference [95% CI]", "difference"),
])
def test_est_kind_from_header(header, kind):
    (f,) = _rows(header, "1.42 [1.10, 1.83]")
    assert f.get("est_kind") == kind


@pytest.mark.parametrize("header", ["Estimate [95% CI]", "Mean or median [95% CI]"])
def test_no_est_kind_when_header_names_no_measure(header):
    (f,) = _rows(header, "1.42 [1.10, 1.83]")
    assert "est_kind" not in f


@pytest.mark.parametrize("caption", [
    "Odds ratios for vitamin D",
    "Outcomes in Study D",
    "Results reported in Appendix D",
])
def test_caption_capital_d_is_not_cohens_d(caption):
    (f,) = _rows("Estimate [95% CI]", "1.42 [1.10, 1.83]", caption)
    assert "d" not in f and f.get("est") == 1.42


@pytest.mark.parametrize("caption", [
    # a footnote letter fused to a header's number: 10.1001/jamanetworkopen.2023.48333
    # Table 3 ("Crude model^b Model 1c Model 2d"), hazard ratios typed as d in the
    # first 2026-11-13 diff of this very change
    "Mortality by group. Crude model^b Model 1c Model 2d",
    "Results ^d",
    "Results. d Adjusted for age and sex.",
    "Results. g Excluding missing data.",
])
def test_footnote_letter_is_not_cohens_d(caption):
    (f,) = _rows("Estimate [95% CI]", "1.42 [1.10, 1.83]", caption)
    assert "d" not in f and "g" not in f and f.get("est") == 1.42


@pytest.mark.parametrize("caption", ["Effect sizes (Cohen's d)", "Standardized effects, d [95% CI]",
                                     "Effects (d = standardized mean difference)"])
def test_caption_that_names_d_still_types_it(caption):
    (f,) = _rows("Estimate [95% CI]", "0.42 [0.10, 0.83]", caption)
    assert f.get("d") == 0.42


# The blank-column recovery gate (`_recover_blank_roles`) read the same lone
# "d" case-insensitively: "Appendix D" or a note's footnote letter opened it.
from docpluck.tables.flatten import _recover_blank_roles  # noqa: E402

_BODY = [["Item A", "0.42 [0.10, 0.83]", "1.10 [0.90, 1.30]"],
         ["Item B", "0.30 [0.05, 0.61]", "0.95 [0.70, 1.20]"]]


@pytest.mark.parametrize("caption", ["Outcomes in Appendix D", "Outcomes. ^d", "Outcomes. d Adjusted for age."])
def test_blank_role_gate_ignores_footnote_letters(caption):
    assert _recover_blank_roles(["Item", "", ""], _BODY, 0, caption, "") == {}


def test_blank_role_gate_still_opens_on_cohens_d():
    assert _recover_blank_roles(["Item", "", ""], _BODY, 0, "Effects (Cohen's d)", "") != {}
