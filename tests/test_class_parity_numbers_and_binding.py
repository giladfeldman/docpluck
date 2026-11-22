"""Parity matrix: one printed number, one reading -- in every column role and cell shape.

Class sweep of 2026-11-18 (defect classes found in citelink: a comma read as a
thousands separator in one path and a list separator in another; copied
number patterns that drifted; values bound to a result they do not belong
to; reject paths that drop a value with no trace). Each test enumerates a
class, not one reported case:

* NUMBER SHAPE x COLUMN ROLE. A token is read the same way whether it sits
  in a single-statistic column, a combined "estimate [CI]" cell, a pair cell
  or a count cell. English + US convention (docs/SCOPE.md): ``1,234`` is one
  thousand two hundred thirty-four; ``0,05`` / ``2,21`` are not US numbers
  and are never typed (they pass through in ``raw_cells`` and are listed in
  ``unparsed``); a sign detached from its number by a space (``- 2.10``) is
  never read as a positive value.
* DOMAIN. A value outside its statistic's definitional domain is withheld
  in every column and listed in ``unparsed`` as ``value_out_of_domain``.
* BINDING. A record never holds values from two printed results: a df lent
  by one column's header to another column's statistic, or an earlier
  block's statistic kept beside a later block's p, are the ESCImate 0.7.23
  class (a value bound to a result it does not belong to) in table form.
* TEXT. Normalization never asserts that a thousands comma is a separator.
"""
from __future__ import annotations

import pytest

from docpluck.normalize import NormalizationLevel, normalize_text
from docpluck.tables.flatten import flatten_table


def _table(rows):
    cells = []
    for r, row in enumerate(rows):
        for c, text in enumerate(row):
            if text:
                cells.append({"r": r, "c": c, "rowspan": 1, "colspan": 1, "text": text,
                              "is_header": r == 0, "bbox": (0.0, 0.0, 0.0, 0.0)})
    return {"id": "t1", "label": "Table 1", "page": 3, "cells": cells,
            "caption": "Table 1. Results", "footnote": None, "kind": "structured"}


def _one(rows):
    recs = flatten_table(_table(rows))
    assert len(recs) == 1, recs
    r = recs[0]
    fields = {k: v for k, v in r["fields"].items() if k != "group"}
    return fields, r.get("fields_raw") or {}, {u["col"]: u["reason"] for u in r.get("unparsed") or []}


# Header -> the field key a single value in that column is typed as.
SINGLE = {"N": "n", "n": "n", "t": "t", "F": "F", "chi2": "chi2", "z": "z", "U": "U",
          "M": "M", "SD": "SD", "d": "d"}

# US-grouped numbers: (printed, value)
GROUPED = [("1,234", 1234.0), ("12,345,678", 12345678.0), ("110,111", 110111.0),
           ("1 234", 1234.0), ("1 234", 1234.0)]
# Comma shapes that are not US numbers.
# A leading-zero group ("0,125", "< 0,001") is a decimal comma: US grouping never
# prints "0,ddd" (tier-2 review: "0,125" was d = 125, "< 0,001" was p < 1).
NOT_US = ["0,05", "2,21", "1,23456", "12,3456", "1,2", "0,125", "0,001", "< 0,001"]
# A sign separated from its digits by a space.
DETACHED = ["- 2.10", "– 2.10", "− 2.10"]


@pytest.mark.parametrize("header", sorted(SINGLE))
@pytest.mark.parametrize("printed,value", GROUPED)
def test_grouped_number_reads_as_its_us_value_in_every_single_column(header, printed, value):
    fields, raw, unparsed = _one([["Measure", header], ["A", printed]])
    key = SINGLE[header]
    assert fields.get(key) == value, (fields, unparsed)
    assert raw.get(key) == printed
    assert not unparsed


@pytest.mark.parametrize("printed,value", GROUPED + [("1,234.5", 1234.5)])
def test_grouped_number_reads_the_same_in_a_combined_estimate_cell(printed, value):
    fields, raw, _ = _one([["Measure", "d [95% CI]"], ["A", f"{printed} [0.10, 0.70]"]])
    assert fields.get("d") == value
    assert raw.get("d") == printed


@pytest.mark.parametrize("header", sorted(SINGLE) + ["d [95% CI]", "M (SD)", "p", "r",
                                                       "95% CI"])
@pytest.mark.parametrize("printed", NOT_US)
def test_a_non_us_comma_number_is_never_typed(header, printed):
    for cell in (printed, f"{printed} [0.10, 0.70]"):
        fields, _, unparsed = _one([["Measure", header], ["A", cell]])
        assert not {k for k in fields if k in ("n", "t", "F", "chi2", "z", "U", "M", "SD",
                                                 "d", "p", "r", "est")}, (cell, fields)
        if not fields:
            assert unparsed.get(1) in ("value_not_parsed", "interval_not_parsed"), unparsed


