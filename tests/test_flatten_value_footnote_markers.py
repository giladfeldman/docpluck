"""A statistic printed with a footnote or significance marker is still typed.

10.1016/j.jesp.2021.104154 p14 Table 12 prints ``-1.48a`` and ``-2.92a`` (a: Levene's
test significant) and p16 Table 15 ``9.84 a``; tables everywhere print ``3.67***``.
The number parse refused any trailing mark, so the t of those rows was silently
missing from `fields` while the row's df and p were kept. The marker is not part of
the value; `raw_cells` still carries it as printed.
"""
from __future__ import annotations

from docpluck.tables.flatten import flatten_table


def _fields(rows):
    cells = [{"r": r, "c": c, "rowspan": 1, "colspan": 1, "text": x, "is_header": r == 0,
              "bbox": (0.0, 0.0, 0.0, 0.0)}
             for r, row in enumerate(rows) for c, x in enumerate(row) if x]
    out = flatten_table({"id": "t", "label": "Table 1", "page": 1, "cells": cells,
                         "caption": "Table 1 Tests"})
    return [(f if isinstance(f, dict) else f.__dict__) for f in out]


def test_trailing_markers_do_not_drop_the_value():
    out = _fields([["Item", "t", "df", "p", "d"],
                   ["A", "-1.48a", "399", ".140", "-.15"],
                   ["B", "3.67***", "399", ".001", ".30*"],
                   ["C", "9.84 a", "364", "<0.001", "1.03"],
                   ["D", "2.10\u2020", "9", ".04", ".20"]])
    assert [f["fields"].get("t") for f in out] == [-1.48, 3.67, 9.84, 2.1]
    assert out[1]["fields"].get("d") == 0.3
    assert out[0]["raw_cells"][1] == "-1.48a"
    assert "t(399) = -1.48," in out[0]["sentence"], out[0]["sentence"]


def test_words_are_not_markers():
    out = _fields([["Item", "t", "p"], ["A", "n.s", ".50"], ["B", "2.0 ab cd", ".04"]])
    assert "t" not in out[0]["fields"] and "t" not in out[1]["fields"]
