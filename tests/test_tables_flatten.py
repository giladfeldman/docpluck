"""
Regression tests for `docpluck.tables.flatten` (EC-T1 — table-row flattening).

Fixtures synthesize the 6 canary table shapes from the ESCIcheck handoffs
(`ESCIcheckapp/docs/DOCPLUCK_HANDOFF_2026-05-24.md` D1a-d and
`DOCPLUCK_HANDOFF_2026-05-25.md` D-B/D/E/F). Each fixture is a flat
``list[Cell]`` matching docpluck's `Table` schema, fed through
`flatten_table` and asserted at the sentence + fields level.

Triage: `docs/TRIAGE_2026-05-14_phase_5d_gold_audit.md` → cluster EC-T1.
"""

from __future__ import annotations

import pytest

from docpluck.tables.flatten import (
    _parse_ci_cell,
    flatten_table,
    flatten_tables_for_paper,
    render_flattened_inline,
)


def mk_cell(r, c, text, is_header=False):
    return {
        "r": r,
        "c": c,
        "rowspan": 1,
        "colspan": 1,
        "text": text,
        "is_header": is_header,
        "bbox": (0.0, 0.0, 0.0, 0.0),
    }


def mk_table(cells, *, id_="T1", label="Table 1", page=1):
    return {
        "id": id_,
        "label": label,
        "page": page,
        "cells": cells,
        "bbox": (0.0, 0.0, 0.0, 0.0),
        "caption": None,
        "footnote": None,
        "kind": "structured",
        "rendering": "lattice",
        "confidence": 1.0,
        "n_rows": None,
        "n_cols": None,
        "header_rows": None,
        "html": None,
        "raw_text": "",
    }


# ── D1d / collabra_57785 Table 8 — t-rows with df column ────────────────────


class TestT57785Table8:
    """Bare ``t = X`` cells with df in a separate column → t(df) consolidation."""

    def _table(self):
        cells = [
            mk_cell(0, 0, "", True),
            mk_cell(0, 1, "t-value", True),
            mk_cell(0, 2, "df", True),
            mk_cell(0, 3, "p", True),
            mk_cell(0, 4, "d", True),
            mk_cell(1, 0, "Importance"),
            mk_cell(1, 1, "3.93"),
            mk_cell(1, 2, "741"),
            mk_cell(1, 3, "<.001"),
            mk_cell(1, 4, "0.29"),
            mk_cell(2, 0, "Effort"),
            mk_cell(2, 1, "6.79"),
            mk_cell(2, 2, "742"),
            mk_cell(2, 3, "<.001"),
            mk_cell(2, 4, "0.25"),
        ]
        return mk_table(cells, id_="T8", label="Table 8", page=7)

    def test_t_with_df_consolidates(self):
        rows = flatten_table(self._table())
        assert len(rows) == 2
        assert rows[0]["sentence"] == (
            "Importance: t(741) = 3.93, p < .001, d = 0.29"
        )
        assert rows[1]["sentence"] == (
            "Effort: t(742) = 6.79, p < .001, d = 0.25"
        )

    def test_fields_parsed(self):
        rows = flatten_table(self._table())
        f = rows[0]["fields"]
        assert f["t"] == 3.93
        assert f["df"] == 741
        assert f["p"] == 0.001
        assert f["p_op"] == "<"
        assert f["d"] == 0.29

    def test_df_is_int_when_integral(self):
        # Real-world load-bearing: downstream consumers expect df as int.
        f = flatten_table(self._table())[0]["fields"]
        assert isinstance(f["df"], int)


# ── D1a / collabra_90203 Table 8 — F-with-df in header (F(1, 998)) ──────────


