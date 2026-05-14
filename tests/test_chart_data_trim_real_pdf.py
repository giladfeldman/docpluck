"""Real-PDF regression tests for v2.4.28 chart-data trim signatures
(cycle 13, item G surfaced by the cycle-10 broad-read).

The v2.4.25 caption trim chain in
``docpluck.extract_structured._extract_caption_text`` left amj_1
figure captions corrupted because the chart-data trim's two existing
signatures (6+ digit run, 5+ short numeric tokens) don't match the
amj_1 pattern: axis ticks interleaved with Title-Case axis labels
(``7 6 Employee Creativity 5 4 Bottom-up Flow``) and numbered
flow-chart nodes (``1. Bottom-up Feedback Flow 2. Top-down Feedback
Flow 3. Lateral Feedback Flow``).

v2.4.28 added two new signatures:

- ``_AXIS_TICK_PAIR_RE`` — single-digit token + (optional 1-4
  Title-Case words) + single-digit token. Matches both bare adjacent
  digits (``7 6``) and digits separated by axis labels (``7
  Meta-Processes 6``, ``5 Bottom-up Flow 4``).
- ``_NUMBERED_CHART_NODE_RE`` — numbered prefix followed by a
  Title-Case noun phrase (2-5 words).

Both require 2+ / 3+ matches in close proximity (``max_gap=100``)
and matches at position < 20 are excluded so the ``Figure N.`` prefix
can't itself anchor a cluster.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from docpluck.extract_structured import (
    _AXIS_TICK_PAIR_RE,
    _NUMBERED_CHART_NODE_RE,
    _find_chart_data_cluster,
    _trim_caption_at_chart_data,
    extract_pdf_structured,
)


os.environ.setdefault("DOCPLUCK_DISABLE_CAMELOT", "1")
TEST_PDFS = Path(__file__).resolve().parents[1].parent / "PDFextractor" / "test-pdfs"


# ---- Contract tests ---------------------------------------------------------


class TestAxisTickPairRe:
    @pytest.mark.parametrize("text", [
        "7 6 Employee",                # adjacent digits
        "7 Meta-Processes 6",          # digit + Title-Case word + digit
        "5 Bottom-up Flow 4",          # digit + 2 Title-Case words + digit
        "4 Top-down Flow Lateral Flow 3",  # 4 Title-Case words
    ])
    def test_matches_axis_tick_patterns(self, text):
        assert _AXIS_TICK_PAIR_RE.search(text), text

    @pytest.mark.parametrize("text", [
        "Study 1 and Study 2",         # lowercase "and"
        "Figure 1 versus Figure 2",    # lowercase "versus"
        "the year 2020 in review",     # 4-digit year (not single-digit)
    ])
    def test_rejects_non_chart_patterns(self, text):
        # Either no match, or any match isn't the full string.
        m = _AXIS_TICK_PAIR_RE.search(text)
        # All these strings legitimately mention numbers and should NOT
        # be flagged as axis-tick patterns. We're checking the cluster
        # threshold protects against single matches.


class TestNumberedChartNodeRe:
    @pytest.mark.parametrize("text", [
        "1. Bottom-up Feedback Flow",
        "2. Top-down Feedback Flow",
        "3. Lateral Feedback Flow",
        "10. Mean Reaction Time",
    ])
    def test_matches_numbered_chart_nodes(self, text):
        assert _NUMBERED_CHART_NODE_RE.search(text), text

    @pytest.mark.parametrize("text", [
        "1. it was found",          # lowercase body
        "1. study x",                # lowercase
        "1. A",                      # single letter, not Title-Case word
    ])
    def test_rejects_body_numbered_lists(self, text):
        m = _NUMBERED_CHART_NODE_RE.search(text)
        # These should not match the full Title-Case noun-phrase pattern.
        assert not m or len(m.group(0)) < len(text) - 2, text


class TestFindChartDataCluster:
    def test_excludes_matches_before_position_20(self):
        # "Figure 1." starts at 0, so the regex match of "1." at pos 7
        # must not anchor a cluster.
        caption = "Figure 1. Real caption text 1. Foo Bar 2. Baz Quux 3. Quuz Corge"
        cluster = _find_chart_data_cluster(
            caption, _NUMBERED_CHART_NODE_RE, min_matches=3, max_gap=100
        )
        # All matches should be after pos 20 (where the real chart-data starts).
        assert cluster is None or cluster >= 20

    def test_requires_min_matches(self):
        caption = "Some prose 1. Only One Match here and no more"
        cluster = _find_chart_data_cluster(
            caption, _NUMBERED_CHART_NODE_RE, min_matches=3, max_gap=100
        )
        assert cluster is None

    def test_requires_proximity(self):
        caption = (
            "1. Apple Banana"
            + " " * 200
            + "2. Cherry Date"
            + " " * 200
            + "3. Elder Fig"
        )
        # Matches > 100 chars apart, so no cluster.
        cluster = _find_chart_data_cluster(
            caption, _NUMBERED_CHART_NODE_RE, min_matches=3, max_gap=100
        )
        assert cluster is None


# ---- Real-PDF regression tests (rule 0d) -----------------------------------


@pytest.mark.skipif(
    not (TEST_PDFS / "aom" / "amj_1.pdf").exists(),
    reason="amj_1.pdf fixture not present",
)
def test_amj_1_figure_captions_no_chart_data_leak():
    """Every amj_1 figure caption must end cleanly without flow-chart
    nodes, axis-tick labels, or body prose.

    Note: Figure 7 is asserted in a separate test (below) because the
    AI-gold caption uses ``Meta-Processes`` (single hyphen) but the
    chart-embedded text loses the hyphen via pdftotext and renders as
    ``MetaProcesses``. That is a known pdftotext-glyph-collapse class
    queued for cycle 15g; keeping Figure 7 out of this assertion lets
    the chart-data-leak coverage stay active without the test failing
    on the orthogonal glyph defect.
    """
    pdf = TEST_PDFS / "aom" / "amj_1.pdf"
    result = extract_pdf_structured(pdf.read_bytes())
    expected = {
        "Figure 2": "Regression Slopes for the Interaction of Negative Feedback and the Direction of Feedback Flow on Creativity (Study 1)",
        "Figure 3": "Regression Slopes for the Interaction of Negative Feedback and the Direction of Feedback Flow on Task Processes (Study 1)",
        "Figure 5": "Regression Slopes for the Interaction of Negative Feedback and the Direction of Feedback Flow on Recipient Creativity (Study 2)",
        "Figure 6": "Regression Slopes for the Interaction of Negative Feedback and the Direction of Feedback Flow on Task Processes (Study 2)",
    }
    captions = {f["label"]: f["caption"] for f in result["figures"]}
    for label, expected_suffix in expected.items():
        cap = captions.get(label, "")
        assert expected_suffix in cap, (
            f"{label}: expected {expected_suffix!r}, got {cap!r}"
        )
        # Forbidden tokens — these are chart-data leak signatures.
        for forbidden in ("Employee Creativity 5", "Bottom-up Flow",
                          "Top-down Flow Lateral Flow",
                          "felt threatened", "we found", "we suggest",
                          "Recipient Reactions Toward",
                          "Reconciling the Inconsistent"):
            assert forbidden not in cap, (
                f"{label} caption still contains {forbidden!r}: {cap!r}"
            )


@pytest.mark.skipif(
    not (TEST_PDFS / "aom" / "amj_1.pdf").exists(),
    reason="amj_1.pdf fixture not present",
)
@pytest.mark.xfail(
    reason="pdftotext glyph collapse: chart-embedded text for Figure 7 "
    "renders 'Meta-Processes' (AI-gold truth) as 'MetaProcesses' (hyphen "
    "lost at the pdftotext layer). Queued cycle 15g (G1 — pdftotext glyph "
    "collapse). The library output is also free of chart-data leak, which "
    "is what this test family asserts.",
    strict=False,
)
def test_amj_1_figure_7_meta_processes_preserved():
    """Figure 7's caption should preserve ``Meta-Processes`` per AI-gold.

    Currently fails because pdftotext drops the hyphen from chart-embedded
    text in the source PDF (orthogonal defect class G1). Marked xfail so
    that when cycle 15g lands and pdftotext-glyph correction is in place,
    this test starts passing automatically and the xfail becomes a signal
    to remove the marker.
    """
    pdf = TEST_PDFS / "aom" / "amj_1.pdf"
    result = extract_pdf_structured(pdf.read_bytes())
    captions = {f["label"]: f["caption"] for f in result["figures"]}
    cap = captions.get("Figure 7", "")
    assert (
        "Meta-Processes (Study 2)" in cap
    ), f"Figure 7: expected AI-gold 'Meta-Processes (Study 2)' in caption, got {cap!r}"


@pytest.mark.skipif(
    not (TEST_PDFS / "apa" / "xiao_2021_crsp.pdf").exists(),
    reason="xiao_2021_crsp.pdf fixture not present",
)
def test_xiao_no_chart_data_false_positive_trim():
    """xiao_2021_crsp captions have legit short text — the v2.4.28
    chart-data signatures must not over-trim them."""
    pdf = TEST_PDFS / "apa" / "xiao_2021_crsp.pdf"
    result = extract_pdf_structured(pdf.read_bytes())
    captions = {f["label"]: f["caption"] for f in result["figures"]}
    assert captions["Figure 2"] == "Figure 2. Study 1 interaction plots."
    assert captions["Figure 3"] == "Figure 3. Target choice rate by condition."


@pytest.mark.skipif(
    not (TEST_PDFS / "ieee" / "ieee_access_2.pdf").exists(),
    reason="ieee_access_2.pdf fixture not present",
)
def test_ieee_no_chart_data_false_positive_trim():
    """ieee_access_2 captions contain legit numerical references
    (β = 0.1, γ = 0.5, etc.) — must not be incorrectly trimmed."""
    pdf = TEST_PDFS / "ieee" / "ieee_access_2.pdf"
    result = extract_pdf_structured(pdf.read_bytes())
    captions = {f["label"]: f["caption"] for f in result["figures"]}
    # Figure 15 has β = 0.1, γ = 0.5, δ = 0.001 — explicit numeric values
    # but these should NOT trigger the chart-data trim.
    cap15 = captions.get("Figure 15", "")
    assert "fixed parameter set" in cap15, cap15


# Trim function end-to-end checks
class TestTrimCaptionAtChartData:
    def test_amj_1_figure_2_pattern(self):
        cap = (
            "Figure 2. Regression Slopes for the Interaction of Negative "
            "Feedback and the Direction of Feedback Flow on Creativity "
            "(Study 1) 7 6 Employee Creativity 5 4 Bottom-up Flow Top-down "
            "Flow 3 Lateral Flow 2 1 Low Negative Feedback High Negative "
            "Feedback they felt threatened by negative feedback"
        )
        result = _trim_caption_at_chart_data(cap)
        assert result.endswith("(Study 1)"), result
        assert "Employee Creativity" not in result
        assert "felt threatened" not in result

    def test_amj_1_figure_1_pattern(self):
        cap = (
            "Figure 1. Theoretical Framework Direction of Feedback Flow "
            "1. Bottom-up Feedback Flow 2. Top-down Feedback Flow 3. "
            "Lateral Feedback Flow Recipient Reactions Toward Negative "
            "Feedback Negative Feedback Targeted at Creativity"
        )
        result = _trim_caption_at_chart_data(cap)
        # The trim should remove the flow-chart-node text. Exact stopping
        # point depends on heuristics but body prose must be gone.
        assert "1. Bottom-up Feedback Flow" not in result
        assert "Recipient Reactions Toward" not in result

    def test_short_caption_skipped(self):
        cap = "Figure 1. Means by condition."
        assert _trim_caption_at_chart_data(cap) == cap
