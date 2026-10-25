"""A data row whose cells the continuation merge joined is not a header row.

10.1080/23743603.2021.1878340 Table 2 (p13, rotated; raster checked
2026-10-24) prints two rows per product (items A and C) with the product name
only on the first. The continuation merge joins each pair into one row whose
cells hold both values sentinel-joined ("50.26 (19.63) (502)" + "24.05 (15.51)
(502)"). Such a cell matched no data-value pattern, so the first product row
("Running shoes") passed as a third header row: it vanished from the records,
and once packed arms were decided before column groups, the remaining rows'
values were typed against that data-as-header -- F took the t-test's p column
and eta2 took the F column (1.14, outside [0, 1]).
"""
from __future__ import annotations

import pytest

from docpluck.tables.cell_cleaning import _is_header_like_row
from docpluck.testing.corpus import custody_path

SEP = "\x00BR\x00"


def test_sentinel_joined_values_count_as_data():
    row = [
        "Running shoes",
        f"A{SEP}C",
        f"50.26 (19.63){SEP}24.05 (15.51)",
        f"−3.23{SEP}−3.50",
        f".001{SEP}< .001",
    ]
    assert _is_header_like_row(row) is False


def test_two_line_column_labels_stay_header():
    row = ["", f"Underfilled{SEP}M (SD)", f"Overfilled{SEP}M (SD)", "t", "p", "df"]
    assert _is_header_like_row(row) is True


@pytest.fixture(scope="module")
def xiao_tables():
    from docpluck.extract_structured import extract_pdf_structured

    p = custody_path("fulltext", "10.1080__23743603.2021.1878340.pdf")
    return extract_pdf_structured(p.read_bytes())["tables"]


def _records(tables, label, page):
    from docpluck.tables.flatten import flatten_table

    t = next(t for t in tables if t.get("label") == label and t.get("page") == page)
    return flatten_table(t)


@pytest.fixture(scope="module")
def xiao_t2_records(xiao_tables):
    return _records(xiao_tables, "Table 2", 13)


def test_first_product_row_is_a_record(xiao_t2_records):
    labels = {r["row_label"] for r in xiao_t2_records}
    assert "Running shoes" in labels


def test_no_value_is_typed_from_the_wrong_column(xiao_t2_records):
    t_test_p = {0.001, 0.271, 0.124, 0.316, 0.02, 0.86, 0.055, 0.44, 0.267}
    for r in xiao_t2_records:
        f = r.get("fields") or {}
        eta = f.get("eta2")
        assert eta is None or 0.0 <= eta <= 1.0, (r["row_label"], f)
        assert f.get("F") not in t_test_p, (r["row_label"], f)


def test_alphanumeric_arm_labels_give_one_record_per_arm(xiao_tables):
    """Table 3 (p15) prints conditions 1A and 1C under each product; the merged
    row packs both, and arm labels with a digit ("1A") are still arm labels."""
    recs = _records(xiao_tables, "Table 3", 15)
    by = {(r["row_label"], (r.get("fields") or {}).get("group")): r["fields"] for r in recs}
    rs_c = by[("Running shoes", "1C")]
    assert (rs_c.get("t"), rs_c.get("df"), rs_c.get("d")) == (11.35, 498, 0.51)
    rs_a = by[("Running shoes", "1A")]
    assert (rs_a.get("t"), rs_a.get("df"), rs_a.get("d")) == (18.30, 501, 0.82)
    assert by[("Bicycles", "1C")].get("t") == -4.29


def test_space_separated_values_count_as_data():
    """Once Camelot's appended values keep their separator ("52.96 36.06" rather
    than "52.9636.06", which happened to match the value pattern), a cell of
    space-separated values must still count as data."""
    row = ["Kogut and", "F(1,108)", "F(1,108)", "52.96 36.06", "29.95 45.37", "2.75 2.85"]
    assert _is_header_like_row(row) is False


def test_a_study_row_is_not_the_header_jdm_table2():
    """10.1017/jdm.2024.31 Table 2 (p6, raster checked 2026-10-25): the first
    study row prints F(1,108); the replication rows print F(1, 926) and
    F(3,1827). Taken as the header, the first row's df went onto every record."""
    from docpluck.extract_structured import extract_pdf_structured
    from docpluck.tables.flatten import flatten_table

    p = custody_path("fulltext", "10.1017__jdm.2024.31.pdf")
    t = next(
        t
        for t in extract_pdf_structured(p.read_bytes())["tables"]
        if t.get("label") == "Table 2" and t.get("page") == 6
    )
    for r in flatten_table(t):
        if (r["row_label"] or "").startswith("Replication"):
            assert (r.get("fields") or {}).get("df2") != 108, r["fields"]


def test_a_thousands_grouped_count_is_one_value_not_two():
    """"177 709" is one count with a thin-space thousands separator
    (10.1001/jamanetworkopen.2023.21102 Table 1 'No.' row), not two values; the
    space-separated rule must not reclassify that header-band row."""
    row = ["No.", "177 709", "19 606", "64 901", "58 736", "34 466"]
    assert _is_header_like_row(row) is True
