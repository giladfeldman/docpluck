"""Super-header alignment + first-data-row recovery for parallel-arm tables (DP-2/DP-5).

Two coupled defects in the flatten pipeline, both surfaced by the ESCImate
iterate cycle (a consumer's 2026-06-21 report, DP-5):

1. **First data row swallowed as a header row.** `cell_cleaning._is_header_like_row`
   counted a cell as "data" only via the bare ``_NUMERIC_CELL_RE`` — which misses
   APA leading-dot decimals (".34"), bracketed CIs ("[0.53, 0.72]"), operator-
   prefixed p ("< .001") and the "N/A" filler. So in a two-header-row table the
   FIRST real data row read as ~1/7 numeric and was mis-classified as a third
   header row, silently dropping it (collabra.90203 Table 10 lost the
   Identifiable/Explicit-learning correlation). The broader `_DATA_VALUE_CELL_RE`
   recognizes those shapes (the bracket branch requires a digit and NO letters
   inside so a real "[95% CI]" header cell stays a header).

2. **Centered super-header mis-binned the arms.** camelot stream loses colspan, so
   a *centered* spanning super-label ("Target article" / "Replication";
   "Original" / "Replication") lands at its visual-center column, not its arm's
   first column. `_detect_column_groups` trusted the sentinel column as the arm
   boundary and split arms with the values SWAPPED (xiao_2021 T4 Original↔Replication
   F) or a stat column pushed into the label region (collabra.90203 T10). The fix
   re-derives arm boundaries from equal-width blocks of the data region, each of
   which must contain exactly one super-label; left-aligned super-headers (already
   at the block start) are unaffected.

   **Superseded where the page states the span (v2.4.146).** The equal-width cut
   is a guess, and it was wrong on collabra.90203 T10 itself: the page prints
   2 + 4 columns, not 3 + 3, so the Replication's `n` went to the Target article.
   `tables/arm_spans.py` now reads each span from the page's rules and records it
   as the label cell's `colspan`; `_detect_column_groups(header, spans)` binds by
   it. The equal-width cut remains only for tables whose page draws no rules.

Real-PDF (rule 0d) + structural-signature general fix (rule 16). PDFs are
closed-access (`feedback_no_pdfs_in_repo`); each test skips when the article
repository fixture is absent. Camelot under parallel xdist load is non-
deterministic, so the real-PDF tests skip there and run serially (the canonical
`/docpluck-qa` `pytest tests/ -q` run is the real gate).
"""
from __future__ import annotations

from pathlib import Path

import pytest

from docpluck.extract_structured import extract_pdf_structured
from docpluck.tables.cell_cleaning import _MERGE_SEPARATOR, _is_header_like_row
from docpluck.tables.flatten import _detect_column_groups, flatten_table

from .conftest import pdf_available, pdf_path, requires_pdftotext

_AR = "articlerepo"


# ── Contract: _is_header_like_row recognizes APA data-value cells ─────────────


class TestHeaderLikeRowDataRecognition:
    """A real data row of APA-formatted statistics must NOT read as a header."""

    def test_apa_correlation_data_row_is_not_header(self):
        # collabra.90203 Table 10 first data row: leading-dot r, N/A, integer n,
        # leading-dot r, bracketed CI, operator-prefixed p.
        row = ["Identifiable/ Explicit learning", ".34", "N/A", "170", ".63",
               "[0.53, 0.72]", "< .001"]
        assert _is_header_like_row(row) is False

    def test_real_subheader_still_reads_as_header(self):
        # The genuine column sub-header stays header-like (label words, no values).
        assert _is_header_like_row(["Conditions", "r", "p", "n", "r", "95% CI", "p"]) is True

    def test_ci_label_cell_does_not_count_as_data(self):
        # A header cell "[95% CI]" (letters inside the brackets) must NOT be
        # mistaken for a numeric interval — it is a header.
        assert _is_header_like_row(["Outcome", "Estimate", "[95% CI]"]) is True


# ── Contract: _detect_column_groups block-aligns a centered super-header ──────


