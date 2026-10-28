"""A table's own label and caption lines at the top of its grid leave the grid.

A capture region that starts at (or inside) the caption puts the caption's
lines in the grid's first rows. The html then took them as the column header:
10.1016/j.jesp.2021.104154 Table 3 (p6) shipped ``<thead>`` = "Table 3";
10.1177/0956797615601103 Table 1 (p4) shipped the caption's last line
"Midlife in the United States (MIDUS) Study Samples" as its header, and
10.1037/0278-6133.15.3.167 Table 1 (p5) the page's running head
"COPING WITH PARENTAL CANCER" (each rasterized 2026-10-27).

Rows leave only when their text is found verbatim (spacing aside) in the
table's caption -- the text is not lost, it is the caption -- and only from
the top of the grid, contiguously. Without the printed label, the rows must
end the caption (the region began inside it). A running head is dropped only
directly above the label row.
"""
from __future__ import annotations

from docpluck.tables.caption_rows import move_caption_rows_out_of_grid


def _cells(rows):
    return [
        {"r": r, "c": c, "rowspan": 1, "colspan": 1, "text": t, "is_header": r == 0,
         "bbox": (0.0, 0.0, 0.0, 0.0)}
        for r, row in enumerate(rows) for c, t in enumerate(row)
    ]


def _table(rows, label, caption):
    from docpluck.tables.render import cells_to_html
    cells = _cells(rows)
    return {"label": label, "caption": caption, "cells": cells, "html": cells_to_html(cells),
            "n_rows": len(rows), "n_cols": len(rows[0]), "rendering": "whitespace",
            "accuracy": None}


def _texts(t):
    by = {}
    for c in t["cells"]:
        by.setdefault(c["r"], []).append(c["text"])
    return [by[r] for r in sorted(by)]


_BODY = [
    ["U", "z", "p", "r"],
    ["Event A Outcome 1", "462", "4.24", "<0.001"],
    ["Event A Outcome 2", "780", "1.09", "0.277"],
]


def test_label_and_title_rows_leave_and_the_header_is_the_column_row():
    rows = [["Table 3", "", "", ""],
            ["Study 1: Mann-Whitney U tests of probability estimates", "", "", ""],
            *_BODY]
    t = _table(rows, "Table 3", "Table 3 Study 1: Mann-Whitney U tests of probability estimates")
    move_caption_rows_out_of_grid([t])
    assert _texts(t) == _BODY
    assert "<th>U</th>" in t["html"] and "Table 3" not in t["html"]
    assert {c["r"] for c in t["cells"]} == {0, 1, 2}
    assert t["n_rows"] == 3


def test_caption_tail_without_the_label_leaves():
    rows = [["Midlife in the United States (MIDUS) Study Samples", "", ""],
            ["Variable", "HRS", "MIDUS"],
            ["Female (%)", "59%", "53%"],
            ["Black", "13%", "4%"]]
    cap = ("Table 1. Unweighted Descriptive Statistics for the Health and Retirement Study "
           "(HRS) and Midlife in the United States (MIDUS) Study Samples")
    t = _table(rows, "Table 1", cap)
    move_caption_rows_out_of_grid([t])
    assert _texts(t)[0] == ["Variable", "HRS", "MIDUS"]


def test_running_head_above_the_label_row_leaves():
    rows = [["COPING WITH PARENTAL CANCER", "", ""],
            ["Table 1", "", ""],
            ["Means and Standard Deviations of Coping", "", ""],
            ["Variable", "M", "SD"],
            ["Personal control", "1.77", "1.02"],
            ["External control", "2.90", "1.16"]]
    t = _table(rows, "Table 1", "Table 1 Means and Standard Deviations of Coping")
    move_caption_rows_out_of_grid([t])
    assert _texts(t)[0] == ["Variable", "M", "SD"]


def test_a_header_row_whose_words_are_in_the_caption_stays():
    rows = [["Condition", "Mean", "SD"],
            ["Control", "1.2", "0.3"],
            ["Treatment", "1.9", "0.4"]]
    t = _table(rows, "Table 2", "Table 2 Mean and SD by Condition")
    before = _texts(t)
    move_caption_rows_out_of_grid([t])
    assert _texts(t) == before


def test_mid_caption_text_without_the_label_stays():
    # Not the caption's END and no label: the region did not begin inside it.
    rows = [["Unweighted Descriptive Statistics for the Health", "", ""],
            ["Variable", "HRS", "MIDUS"],
            ["Female (%)", "59%", "53%"]]
    t = _table(rows, "Table 1", "Table 1. Unweighted Descriptive Statistics for the Health and Retirement Study")
    before = _texts(t)
    move_caption_rows_out_of_grid([t])
    assert _texts(t) == before


def test_a_short_spanner_the_caption_absorbed_stays_in_the_grid():
    # 10.1001/jamanetworkopen.2023.39337 Table 3 (p9): the caption text ends
    # with the spanner "Participant group, mean (SD)a"; the row is a header
    # line, too short (< 30 letters/digits) to be taken for the caption's tail.
    rows = [["Participant group, mean (SD)a", "", ""],
            ["", "TRE", "CR"],
            ["Variable", "Baseline", "6 mo"],
            ["Weight, kg", "98.1", "95.2"],
            ["BMI", "35.1", "34.0"]]
    cap = "Table 3. Outcomes by Participant Group Participant group, mean (SD)a"
    t = _table(rows, "Table 3", cap)
    before = _texts(t)
    move_caption_rows_out_of_grid([t])
    assert _texts(t) == before


def test_a_grid_that_is_only_caption_is_left_alone():
    rows = [["Table 3", ""], ["Study 1: Mann-Whitney U tests of probability", ""]]
    t = _table(rows, "Table 3", "Table 3 Study 1: Mann-Whitney U tests of probability")
    before = _texts(t)
    move_caption_rows_out_of_grid([t])
    assert _texts(t) == before


def test_jesp_2021_104154_table_3_header_is_the_column_row():
    from docpluck.extract_structured import extract_pdf_structured
    from docpluck.testing.corpus import custody_path

    p = custody_path("fulltext", "10.1016__j.jesp.2021.104154.pdf")
    tables = extract_pdf_structured(p.read_bytes())["tables"]
    t3 = next(t for t in tables if t.get("label") == "Table 3")
    thead = t3["html"].split("</thead>")[0]
    assert "Table 3" not in thead
    assert "padjusted" in thead