class TestT90203Table8:
    """F-value column header carries the df pair: ``F(1, 998)`` → df1/df2 parsed."""

    def _table(self):
        cells = [
            mk_cell(0, 0, "Source", True),
            mk_cell(0, 1, "F(1, 998)", True),
            mk_cell(0, 2, "p", True),
            mk_cell(1, 0, "Condition"),
            mk_cell(1, 1, "0.01"),
            mk_cell(1, 2, ".938"),
            mk_cell(2, 0, "Stim"),
            mk_cell(2, 1, "0.654"),
            mk_cell(2, 2, ".419"),
        ]
        return mk_table(cells, id_="T8b", label="Table 8")

    def test_f_with_df_consolidates(self):
        rows = flatten_table(self._table())
        assert rows[0]["sentence"] == "Condition: F(1, 998) = 0.01, p = .938"
        assert rows[1]["sentence"] == "Stim: F(1, 998) = 0.654, p = .419"

    def test_df1_df2_in_fields(self):
        f = flatten_table(self._table())[0]["fields"]
        assert f["F"] == 0.01
        assert f["df1"] == 1
        assert f["df2"] == 998
        assert f["p"] == 0.938


# ── D1c / collabra_90203 Table 10 — correlations with n column ──────────────


class TestT90203Table10:
    """r + n columns → r(n - 2) consolidation per APA convention."""

    def _table(self):
        cells = [
            mk_cell(0, 0, "Pair", True),
            mk_cell(0, 1, "n", True),
            mk_cell(0, 2, "r", True),
            mk_cell(1, 0, "Identifiable/Explicit"),
            mk_cell(1, 1, "170"),
            mk_cell(1, 2, ".63"),
            mk_cell(2, 0, "Other/Explicit"),
            mk_cell(2, 1, "160"),
            mk_cell(2, 2, ".58"),
        ]
        return mk_table(cells, id_="T10", label="Table 10")

    def test_r_with_n_consolidates_to_df_n_minus_2(self):
        rows = flatten_table(self._table())
        assert rows[0]["sentence"] == "Identifiable/Explicit: r(168) = .63"
        assert rows[1]["sentence"] == "Other/Explicit: r(158) = .58"

    def test_r_field_is_float(self):
        f = flatten_table(self._table())[0]["fields"]
        assert f["r"] == 0.63
        assert f["n"] == 170


# ── D-2026-05-25-F / majumder JDM — effect size + CI columns ────────────────


class TestMajumderEffectSizeCI:
    """``d | CI lower | CI upper`` rows → ``d = X, 95% CI [lo, hi]``."""

    def _table(self):
        cells = [
            mk_cell(0, 0, "Hypothesis", True),
            mk_cell(0, 1, "d", True),
            mk_cell(0, 2, "lower", True),
            mk_cell(0, 3, "upper", True),
            mk_cell(1, 0, "H1 single"),
            mk_cell(1, 1, "0.04"),
            mk_cell(1, 2, "-0.19"),
            mk_cell(1, 3, "0.27"),
            mk_cell(2, 0, "H1 combined"),
            mk_cell(2, 1, "0.12"),
            mk_cell(2, 2, "-0.08"),
            mk_cell(2, 3, "0.32"),
        ]
        return mk_table(cells, id_="T2", label="Table 2")

    def test_ci_from_lower_upper_columns(self):
        rows = flatten_table(self._table())
        assert "d = 0.04" in rows[0]["sentence"]
        assert "95% CI [-0.19, 0.27]" in rows[0]["sentence"]

    def test_ci_fields_populated(self):
        f = flatten_table(self._table())[0]["fields"]
        assert f["d"] == 0.04
        assert f["CI_lower"] == -0.19
        assert f["CI_upper"] == 0.27


# ── D-2026-05-25-E / lee_feldman — bare t + p in nodf table ─────────────────


