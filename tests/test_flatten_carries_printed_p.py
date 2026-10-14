"""Flattened rows carry the p-value as printed (ESCImate request, 2026-10-09).

`fields.p` is a number, so a cell printed `.050` arrived as 0.05 and its printed
precision was lost; effectcheck judges p consistency within half a unit of the last
printed decimal. `fields.p_text` carries the number exactly as the cell prints it.
Additive: `fields.p` is unchanged.
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
    return {"id": "t1", "label": "Table 1", "page": 3, "cells": cells,
            "caption": "Table 1. Results", "kind": "structured"}


def _fields(rows):
    out = flatten_table(_table(rows))
    return [(fr if isinstance(fr, dict) else fr.__dict__)["fields"] for fr in out]


def test_printed_precision_survives():
    f = _fields([["Measure", "t", "df", "p"],
                 ["Anxiety", "2.10", "48", ".050"],
                 ["Mood", "3.75", "48", "< .001"],
                 ["Sleep", "1.20", "48", "0.2"]])
    assert [x.get("p") for x in f] == [0.05, 0.001, 0.2]
    assert [x.get("p_text") for x in f] == [".050", ".001", "0.2"]
    assert f[1].get("p_op") == "<"


def test_no_p_no_p_text():
    f = _fields([["Measure", "M", "SD"], ["Anxiety", "2.10", "0.48"], ["Mood", "3.1", "0.9"]])
    assert all("p_text" not in x for x in f)
