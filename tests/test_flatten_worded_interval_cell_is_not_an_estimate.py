"""A cell that names its interval in words is not an estimate-and-interval cell.

10.1525/collabra.77859 Table 1 (p4, raster checked 2026-10-24): the Preference
row prints "95%CI scarf: [55-72%]" in the "d or dz [95%CI]" column -- a
binomial proportion interval, no d at all. Its leading "95" was typed d = 95.0.
"""
from __future__ import annotations

import pytest

from docpluck.testing.corpus import custody_path


@pytest.fixture(scope="module")
def t1_records():
    from docpluck.extract_structured import extract_pdf_structured
    from docpluck.tables.flatten import flatten_table

    p = custody_path("fulltext", "10.1525__collabra.77859.pdf")
    t = next(
        t
        for t in extract_pdf_structured(p.read_bytes())["tables"]
        if t.get("label") == "Table 1" and t.get("page") == 4
    )
    return flatten_table(t)


def test_worded_interval_is_not_typed_as_d(t1_records):
    for r in t1_records:
        if r["row_label"] == "Preference":
            assert (r.get("fields") or {}).get("d") is None, r["fields"]


def test_a_plain_estimate_interval_cell_is_still_read(t1_records):
    exp = [r["fields"] for r in t1_records if r["row_label"] == "Expensive" and "d" in r["fields"]]
    assert exp and exp[0]["d"] == 1.91
    assert (exp[0]["CI_lower"], exp[0]["CI_upper"]) == (1.57, 2.23)
