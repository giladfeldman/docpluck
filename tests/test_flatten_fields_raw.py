"""Every typed number carries the text the cell prints (`fields_raw`).

`fields` holds numbers, so a cell printed `-1.40` arrives as -1.4 and a cell
printed `.050` as 0.05: the printed precision is lost. A consumer that judges a
reported value within half a unit of its last printed decimal needs the printed
digits. `fields_raw` is keyed like `fields` and holds, for each typed numeric
value, the number token exactly as the cell prints it. Additive: `fields` is
unchanged, and a key is present in `fields_raw` only when its token parses back
to exactly the value in `fields` (a value docpluck repaired, such as a restored
minus sign, has no printed token and is omitted rather than misreported).
"""
from __future__ import annotations

from docpluck.tables.flatten import flatten_table


def _table(rows, caption="Table 1. Results", footnote=None):
    cells = []
    for r, row in enumerate(rows):
        for c, text in enumerate(row):
            if text:
                cells.append({"r": r, "c": c, "rowspan": 1, "colspan": 1, "text": text,
                              "is_header": r == 0, "bbox": (0.0, 0.0, 0.0, 0.0)})
    return {"id": "t1", "label": "Table 1", "page": 3, "cells": cells,
            "caption": caption, "footnote": footnote, "kind": "structured"}


def _recs(rows, **kw):
    return flatten_table(_table(rows, **kw))


def test_printed_tokens_for_every_typed_number():
    recs = _recs([["Measure", "t", "df", "p", "d", "95% CI"],
                  ["Anxiety", "-2.10", "48", ".050", "0.30", "[-0.10, 0.70]"],
                  ["Mood", "3.750", "48", "< .001", "1.20", "[.80, 1.60]"]])
    a, m = recs
    assert a["fields"]["t"] == -2.1
    assert a["fields_raw"] == {"t": "-2.10", "df": "48", "p": ".050", "d": "0.30",
                               "CI_lower": "-0.10", "CI_upper": "0.70"}
    assert m["fields_raw"] == {"t": "3.750", "df": "48", "p": ".001", "d": "1.20",
                               "CI_lower": ".80", "CI_upper": "1.60"}


def test_every_raw_key_is_a_fields_key_and_parses_to_its_value():
    recs = _recs([["Measure", "F(1, 98)", "p", "eta2"],
                  ["Load", "4.50*", ".036", ".044"]])
    r = recs[0]
    assert r["fields_raw"]["F"] == "4.50"           # the mark stays in raw_cells
    assert r["fields_raw"]["df1"] == "1" and r["fields_raw"]["df2"] == "98"
    for k, tok in r["fields_raw"].items():
        assert k in r["fields"]
        assert float(tok.replace("−", "-")) == r["fields"][k]


def test_combined_estimate_and_interval_cell():
    recs = _recs([["Measure", "d [95% CI]", "p"],
                  ["Anxiety", "0.40 [0.10, 0.70]", ".010"]])
    r = recs[0]
    assert r["fields"]["d"] == 0.4
    assert r["fields_raw"]["d"] == "0.40"
    assert r["fields_raw"]["CI_lower"] == "0.10"
    assert r["fields_raw"]["CI_upper"] == "0.70"


def test_untyped_row_has_empty_fields_raw():
    recs = _recs([["Measure", "Note"], ["Anxiety", "see text"], ["Mood", "n/a"]])
    assert all(r["fields_raw"] == {} for r in recs)
