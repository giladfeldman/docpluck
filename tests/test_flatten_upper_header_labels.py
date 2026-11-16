"""A column named only in an upper header row keeps that name; a field typed
without any header naming its column says so (`typed_without_header`).

Real case (ESCImate, 2026-11-15): 10.1016/j.jesp.2021.104154 Table 15 (p16)
prints "Mean Difference | t | df | p | Cohen's d | 95% CI" over a second header
row holding only "Lower | Upper". The super-header fold refuses (a label with
nothing printed under it), the flattener kept only the second row, and
blank-column recovery typed the left-most number column -- the Mean Difference
-- as t. Every number below is invented; the grid has the same shape.
"""
from __future__ import annotations

from docpluck.tables.flatten import flatten_table


def _table(rows, n_header=2, caption="Table 15 Study 3: Independent Samples T-Tests."):
    cells = []
    for r, row in enumerate(rows):
        for c, text in enumerate(row):
            if text:
                cells.append({"r": r, "c": c, "rowspan": 1, "colspan": 1, "text": text,
                              "is_header": r < n_header, "bbox": (0.0, 0.0, 0.0, 0.0)})
    return {"id": "t15", "label": "Table 15", "page": 16, "cells": cells,
            "caption": caption, "footnote": None, "kind": "structured"}


TWO_ROW_HEADER = [
    ["Comparison", "Mean Difference", "t", "df", "p", "Cohen's d", "", "95% CI of Cohen's d"],
    ["", "", "", "", "", "", "Lower", "Upper"],
    ["Group A vs. Group B", "0.27", "1.84", "210", "0.067", "0.25", "-0.02", "0.52"],
    ["Group A vs. Group C", "-0.41", "-2.96", "198", "0.003", "-0.42", "-0.70", "-0.14"],
    ["Group B vs. Group C", "0.66", "4.12", "204", "<0.001", "0.58", "0.30", "0.86"],
]


def test_upper_row_names_the_column_and_t_is_the_printed_t():
    recs = flatten_table(_table(TWO_ROW_HEADER))
    assert len(recs) == 3
    a = recs[0]
    assert a["header"][:6] == ["Comparison", "Mean Difference", "t", "df", "p", "Cohen's d"]
    # The printed t, never the Mean Difference beside it.
    assert a["fields"]["t"] == 1.84
    assert a["fields"]["df"] == 210
    assert a["fields"]["p"] == 0.067
    assert a["fields"]["d"] == 0.25
    assert (a["fields"]["CI_lower"], a["fields"]["CI_upper"]) == (-0.02, 0.52)
    assert [r["fields"]["t"] for r in recs] == [1.84, -2.96, 4.12]
    # Every typed field sits under a header that names it.
    assert all(r["typed_without_header"] == [] for r in recs)
    # The Mean Difference is a column this parser does not type: it is listed,
    # not dropped and not published under another statistic's name.
    assert {"col": 1, "header": "Mean Difference", "cell": "0.27",
            "reason": "column_role_unknown"} in a["unparsed"]


def test_last_row_label_is_never_replaced():
    from docpluck.tables.flatten import _inherit_upper_header_labels as inherit
    upper = ["Comparison", "Mean Difference", "t", "A long line of running prose " * 3, "12.5"]
    lower = ["", "", "t value", "", ""]
    # A printed lower label stays; a blank one takes the label above it; prose
    # and a bare number above are not labels.
    assert inherit([upper, lower]) == ["Comparison", "Mean Difference", "t value", "", ""]
    assert inherit([lower]) == lower


def test_header_stripped_table_lists_recovered_fields():
    # The column header row is gone (absorbed into the caption): every role is
    # recovered, so every typed field is listed as typed without a header.
    rows = [
        ["", "", "", "", ""],
        ["Study 1", "2.41", "98", ".018", "0.15 [0.04, 0.26]"],
        ["Study 2", "-3.07", "98", ".003", "-0.31 [-0.52, -0.10]"],
    ]
    recs = flatten_table(_table(
        rows, n_header=1,
        caption="Table 2. Planned contrasts. t df p d [95% CI]"))
    assert recs, "the header-stripped table produced no records"
    typed = recs[0]["typed_without_header"]
    assert typed, recs[0]
    assert set(typed) <= set(recs[0]["fields"])
    assert "t" in typed


def test_effect_named_only_by_the_caption_is_listed():
    # The column says "Estimate [95% CI]"; only the caption says Cohen's d.
    rows = [
        ["Measure", "t", "df", "p", "Estimate [95% CI]"],
        ["Anxiety", "2.10", "48", ".041", "0.30 [0.01, 0.59]"],
        ["Mood", "3.75", "48", "< .001", "0.54 [0.25, 0.83]"],
    ]
    recs = flatten_table(_table(rows, n_header=1,
                                caption="Table 3. Contrasts with Cohen's d."))
    r = recs[0]
    assert r["fields"]["d"] == 0.3
    assert r["typed_without_header"] == ["d"], r
    # t, df and p are named by their own headers.
    assert not {"t", "df", "p"} & set(r["typed_without_header"])
