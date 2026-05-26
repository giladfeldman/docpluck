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

from docpluck.tables.flatten import (
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
