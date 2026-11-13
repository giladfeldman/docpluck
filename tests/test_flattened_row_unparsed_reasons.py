"""Each flattened row says which value cells reached no field, and why (d-6bff50).

A consumer saw `fields == {}` (or a partial one) with no way to tell which
cells were dropped or why. Failed on v2.4.159 (no `unparsed` key).
"""
from __future__ import annotations

from docpluck.tables.flatten import flatten_tables_for_paper


def _flat(rows):
    cells = [{"r": r, "c": c, "text": t, "is_header": r == 0}
             for r, row in enumerate(rows) for c, t in enumerate(row)]
    return flatten_tables_for_paper([{
        "id": "t1", "label": "Table 1", "caption": "Results", "page": 1, "cells": cells,
        "n_rows": len(rows), "n_cols": len(rows[0]), "caption_status": "matched"}])


def test_reasons_name_each_untyped_value_cell():
    (a, b) = _flat([["Predictor", "b", "SE", "t", "p"],
                    ["Age", "0.12", "0.05", "2.40", ".050"],
                    ["Sex", "0.30", "n/a", "x1", "<.001"]])
    assert [(u["header"], u["reason"]) for u in a["unparsed"]] == [
        ("b", "column_role_unknown"), ("SE", "column_role_unknown")]
    assert [(u["header"], u["cell"], u["reason"]) for u in b["unparsed"]] == [
        ("b", "0.30", "column_role_unknown"), ("t", "x1", "value_not_parsed")]


def test_fully_typed_row_has_empty_unparsed():
    (r,) = _flat([["Effect", "F(1, 40)", "p", "d [95% CI]"],
                  ["Cond", "5.10", ".03", "0.42 [0.10, 0.83]"]])
    assert r["unparsed"] == []
    assert r["fields"]["F"] == 5.1


def test_unlabelled_pair_columns_are_reported_not_dropped():
    # Two "M (SD)" columns with no arm label cannot say which arm each is, so
    # neither is typed -- and the row now says so.
    (r,) = _flat([["Item", "M (SD)", "M (SD)"], ["Score", "3.2 (1.1)", "3.9 (0.8)"]])
    assert r["fields"] == {}
    assert [(u["col"], u["reason"]) for u in r["unparsed"]] == [
        (1, "pair_column_without_arm_label"), (2, "pair_column_without_arm_label")]


def test_labelled_arms_are_typed_in_their_own_records():
    out = _flat([["Item", "Control M (SD)", "Treatment M (SD)"], ["Score", "3.2 (1.1)", "3.9 (0.8)"]])
    assert [(r["fields"].get("group"), r["fields"].get("M")) for r in out] == [
        ("Control", 3.2), ("Treatment", 3.9)]
    assert all(r["unparsed"] == [] for r in out)