class TestLeeNewmanBareTPNoDf:
    """Cells like ``t = 37.7, p < 0.001`` without a df column. Without df,
    sentence reads ``t = 37.7, p < 0.001`` (no parens). effectcheck v0.6.1
    extracts these as NOTE status; this test asserts our flatten preserves
    the same shape so the upgrade-to-OK path is open later."""

    def test_t_without_df_no_parens(self):
        cells = [
            mk_cell(0, 0, "Item", True),
            mk_cell(0, 1, "M", True),
            mk_cell(0, 2, "SD", True),
            mk_cell(0, 3, "t", True),
            mk_cell(0, 4, "p", True),
            mk_cell(1, 0, "alcoholism good change"),
            mk_cell(1, 1, "67.1"),
            mk_cell(1, 2, "35.9"),
            mk_cell(1, 3, "37.7"),
            mk_cell(1, 4, "<0.001"),
        ]
        rows = flatten_table(mk_table(cells, id_="T10", label="Table 10"))
        s = rows[0]["sentence"]
        assert "t = 37.7" in s
        assert "p < 0.001" in s
        assert "M = 67.1" in s
        assert "SD = 35.9" in s


# ── D1b / collabra_90203 Table 9 — bare numeric rows (no labels) ────────────


class TestBareNumericRow:
    """When the row is all numeric, the first column header is used as the
    label-column hint. Test the bare-number case degrades gracefully."""

    def test_first_column_becomes_label_when_non_numeric(self):
        cells = [
            mk_cell(0, 0, "Replication", True),
            mk_cell(0, 1, "df", True),
            mk_cell(0, 2, "F", True),
            mk_cell(0, 3, "p", True),
            mk_cell(1, 0, "Replication 1"),
            mk_cell(1, 1, "114"),
            mk_cell(1, 2, "0.09"),
            mk_cell(1, 3, ".764"),
        ]
        rows = flatten_table(mk_table(cells, id_="T9", label="Table 9"))
        assert rows[0]["sentence"] == "Replication 1: F = 0.09, p = .764"
        # df present but F has no df-in-header pair; F-with-1-df reads as
        # ``F = 0.09`` only (we don't synthesize F(df) from a single column).
        assert rows[0]["fields"]["df"] == 114


# ── Inline-block rendering + sentinel boundaries ────────────────────────────


class TestInlineRender:
    def _records(self):
        cells = [
            mk_cell(0, 0, "", True),
            mk_cell(0, 1, "t-value", True),
            mk_cell(0, 2, "df", True),
            mk_cell(0, 3, "p", True),
            mk_cell(1, 0, "Importance"),
            mk_cell(1, 1, "3.93"),
            mk_cell(1, 2, "741"),
            mk_cell(1, 3, "<.001"),
        ]
        return flatten_table(mk_table(cells, id_="T8", label="Table 8"))

    def test_sentinel_markers_present(self):
        block = render_flattened_inline(
            self._records(), table_id="T8", label="Table 8", version="2.4.76"
        )
        assert '<!-- docpluck:flattened-table id="T8" start -->' in block
        assert '<!-- docpluck:flattened-table id="T8" end -->' in block

    def test_heading_and_sentence_in_block(self):
        block = render_flattened_inline(
            self._records(), table_id="T8", label="Table 8", version="2.4.76"
        )
        assert "### Table 8 — rendered as text" in block
        assert "- Importance: t(741) = 3.93, p < .001" in block

    def test_empty_records_yield_empty_block(self):
        assert render_flattened_inline([], table_id="T8") == ""

    def test_version_suffix_optional(self):
        # Without version, no `vX.Y.Z` suffix in the caption.
        block = render_flattened_inline(
            self._records(), table_id="T8", label="Table 8"
        )
        assert "docpluck v" not in block
        assert "docpluck." in block  # Trailing period from caption sentence.


# ── Edge cases ──────────────────────────────────────────────────────────────


