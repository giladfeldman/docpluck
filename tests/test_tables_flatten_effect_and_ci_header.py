"""A combined effect-and-interval column headed "<effect> and CI" is typed.

10.1177/01461672251327169 p.11, Table 6 (rotated page) heads two columns
"Cohen's d and CI"; each cell prints an estimate and its interval,
``−1.00 [−1.10, −0.90]``. The est_ci header pattern required a stated level in a
bracket ("d [95% CI]", "OR (95% CI)"), so this header matched no role and every
d and interval in the table reached consumers untyped: ESCImate measured on
v2.4.147 that the table's three printed sign errors could not be checked.

The paper's own sign errors (``−0.32 [−0.40, 0.24]``) must pass through as
printed -- docpluck extracts, it does not fix the paper. (A DESCENDING interval
such as ``−0.83 [0.92, 0.74]`` is dropped by the existing, recorded
``flatten_dropped_descending_ci`` policy; this file does not change that.)
"""
from __future__ import annotations

from pathlib import Path

import pytest

from docpluck.tables.flatten import _classify_column, flatten_table

from .conftest import pdf_available, pdf_path, requires_pdftotext


def _cell(r, c, text, is_header=False):
    return {"r": r, "c": c, "rowspan": 1, "colspan": 1, "text": text,
            "is_header": is_header, "bbox": (0.0, 0.0, 0.0, 0.0)}


def _table(rows):
    cells = [_cell(r, c, t, is_header=(r == 0)) for r, row in enumerate(rows) for c, t in enumerate(row)]
    return {"id": "T6", "label": "Table 6", "page": 11, "cells": cells, "bbox": (0.0,) * 4,
            "caption": "Table 6. One-Sample t-Tests of Estimation Error.", "footnote": None,
            "kind": "structured", "rendering": "stream", "confidence": 1.0, "n_rows": None,
            "n_cols": None, "header_rows": 1, "html": None, "raw_text": ""}


@pytest.mark.parametrize("header", [
    "Cohen’s d and CI", "Cohen's d and CI", "d and 95% CI", "d & CI", "Hedges' g and CI",
    "Original Effect and CI", "Mean difference and CI",
])
def test_effect_and_ci_header_is_a_combined_column(header):
    assert _classify_column(header) == "est_ci"


# A joined header that names no EFFECT is not an effect column. Sonnet review
# 2026-10-01: "M and CI" in a table with an F column was typed eta2 = 0.45 -- a mean.
@pytest.mark.parametrize("header", ["CI", "95% CI", "d", "Cohen’s d", "Interpretation", "Mean and SD",
                                    "M and CI", "n and CI", "Age and CI", "Mean and 95% CI", "Range and CI"])
def test_other_headers_keep_their_role(header):
    assert _classify_column(header) != "est_ci"


def test_table6_shape_types_d_and_interval_verbatim():
    rows = flatten_table(_table([
        ["Experiences", "t-stat", "p", "Cohen’s d and CI"],
        ["Had fight/argument", "−24.47", "<.001", "−1.00 [−1.10, −0.90]"],
        ["Received low grade", "−7.82", "<.001", "−0.32 [−0.40, 0.24]"],
    ]))
    by = {r["row_label"]: r["fields"] for r in rows}
    assert by["Had fight/argument"]["d"] == pytest.approx(-1.00)
    assert by["Had fight/argument"]["CI_lower"] == pytest.approx(-1.10)
    assert by["Had fight/argument"]["CI_upper"] == pytest.approx(-0.90)
    # The paper's dropped minus signs are passed through, never repaired.
    assert by["Received low grade"]["d"] == pytest.approx(-0.32)
    assert by["Received low grade"]["CI_lower"] == pytest.approx(-0.40)
    assert by["Received low grade"]["CI_upper"] == pytest.approx(0.24)


_PAPER = "10.1177__01461672251327169.pdf"


@requires_pdftotext
@pytest.mark.skipif(not pdf_available("articlerepo", _PAPER),
                    reason="closed-access fixture not present in the article repository")
