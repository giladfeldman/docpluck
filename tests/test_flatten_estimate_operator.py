"""A printed inequality on an estimate survives flattening (`<key>_op`).

Only the p-value used to carry its operator (`p_op`). An effect-size cell printed
``< 0.001 [0.000, 0.004]`` was flattened to ``eta2 = 0.001`` with no operator, so
a consumer read a bound as an equality. 10.1080/23743603.2021.1878340 p16
Table 4 (Replication arm) prints exactly that, rasterised 2026-10-24.

Additive contract: the numeric field is unchanged; a sibling ``<key>_op``
(``eta2_op``, ``est_op``, ``d_op``, ...) is present only when the cell prints an
inequality, and the sentence reads ``η² < 0.001`` rather than ``η² = < 0.001``.
"""
from __future__ import annotations

from docpluck.tables.flatten import flatten_table


def _rows(rows, caption="Table 1. Results"):
    cells = []
    for r, row in enumerate(rows):
        for c, text in enumerate(row):
            if text:
                cells.append({"r": r, "c": c, "rowspan": 1, "colspan": 1, "text": text,
                              "is_header": r == 0, "bbox": (0.0, 0.0, 0.0, 0.0)})
    t = {"id": "t1", "label": "Table 1", "page": 3, "cells": cells,
         "caption": caption, "kind": "structured"}
    return [(fr if isinstance(fr, dict) else fr.__dict__) for fr in flatten_table(t)]


def test_effect_with_interval_keeps_its_inequality():
    out = _rows([["Item", "F", "p", "η2p (90% CI)"],
                 ["Shoes", "0.14", ".707", "< 0.001 [0.000, 0.004]"],
                 ["TVs", "0.68", ".409", "0.001 [0.000, 0.006]"]])
    f0, f1 = out[0]["fields"], out[1]["fields"]
    assert f0["eta2"] == 0.001 and f0.get("eta2_op") == "<", f0
    assert "η² < 0.001" in out[0]["sentence"], out[0]["sentence"]
    assert "= <" not in out[0]["sentence"]
    # The paired opposite: a printed equality carries no operator field.
    assert f1["eta2"] == 0.001 and "eta2_op" not in f1, f1
    assert "η² = 0.001" in out[1]["sentence"]


def test_bare_typed_column_keeps_its_inequality():
    out = _rows([["Effect", "t", "d"],
                 ["A", "2.10", "< .01"],
                 ["B", "3.00", "0.42"]])
    f0, f1 = out[0]["fields"], out[1]["fields"]
    assert f0.get("d") == 0.01 and f0.get("d_op") == "<", f0
    assert "d < .01" in out[0]["sentence"], out[0]["sentence"]
    assert f1.get("d") == 0.42 and "d_op" not in f1, f1


def test_greater_than_and_unicode_le():
    out = _rows([["Effect", "t", "d"],
                 ["A", "2.10", "> 1.20"],
                 ["B", "3.00", "≤ .05"]])
    assert out[0]["fields"].get("d_op") == ">" and out[0]["fields"]["d"] == 1.2
    assert out[1]["fields"].get("d_op") == "≤" and out[1]["fields"]["d"] == 0.05


def test_p_contract_unchanged():
    out = _rows([["Measure", "t", "p"], ["A", "2.10", "< .001"]])
    f = out[0]["fields"]
    assert f["p"] == 0.001 and f["p_op"] == "<" and f["p_text"] == ".001"
    assert not any(k.endswith("_op") and k != "p_op" for k in f), f


def test_real_table_replication_arm_inequality():
    from docpluck.testing import require_corpus_pdf
    from docpluck.extract_structured import extract_pdf_structured
    from docpluck.tables.flatten import flatten_tables_for_paper

    pdf = require_corpus_pdf("apa/xiao_2021_crsp.pdf")   # 10.1080/23743603.2021.1878340
    res = extract_pdf_structured(pdf.read_bytes())
    rows = [(f if isinstance(f, dict) else f.__dict__) for f in flatten_tables_for_paper(res["tables"])]
    t4 = [r for r in rows if r["label"] == "Table 4" and r["page"] == 16]
    rep = {r["row_label"]: r["fields"] for r in t4 if r["fields"].get("group") == "Replication"}
    orig = {r["row_label"]: r["fields"] for r in t4 if r["fields"].get("group") == "Original"}
    # The page prints "< 0.001" for these three Replication cells, "0.001" for the other two.
    for label in ("Running shoes", "Microwaves", "Computers"):
        assert rep[label].get("eta2_op") == "<", (label, rep[label])
    for label in ("TVs", "Bicycles"):
        assert rep[label]["eta2"] == 0.001 and "eta2_op" not in rep[label], (label, rep[label])
    assert all("eta2_op" not in f for f in orig.values()), orig