class TestEdgeCases:
    def test_empty_cell_list_returns_empty(self):
        assert flatten_table(mk_table([], id_="T0")) == []

    def test_single_row_table_returns_empty(self):
        cells = [mk_cell(0, 0, "Only", True), mk_cell(0, 1, "One", True)]
        assert flatten_table(mk_table(cells)) == []

    def test_unknown_column_headers_degrade_to_label_only(self):
        # If no column header matches a known stat role, the sentence falls
        # back to the row label so the row stays visible but un-parseable.
        cells = [
            mk_cell(0, 0, "Animal", True),
            mk_cell(0, 1, "Class", True),
            mk_cell(0, 2, "Color", True),
            mk_cell(1, 0, "Cat"),
            mk_cell(1, 1, "Mammal"),
            mk_cell(1, 2, "Black"),
        ]
        rows = flatten_table(mk_table(cells))
        assert rows[0]["sentence"] == "Cat"
        assert rows[0]["fields"] == {}
        # raw_cells + header preserved so downstream can roll its own parser.
        assert rows[0]["raw_cells"] == ["Cat", "Mammal", "Black"]
        assert rows[0]["header"] == ["Animal", "Class", "Color"]

    def test_flatten_tables_for_paper_concatenates(self):
        t1 = mk_table(
            [
                mk_cell(0, 0, "", True),
                mk_cell(0, 1, "t", True),
                mk_cell(0, 2, "df", True),
                mk_cell(1, 0, "A"),
                mk_cell(1, 1, "2.0"),
                mk_cell(1, 2, "10"),
            ],
            id_="T1",
            label="Table 1",
        )
        t2 = mk_table(
            [
                mk_cell(0, 0, "", True),
                mk_cell(0, 1, "r", True),
                mk_cell(0, 2, "n", True),
                mk_cell(1, 0, "B"),
                mk_cell(1, 1, ".5"),
                mk_cell(1, 2, "30"),
            ],
            id_="T2",
            label="Table 2",
        )
        all_rows = flatten_tables_for_paper([t1, t2])
        assert len(all_rows) == 2
        assert all_rows[0]["table_id"] == "T1"
        assert all_rows[1]["table_id"] == "T2"


# ── v2.4.93 — dash-sign CI parsing + combined est_ci column + parallel groups ─
# Source: REQUEST_10_TABLE_FLATTEN_HTTP_EXPOSURE.md (PROSECCO trial Table 2,
# 10.1371/journal.pmed.1004323). Confidence-interval cells in clinical tables
# use a dash as the lo–hi separator that collides with a negative sign, e.g.
# "(-11.2-7.5)" = (lo -11.2, hi +7.5). docpluck resolves the sign with two
# general invariants: interval monotonicity (lo < hi) and, when a point
# estimate is known, the estimate-in-interval invariant (lo <= est <= hi).


class TestParseCiCell:
    """Dash-sign CI disambiguation — the one genuinely new parsing logic."""

    @pytest.mark.parametrize(
        "cell, estimate, expected",
        [
            # Distinct range glyph (en-dash) — sign-unambiguous on its own.
            ("−10.36–8.34", None, (-10.36, 8.34)),
            ("−9.53–9.65", None, (-9.53, 9.65)),
            # Comma form (unchanged, back-compat).
            ("[0.20, 0.38]", None, (0.20, 0.38)),
            ("0.20, 0.38", None, (0.20, 0.38)),
            # Spelled-out range.
            ("0.20 to 0.38", None, (0.20, 0.38)),
            # ASCII-hyphen collision — resolved by the estimate-in-interval rule.
            ("(-11.2-7.5)", -1.83, (-11.2, 7.5)),
            ("(-8.63-10.28)", 0.82, (-8.63, 10.28)),
            ("(-3.2-18.5)", 7.7, (-3.2, 18.5)),
            # ASCII-hyphen collision with no estimate — monotonicity still picks
            # the sign-correct split (the only one with lo < hi).
            ("(-11.2-7.5)", None, (-11.2, 7.5)),
            # Combined estimate cell: the parenthesised interval is parsed.
            ("-1.83% (-11.2-7.5)", None, (-11.2, 7.5)),
        ],
    )
    def test_parse(self, cell, estimate, expected):
        lo, hi = _parse_ci_cell(cell, estimate=estimate)
        assert lo == pytest.approx(expected[0])
        assert hi == pytest.approx(expected[1])
        assert lo < hi  # monotonicity always holds

    def test_unparseable_returns_none(self):
        assert _parse_ci_cell("n/a") == (None, None)
        assert _parse_ci_cell("") == (None, None)