class TestSuperHeaderBlockAlignment:
    """A centered super-label (folded mid-span) is re-aligned to its arm block."""

    def test_centered_superheader_blocks_not_sentinel_positions(self):
        ms = _MERGE_SEPARATOR
        # "Target article" centered over cols 1-3, "Replication" over cols 4-6;
        # the fold drops the sentinel at cols 2 and 5 (mid-span).
        header = ["Conditions", "r", f"Target article{ms}p", "n", "r",
                  f"Replication{ms}95% CI", "p"]
        out = _detect_column_groups(header)
        assert out is not None
        label_cols, groups = out
        assert label_cols == [0]
        assert [g[0] for g in groups] == ["Target article", "Replication"]
        # Arm blocks start at the true arm-start columns (1 and 4), NOT the
        # sentinel columns (2 and 5).
        assert groups[0][1] == [1, 2, 3]
        assert groups[1][1] == [4, 5, 6]

    def test_printed_spans_override_the_equal_width_guess(self):
        # collabra.90203 T10 after `arm_spans` has read the page: the labels sit
        # at their arm-start columns and carry the printed colspan (2 + 4).
        ms = _MERGE_SEPARATOR
        header = ["Conditions", f"Target article{ms}r", "p", f"Replication{ms}n",
                  "r", "95% CI", "p"]
        label_cols, groups = _detect_column_groups(header, {1: 2, 3: 4})
        assert label_cols == [0]
        assert groups == [("Target article", [1, 2]), ("Replication", [3, 4, 5, 6])]

    def test_printed_spans_beat_an_equal_width_split_that_fits(self):
        # Starts at 1 and 5 of a 6-column data region DO fit the 3 + 3 guess
        # (1 in [1-3], 5 in [4-6]); the printed spans (4 + 2) must still win.
        ms = _MERGE_SEPARATOR
        header = ["Cond", f"A{ms}M", "SD", "n", "t", f"B{ms}M", "SD"]
        _, guessed = _detect_column_groups(header)
        assert [g[1] for g in guessed] == [[1, 2, 3], [4, 5, 6]]
        _, groups = _detect_column_groups(header, {1: 4, 5: 2})
        assert [g[1] for g in groups] == [[1, 2, 3, 4], [5, 6]]

    def test_stat_column_under_no_arm_is_its_own_record(self):
        # 10.1001/jamanetworkopen.2024.18729 p6 Table 3: `P value` is printed
        # beside the two follow-up periods, under neither label.
        ms = _MERGE_SEPARATOR
        header = ["Cause of death", f"Follow-up period 1a{ms}Nondaily use",
                  "Daily use", f"Follow-up period 2a{ms}Nondaily use",
                  "Daily use", "P value"]
        label_cols, groups = _detect_column_groups(header, {1: 2, 3: 2})
        assert label_cols == [0]
        assert groups == [("Follow-up period 1a", [1, 2]),
                          ("Follow-up period 2a", [3, 4]), ("", [5])]
        rows = flatten_table({
            "id": "t", "page": 6, "label": "Table 3", "cells": [
                {"r": r, "c": c, "rowspan": 1, "colspan": 2 if (r == 0 and c) else 1,
                 "text": t, "is_header": r == 0, "bbox": (0, 0, 0, 0)}
                for r, row in enumerate([
                    {1: "Follow-up period 1a", 3: "Follow-up period 2a"},
                    {0: "Cause of death", 1: "Nondaily use", 2: "Daily use",
                     3: "Nondaily use", 4: "Daily use", 5: "P value"},
                    {0: "Age and sex-adjusted HR (95% CI)", 1: "1.06 (1.02-1.09)",
                     2: "0.99 (0.97-1.01)", 3: "0.92 (0.86-0.99)",
                     4: "0.99 (0.95-1.04)", 5: "<.001"},
                ]) for c, t in row.items()
            ],
        })
        p_rows = [x for x in rows if "p" in x["fields"]]
        assert len(p_rows) == 1 and "group" not in p_rows[0]["fields"]

    def test_wrapped_subheader_inside_a_span_is_not_an_arm(self):
        # 10.1001/jamanetworkopen.2023.35237 p6 Table 2: "Age 1 y" spans
        # "Low-cash gift / group (n = 547)" and "High-cash gift / group (n = 382)";
        # the wrapped sub-header folds a sentinel into BOTH columns. Without the
        # printed spans the high-cash columns became a separate "High-cash gift"
        # arm with no age at all.
        ms = _MERGE_SEPARATOR
        header = ["Outcome",
                  f"Age 1 y{ms}Low-cash gift{ms}group (n = 547)", f"High-cash gift{ms}group (n = 382)",
                  f"Age 2 y{ms}Low-cash gift{ms}group (n = 543)", f"High-cash gift{ms}group (n = 376)"]
        _, guessed = _detect_column_groups(header)
        assert "High-cash gift" in [g[0] for g in guessed]
        label_cols, groups = _detect_column_groups(header, {1: 2, 3: 2})
        assert label_cols == [0]
        assert groups == [("Age 1 y", [1, 2]), ("Age 2 y", [3, 4])]

    def test_partial_spans_fall_back(self):
        # Spans for only some labels are not used (all or nothing).
        ms = _MERGE_SEPARATOR
        header = ["Conditions", "r", f"Target article{ms}p", "n", "r",
                  f"Replication{ms}95% CI", "p"]
        assert _detect_column_groups(header, {2: 2}) == _detect_column_groups(header)

    def test_left_aligned_superheader_unchanged(self):
        ms = _MERGE_SEPARATOR
        # Super-label already at the arm-start column — grouping is identical to
        # the pre-existing sentinel-boundary behavior (no regression).
        header = ["Outcome", f"Study 1{ms}M", "SD", f"Study 2{ms}M", "SD"]
        out = _detect_column_groups(header)
        assert out is not None
        label_cols, groups = out
        assert label_cols == [0]
        assert groups[0][1] == [1, 2] and groups[1][1] == [3, 4]


