"""A section line under the column header is not another header line when the
same column prints a second section line further down.

10.1037/a0012616 Table 4 (p7, rasterized 2026-10-28) prints "Posttreatment"
centred under the column header and "Follow-up" half-way down; the first was
folded into the "In vivo exposure" header cell, so every in-vivo record of BOTH
blocks carried group "In vivo exposure Posttreatment" (52.53 (30.92) is a
follow-up value). 10.1177/0956797615612694 Table 1 (p5) does the same with
"Outcome variable: feeling respected" / "Outcome variable: punishment per round
per target". A header that wraps onto a second line in one column has no such
twin below a data row, and still joins its header.
"""
from __future__ import annotations

from docpluck.tables.cell_cleaning import _merge_continuation_rows

_HDR = [
    ["Outcome", "", "", "", "Imaginal/in vivo exposure/"],
    ["measure", "Imaginal exposure", "In vivo exposure", "Imaginal/in vivo exposure",
     "cognitive restructuring"],
]


def test_recurring_section_line_stays_its_own_row():
    rows = _HDR + [
        ["", "", "Posttreatment", "", ""],
        ["CAPS", "45.35 (32.83)", "49.55 (23.28)", "36.95 (30.57)", "21.71 (18.42)"],
        ["BDI", "18.57 (13.62)", "18.59 (11.48)", "15.00 (12.26)", "12.71 (11.56)"],
        ["", "", "Follow-up", "", ""],
        ["CAPS", "46.81 (29.10)", "52.53 (30.92)", "38.43 (28.60)", "23.71 (19.46)"],
    ]
    out = _merge_continuation_rows([r[:] for r in rows])
    assert out[1][2] == "In vivo exposure"
    assert ["", "", "Posttreatment", "", ""] in out
    assert ["", "", "Follow-up", "", ""] in out


def test_a_one_column_header_wrap_still_joins():
    rows = [
        ["Predictor", "b", "Cohen's d"],
        ["", "", "and 95% confidence interval"],
        ["Age", "0.21", "0.30 [0.10, 0.50]"],
        ["Sex", "0.11", "0.12 [0.01, 0.23]"],
    ]
    out = _merge_continuation_rows([r[:] for r in rows])
    assert len(out) == 3
    assert "and 95% confidence interval" in out[0][2]


def test_a0012616_table_4_follow_up_values_are_not_posttreatment():
    from docpluck.extract_structured import extract_pdf_structured
    from docpluck.tables.flatten import flatten_table
    from docpluck.testing.corpus import custody_path

    p = custody_path("fulltext", "10.1037__a0012616.pdf")
    t4 = next(t for t in extract_pdf_structured(p.read_bytes())["tables"]
              if t.get("label") == "Table 4")
    groups = {(r["fields"] or {}).get("group") for r in flatten_table(t4)}
    assert not any("Posttreatment" in (g or "") for g in groups)
    assert "In vivo exposure" in groups


def test_a_wrapped_label_word_off_the_label_column_still_joins():
    # 10.1016/j.jesp.2021.104154 Table 12 (p8): "c. Gosling" / "imprinting"
    # recur in the label cell's column with data rows between; each is a wrap.
    from docpluck.tables.cell_cleaning import _recurring_section_rows

    rows = [
        ["Outcome", "Item", "t", "p"],
        ["A", "b. Hurricane", ".88", ".382"],
        ["", "Seeding", "", ""],
        ["", "c. Gosling", "-.67", ".320"],
        ["", "Imprinting", "", ""],
        ["B", "c. Gosling", "-2.30", ".022"],
        ["", "Imprinting", "", ""],
    ]
    assert _recurring_section_rows(rows) == set()


def test_footnote_lines_inside_the_grid_are_not_section_rows():
    # 10.1001/jamanetworkopen.2023.48333 Table 1 (p5): footnote lines that land
    # in a side column between data rows are not section lines.
    from docpluck.tables.cell_cleaning import _recurring_section_rows

    rows = [
        ["Characteristic", "Low", "High"],
        ["Diabetes", "12.1", "8.4"],
        ["", "", "Abbreviations: CVH, cardiovascular health; eGFR,"],
        ["Stroke", "3.2", "2.1"],
        ["", "", "survey designs."],
        ["Cancer", "6.0", "5.5"],
        ["", "", "c Other includes American Indian or Alaska Native,"],
    ]
    assert _recurring_section_rows(rows) == set()


def test_stacked_lines_of_a_text_cell_are_not_section_rows():
    # A sample-description table (Original vs Replication): a cell listing one
    # line per study, in a table whose other rows hold numbers.
    from docpluck.tables.cell_cleaning import _recurring_section_rows

    rows = [
        ["", "Original", "Replication"],
        ["Sample size", "122", "821"],
        ["Geographic origin", "Study 1: Hong Kong", "US American"],
        ["", "Study 2: US American", ""],
        ["", "Study 5: US American", ""],
        ["Median age (years)", "Undisclosed", "42"],
        ["Medium (location)", "Study 1: Physical survey", "Computer (online)"],
        ["", "Study 2: Physical survey", ""],
        ["", "Study 5: Physical survey", ""],
    ]
    assert _recurring_section_rows(rows) == set()


def test_a_wrap_under_a_text_only_row_is_not_a_section_row():
    # 10.5465/amp.2023.0198 Table 6 (p381): "Harvard University (Harvard
    # Business" / "School)" -- the wrap sits under a row that holds only text.
    from docpluck.tables.cell_cleaning import _recurring_section_rows

    rows = [
        ["CSII", "Rank", "School", "Note"],
        ["3", "10", "Stanford University (Graduate School of", "from using CSII as a b"],
        ["5", "2", "Harvard University (Harvard Business", ""],
        ["", "", "", "stones can be created based on the impact of similar"],
        ["", "", "School)", ""],
        ["", "", "faculty(i.e.,", "professorstatus,graduationyear,"],
        ["19", "7", "University of North Carolina at Chapel", ""],
        ["", "", "", "uates after graduation. This could serve as a means"],
        ["", "", "Hill (Kenan-Flagler)", ""],
    ]
    assert _recurring_section_rows(rows) == set()


def test_a_row_spanning_label_in_a_label_column_is_not_a_section_row():
    # 10.15626/mp.2022.3108 Table S9 (p40): "Opt-in default" / "Opt-out
    # default" are printed centred beside their Positive / Negative Framing
    # rows; the column holds labels, not values.
    from docpluck.tables.cell_cleaning import _recurring_section_rows

    rows = [
        ["Replication Study", "Experimental Conditions", "", "n", "Participation rate"],
        ["Replication of", "", "Positive Framing", "324", "88.6%"],
        ["", "Opt-in default", "", "", ""],
        ["Experiment 2 from", "", "Negative Framing", "324", "33.6%"],
        ["Johnson, Bellman &", "", "Positive Framing", "321", "93.1%"],
        ["", "Opt-out default", "", "", ""],
        ["Lohse (2002)", "", "Negative Framing", "319", "27.6%"],
        ["", "No-default (no default)", "Positive Framing", "320", "93.4%"],
    ]
    assert _recurring_section_rows(rows) == set()
