"""Real-PDF regression tests for v2.4.25 figure-caption trim chain.

Covers the three classes of caption corruption surfaced by the cycle-9
handoff (item A) plus the broad-read of amj_1 / ieee_access_2:

1. **Body-prose absorption** (xiao Figure 2 / Figure 3) — pdftotext
   flattened ``"Figure N. <caption>.\\n<inline section heading>
   <body sentence>"`` into a single rejoined paragraph so the
   paragraph-walk in ``_extract_caption_text`` couldn't separate them.
2. **Trailing PMC reprint footer** (ieee_access_2 every figure) —
   ``"IEEE Access. Author manuscript; available in PMC ...."`` absorbed
   at the end.
3. **Duplicate ALL-CAPS label** (amj_1 every figure, ieee_access_2 every
   figure) — pdftotext emits both ``Figure N.`` (title-case caption) and
   ``FIGURE N`` (graphics overlay) so the rendered caption was
   ``"Figure 1. FIGURE 1 Theoretical Framework …"``.

These tests exercise the public structured-extraction entrypoint
(``extract_pdf_structured``) on the actual library code against real
PDF fixtures, per CLAUDE.md hard rule 0d.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from docpluck.extract_structured import (
    _strip_duplicate_uppercase_label,
    _trim_caption_at_body_prose_boundary,
    _trim_caption_at_running_header_tail,
    extract_pdf_structured,
)


# Disable Camelot for speed — these tests only exercise figure captions,
# which don't depend on table extraction.
os.environ.setdefault("DOCPLUCK_DISABLE_CAMELOT", "1")


TEST_PDFS = Path(__file__).resolve().parents[1].parent / "PDFextractor" / "test-pdfs"


# ---- Contract tests (cheap, pure helpers) ---------------------------------


class TestStripDuplicateUppercaseLabel:
    def test_strip_figure_n_uppercase_no_period(self):
        snippet = "Figure 1. FIGURE 1 Theoretical Framework Direction"
        assert _strip_duplicate_uppercase_label(snippet, "Figure 1") == (
            "Figure 1. Theoretical Framework Direction"
        )

    def test_strip_figure_n_uppercase_with_period(self):
        snippet = "Figure 2. FIGURE 2. Continuous-time, Markov Chain SIRS model"
        assert _strip_duplicate_uppercase_label(snippet, "Figure 2") == (
            "Figure 2. Continuous-time, Markov Chain SIRS model"
        )

    def test_strip_table_n_uppercase(self):
        snippet = "Table 3. TABLE 3 Means and standard deviations"
        assert _strip_duplicate_uppercase_label(snippet, "Table 3") == (
            "Table 3. Means and standard deviations"
        )

    def test_no_duplicate_unchanged(self):
        snippet = "Figure 1. Sample task screens (left: replication; right: original)."
        assert (
            _strip_duplicate_uppercase_label(snippet, "Figure 1") == snippet
        )

    def test_no_label_unchanged(self):
        snippet = "FIGURE 1 Theoretical Framework"
        assert _strip_duplicate_uppercase_label(snippet, "") == snippet


class TestTrimCaptionAtRunningHeaderTail:
    def test_author_etal_tail(self):
        snippet = (
            "Figure 2. Study 1 interaction plots. Exploratory analysis To examine "
            "whether and to what extent participants perceived the decoys to be "
            "less preferable than their targets, we performed paired-samples "
            "t-tests to compare the points 14 Q. XIAO ET AL."
        )
        result = _trim_caption_at_running_header_tail(snippet)
        assert result.endswith("interaction plots."), result
        assert "Q. XIAO" not in result
        assert "Exploratory" not in result

    def test_dyad_page_tail(self):
        snippet = (
            "Figure 3. Regression Slopes for the Interaction. "
            "2020 Kim and Kim 599"
        )
        result = _trim_caption_at_running_header_tail(snippet)
        assert result.endswith("Interaction."), result
        assert "Kim and Kim" not in result

    def test_pmc_reprint_footer(self):
        snippet = (
            "Figure 1. Petri nets model formalism elements. "
            "IEEE Access. Author manuscript; available in PMC 2026 February 25."
        )
        result = _trim_caption_at_running_header_tail(snippet)
        assert result.endswith("formalism elements."), result
        assert "PMC" not in result
        assert "Author manuscript" not in result

    def test_no_running_header_unchanged(self):
        snippet = "Figure 1. Means by condition. Bars represent 95% confidence intervals."
        assert _trim_caption_at_running_header_tail(snippet) == snippet


class TestTrimCaptionAtBodyProseBoundary:
    def test_xiao_figure_2_pattern(self):
        snippet = (
            "Figure 2. Study 1 interaction plots. Exploratory analysis To examine "
            "whether and to what extent participants perceived the decoys."
        )
        result = _trim_caption_at_body_prose_boundary(snippet)
        assert result == "Figure 2. Study 1 interaction plots.", result

    def test_xiao_figure_3_pattern(self):
        snippet = (
            "Figure 3. Target choice rate by condition. Choice regret and "
            "justifiability Connolly et al. (2013) observed that Control "
            "participants indicated that an imagined choice."
        )
        result = _trim_caption_at_body_prose_boundary(snippet)
        assert result == "Figure 3. Target choice rate by condition.", result

    def test_legit_two_sentence_caption_kept(self):
        # Note + caption-continuation opener — must NOT be trimmed.
        snippet = (
            "Figure 1. Means by condition. Note. Error bars represent 95% "
            "confidence intervals."
        )
        result = _trim_caption_at_body_prose_boundary(snippet)
        assert result == snippet, result

    def test_legit_caption_with_panel_kept(self):
        snippet = "Figure 4. Effect of X on Y. Panel A shows the main effect."
        result = _trim_caption_at_body_prose_boundary(snippet)
        assert result == snippet, result

    def test_short_caption_skipped(self):
        snippet = "Figure 1. Means."
        assert _trim_caption_at_body_prose_boundary(snippet) == snippet


# ---- Real-PDF regression tests (rule 0d) ----------------------------------


@pytest.mark.skipif(
    not (TEST_PDFS / "apa" / "xiao_2021_crsp.pdf").exists(),
    reason="xiao_2021_crsp.pdf fixture not present",
)
def test_xiao_figure_2_no_body_prose_absorption():
    """Cycle-9 handoff item A ship-blocker: xiao Figure 2 caption must
    NOT absorb the inline body section heading "Exploratory analysis"
    and the body-prose run that follows it."""
    pdf = TEST_PDFS / "apa" / "xiao_2021_crsp.pdf"
    result = extract_pdf_structured(pdf.read_bytes())
    figs = {f["label"]: f["caption"] for f in result["figures"]}
    assert "Figure 2" in figs
    cap = figs["Figure 2"]
    assert cap == "Figure 2. Study 1 interaction plots.", cap
    # Both the body-prose absorption AND the running-header tail must
    # be gone.
    assert "Exploratory analysis" not in cap
    assert "XIAO" not in cap


@pytest.mark.skipif(
    not (TEST_PDFS / "apa" / "xiao_2021_crsp.pdf").exists(),
    reason="xiao_2021_crsp.pdf fixture not present",
)
def test_xiao_figure_3_no_body_prose_absorption():
    """xiao Figure 3 — same root cause as Figure 2."""
    pdf = TEST_PDFS / "apa" / "xiao_2021_crsp.pdf"
    result = extract_pdf_structured(pdf.read_bytes())
    figs = {f["label"]: f["caption"] for f in result["figures"]}
    assert "Figure 3" in figs
    cap = figs["Figure 3"]
    assert cap == "Figure 3. Target choice rate by condition.", cap
    assert "Choice regret" not in cap
    assert "Connolly" not in cap


@pytest.mark.skipif(
    not (TEST_PDFS / "ieee" / "ieee_access_2.pdf").exists(),
    reason="ieee_access_2.pdf fixture not present",
)
def test_ieee_access_no_pmc_footer_on_captions():
    """Every figure caption in ieee_access_2.pdf used to end with
    'IEEE Access. Author manuscript; available in PMC ...'."""
    pdf = TEST_PDFS / "ieee" / "ieee_access_2.pdf"
    result = extract_pdf_structured(pdf.read_bytes())
    offenders = [
        f["label"] for f in result["figures"]
        if "Author manuscript" in f["caption"]
        or "available in PMC" in f["caption"]
    ]
    assert offenders == [], f"PMC footer in: {offenders}"


@pytest.mark.skipif(
    not (TEST_PDFS / "ieee" / "ieee_access_2.pdf").exists(),
    reason="ieee_access_2.pdf fixture not present",
)
def test_ieee_access_no_duplicate_uppercase_label():
    """Every ieee_access_2 figure used to render as
    'Figure N. FIGURE N. <caption>'."""
    pdf = TEST_PDFS / "ieee" / "ieee_access_2.pdf"
    result = extract_pdf_structured(pdf.read_bytes())
    offenders = [
        f["label"] for f in result["figures"]
        if f["caption"].startswith(f"{f['label']}. FIGURE")
    ]
    assert offenders == [], f"Duplicate uppercase label in: {offenders}"


@pytest.mark.skipif(
    not (TEST_PDFS / "aom" / "amj_1.pdf").exists(),
    reason="amj_1.pdf fixture not present",
)
def test_amj_1_no_duplicate_uppercase_label():
    """Every amj_1 figure used to render as
    'Figure N. FIGURE N <caption>' (no period after FIGURE N)."""
    pdf = TEST_PDFS / "aom" / "amj_1.pdf"
    result = extract_pdf_structured(pdf.read_bytes())
    offenders = [
        f["label"] for f in result["figures"]
        if f["caption"].startswith(f"{f['label']}. FIGURE")
    ]
    assert offenders == [], f"Duplicate uppercase label in: {offenders}"