# ── Real-PDF: collabra.90203 Table 10 — all 6 conditions, correct arms (DP-5) ─


@requires_pdftotext
@pytest.mark.skipif(
    not pdf_available(_AR, "10.1525__collabra.90203.pdf"),
    reason="closed-access fixture not present in the article repository",
)
def test_collabra_90203_table10_all_six_conditions_real_pdf():
    b = Path(pdf_path(_AR, "10.1525__collabra.90203.pdf")).read_bytes()
    r = extract_pdf_structured(b)
    t10 = next((t for t in r["tables"] if t.get("label") == "Table 10"), None)
    assert t10 is not None, "Table 10 not extracted from collabra.90203"
    rows = flatten_table(t10)
    labels = {x["row_label"].split("/")[0].strip() for x in rows}
    # All six condition rows present — the Identifiable/Explicit-learning row was
    # dropped at HEAD (read as a third header row).
    assert {"Identifiable", "Statistical", "Joint"} <= labels
    ident_expl = [
        x for x in rows
        if x["row_label"].startswith("Identifiable/ Explicit")
    ]
    assert ident_expl, "the previously-dropped Identifiable/Explicit-learning row is missing"
    # Its Replication arm carries r = .63, 95% CI [0.53, 0.72] (DP-5's expected
    # values) AND n = 170; the Target-article arm carries r = .34 and NO n.
    #
    # THIS TEST USED TO ASSERT `targ["n"] == 170`, i.e. it pinned the defect.
    # The page (p14, rasterized) prints `Target article` over `r p` only and
    # `Replication` over `n r 95% CI p`, with a vertical rule between `p` and
    # `n`; the six n sum to 1004, the replication's N. The equal-width arm guess
    # made 2 + 4 columns into 3 + 3, and a green run of this test was then cited
    # to close the consumer's report as a false positive. A test
    # that encodes a defect passing is not evidence the defect is absent.
    repl = next((x["fields"] for x in ident_expl
                 if x["fields"].get("group") == "Replication"), None)
    targ = next((x["fields"] for x in ident_expl
                 if x["fields"].get("group") == "Target article"), None)
    assert repl is not None and targ is not None, "arms not split into Target/Replication"
    assert repl["r"] == pytest.approx(0.63)
    assert (repl["CI_lower"], repl["CI_upper"]) == pytest.approx((0.53, 0.72))
    assert repl["n"] == 170
    assert targ["r"] == pytest.approx(0.34)
    assert "n" not in targ
    # Every row: n goes to the Replication arm, never to the Target article.
    by = {}
    for x in rows:
        by.setdefault(x["fields"].get("group"), []).append(x)
    assert sorted(x["fields"].get("n") for x in by["Replication"]) == [
        159, 161, 165, 170, 173, 176
    ]
    assert not any("n" in x["fields"] for x in by.get("Target article", []))
    # No df is fabricated for the Target article from the Replication's n.
    assert not any("r(" in x["sentence"] for x in by.get("Target article", []))
    # The span is recorded on the super-label cells, as the page prints it.
    spans = {c["text"]: (c["c"], c["colspan"]) for c in t10["cells"] if c["r"] == 0}
    assert spans == {"Target article": (1, 2), "Replication": (3, 4)}