class TestEstCiCombinedColumn:
    """A "Risk diff. (95% CI)" column carries an estimate AND its interval in
    one cell — previously unclassified (dropped). Now parsed to est + CI."""

    def _table(self):
        cells = [
            mk_cell(0, 0, "", True),
            mk_cell(0, 1, "Risk diff. (95% CI)", True),
            mk_cell(0, 2, "P value", True),
            mk_cell(1, 0, "Resection complete"),
            mk_cell(1, 1, "−1.01% (−10.36–8.34)"),
            mk_cell(1, 2, "0.09"),
        ]
        return mk_table(cells)

    def test_fields(self):
        rows = flatten_table(self._table())
        assert len(rows) == 1
        f = rows[0]["fields"]
        assert f["est"] == pytest.approx(-1.01)
        assert f["CI_lower"] == pytest.approx(-10.36)
        assert f["CI_upper"] == pytest.approx(8.34)
        assert f["p"] == pytest.approx(0.09)

    def test_sentence(self):
        rows = flatten_table(self._table())
        s = rows[0]["sentence"]
        assert "Risk diff" in s
        assert "95% CI [-10.36, 8.34]" in s
        assert "p = 0.09" in s


class TestParallelColumnGroups:
    """ITT/PP super-header → one FlattenedRow per (row × arm), so duplicate
    roles across arms don't collide. Mirrors PROSECCO Table 2's captured row."""

    def _table(self):
        # Super-header row 0 marks the two arms; sub-header row 1 names columns.
        cells = [
            mk_cell(0, 0, "", True),
            mk_cell(0, 1, "ITT", True),
            mk_cell(0, 2, "", True),
            mk_cell(0, 3, "", True),
            mk_cell(0, 4, "PP", True),
            mk_cell(0, 5, "", True),
            mk_cell(0, 6, "", True),
            mk_cell(1, 0, "", True),
            mk_cell(1, 1, "PSA N = 98", True),
            mk_cell(1, 2, "Risk diff. (95% CI)", True),
            mk_cell(1, 3, "P value", True),
            mk_cell(1, 4, "PSA N = 94", True),
            mk_cell(1, 5, "Risk diff. (95% CI)", True),
            mk_cell(1, 6, "P value", True),
            mk_cell(2, 0, "Resection complete"),
            mk_cell(2, 1, "86 (87.8%)"),
            mk_cell(2, 2, "−1.01% (−10.36–8.34)"),
            mk_cell(2, 3, "0.09"),
            mk_cell(2, 4, "83 (88.3%)"),
            mk_cell(2, 5, "0.06% (−9.53–9.65)"),
            mk_cell(2, 6, "0.06"),
        ]
        return mk_table(cells)

    def test_emits_one_row_per_arm(self):
        rows = flatten_table(self._table())
        assert len(rows) == 2
        groups = {r["fields"].get("group") for r in rows}
        assert groups == {"ITT", "PP"}

    def test_arms_carry_distinct_stats(self):
        rows = {r["fields"]["group"]: r for r in flatten_table(self._table())}
        itt, pp = rows["ITT"], rows["PP"]
        # ITT arm
        assert itt["fields"]["est"] == pytest.approx(-1.01)
        assert itt["fields"]["p"] == pytest.approx(0.09)
        assert (itt["fields"]["CI_lower"], itt["fields"]["CI_upper"]) == pytest.approx((-10.36, 8.34))
        # PP arm — its own p (0.06), not ITT's (0.09): no duplicate-role collision
        assert pp["fields"]["est"] == pytest.approx(0.06)
        assert pp["fields"]["p"] == pytest.approx(0.06)
        assert (pp["fields"]["CI_lower"], pp["fields"]["CI_upper"]) == pytest.approx((-9.53, 9.65))

    def test_group_appears_in_sentence_and_no_fold_sentinels(self):
        rows = flatten_table(self._table())
        for r in rows:
            assert "(ITT)" in r["sentence"] or "(PP)" in r["sentence"]
            assert "\x00" not in r["sentence"]
            assert all("\x00" not in h for h in r["header"])
