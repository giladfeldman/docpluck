"""Two columns of one record bind the same field: the record is the LAST
block, whole, and the earlier cell is listed, never silently dropped and never
mixed in (Release B page checks, 2026-11-16).

A row that prints two blocks (Original | Replication, three delivery arms,
Model 1 | Model 2) cannot be one record. The release before kept the last
column's value but said nothing about the earlier one, and an earlier cell's
other fields (its interval, its operator) stayed behind. Choosing the FIRST
column, or the column nearer the record's other fields, was tried and page-
checked: both mixed studies inside one record (10.1016/j.jesp.2020.104052
Table 1: M from the Original, n and SD from the Replication;
10.1186/s12889-023-17390-0 Table 1: n from a different arm row by row). The
later block wins whole; every field of an earlier cell it displaces goes with
that cell, which is listed as `field_bound_by_later_column`.
"""
from __future__ import annotations

from docpluck.tables.flatten import flatten_table


def _table(rows):
    cells = []
    for r, row in enumerate(rows):
        for c, text in enumerate(row):
            if text:
                cells.append({"r": r, "c": c, "rowspan": 1, "colspan": 1, "text": text,
                              "is_header": r == 0, "bbox": (0.0, 0.0, 0.0, 0.0)})
    return {"id": "t1", "label": "Table 11", "page": 11, "cells": cells,
            "caption": "Table 11. Effect sizes", "footnote": None, "kind": "structured"}


def _listed(rec, col):
    return [u for u in rec["unparsed"] if u["col"] == col]


# 10.1016/j.joep.2020.102349 Table 11.
ROWS = [["Problem", "Original effect size [95% CI]", "Replication effect size [95% CI]",
         "Interpretation"],
        ["Problem 1", "0.26 [0.17, 0.37]", "0.28 [0.21, 0.36]", "Signal-consistent"]]


def test_the_later_block_is_the_record_and_the_earlier_cell_is_listed():
    (p1,) = flatten_table(_table(ROWS))
    f = p1["fields"]
    assert (f["est"], f["CI_lower"], f["CI_upper"]) == (0.28, 0.21, 0.36)
    (lost,) = _listed(p1, 1)
    assert lost["reason"] == "field_bound_by_later_column"
    assert lost["cell"] == "0.26 [0.17, 0.37]"


def test_an_earlier_interval_never_stays_beside_a_later_estimate():
    rows = [["Problem", "d [95% CI]", "d"],
            ["Problem 1", "0.26 [0.17, 0.37]", "0.28"]]
    (p1,) = flatten_table(_table(rows))
    f = p1["fields"]
    assert f.get("d") == 0.28 and "CI_lower" not in f and "CI_upper" not in f, f


# 10.1016/j.jesp.2020.104052 Table 1 (p3): Original (N, M) | Replication (N, M, SD).
def test_a_record_never_mixes_two_studies():
    rows = [["", "N", "M", "N", "M", "SD"],
            ["JE", "249", "1.66", "103", "2.01", "1.57"]]
    (rec,) = flatten_table(_table(rows))
    f = rec["fields"]
    assert (f.get("n"), f.get("M"), f.get("SD")) == (103, 2.01, 1.57), f


# 10.1525/collabra.77859 Table 4 (p8): the Original's t is printed inside its
# Mean cell, so its p is the first p column; the Replication's t, p, df, d.
def test_the_replication_p_stays_with_the_replication_t():
    rows = [["", "Mean", "p", "Mean", "t", "p", "df", "d or dz [95%CI]"],
            ["Joint", "$32.03 $29.70 2.15", ".039", "$31.67 $30.35", "1.26", ".210", "133",
             "0.11 [-.06, .28]"]]
    (rec,) = flatten_table(_table(rows))
    f = rec["fields"]
    assert (f["t"], f["df"], f["p"]) == (1.26, 133, 0.21)
    assert any(u["reason"] == "field_bound_by_later_column" and u["cell"] == ".039"
               for u in rec["unparsed"])


