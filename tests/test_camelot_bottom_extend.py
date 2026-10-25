"""A Camelot stream grid must reach the end of its printed table.

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


def _fake_ct(lines):
    """A Camelot-shaped table: 3 rows of a 3-column grid at y 300-270 (bottom-up)."""
    from types import SimpleNamespace

    import pandas as pd

    def tl(x0, x1, y0, text):
        return SimpleNamespace(x0=x0, x1=x1, y0=y0, y1=y0 + 8.0, get_text=lambda t=text: t + "\n")

    body = [tl(50, 90, 292, "Age"), tl(150, 170, 292, "34.1"), tl(250, 270, 292, "4.5"),
            tl(50, 90, 282, "Income"), tl(150, 170, 282, "40.2"), tl(250, 270, 282, "3.3"),
            tl(50, 90, 272, "Order"), tl(150, 170, 272, "1.97"), tl(250, 270, 272, ".75")]
    df = pd.DataFrame([["Age", "34.1", "4.5"], ["Income", "40.2", "3.3"], ["Order", "1.97", ".75"]])
    return SimpleNamespace(flavor="stream", rows=[(300, 290), (290, 280), (280, 270)],
                           cols=[(40, 120), (120, 220), (220, 320)], _bbox=(40, 270, 320, 300),
                           textlines=body + [tl(*a) for a in lines], df=df)


def test_continuation_rows_aligned_with_the_columns_are_taken():
    from docpluck.tables.bottom_extend import continuation_bottom
    ct = _fake_ct([(50, 90, 262, "Partner"), (152, 168, 262, "2.00"), (252, 268, 262, ".76")])
    assert continuation_bottom(ct) == 262


def test_a_panel_with_its_own_column_layout_is_not_taken():
    """`Panel B:` then values printed where the grid has no values (x 180-210, 290-310):
    centred inside Camelot's broad column intervals, but not under its printed columns."""
    from docpluck.tables.bottom_extend import continuation_bottom
    ct = _fake_ct([(50, 100, 262, "Panel B:"), (50, 90, 252, "Wage"),
                   (185, 205, 252, "2.31"), (290, 310, 252, "0.44")])
    assert continuation_bottom(ct) is None
