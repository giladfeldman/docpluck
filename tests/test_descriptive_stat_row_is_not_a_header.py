"""A data row whose cells print "M = x, SD = y" is not a header row.

10.1177/0956797615601103 Table 1 (p4, rasterized 2026-10-27) has the header
"Variable | HRS | MIDUS" above a rule; the first data row below it is
"Age (years) | M = 68.33, SD = 10.48 | M = 47.86, SD = 12.91". No data-value
pattern accepted such a cell, so the row passed as a second header row: it
left the body, and every flattened record of the table was labelled with the
Age values as its column headers.
"""
from __future__ import annotations

import pytest

from docpluck.tables.cell_cleaning import _is_header_like_row


def test_mean_sd_assignments_count_as_data():
    row = ["Age (years)", "M = 68.33, SD = 10.48", "M = 47.86, SD = 12.91"]
    assert _is_header_like_row(row) is False


def test_mean_sd_column_labels_stay_header():
    assert _is_header_like_row(["Variable", "M", "SD"]) is True
    assert _is_header_like_row(["", "M (SD)", "M (SD)"]) is True


def test_sutin_2015_table_1_age_row_is_a_record():
    from docpluck.extract_structured import extract_pdf_structured
    from docpluck.tables.flatten import flatten_table
    from docpluck.testing.corpus import custody_path

    p = custody_path("fulltext", "10.1177__0956797615601103.pdf")
    tables = extract_pdf_structured(p.read_bytes())["tables"]
    t1 = next(t for t in tables if t.get("label") == "Table 1")
    recs = flatten_table(t1)
    assert "Age (years)" in {r["row_label"] for r in recs}
    for r in recs:
        assert not any("68.33" in h for h in r["header"]), r["header"]
