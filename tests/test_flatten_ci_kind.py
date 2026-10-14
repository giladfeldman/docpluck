"""`fields.CI_kind` says what kind of interval `CI_level` belongs to (ESCImate
request, 2026-10-14): a 95% credible interval must not be graded as a
95% confidence interval. Present exactly when `CI_level` is.
"""
from __future__ import annotations

from docpluck.tables.flatten import flatten_table


def _fields(caption=None, footnote=None):
    cells = []
    for r, rr in enumerate([["Effect", "d", "LL", "UL"], ["H1", "0.40", "0.10", "0.70"]]):
        for c, text in enumerate(rr):
            cells.append({"r": r, "c": c, "rowspan": 1, "colspan": 1, "text": text,
                          "is_header": r == 0, "bbox": (0.0, 0.0, 0.0, 0.0)})
    t = {"id": "T1", "label": "Table 1", "page": 1, "cells": cells, "bbox": (0.0, 0.0, 0.0, 0.0),
         "caption": caption, "footnote": footnote}
    return flatten_table(t)[0]["fields"]


def test_kind_rides_with_level():
    f = _fields(footnote="Note. LL and UL bound the 95% credible interval.")
    assert (f.get("CI_level"), f.get("CI_kind")) == (95.0, "CrI"), f
    f = _fields(caption="Table 1. Standardized effects with 90% CIs")
    assert (f.get("CI_level"), f.get("CI_kind")) == (90.0, "CI"), f
    f = _fields(caption="Table 1. Posterior effects, 89% HDI")
    assert (f.get("CI_level"), f.get("CI_kind")) == (89.0, "HDI"), f


def test_no_level_no_kind():
    f = _fields(caption="Table 1. Effects")
    assert "CI_lower" in f and "CI_level" not in f and "CI_kind" not in f, f