# ── Real-PDF: xiao_2021 Table 4 — Original/Replication F not swapped (DP-5) ───


@requires_pdftotext
@pytest.mark.skipif(
    not pdf_available(_AR, "10.1080__23743603.2021.1878340.pdf"),
    reason="closed-access fixture not present in the article repository",
)
def test_xiao_2021_table4_arms_not_swapped_real_pdf():
    b = Path(pdf_path(_AR, "10.1080__23743603.2021.1878340.pdf")).read_bytes()
    r = extract_pdf_structured(b)
    t4 = next((t for t in r["tables"] if t.get("label") == "Table 4"), None)
    assert t4 is not None, "Table 4 not extracted from xiao_2021"
    rows = flatten_table(t4)
    shoes = [x for x in rows if x["row_label"].startswith("Running shoes")]
    by_arm = {x["fields"].get("group"): x["fields"] for x in shoes}
    assert set(by_arm) == {"Original", "Replication"}, "arms not split"
    # The centered super-header had Original F and Replication F SWAPPED at HEAD.
    # Original F = 18.36 (large, significant), Replication F = 0.14 (null).
    assert by_arm["Original"]["F"] == pytest.approx(18.36)
    assert by_arm["Replication"]["F"] == pytest.approx(0.14)
    # p16 prints one underline rule per arm (x 130.8-245.9 and 245.9-354.1);
    # the Interpretation column sits under neither and stays shared.
    spans = {c["text"]: (c["c"], c["colspan"]) for c in t4["cells"] if c["r"] == 0}
    assert spans == {"Original": (1, 2), "Replication": (3, 2)}


# ── Real-PDF: collabra.90203 Table 8 — a heading is not glued onto a value ────


@requires_pdftotext
@_skip_under_xdist
@pytest.mark.skipif(
    not pdf_available(_AR, "10.1525__collabra.90203.pdf"),
    reason="closed-access fixture not present in the article repository",
)
def test_collabra_90203_table8_h1b_keeps_its_f_real_pdf():
    """p12 prints `Replication | 3.91 | .020 | 1.77 | .01 | [.00, .021]` for H1b,
    then the section heading `H2: Interaction: Identifiability and Explicit
    Learning`. The heading landed in column 1 and was merged as a 'wrapped line'
    onto `3.91`, so F was lost and the heading vanished as a row."""
    b = Path(pdf_path(_AR, "10.1525__collabra.90203.pdf")).read_bytes()
    r = extract_pdf_structured(b)
    t8 = next(t for t in r["tables"] if t.get("label") == "Table 8")
    rows = flatten_table(t8)
    h1b = next(x for x in rows if x["fields"].get("BF01") == pytest.approx(1.77))
    assert h1b["fields"]["F"] == pytest.approx(3.91)
    assert any(x["row_label"].startswith("H2: Interaction") for x in rows)
    assert "3.91<br>" not in (t8.get("html") or "")
