"""Flatten reads the column header under the caption, not the caption, and types
Mann-Whitney ``U`` and ``z``.

10.1016/j.jesp.2021.104154 p6 Table 3 (rasterised 2026-10-24): the grid opens with
the printed label ``Table 3`` and the caption's title line before its own two
header rows. Flatten took ``Table 3`` as the header, so every column was untyped
and all 8 rows reached consumers with ``fields == {}`` -- U, z, p, r, d and the
d interval lost. A leading row is skipped only when its text is the table's own
label or a line of its own caption.
"""
from __future__ import annotations

from docpluck.tables.flatten import flatten_table

CAP = ("Table 3 Study 1: Mann-Whitney U tests of probability estimates difference "
       "between before and after conditions.")


def _flat(rows, caption=CAP, label="Table 3"):
    cells = []
    for r, row in enumerate(rows):
        for c, text in enumerate(row):
            if text:
                cells.append({"r": r, "c": c, "rowspan": 1, "colspan": 1, "text": text,
                              "is_header": r == 0, "bbox": (0.0, 0.0, 0.0, 0.0)})
    t = {"id": "t3", "label": label, "page": 6, "cells": cells, "caption": caption,
         "kind": "structured"}
    return [(f if isinstance(f, dict) else f.__dict__) for f in flatten_table(t)]


ROWS = [["Table 3", "", "", "", "", ""],
        ["Study 1: Mann-Whitney U tests of probability estimates difference between "
         "before and after conditions.", "", "", "", "", ""],
        ["After - Before", "U", "z", "p", "r", "d"],
        ["Event A Outcome 1", "462", "4.24", "<0.001", "0.45", "1.00"],
        ["Event A Outcome 2", "780", "1.09", "0.277", "0.12", "0.20"]]


def test_caption_rows_are_not_the_header():
    out = _flat(ROWS)
    assert len(out) == 2, [r["raw_cells"] for r in out]
    f = out[0]["fields"]
    assert out[0]["header"][1:] == ["U", "z", "p", "r", "d"], out[0]["header"]
    assert f.get("U") == 462 and f.get("z") == 4.24, f
    assert f.get("p") == 0.001 and f.get("p_op") == "<" and f.get("r") == 0.45 and f.get("d") == 1.0
    assert "U = 462" in out[0]["sentence"] and "z = 4.24" in out[0]["sentence"]


def test_a_header_that_merely_shares_caption_words_is_kept():
    # The caption ends "...by Condition"; the header's "Condition" cell is NOT a
    # caption line, and no row carries the label, so nothing is skipped.
    rows = [["Condition", "M", "SD"], ["Control", "3.10", "0.90"], ["Treatment", "3.60", "1.00"]]
    out = _flat(rows, caption="Table 2 Means and standard deviations by Condition", label="Table 2")
    assert [r["row_label"] for r in out] == ["Control", "Treatment"]
    assert out[0]["fields"] == {"M": 3.1, "SD": 0.9}


def test_label_row_without_caption_lines():
    rows = [["TABLE 4", "", ""], ["Item", "t", "p"], ["A", "2.00", ".040"], ["B", "1.10", ".300"]]
    out = _flat(rows, caption="TABLE 4 Results", label="Table 4")
    assert [r["row_label"] for r in out] == ["A", "B"]
    assert out[0]["fields"]["t"] == 2.0


def test_real_table_3_is_typed():
    from docpluck.testing import require_corpus_pdf
    from docpluck.extract_structured import extract_pdf_structured
    from docpluck.tables.flatten import flatten_tables_for_paper

    pdf = require_corpus_pdf("apa/chen_2021_jesp.pdf")   # 10.1016/j.jesp.2021.104154
    tabs = extract_pdf_structured(pdf.read_bytes())["tables"]
    rows = [(f if isinstance(f, dict) else f.__dict__) for f in flatten_tables_for_paper(tabs)]
    t3 = [r for r in rows if r["label"] == "Table 3"]
    typed = [r for r in t3 if "U" in r["fields"]]
    # The page prints 8 comparison rows (Events A-B x Outcomes 1-4).
    assert len(typed) == 8, [(r["row_label"], r["fields"]) for r in t3]
    first = {r["row_label"]: r["fields"] for r in typed}["Event A Outcome 1"]
    assert first["U"] == 462 and first["z"] == 4.24 and first["d"] == 1.0, first
    assert (first["CI_lower"], first["CI_upper"]) == (0.53, 1.46), first
    assert not any(r["row_label"].startswith(("Table 3", "Study 1:")) for r in t3)


def test_continuation_head_rows_are_skipped():
    rows = [["", "", "TABLE 6"], ["", "", "(Continued)"], ["Rank", "Source", "d"],
            ["1", "Smith", "0.40"], ["2", "Jones", "0.10"]]
    out = _flat(rows, caption="TABLE 6 (Continued)", label="Table 6")
    assert out[0]["header"] == ["Rank", "Source", "d"], out[0]["header"]
    assert [r["fields"].get("d") for r in out] == [0.4, 0.1]


def test_a_caption_line_split_across_cells_is_skipped_whole():
    # Corpus apa/chandrashekar_2023_mp.pdf p10 Table 8: the title line is split
    # into a short cell ("Summary of") and the rest; the short cell alone is
    # too short to be called a caption line, the joined row is one.
    rows = [["Table 8", "", "", ""],
            ["Summary of", "the replication results of Extension 2 based on logistic", "", ""],
            ["regression analysis", "", "", ""],
            ["", "Model 1", "", "Model 2"],
            ["Predictor", "Z", "p", "Z"],
            ["Intercept", "5.11", "<.001", "1.79"]]
    out = _flat(rows, caption="Table 8 Summary of the replication results of Extension 2 "
                              "based on logistic regression analysis", label="Table 8")
    assert {r["fields"].get("group") for r in out} <= {"Model 1", "Model 2"}, \
        [(r["row_label"], r["fields"]) for r in out]