def test_leading_zero_decimal_comma_bounds_are_never_typed():
    f, _, u = _one([["Group", "LL", "UL", "d"], ["B", "0,100", "0,200", "0,15"]])
    assert not f, f
    assert set(u.values()) == {"value_not_parsed"}, u


@pytest.mark.parametrize("stat,cell,want", [
    ("t", "1,234", {"df": 1234}), ("chi2", "1,234", {"df": 1234}),
    ("F", "2,100", {"df1": 2, "df2": 100}), ("F", "1, 98", {"df1": 1, "df2": 98})])
def test_a_df_cell_is_a_pair_only_beside_an_f(stat, cell, want):
    # A t or chi-square has one df: "1,234" there was split into df1 = 1, df2 = 234.
    f, raw, _ = _one([["Group", stat, "df", "p"], ["A", "4.2", cell, ".04"]])
    assert {k: f.get(k) for k in want} == want, f
    assert not ({"df", "df1", "df2"} - set(want)) & set(f), f
    assert set(want) <= set(raw), raw


@pytest.mark.parametrize("header", sorted(SINGLE) + ["d [95% CI]"])
@pytest.mark.parametrize("printed", DETACHED)
def test_a_detached_sign_is_never_read_as_a_positive_value(header, printed):
    for cell in (printed, f"{printed} [0.10, 0.70]"):
        fields, _, unparsed = _one([["Measure", header], ["A", cell]])
        for k in ("n", "t", "F", "chi2", "z", "U", "M", "SD", "d"):
            assert fields.get(k) != 2.1, (cell, fields)
        assert unparsed, (cell, fields)


@pytest.mark.parametrize("printed", ["2.10", "-2.10", "−2.10", ".45", "45", "2.10*",
                                     "1,234", "1,234.5"])
def test_single_column_and_combined_cell_agree(printed):
    single, _, _ = _one([["Measure", "d"], ["A", printed]])
    combined, _, _ = _one([["Measure", "d [95% CI]"], ["A", f"{printed} [0.10, 0.70]"]])
    assert single.get("d") == combined.get("d")


def test_pair_cells_read_grouped_numbers_like_count_cells():
    f, raw, _ = _one([["Measure", "M (SD)"], ["A", "1,234.5 (12.3)"]])
    assert (f.get("M"), f.get("SD")) == (1234.5, 12.3)
    assert raw.get("M") == "1,234.5"
    f, raw, _ = _one([["Measure", "n (%)"], ["A", "1,234 (45.6)"]])
    assert (f.get("count"), f.get("pct")) == (1234, 45.6)
    assert raw.get("count") == "1,234"


def test_grouped_ci_bounds_with_a_range_glyph():
    f, _, _ = _one([["Measure", "95% CI"], ["A", "1,234–2,345"]])
    assert (f.get("CI_lower"), f.get("CI_upper")) == (1234.0, 2345.0)
    f, _, u = _one([["Measure", "95% CI"], ["A", "0,10–0,70"]])
    assert "CI_lower" not in f and u.get(1) == "value_not_parsed"


# ── DOMAIN ──────────────────────────────────────────────────────────────────

OUT_OF_DOMAIN = [("SD", "-2.10"), ("F", "-2.10"), ("chi2", "-2.10"), ("U", "-2.10"),
                 ("r", "1.40"), ("p", "1.40"), ("N", "0"), ("n", "12.5"), ("df", "-2"),
                 ("df", "0"), ("df", "0, 5")]


@pytest.mark.parametrize("header,cell", OUT_OF_DOMAIN)
@pytest.mark.parametrize("last", [True, False])
def test_out_of_domain_value_is_withheld_and_listed_in_any_column_position(header, cell, last):
    rows = ([["Measure", "t", header], ["A", "2.10", cell]] if last
            else [["Measure", header, "t"], ["A", cell, "2.10"]])
    fields, _, unparsed = _one(rows)
    col = 2 if last else 1
    key = {"N": "n", "df": "df"}.get(header, header)
    assert key not in fields and "df1" not in fields, fields
    assert unparsed.get(col) == "value_out_of_domain", unparsed
    assert fields.get("t") == 2.1


# ── BINDING ─────────────────────────────────────────────────────────────────

def test_a_header_df_belongs_to_its_own_column():
    f, _, _ = _one([["Measure", "F(1, 98)", "F(2, 200)"], ["A", "4.20", "5.10"]])
    assert (f.get("F"), f.get("df1"), f.get("df2")) == (5.1, 2, 200)
    f, _, _ = _one([["Measure", "F(1, 98)", "F(2, 200)"], ["A", "", "5.10"]])
    assert (f.get("F"), f.get("df1"), f.get("df2")) == (5.1, 2, 200)
    f, _, _ = _one([["Measure", "F", "df", "F(2, 200)"], ["A", "4.20", "1, 98", "5.10"]])
    assert (f.get("F"), f.get("df1"), f.get("df2")) == (5.1, 2, 200)


