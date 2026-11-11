"""A signed number whose cell wrapped above and below its row keeps its sign.

10.15626/mp.2022.3108 p39 Table S8 (raster-checked 2026-11-11) prints the
Intercept's Z as "-" over "0.798" inside one cell, centred on the row. The grid
read three rows -- a lone "-", the Intercept row with Z empty, and "0.798" alone
-- so the table html and flatten delivered Z = +0.798 (on a row of its own).
"""
from __future__ import annotations

import pytest

from docpluck.tables.cell_cleaning import _attach_detached_sign_rows


def test_sign_above_and_digits_below_join_the_row_between():
    rows = [
        ["Predictor", "Estimate", "Z", "p"],
        ["", "", "-", ""],
        ["Intercept", "-0.258", "", "0.425"],
        ["", "", "0.798", ""],
        ["Framing:", "", "", ""],
    ]
    out = _attach_detached_sign_rows(rows)
    assert out == [
        ["Predictor", "Estimate", "Z", "p"],
        ["Intercept", "-0.258", "-0.798", "0.425"],
        ["Framing:", "", "", ""],
    ]


@pytest.mark.parametrize(
    "rows",
    [
        # A dash placeholder inside a labelled data row is "not applicable".
        [["A", "-", "1.2"], ["B", "", "1.3"], ["", "0.5", ""]],
        # The row between holds no label: not a data row the cell can belong to.
        [["", "-", ""], ["", "", "1.3"], ["", "0.5", ""]],
        # The row between already holds a value in that column.
        [["", "-", ""], ["B", "0.7", "1.3"], ["", "0.5", ""]],
        # Below is a word, not an unsigned number.
        [["", "-", ""], ["B", "", "1.3"], ["", "n/a", ""]],
        # Below is already signed.
        [["", "-", ""], ["B", "", "1.3"], ["", "-0.5", ""]],
    ],
)
def test_other_shapes_are_left_as_captured(rows):
    assert _attach_detached_sign_rows(rows) == rows


def test_real_table_s8_intercept_z_is_negative():
    from docpluck.extract_structured import extract_pdf_structured
    from docpluck.tables.flatten import flatten_table
    from docpluck.testing.corpus import custody_path

    p = custody_path("fulltext", "10.15626__mp.2022.3108.pdf")
    tables = [t for t in extract_pdf_structured(p.read_bytes())["tables"] if t.get("page") == 39]
    assert tables, "no table on p39"
    t = next(t for t in tables if "Intercept" in " ".join(c["text"] for c in t["cells"]))
    assert "<td>-0.798</td>" in t["html"]
    rec = next(r for r in flatten_table(t) if r.get("row_label") == "Intercept")
    assert rec["fields"]["z"] == -0.798
