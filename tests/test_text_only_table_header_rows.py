"""In a table with no values at all, a full row of words under a full header row
is a body row.

10.1177/19485506211056761 Table 1 (p2, rasterized 2026-10-27) prints one header
row "Manipulated attribute | Impact on affect | Impact on non-manipulated
attribute" over four rows of words ("Risk is high | Negative affect | Benefit
is low"). Every row is short text, so the header heuristic took the first two
body rows into ``<thead>``: three header rows, and the records lost "Risk is
high" and "Risk is low".

A header-like row extends the header only while the header above it is not yet
complete -- a sparse spanner row ("Outcome &") over the full column row still
folds -- or when the grid carries values to tell header from body.
"""
from __future__ import annotations

from docpluck.tables.cell_cleaning import _header_row_count, cells_grid_to_html

_T1 = [
    ["Manipulated attribute", "Impact on affect", "Impact on non-manipulated attribute"],
    ["Risk is high", "Negative affect", "Benefit is low"],
    ["Risk is low", "Positive affect", "Benefit is high"],
    ["Benefit is high", "Positive affect", "Risk is low"],
    ["Benefit is low", "Negative affect", "Risk is high"],
]


def test_text_only_table_keeps_one_header_row():
    assert _header_row_count([r[:] for r in _T1], 3) == 1
    html = cells_grid_to_html([r[:] for r in _T1])
    assert html.split("</thead>")[0].count("<tr") == 1
    assert "<td>Risk is high</td>" in html


def test_sparse_spanner_over_column_row_still_heads_a_text_table():
    rows = [
        ["", "", "Outcome &", "", ""],
        ["Study", "Setting", "operationalization", "Treatment", "Design"],
        ["Ahlquist et al.", "Poland, 2015", "Populist radical right", "Foreign currency", "Survey"],
        ["Albanese et al.", "Italy, 2008", "Populist left", "Redistribution", "Reg. discont."],
    ]
    assert _header_row_count([r[:] for r in rows], 5) == 2


def test_two_header_rows_over_values_are_unchanged():
    rows = [
        ["Predictor", "Model 1", "Model 2"],
        ["", "B (SE)", "B (SE)"],
        ["Age", "0.12 (0.03)", "0.10 (0.03)"],
        ["Sex", "0.40 (0.11)", "0.38 (0.11)"],
    ]
    assert _header_row_count([r[:] for r in rows], 3) == 2


def test_spps_2022_table_1_has_one_header_row():
    from docpluck.extract_structured import extract_pdf_structured
    from docpluck.testing.corpus import custody_path

    p = custody_path("fulltext", "10.1177__19485506211056761.pdf")
    tables = extract_pdf_structured(p.read_bytes())["tables"]
    t1 = next(t for t in tables if t.get("label") == "Table 1")
    assert t1["header_rows"] == 1
    assert "<td>Risk is high</td>" in t1["html"]


def test_flatten_agrees_with_the_html_header_split():
    # flatten._clean_grid must take the same count (one input, one answer).
    from docpluck.tables.flatten import _clean_grid

    header, body = _clean_grid([r[:] for r in _T1])
    assert len(header) == 1
    assert [r[0] for r in body][:2] == ["Risk is high", "Risk is low"]
