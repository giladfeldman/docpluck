"""A row label wrapped before its "×" joins the row above, not a new group.

10.1177/0956797615612694 Table 1 (p5, rasterized 2026-10-27) prints the stub
"Feeling Respected" / "× Culture" on two lines with the values
-1.89*** (0.53) and -1.04** (0.36) on the first. The second line, alone in the
label column, was kept as its own label-only row and rendered as a group
heading, so the interaction coefficients were published under the main
effect "Feeling Respected" and the interaction term had no row at all.
"""
from __future__ import annotations

import pytest

from docpluck.tables.cell_cleaning import _merge_continuation_rows


def test_times_led_label_line_joins_the_data_row_above():
    rows = [
        ["Feeling respected", "1.21** (0.43)", "0.79** (0.23)"],
        ["Feeling Respected", "–1.89*** (0.53)", "–1.04** (0.36)"],
        ["× Culture", "", ""],
        ["Constant", "0.63 (1.27)", "0.08 (0.68)"],
    ]
    out = _merge_continuation_rows([list(r) for r in rows])
    labels = [r[0] for r in out]
    assert labels == ["Feeling respected", "Feeling Respected × Culture", "Constant"]
    assert out[1][1] == "–1.89*** (0.53)"


def test_a_times_led_line_above_a_new_label_row_still_joins():
    # The row after the wrap is a new labelled data row; that must not stop it.
    rows = [
        ["Status", "0.60** (0.17)", "0.10 (0.20)"],
        ["× Culture", "", ""],
        ["Culture", "1.11* (0.51)", "–0.85* (0.33)"],
    ]
    out = _merge_continuation_rows([list(r) for r in rows])
    assert [r[0] for r in out] == ["Status × Culture", "Culture"]


def test_wang_2015_table_1_interaction_row_keeps_its_label():
    from docpluck.extract_structured import extract_pdf_structured
    from docpluck.tables.flatten import flatten_table
    from docpluck.testing.corpus import custody_path

    p = custody_path("fulltext", "10.1177__0956797615612694.pdf")
    tables = extract_pdf_structured(p.read_bytes())["tables"]
    t1 = next(t for t in tables if t.get("label") == "Table 1")
    recs = {r["row_label"]: r for r in flatten_table(t1)}
    assert "Feeling Respected × Culture" in recs, sorted(recs)
    assert "–1.89" in " ".join(recs["Feeling Respected × Culture"]["raw_cells"]) or \
        "-1.89" in " ".join(recs["Feeling Respected × Culture"]["raw_cells"])
