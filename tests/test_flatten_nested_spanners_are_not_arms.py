"""A spanning label binds the columns under it; the column names under it are
not arms.

10.1001/jamanetworkopen.2023.48333 p5 Table 1 prints four header lines:
"No. (weighted %)" over all four count columns, "UACR, mg/g" over Low, Medium
and High, the column names "Total | Low | Medium | High", then the "(n = ...)"
line beside "P value". Folded into one header row, "No. (weighted %)",
"UACR, mg/g", "Medium" and "High" each carried a fold mark and became four
"arms": the record count went from 28 to 100 and the P value was attached to
"High" alone. A name printed beside other names in its line is a column name;
two spanning labels on different lines are nested, not parallel arms.
"""
from __future__ import annotations

from docpluck.tables.flatten import flatten_table


def _table(rows, footnote=None):
    cells = []
    for r, row in enumerate(rows):
        for c, text in enumerate(row):
            if text:
                cells.append({"r": r, "c": c, "rowspan": 1, "colspan": 1, "text": text,
                              "is_header": False, "bbox": (0.0, 0.0, 0.0, 0.0)})
    return {"id": "t1", "label": "Table 1", "page": 5, "cells": cells,
            "caption": "Table 1. Baseline characteristics by tertile",
            "footnote": footnote, "kind": "structured"}


ROWS = [
    ["", "No. (weighted %)", "", "", "", ""],
    ["", "", "UACR, mg/g", "", "", ""],
    ["", "Total", "Low", "Medium", "High", ""],
    ["Characteristic", "(n = 23 697)", "(n = 7336)", "(n = 7604)", "(n = 8757)", "P value"],
    ["Age, mean (SD), y", "45.58 (15.44)", "42.26 (14.45)", "45.70 (15.07)", "48.71 (16.06)", "<.001"],
    ["Male", "11 891 (50.3)", "4887 (67.1)", "3529 (45.7)", "3475 (38.3)", "<.001"],
    ["Female", "11 806 (49.7)", "2449 (32.9)", "4075 (54.3)", "5282 (61.7)", ""],
    ["Hypertension", "8304 (31.2)", "1778 (22.2)", "2496 (29.7)", "4030 (41.4)", "<.001"],
]


def test_column_names_under_a_spanner_are_not_groups():
    recs = flatten_table(_table(ROWS))
    groups = {r["fields"].get("group") for r in recs}
    assert "High" not in groups and "Medium" not in groups
    assert "No. (weighted %)" not in groups and "UACR, mg/g" not in groups


def test_the_p_value_belongs_to_no_arm():
    recs = flatten_table(_table(ROWS))
    with_p = [r for r in recs if "p" in r["fields"]]
    assert {r["row_label"] for r in with_p} == {"Age, mean (SD), y", "Male", "Hypertension"}
    assert all("group" not in r["fields"] for r in with_p)


def test_the_stated_means_still_type_per_column():
    recs = flatten_table(_table(ROWS))
    age = {r["fields"].get("group"): r["fields"] for r in recs
           if r["row_label"] == "Age, mean (SD), y" and "M" in r["fields"]}
    # Each record is labelled with its column's header lines.
    assert set(age) == {"No. (weighted %) Total (n = 23 697)", "UACR, mg/g Low (n = 7336)",
                        "Medium (n = 7604)", "High (n = 8757)"}
    assert (age["High (n = 8757)"]["M"], age["High (n = 8757)"]["SD"]) == (48.71, 16.06)
    assert age["UACR, mg/g Low (n = 7336)"]["M"] == 42.26


def test_parallel_arms_under_one_label_over_all_of_them_still_group():
    # "Participants" over three cohorts, each cohort over its own columns
    # (the shape of 10.1001/jamanetworkopen.2024.18729 p5 Table 2): the cohorts
    # are the arms, named by their own line.
    recs = flatten_table(_table([
        ["", "Participants", "", "", "", "", ""],
        ["", "Cohort A", "", "Cohort B", "", "Cohort C", ""],
        ["Measure", "t", "p", "t", "p", "t", "p"],
        ["Item", "2.10", "0.040", "1.20", "0.230", "3.00", "0.004"],
    ]))
    groups = {r["fields"].get("group") for r in recs if r["row_label"] == "Item"}
    assert groups == {"Cohort A", "Cohort B", "Cohort C"}


def test_parallel_arms_on_one_line_still_group():
    recs = flatten_table(_table([
        ["", "Original", "", "", "Replication", "", ""],
        ["Item", "t", "p", "d", "t", "p", "d"],
        ["Anchor", "2.10", ".040", "0.45", "1.20", ".230", "0.20"],
    ]))
    by = {r["fields"].get("group"): r["fields"] for r in recs}
    assert by["Original"]["t"] == 2.1 and by["Replication"]["d"] == 0.2