def test_a_later_block_never_keeps_an_earlier_blocks_statistic():
    f, _, u = _one([["Measure", "F(1, 98)", "p", "t", "p"],
                    ["A", "4.20", ".040", "2.10", ".041"]])
    assert "F" not in f and "df1" not in f, f
    assert (f.get("t"), f.get("p")) == (2.1, 0.041)
    assert set(u) == {1, 2}
    f, _, u = _one([["Measure", "M", "SD", "n", "M", "n"],
                    ["A", "4.10", "1.20", "40", "4.50", "42"]])
    assert (f.get("M"), f.get("n")) == (4.5, 42) and "SD" not in f, f
    assert set(u) == {1, 2, 3}


def test_a_repeated_interval_alone_is_not_a_second_block():
    # 10.1016/j.jesp.2021.104154 Table 3 shape: one comparison per row, r and d
    # each printed with their own interval. The later interval replaces the
    # earlier one; U, z, p and r stay.
    f, _, u = _one([["Comparison", "U", "z", "p", "r", "LL", "UL", "d", "LL", "UL"],
                    ["A", "462", "4.24", ".001", "0.45", "0.65", "0.84", "1.00", "0.53", "1.46"]])
    assert (f.get("U"), f.get("z"), f.get("r"), f.get("d")) == (462, 4.24, 0.45, 1.0), f
    assert (f.get("CI_lower"), f.get("CI_upper")) == (0.53, 1.46), f
    assert set(u) == {5, 6}, u


@pytest.mark.parametrize("cell", ["1403 (23 697)", "83 (3797)", "0.41 (0.22)"])
def test_a_cell_without_an_interval_is_not_an_estimate_under_an_interval_header(cell):
    # 10.1001/jamanetworkopen.2023.48333 Table 2: a count and its total under
    # a spanning "HR (95% CI)" header was published as HR = 1403.
    f, _, u = _one([["Model", "HR (95% CI)"], ["Deaths (total)", cell]])
    assert "est" not in f and "CI_lower" not in f, f
    assert u == {1: "cell_shape_not_estimate_interval"}, u


@pytest.mark.parametrize("cell,est,lo,hi", [("1.31 (1.20-1.44)", 1.31, 1.2, 1.44),
                                            ("1.31 (1.20 to 1.44)", 1.31, 1.2, 1.44),
                                            ("1.31 [1.20, 1.44]", 1.31, 1.2, 1.44)])
def test_an_estimate_with_its_interval_still_types(cell, est, lo, hi):
    f, _, u = _one([["Model", "HR (95% CI)"], ["Crude", cell]])
    assert (f.get("est"), f.get("CI_lower"), f.get("CI_upper")) == (est, lo, hi), (f, u)


def test_an_interval_cut_at_the_cell_edge_keeps_its_estimate():
    # 10.1016/j.joep.2020.102350 Table 1: "0.218 [0.137," wraps to the next line.
    f, _, u = _one([["Model", "HR (95% CI)"], ["Crude", "0.218 [0.137,"]])
    assert f.get("est") == 0.218 and u == {1: "interval_not_parsed"}, (f, u)


def test_a_block_that_repeats_no_key_is_unchanged():
    f, _, u = _one([["Measure", "t", "df", "p", "d"], ["A", "2.10", "45", ".041", "0.62"]])
    assert f == {"t": 2.1, "df": 45, "p": 0.041, "p_op": "=", "p_text": ".041", "d": 0.62}
    assert not u


@pytest.mark.parametrize("header,key,df", [("t(45)", "t", 45), ("t(45.3)", "t", 45.3),
                                           ("χ2(2)", "chi2", 2), ("chi2(1)", "chi2", 1)])
def test_statistic_with_df_in_its_header_like_F(header, key, df):
    f, _, u = _one([["Measure", header, "p"], ["A", "2.10", ".041"]])
    assert f.get(key) == 2.1 and f.get("df") == df, (f, u)


def test_combined_cell_whose_interval_did_not_parse_is_listed():
    f, _, u = _one([["Measure", "d [95% CI]"], ["A", "0.40 [0,10; 0,70]"]])
    assert f.get("d") == 0.4 and "CI_lower" not in f
    assert u.get(1) == "interval_not_parsed"


# ── TEXT ────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("src", ["t(1,234.5) = 2.10", "F(12,345.6) = 2.10",
                                 "a total of [1,234.5] units", "(N = 1,234)"])
def test_normalization_keeps_a_grouped_number_whole(src):
    text = f"The effect was significant, {src}, in the full sample we report."
    for lvl in (NormalizationLevel.standard, NormalizationLevel.academic):
        out = normalize_text(text, lvl)
        out = out[0] if isinstance(out, tuple) else out
        assert src in out, out


@pytest.mark.parametrize("src,want", [("[7.77,31.28]", "[7.77, 31.28]"),
                                      ("(0.5,0.8)", "(0.5, 0.8)")])
def test_normalization_still_spaces_a_real_interval(src, want):
    out = normalize_text(f"The interval was {src} in the sample.", NormalizationLevel.academic)
    out = out[0] if isinstance(out, tuple) else out
    assert want in out
