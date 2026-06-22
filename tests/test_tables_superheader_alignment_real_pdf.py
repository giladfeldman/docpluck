"""Super-header alignment + first-data-row recovery for parallel-arm tables (DP-2/DP-5).

Two coupled defects in the flatten pipeline, both surfaced by the ESCImate
iterate handoff (`ESCIcheckapp/docs/DOCPLUCK_HANDOFF_2026-06-21.md` DP-5):

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

Real-PDF (rule 0d) + structural-signature general fix (rule 16). PDFs are
closed-access (`feedback_no_pdfs_in_repo`); each test skips when the article
repository fixture is absent. Camelot under parallel xdist load is non-
deterministic, so the real-PDF tests skip there and run serially (the canonical
`/docpluck-qa` `pytest tests/ -q` run is the real gate).
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from docpluck.extract_structured import extract_pdf_structured
from docpluck.tables.cell_cleaning import _MERGE_SEPARATOR, _is_header_like_row
from docpluck.tables.flatten import _detect_column_groups, flatten_table

from .conftest import pdf_available, pdf_path, requires_pdftotext

_AR = "articlerepo"
_skip_under_xdist = pytest.mark.skipif(
    bool(os.environ.get("PYTEST_XDIST_WORKER")),
    reason="real-PDF Camelot extraction is non-deterministic under parallel xdist; "
    "runs serially (the serial run is the real gate)",
)


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
@_skip_under_xdist
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
    # values); the Target-article arm carries r = .34, n = 170 — NOT swapped.
    repl = next((x["fields"] for x in ident_expl
                 if x["fields"].get("group") == "Replication"), None)
    targ = next((x["fields"] for x in ident_expl
                 if x["fields"].get("group") == "Target article"), None)
    assert repl is not None and targ is not None, "arms not split into Target/Replication"
    assert repl["r"] == pytest.approx(0.63)
    assert (repl["CI_lower"], repl["CI_upper"]) == pytest.approx((0.53, 0.72))
    assert targ["r"] == pytest.approx(0.34)
    assert targ["n"] == 170


# ── Real-PDF: xiao_2021 Table 4 — Original/Replication F not swapped (DP-5) ───


@requires_pdftotext
@_skip_under_xdist
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
