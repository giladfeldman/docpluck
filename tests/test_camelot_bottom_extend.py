"""A Camelot stream grid must reach the end of its printed table (d-15267e).

10.1177/00031224241252079 (am_sociol_rev_4) p12, Table 1 "Descriptive Statistics",
checked on the rasterized page 2026-10-14. The table is printed sideways and ends with
four indented education rows, "Individuals" (4,972 / 2,101 / 2,871) and "Observations"
(461,253 / 197,097 / 264,156), then the bottom rule. Camelot's stream area detection
derives the table area from aligned text EDGES; the label column's left edge breaks at
the indented sub-block, so the area -- and the grid -- ended at the label-only row
"Partner's education". The six rows below it were in no cell and the sample sizes were
lost from the structured channel.
"""
from __future__ import annotations

from collections import defaultdict

import pytest

from docpluck.extract_structured import extract_pdf_structured
from docpluck.testing import require_corpus_pdf


@pytest.fixture(scope="module")
def table1():
    pdf = require_corpus_pdf("asa/am_sociol_rev_4.pdf").read_bytes()
    tables = {t.get("label"): t for t in extract_pdf_structured(pdf)["tables"]}
    return tables["Table 1"]


def _rows(t) -> list[list[str]]:
    rows: dict[int, dict[int, str]] = defaultdict(dict)
    for c in t.get("cells") or []:
        rows[c["r"]][c["c"]] = c["text"]
    return [[rows[r][c] for c in sorted(rows[r])] for r in sorted(rows)]


def test_rows_below_the_label_only_row_are_in_the_grid(table1):
    flat = [" ".join(r) for r in _rows(table1)]
    for label, values in [
        ("No high school diploma", ["19.0%", "18.8%", "19.2%"]),
        ("Master", ["26.9%", "23.8%", "29.2%"]),
        ("Individuals", ["4,972", "2,101", "2,871"]),
        ("Observations", ["461,253", "197,097", "264,156"]),
    ]:
        hit = [r for r in flat if label in r]
        assert hit, f"row {label!r} is not in the grid: {flat[-4:]}"
        for v in values:
            assert v in hit[0], f"{v} missing from row {hit[0]!r}"


def test_rows_already_captured_are_unchanged(table1):
    """The extension may only append rows: the 14 rows Camelot had stay cell-for-cell."""
    rows = _rows(table1)
    age = [r for r in rows if r and r[0] == "Age"]
    assert age == [["Age", "34.16", "4.57", "34.28", "4.59", "34.06", "4.55"]]
    inc = [r for r in rows if r and r[0].endswith("annual gross income")]
    assert inc and inc[0][1:] == ["40,237.22", "35,291.24", "49,455.63", "41,090.54",
                                  "33,259.02", "28,359.31"]
    assert table1.get("n_cols") == 7
