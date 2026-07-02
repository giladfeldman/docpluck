"""Blank-header column-role recovery for result-table flattening (Request 11).

Some non-clinical result tables (Collabra t-/F-/Bayes-factor tables) capture the
data grid but emit BLANK stat-column headers — the header row was absorbed into
the caption region or sits a row above the data and got dropped. v2.4.94 already
flattened the clinical PROSECCO table (labeled headers); this module covers the
blank-header shapes that previously returned ``fields: {}``.

The fix recovers a column's role from two grounded signals — the *shape* of its
data tokens (CI brackets, a "df1, df2" pair, an estimate adjacent to a CI, a
p-value with a comparison operator) and the statistic *vocabulary* recovered
from the caption / footnote / all header rows — never from bare column position.

Contract tests use synthetic grids that mirror the real cleaned grids of
``10.1525/collabra.77859`` (its Replication-analyses / Study-2-results tables —
Tables 4 and 2 per the physical captions + reading gold) and
``10.1525/collabra.90203`` Tables 8/9; ``test_*_real_pdf`` exercise the public
library on the actual PDFs (rule 0d), skipping when the closed-access fixtures
aren't present.

Request: ``REQUEST_11_FLATTEN_FIELDS_NONCLINICAL_TABLES.md``.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from docpluck.extract_structured import extract_pdf_structured
from docpluck.tables.flatten import (
    _detect_packed_arms,
    _effect_type_for,
    _flatten_one_row,
    _flatten_packed_arms,
    _recover_blank_roles,
    _split_value_groups,
    _table_label_col,
    flatten_table,
)

from .conftest import pdf_available, pdf_path, requires_pdftotext


def _flatten_grid(header, body, *, label="Table", caption=None, footnote=None):
    """Drive the recovery + row-flattening on an explicit cleaned (header, body)
    — exactly what `_clean_grid` hands `flatten_table` for a non-grouped table.
    Bypasses `_clean_grid`'s header-row heuristic so a small fixture grid isn't
    mangled (the full pipeline is exercised by the real-PDF tests below)."""
    n = len(header)
    body = [(list(r) + [""] * (n - len(r)))[:n] for r in body]
    label_col = _table_label_col(body, n)
    override = _recover_blank_roles(header, body, label_col, caption, footnote)
    vocab_all = " ".join(header + [caption or "", footnote or ""])
    hint = _effect_type_for(vocab_all)
    return [
        _flatten_one_row(
            "T", 1, label, i, header, row,
            roles_override=override, effect_hint=hint,
        )
        for i, row in enumerate(body)
    ]


# ── Collabra 90203 Table 8 — [stat, p, BF01, eta²p, CI], only BF01 labelled ──


class TestT90203Table8BlankHeaders:
    """Stat column blank, p blank, BF01 labelled in-grid, effect+CI blank.
    The statistic vocabulary ("F p") survives in the caption tail."""

    HEADER = ["", "", "", "BF01", "", ""]
    BODY = [
        ["Target article", "6.75", "< .05", "N/A", ".06", "[.00, .15]"],
        ["Replication", "0.01", ".923", "11.57", ".00", "[.00, .003]"],
        ["Target article", "5.32", "< .05", "N/A", ".04", "[.00, .14]"],
        ["Replication", "0.654", ".419", "6.30", ".001", "[.000, .011]"],
    ]
    CAPTION = ("Table 8. Statistical Tests for Identifiability and "
               "Explicit Learning F p")

    def _rows(self):
        return _flatten_grid(self.HEADER, self.BODY, label="Table 8", caption=self.CAPTION)

    def test_replication_row_fields(self):
        repl = next(r for r in self._rows() if r["row_label"] == "Replication")
        f = repl["fields"]
        assert f["F"] == 0.01
        assert f["p"] == 0.923
        assert f["BF01"] == 11.57
        # The η²p header glyph is dropped by the font (no ToUnicode), so the
        # effect column is blank and no "eta" token survives in the vocab. The
        # estimate is nonetheless typed `eta2` by STRUCTURAL inference: an F-test
        # results table that reports a Bayes factor + CI and names no competing
        # effect reports η²p by APA convention (ESCIcheck DP-2026-06-25-3). The
        # value is range-guarded to η²'s domain [0, 1].
        assert "est" not in f
        assert f["eta2"] == 0.0
        assert (f["CI_lower"], f["CI_upper"]) == pytest.approx((0.0, 0.003))

    def test_eta2_typed_for_all_f_rows(self):
        # Every Replication/Target F-row's effect column types as η²p, not est.
        for r in self._rows():
            f = r["fields"]
            if "F" in f or "BF01" in f:
                assert "est" not in f, f"row {r['row_label']!r} left a generic est"

    def test_na_bf01_not_emitted(self):
        tgt = next(r for r in self._rows() if r["row_label"] == "Target article")
        # "N/A" in the BF01 cell must not produce a bogus numeric field.
        assert "BF01" not in tgt["fields"]
        assert tgt["fields"]["F"] == 6.75
        assert tgt["fields"]["p"] == 0.05
        assert tgt["fields"]["p_op"] == "<"


# ── Collabra 90203 Table 9 — all-blank headers, df pair in one cell ──────────


class TestT90203Table9DfPair:
    """All stat headers blank; df reported as a "1, 114" pair in one cell;
    full header run ("df F p BF01 95% CI") recovered from the caption."""

    HEADER = ["", "", "", "", "", "", ""]
    BODY = [
        ["Replication", "1, 114", "0.01", ".940", "11.56", ".00", "[.00, .002]"],
        ["Target article", "1, 114", "0.24", ".63", "N/A", ".00", "[.00, .05]"],
        ["Replication", "2, 998", "0.792", ".453", "44.85", ".002", "[.00, .009]"],
    ]
    CAPTION = ("Table 9. Aggregated Feelings: Statistical Tests for "
               "Identifiability and Explicit Learning df F p BF01 95% CI")

    def _rows(self):
        return _flatten_grid(self.HEADER, self.BODY, label="Table 9", caption=self.CAPTION)

    def test_df_pair_split(self):
        repl = next(r for r in self._rows() if r["row_label"] == "Replication")
        f = repl["fields"]
        assert f["df1"] == 1
        assert f["df2"] == 114
        assert f["F"] == 0.01
        assert f["p"] == 0.94
        assert f["BF01"] == 11.56
        assert (f["CI_lower"], f["CI_upper"]) == pytest.approx((0.0, 0.002))

    def test_sentence_uses_f_with_df(self):
        repl = next(r for r in self._rows() if r["row_label"] == "Replication")
        assert "F(1, 114) = 0.01" in repl["sentence"]
        assert "BF01 = 11.56" in repl["sentence"]


# ── Collabra 77859 Table 4 — blank t/p/df cols + "d or dz [95% CI]" header ───
# (Synthetic grid mirroring the "Study 4: Replication analyses" table. That
# table is **Table 4** per the physical caption + reading gold; the class name
# keeps the legacy "Table5" spelling only to avoid churn — the grid it mirrors is
# the same Separate/Joint-Evaluation table whose real-PDF row the
# ``test_collabra_77859_table4_separate_eval_real_pdf`` test now verifies.)


class TestT77859Table5DorDz:
    """Replication arm columns (t, p, df, d[CI]) are cleanly separated but
    blank-headed; the "d or dz [95%CI]" header sits in a non-final header row.
    Effect should be typed `d` (Cohen's d evidence) — Request 11 acceptance #1.
    HEADER below is the FINAL cleaned header row; the effect-type vocabulary
    (`d or dz`) is fed via caption (mirroring the all-header-rows vocab)."""

    HEADER = ["", "Mean", "", "Mean", "", "", "", ""]
    BODY = [
        ["Separate", "$23.25 $32.69 3.91", "< .001", "$23.96 $33.70",
         "6.23", "< .001", "257", "0.76 [.50, 1.02]"],
        ["Joint", "$32.03 $29.70 2.15", ".039", "$31.67 $30.35",
         "1.26", ".210", "133", "0.11 [-.06, .28]"],
    ]
    CAPTION = "Table 5. d or dz [95% CI]"  # effect-type vocab (non-final header row)

    def _rows(self):
        return _flatten_grid(self.HEADER, self.BODY, label="Table 5", caption=self.CAPTION)

    def test_separate_row_acceptance_1(self):
        sep = next(r for r in self._rows() if r["row_label"] == "Separate")
        f = sep["fields"]
        assert f["t"] == 6.23
        assert f["df"] == 257
        assert f["p"] == 0.001
        assert f["p_op"] == "<"
        assert f["d"] == 0.76
        assert (f["CI_lower"], f["CI_upper"]) == pytest.approx((0.50, 1.02))

    def test_joint_row(self):
        joint = next(r for r in self._rows() if r["row_label"] == "Joint")
        f = joint["fields"]
        assert f["t"] == 1.26
        assert f["df"] == 133
        assert f["d"] == 0.11
        assert (f["CI_lower"], f["CI_upper"]) == pytest.approx((-0.06, 0.28))

    def test_sentence(self):
        sep = next(r for r in self._rows() if r["row_label"] == "Separate")
        assert "t(257) = 6.23" in sep["sentence"]
        assert "d = 0.76" in sep["sentence"]
        assert "95% CI [" in sep["sentence"]
        assert "[[" not in sep["sentence"]  # no doubled brackets


# ── Collabra 77859 Table 2 — parallel arms PACKED into single cells ──────────
# (Synthetic grid mirroring the "Study 2 results" table — **Table 2** per the
# physical caption + reading gold. The class name keeps the legacy "Table3"
# spelling only to avoid churn; the real-PDF row is now verified by
# ``test_collabra_77859_table2_packed_arms_real_pdf``.)

_MS = "\x00BR\x00"  # the _MERGE_SEPARATOR sentinel, as it appears in a folded cell


class TestT77859Table3PackedArms:
    """This "Study 2 results" grid packs both evaluation arms (Separate, Joint)
    into single cells: the arm-label column reads ``"Separate<sep>Joint"`` and
    every data cell holds two space-joined values
    (``".07 [-.17,.31] .08 [-.09, .25]"``). Request 11 acceptance #1 requires
    these split into one record per arm carrying d + CI. Grid mirrors the real
    cleaned grid (fold sentinels included)."""

    HEADER = ["", "", "M (SD)", "M (SD)", "", "", "", "d or dz [95%CI]"]
    BODY = [
        ["Attractive", f"Separate{_MS}Joint", "4.76 (1.14) 4.50 (1.17)",
         "4.84 (1.04) 4.61 (1.19)", "0.60 0.95", ".551 .344", "260.54 131",
         ".07 [-.17,.31] .08 [-.09, .25]"],
        ["Affect", f"Separate{_MS}Joint", "4.62 (1.23) 4.52 (1.12)",
         "4.80 (1.06) 4.65 (1.08)", "1.31 1.27", ".192 .208", "257.69 131",
         ".16 [-.08, .40] .11 [-.06, .28]"],
    ]

    def _rows(self):
        packed = _detect_packed_arms(self.HEADER, self.BODY)
        assert packed is not None, "packed-arm signature not detected"
        return _flatten_packed_arms(
            "T", 1, "Table 3", self.HEADER, self.BODY, packed,
            caption="Table 3. Study 4: Dish sets", footnote=None,
            vocab_all=" ".join(self.HEADER), effect_hint=None,
            n_cols=len(self.HEADER),
        )

    def test_detects_two_arms(self):
        packed = _detect_packed_arms(self.HEADER, self.BODY)
        assert packed is not None
        arm_col, labels = packed
        assert arm_col == 1
        assert labels == ["Separate", "Joint"]

    def test_both_arms_emitted_per_row(self):
        rows = self._rows()
        attr = [r for r in rows if r["row_label"].startswith("Attractive")]
        assert len(attr) == 2
        assert {r["fields"].get("group") for r in attr} == {"Separate", "Joint"}

    def test_separate_arm_d_and_ci(self):  # acceptance #1: d + CI per arm
        sep = next(
            r for r in self._rows()
            if r["row_label"].startswith("Attractive")
            and r["fields"].get("group") == "Separate"
        )
        f = sep["fields"]
        assert f["d"] == 0.07
        assert (f["CI_lower"], f["CI_upper"]) == pytest.approx((-0.17, 0.31))

    def test_joint_arm_d_and_ci(self):
        joint = next(
            r for r in self._rows()
            if r["row_label"].startswith("Attractive")
            and r["fields"].get("group") == "Joint"
        )
        f = joint["fields"]
        assert f["d"] == 0.08
        assert (f["CI_lower"], f["CI_upper"]) == pytest.approx((-0.09, 0.25))

    def test_separate_arm_p_and_df(self):  # DP-2: p + Welch df must be recovered
        sep = next(
            r for r in self._rows()
            if r["row_label"].startswith("Attractive")
            and r["fields"].get("group") == "Separate"
        )
        f = sep["fields"]
        # p (".551", no comparison op) and a Welch-corrected df ("260.54", a
        # decimal) sat in blank-header columns; both previously dropped (DP-2).
        assert f["p"] == pytest.approx(0.551)
        assert f["df"] == pytest.approx(260.54)

    def test_joint_arm_p_and_integer_df(self):  # DP-2: integer df recovered too
        joint = next(
            r for r in self._rows()
            if r["row_label"].startswith("Attractive")
            and r["fields"].get("group") == "Joint"
        )
        f = joint["fields"]
        assert f["p"] == pytest.approx(0.344)
        # Whole-number df stays an int (not 131.0).
        assert f["df"] == 131 and isinstance(f["df"], int)

    def test_packed_values_split_not_concatenated(self):  # acceptance #3
        sep = next(
            r for r in self._rows()
            if r["row_label"].startswith("Attractive")
            and r["fields"].get("group") == "Separate"
        )
        # The Separate sentence/fields must NOT contain the Joint arm's value.
        assert ".08" not in sep["sentence"]
        assert "-.09" not in sep["sentence"] and "-0.09" not in sep["sentence"]
        assert "[[" not in sep["sentence"]  # no doubled brackets


class TestSplitValueGroups:
    """`_split_value_groups` returns exactly k groups or None (never a partial /
    mis-aligned split)."""

    def test_d_ci_pairs(self):
        assert _split_value_groups(".07 [-.17,.31] .08 [-.09, .25]", 2) == [
            ".07 [-.17,.31]", ".08 [-.09, .25]"
        ]

    def test_mean_sd_pairs(self):
        assert _split_value_groups("4.76 (1.14) 4.50 (1.17)", 2) == [
            "4.76 (1.14)", "4.50 (1.17)"
        ]

    def test_bare_numbers(self):
        assert _split_value_groups("0.60 0.95", 2) == ["0.60", "0.95"]
        assert _split_value_groups("260.54 131", 2) == ["260.54", "131"]

    def test_wrong_count_returns_none(self):
        assert _split_value_groups("0.60 0.95", 3) is None
        assert _split_value_groups("0.60", 2) is None

    def test_non_numeric_returns_none(self):
        assert _split_value_groups("Separate Joint", 2) is None
        assert _split_value_groups("", 2) is None


def test_packed_arms_does_not_fire_on_single_arm_table():
    """A normal single-arm table (no repeated multi-token label column, no
    cleanly k-splittable data cells) must NOT trigger the packed-arm path —
    keeps every ordinary table byte-identical."""
    header = ["Outcome", "t", "p", "d"]
    body = [
        ["Recall", "2.10", ".038", "0.42"],
        ["Recognition", "1.55", ".121", "0.31"],
    ]
    assert _detect_packed_arms(header, body) is None


# ── Anti-fabrication guard — no positional invention ─────────────────────────


class TestNoFabrication:
    """A blank-header table with NO recoverable vocabulary and ambiguous
    (operator-less) numeric columns must NOT invent stat roles."""

    def test_blank_headers_no_vocab_stays_empty(self):
        header = ["", "", ""]
        body = [
            ["Row A", "0.50", "0.30"],
            ["Row B", "0.60", "0.40"],
            ["Row C", "0.55", "0.35"],
        ]
        rows = _flatten_grid(header, body, label="Table X", caption="Table X.")
        for r in rows:
            assert all(
                k not in r["fields"] for k in ("t", "F", "p", "r", "BF01", "d", "eta2")
            )

    def test_no_grounding_signal_does_not_fire(self):
        # df-pair + CI shapes are present, but with NO grounding signal (no
        # caption header-run, no named effect size) the recovery must NOT fire —
        # we don't second-guess an ungrounded blank table (the gate).
        header = ["", "", ""]
        body = [["A", "1, 50", "[0.10, 0.30]"], ["B", "1, 48", "[0.05, 0.25]"]]
        rows = _flatten_grid(header, body, label="T", caption="T.")
        assert all(r["fields"] in ({}, None) for r in rows)

    def test_shapes_recover_when_grounded_by_caption_run(self):
        # Same shapes, but now the caption carries a header run ("df F p 95% CI")
        # — the header-stripped signature — so df-pair + CI recover.
        header = ["", "", "", ""]
        body = [["A", "1, 50", "2.1", "[0.10, 0.30]"], ["B", "1, 48", "3.4", "[0.05, 0.25]"]]
        rows = _flatten_grid(header, body, label="T", caption="Table. df F 95% CI")
        f = rows[0]["fields"]
        assert f["df1"] == 1 and f["df2"] == 50
        assert (f["CI_lower"], f["CI_upper"]) == pytest.approx((0.10, 0.30))


# ── Real-PDF regression (rule 0d) ────────────────────────────────────────────


_AR = "articlerepo"

# These end-to-end tests assert EXACT statistics from a live Camelot extraction.
# Camelot's table extraction is non-deterministic under heavy parallel load
# (the project's baseline gate runs `-n10`; see test_benchmark_docx_html.py) —
# the same PDF can yield a degraded cell grid when 10 workers extract at once,
# making value-exact assertions flake. The flatten LOGIC is fully covered by the
# synthetic-grid contract tests above (which run under `-n10`); these run
# serially, where Camelot is deterministic. Skip under an xdist worker so the
# parallel gate doesn't false-fail; `pytest tests/ -q` (the canonical
# /docpluck-qa command) runs them for real.
_skip_under_xdist = pytest.mark.skipif(
    bool(os.environ.get("PYTEST_XDIST_WORKER")),
    reason="real-PDF Camelot value-exact extraction is non-deterministic under "
    "parallel xdist load; runs serially (synthetic-grid tests cover the logic under -n10)",
)


@requires_pdftotext
@_skip_under_xdist
@pytest.mark.skipif(
    not pdf_available(_AR, "10.1525__collabra.77859.pdf"),
    reason="closed-access fixture not present in the article repository",
)
def test_collabra_77859_table4_separate_eval_real_pdf():
    """The Separate-Evaluation t/df/d row of collabra.77859's "Study 4:
    Replication analyses" table flattens with every blank-header stat field.

    This row lives in **Table 4** ("Table 4. Study 4: Replication analyses" —
    confirmed by the physical PDF caption AND the article-finder `reading` gold,
    where it is gold Table 4 line "Separate Evaluation … 6.23 <.001 257 0.76
    [.50, 1.02]"). An earlier revision of this test asserted it against "Table 5"
    because the pre-v2.4.99 caption pairing mislabeled the page-7/8 grids; the
    region-driven capture (v2.4.99) + the reading-order pairing tie-break now
    label it correctly, so the assertion targets Table 4 (gold-correct). Table 5
    is the "Comparison of original and replication effects" grid (Less is better /
    More is better), a different table.
    """
    b = Path(pdf_path(_AR, "10.1525__collabra.77859.pdf")).read_bytes()
    r = extract_pdf_structured(b)
    t4 = next((t for t in r["tables"] if t.get("label") == "Table 4"), None)
    assert t4 is not None, "Table 4 not extracted from collabra.77859"
    rows = flatten_table(t4)
    sep = next((x for x in rows if x["row_label"].startswith("Separate")), None)
    assert sep is not None, "Separate-evaluation row missing"
    f = sep["fields"]
    assert f["t"] == 6.23
    assert f["df"] == 257
    assert f["d"] == 0.76
    assert (f["CI_lower"], f["CI_upper"]) == pytest.approx((0.50, 1.02))
    assert f["p"] == 0.001 and f["p_op"] == "<"


@requires_pdftotext
@_skip_under_xdist
@pytest.mark.skipif(
    not pdf_available(_AR, "10.1525__collabra.77859.pdf"),
    reason="closed-access fixture not present in the article repository",
)
def test_collabra_77859_table2_packed_arms_real_pdf():
    """Acceptance #1: the packed Separate/Joint arms of the "Study 2 results"
    table split into one record per arm, each carrying d + sign-correct CI. DP-2
    extends this: the blank-header p and (Welch) df columns must also be typed
    into `fields`.

    These Attractive/Affect rows live in **Table 2** ("Table 2. Study 2 results"
    — confirmed by the physical PDF caption AND the article-finder `reading` gold,
    where they are gold Table 2). An earlier revision asserted them against
    "Table 3" because the pre-v2.4.99 same-page caption pairing swapped the two
    page-7 grids (Study-2-results ↔ Dish-sets); the reading-order pairing
    tie-break now labels them correctly, so the assertion targets Table 2
    (gold-correct). Table 3 is the "Study 4: Dish sets" categorical grid.
    """
    b = Path(pdf_path(_AR, "10.1525__collabra.77859.pdf")).read_bytes()
    r = extract_pdf_structured(b)
    t2 = next((t for t in r["tables"] if t.get("label") == "Table 2"), None)
    assert t2 is not None, "Table 2 not extracted from collabra.77859"
    rows = flatten_table(t2)
    attr = [x for x in rows if x["row_label"].startswith("Attractive")]
    assert len(attr) == 2, "Attractive row should split into Separate + Joint arms"
    by_arm = {x["fields"].get("group"): x["fields"] for x in attr}
    assert set(by_arm) == {"Separate", "Joint"}
    assert by_arm["Separate"]["d"] == 0.07
    assert (by_arm["Separate"]["CI_lower"], by_arm["Separate"]["CI_upper"]) == pytest.approx((-0.17, 0.31))
    assert by_arm["Joint"]["d"] == 0.08
    assert (by_arm["Joint"]["CI_lower"], by_arm["Joint"]["CI_upper"]) == pytest.approx((-0.09, 0.25))
    # DP-2: p (operator-less ".551"/".344") and df (Welch "260.54" / integer
    # "131") were dropped before the Pass 4.5 positional recovery.
    assert by_arm["Separate"]["p"] == pytest.approx(0.551)
    assert by_arm["Separate"]["df"] == pytest.approx(260.54)
    assert by_arm["Joint"]["p"] == pytest.approx(0.344)
    assert by_arm["Joint"]["df"] == 131
    # Every CI is monotone (sign-correct).
    for f in by_arm.values():
        assert f["CI_lower"] <= f["CI_upper"]


@requires_pdftotext
@_skip_under_xdist
@pytest.mark.skipif(
    not pdf_available(_AR, "10.1525__collabra.90203.pdf"),
    reason="closed-access fixture not present in the article repository",
)
def test_collabra_90203_tables_8_9_real_pdf():
    b = Path(pdf_path(_AR, "10.1525__collabra.90203.pdf")).read_bytes()
    r = extract_pdf_structured(b)
    by_label = {t.get("label"): t for t in r["tables"]}

    # Table 8 — a Replication row with F/p/BF01/est/CI.
    t8 = flatten_table(by_label["Table 8"])
    bf_rows = [x for x in t8 if "BF01" in x["fields"]]
    assert bf_rows, "no BF01 recovered in Table 8"
    sample = bf_rows[0]["fields"]
    assert "F" in sample and "p" in sample
    assert "CI_lower" in sample and "CI_upper" in sample
    assert sample["CI_lower"] <= sample["CI_upper"]  # monotone CI

    # Table 9 — df reported as a "df1, df2" pair, F-with-df sentence.
    t9 = flatten_table(by_label["Table 9"])
    df_rows = [x for x in t9 if "df1" in x["fields"] and "df2" in x["fields"]]
    assert df_rows, "no df-pair recovered in Table 9"
    assert any("BF01" in x["fields"] for x in t9), "no BF01 recovered in Table 9"


@requires_pdftotext
@_skip_under_xdist
@pytest.mark.skipif(
    not pdf_available(_AR, "10.1371__journal.pmed.1004323.pdf"),
    reason="closed-access fixture not present in the article repository",
)
def test_prosecco_table2_unchanged_real_pdf():
    """Acceptance #4: the 6 PROSECCO Table 2 stat rows are unchanged by the
    blank-header recovery (their headers are labelled, so recovery is a no-op)."""
    b = Path(pdf_path(_AR, "10.1371__journal.pmed.1004323.pdf")).read_bytes()
    r = extract_pdf_structured(b)
    t2 = next(t for t in r["tables"] if t.get("label") == "Table 2")
    rows = flatten_table(t2)
    stat_rows = [x for x in rows if "est" in x["fields"]]
    assert len(stat_rows) == 6, f"expected 6 PROSECCO stat rows, got {len(stat_rows)}"
    itt = next(x for x in stat_rows if x["fields"].get("group") == "ITT" and "p" in x["fields"])
    assert itt["fields"]["est"] == pytest.approx(-1.01)
    assert (itt["fields"]["CI_lower"], itt["fields"]["CI_upper"]) == pytest.approx((-10.36, 8.34))
    # The dash-ambiguous adjusted-ITT CI stays sign-correct.
    adj = next(
        x for x in stat_rows
        if x["fields"].get("group") == "ITT" and x["fields"]["est"] == pytest.approx(-1.83)
    )
    assert (adj["fields"]["CI_lower"], adj["fields"]["CI_upper"]) == pytest.approx((-11.2, 7.5))