def test_distinct_fields_in_later_columns_still_bind():
    recs = flatten_table(_table([["Measure", "t", "df", "p", "d"],
                                 ["Anxiety", "-2.10", "48", ".050", "0.30"]]))
    assert recs[0]["fields"]["d"] == 0.3 and recs[0]["unparsed"] == []


# 10.1525/collabra.77859 Table 1 (p4): one cell prints two stacked results,
# Separate over Joint. Its t, p and df siblings already refuse two numbers;
# the d cell is refused the same way, never a d from one and an interval from
# the other.
def test_a_cell_holding_two_stacked_results_is_not_bound():
    rows = [["", "", "Coat M (SD)", "t", "p", "df", "d or dz [95%CI]"],
            ["Attractive", "Separate Joint", "4.09 (1.51) 3.83 (1.73)", "5.65 4.52",
             "<.001 <.001", "259.58 133", ".69 [.44, .94] .39 [.21, .57]"]]
    (rec,) = flatten_table(_table(rows))
    f = rec["fields"]
    assert "d" not in f and "CI_lower" not in f, f
    assert any(u["col"] == 6 for u in rec["unparsed"])


# 10.1001/jamanetworkopen.2023.48333 Table 2 (p6): the page footer was glued
# into the cell. "2023;6(12)" is a citation, not a second result.
def test_a_glued_footer_citation_is_not_a_second_result():
    rows = [["", "HR (95% CI)"],
            ["Total participants",
             "1.31 (1.20-1.44) JAMA Network Open. 2023;6(12):e2348333."]]
    (rec,) = flatten_table(_table(rows))
    assert not any(u["col"] == 1 and u["reason"] == "value_not_parsed"
                   for u in rec["unparsed"]), rec


# 10.1186/s12916-023-03229-3 Table 3: Unadjusted HR (95% CI) | P | Adjusted HR
# (95% CI) | P. Two intervals sharing a bound once left one bound behind and
# crashed the flattener (KeyError 'CI_upper').
def test_a_displaced_interval_leaves_as_a_pair():
    rows = [["Variables", "Total number", "Atrial fibrillation", "Incidence rates",
             "Unadjusted HR (95% CI)", "P-value", "Adjusted HR^a (95% CI)", "P-value"],
            ["Mild-to-moderate drinkers", "207,254", "8781", "4.73", "0.89 (0.86–0.92)", "",
             "0.96 (0.92–0.99)", ""],
            ["Per 1 SD increment in PRS", "", "", "", "1.01 (1.00–1.02)", "0.221",
             "1.00 (0.99–1.02)", "0.551"]]
    drinkers, prs = flatten_table(_table(rows))
    f = drinkers["fields"]
    assert (f["est"], f["CI_lower"], f["CI_upper"]) == (0.96, 0.92, 0.99)
    # The two intervals share their upper bound: equal is still the later one's.
    f = prs["fields"]
    assert (f["est"], f["CI_lower"], f["CI_upper"], f["p"]) == (1.0, 0.99, 1.02, 0.551)


# 10.1177/17470218241255916 Table 7 (p14): two sub-rows merged into one cell,
# each result printed over two lines. Read with the line breaks as spaces it is
# two results; once it gave 0.79 with the second result's interval.
def test_two_stacked_results_split_over_lines_are_not_bound():
    br = "\x00BR\x00"
    rows = [["Problem", "Cohen's h [95% CI]"],
            ["Problem 1", br.join(["0.79", "[0.68, 0.89]", "0.87", "[0.77, 0.98]"])]]
    (rec,) = flatten_table(_table(rows))
    assert "CI_lower" not in rec["fields"] and "est" not in rec["fields"], rec["fields"]
    assert any(u["col"] == 1 and u["reason"] == "value_not_parsed" for u in rec["unparsed"])
