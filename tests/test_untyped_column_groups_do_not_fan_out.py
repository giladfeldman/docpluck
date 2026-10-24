"""A column grouping that binds no statistic does not multiply a row's records.

A folded super-header splits a row into one record per arm so that each arm's
statistics stay apart. When no arm yields a single typed value, the split binds
nothing: it only repeats the row once per "arm", often under a wrapped header
word mistaken for an arm label. 10.5465/amle.2017.0488 p13 Table 5 (a citation
count table) became three records per row, labelled "Academic", "Book" and
"WoS" -- the first words of the wrapped headers "Academic Source", "Book
Citations", "WoS Citations" -- with row labels "Yes" and "1". Such a table is
flattened as one record per row, as an ungrouped table is.
"""
from __future__ import annotations

from docpluck.tables.flatten import flatten_table


def _flat(rows, header_rows=2):
    cells = [{"r": r, "c": c, "rowspan": 1, "colspan": 1, "text": t,
              "is_header": r < header_rows, "bbox": (0.0, 0.0, 0.0, 0.0)}
             for r, row in enumerate(rows) for c, t in enumerate(row) if t]
    t = {"id": "t5", "label": "Table 5", "page": 1, "cells": cells,
         "caption": "Table 5 Most cited sources", "kind": "structured"}
    return [(f if isinstance(f, dict) else f.__dict__) for f in flatten_table(t)]


def test_wrapped_header_words_are_not_arms():
    rows = [["", "Academic", "", "", "Book", "WoS"],
            ["Rank", "Source", "Title", "Year", "Citations", "Citations"],
            ["1", "Yes", "Personality", "2002", "11", "879"],
            ["2", "No", "Goals", "1990", "9", "500"]]
    out = _flat(rows)
    assert len(out) == 2, [(r["row_label"], r["fields"]) for r in out]
    assert all("group" not in r["fields"] for r in out)


def test_untyped_model_columns_are_one_record_per_row():
    rows = [["", "Creativity", "", "Task", ""],
            ["", "Model 1", "Model 2", "Model 1", "Model 2"],
            ["Variables", "b (SE)", "b (SE)", "b (SE)", "b (SE)"],
            ["Gender", "-0.09 (0.14)", "-0.08 (0.13)", "-0.05 (0.17)", "-0.09 (0.15)"]]
    out = _flat(rows, header_rows=3)
    assert [r["row_label"] for r in out] == ["Gender"], [(r["row_label"], r["fields"]) for r in out]


def test_typed_arms_still_split():
    rows = [["", "Study 1", "", "Study 2", ""],
            ["Item", "M", "SD", "M", "SD"],
            ["A", "3.1", "0.9", "3.4", "1.0"]]
    out = _flat(rows)
    assert [r["fields"] for r in out] == [
        {"group": "Study 1", "M": 3.1, "SD": 0.9},
        {"group": "Study 2", "M": 3.4, "SD": 1.0},
    ]


def test_real_citation_table_is_one_record_per_row():
    from docpluck.testing import require_corpus_pdf
    from docpluck.extract_structured import extract_pdf_structured
    from docpluck.tables.flatten import flatten_tables_for_paper

    pdf = require_corpus_pdf("aom/amle_1.pdf")   # 10.5465/amle.2017.0488
    tabs = extract_pdf_structured(pdf.read_bytes())["tables"]
    rows = [(f if isinstance(f, dict) else f.__dict__) for f in flatten_tables_for_paper(tabs)]
    t5 = [r for r in rows if r["label"] == "Table 5"]
    assert t5 and not any("group" in r["fields"] for r in t5), \
        sorted({r["fields"].get("group") for r in t5}, key=str)


def test_a_label_repeated_over_each_column_of_its_span_is_one_arm():
    # A descriptive table whose spanning label is
    # repeated into every column it covers ("Controllability" over M and over
    # SD). Each arm keeps its M with its SD.
    rows = [["", "Controllability", "Controllability", "Certainty", "Certainty"],
            ["Item", "M", "SD", "M", "SD"],
            ["1. Heart attack", "3.62", "1.25", "1.85", "1.16"]]
    out = _flat(rows)
    assert [r["fields"] for r in out] == [
        {"group": "Controllability", "M": 3.62, "SD": 1.25},
        {"group": "Certainty", "M": 1.85, "SD": 1.16},
    ], [r["fields"] for r in out]


def test_repeated_labels_over_repeated_subheaders_stay_apart():
    # Corpus escicheck/majumder_2024_jdm.pdf p6 Table 2: the same label over
    # two columns that each carry the SAME sub-header is two comparisons, not
    # one arm -- merging them would keep one d and drop the other.
    rows = [["", "Comparison", "Comparison"],
            ["Item", "d", "d"],
            ["ingroup", "0.29", "0.01"]]
    out = _flat(rows)
    assert sorted(r["fields"].get("d") for r in out) == [0.01, 0.29], [r["fields"] for r in out]