def test_table6_real_pdf_carries_typed_d_and_ci():
    from docpluck.extract_structured import extract_pdf_structured
    r = extract_pdf_structured(Path(pdf_path("articlerepo", _PAPER)).read_bytes())
    t6 = next(t for t in r["tables"] if t.get("label") == "Table 6")
    rows = flatten_table(t6)
    typed = [x["fields"] for x in rows if "d" in x["fields"] and "CI_lower" in x["fields"]]
    # p.11 prints 19 d-and-CI cells; 1 is descending ([0.92, 0.74]) and dropped.
    assert len(typed) >= 15, len(typed)
    vals = {(f["d"], f["CI_lower"], f["CI_upper"]) for f in typed}
    assert (-1.0, -1.1, -0.9) in vals
    # The three printed sign errors arrive as printed.
    assert (-0.32, -0.40, 0.24) in vals
    assert (-0.64, -0.73, 0.56) in vals
    assert (-0.86, -0.95, 0.76) in vals


# ── A dash printed in SIGN position is a minus ──────────────────────────────
#
# 10.1017/s1930297500009189 p.29 (JDM 17(1), p. 477) Table 17 prints every minus
# as an en dash: "–1.44 [–2.17, –0.72]". The combined-cell parser read the en
# dash only as a RANGE separator, so typing that column emitted d = 1.44 and
# CI_lower = 0.02 for "0.11 [–0.02, 0.23]": the sign silently dropped. A dash
# between two numbers ("-10.36–8.34") is still a range separator.


@pytest.mark.parametrize("cell,d,lo,hi", [
    ("–1.44 [–2.17, –0.72]", -1.44, -2.17, -0.72),
    ("0.11 [–0.02, 0.23]", 0.11, -0.02, 0.23),
    ("–0.33 [–0.46, –0.20]", -0.33, -0.46, -0.20),
])
def test_dash_in_sign_position_is_a_minus(cell, d, lo, hi):
    rows = flatten_table(_table([["", "Cohen’s d and 95% CI"], ["Playing chess", cell]]))
    f = rows[0]["fields"]
    assert (f["d"], f["CI_lower"], f["CI_upper"]) == (pytest.approx(d), pytest.approx(lo), pytest.approx(hi))


def test_dash_between_numbers_is_still_a_range():
    from docpluck.tables.flatten import _parse_ci_cell

    assert _parse_ci_cell("-1.01% (-10.36–8.34)", estimate=-1.01) == (-10.36, 8.34)
    assert _parse_ci_cell("[0.20 – 0.38]") == (0.20, 0.38)


_JDM = "10.1017__s1930297500009189.pdf"


@requires_pdftotext
@pytest.mark.skipif(not pdf_available("articlerepo", _JDM),
                    reason="closed-access fixture not present in the article repository")
def test_table17_real_pdf_keeps_en_dash_signs():
    from docpluck.extract_structured import extract_pdf_structured
    r = extract_pdf_structured(Path(pdf_path("articlerepo", _JDM)).read_bytes())
    t = next(t for t in r["tables"] if t.get("label") == "Table 17")
    by = {x["row_label"]: x["fields"] for x in flatten_table(t)}
    assert by["Playing chess"]["d"] == pytest.approx(-0.33)
    assert (by["Playing chess"]["CI_lower"], by["Playing chess"]["CI_upper"]) == (
        pytest.approx(-0.46), pytest.approx(-0.20))
    assert by["Telling jokes"]["CI_lower"] == pytest.approx(-0.02)
    assert by["Using mouse"]["d"] == pytest.approx(1.18)


def test_a_mean_and_ci_column_is_never_typed_as_an_effect():
    # Sonnet review 2026-10-01, reproduced: eta2 = 0.45 from a mean.
    rows = flatten_table(_table([
        ["Condition", "M and CI", "F", "p"],
        ["Control", "0.45 [0.30, 0.60]", "4.1", ".04"],
    ]))
    f = rows[0]["fields"]
    assert "eta2" not in f and "d" not in f, f
    assert f["F"] == pytest.approx(4.1)


@pytest.mark.parametrize("cell,expected", [
    ("— 0.35", None),          # em-dash "not applicable" placeholder beside a value
    ("—0.35", None),           # em dash is never read as a minus
])
def test_a_placeholder_dash_is_not_a_minus(cell, expected):
    from docpluck.tables.flatten import _parse_number

    assert _parse_number(cell) == expected


def test_a_range_after_a_footnote_marker_is_still_a_range():
    from docpluck.tables.flatten import _parse_ci_cell

    assert _parse_ci_cell("0.20ᵃ–0.38") == (0.20, 0.38)
    assert _parse_ci_cell("[0.20* – 0.38]") == (0.20, 0.38)
