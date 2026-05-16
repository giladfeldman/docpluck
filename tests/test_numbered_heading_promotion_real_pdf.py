"""Regression test for G5 numbered-subsection demotion (cycle 9, v2.4.41).

The APA Phase-5d sweep found that numbered subsection headings in the
dominant Cambridge/JDM and Elsevier style — `5.1. Participants`,
`5.3.3. Choice deferral`, `6.1.1. Replication: Retrospective hindsight
bias` — were rendered as plain body text, not `###` headings.

Root cause: `_NUMBERED_SUBSECTION_HEADING_RE` required whitespace
immediately after the digit run, so a number with a trailing dot
(`5.1.`) never matched. The title character class also excluded the
colon, rejecting headings like `Replication: Retrospective hindsight
bias`.

Fix (v2.4.41): the number group tolerates an optional trailing dot and
the title may carry an internal colon. A title that ENDS in a colon is
still rejected downstream; titles with terminal sentence punctuation are
still rejected.

Cycle 13 (v2.4.45, G5b): the lowercase-run prose guard was removed from
the subsection promoter. Multi-level dotted numbering at line-start is
itself a strong heading signal, and descriptive subsection titles
legitimately run to many lowercase words ("3.3.2.1 The quality of
planning on the previous trial moderates the effect of reflection") — the
guard mis-rejected real headings. Long descriptive headings now promote.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("DOCPLUCK_DISABLE_CAMELOT", "1")

from docpluck.render import _promote_numbered_subsection_headings, render_pdf_to_markdown

TEST_PDFS = Path(__file__).resolve().parents[1].parent / "PDFextractor" / "test-pdfs"


# ── Unit tests on _promote_numbered_subsection_headings ─────────────────

def test_promotes_trailing_dot_two_level():
    out = _promote_numbered_subsection_headings("5.1. Participants and design")
    assert "### 5.1. Participants and design" in out


def test_promotes_trailing_dot_three_level():
    out = _promote_numbered_subsection_headings("5.3.3. Choice deferral")
    assert "### 5.3.3. Choice deferral" in out


def test_promotes_title_with_internal_colon():
    out = _promote_numbered_subsection_headings(
        "6.1.1. Replication: Retrospective hindsight bias"
    )
    assert "### 6.1.1. Replication: Retrospective hindsight bias" in out


def test_no_trailing_dot_still_promoted():
    out = _promote_numbered_subsection_headings("2.1 Procedure")
    assert "### 2.1 Procedure" in out


def test_body_prose_with_terminal_period_not_promoted():
    line = "5.1. We found that the manipulation produced a significant effect."
    assert _promote_numbered_subsection_headings(line) == line


def test_title_ending_in_colon_not_promoted():
    # A colon as the LAST char is a label-into-prose, not a heading.
    line = "5.1. Results:"
    assert _promote_numbered_subsection_headings(line) == line


def test_long_descriptive_title_promoted():
    # G5b (cycle 13): a descriptive subsection title with a long run of
    # lowercase words is still a heading — the prose guard was removed.
    line = "3.3.2.1. The quality of planning on the previous trial moderates the effect"
    out = _promote_numbered_subsection_headings(line)
    assert out.startswith("### 3.3.2.1. The quality of planning")


# ── Real-PDF regression test ────────────────────────────────────────────

def test_jdm_m_2022_2_numbered_subsections_promoted():
    pdf = TEST_PDFS / "apa" / "jdm_m.2022.2.pdf"
    if not pdf.exists():
        pytest.skip(f"fixture missing: {pdf}")
    md = render_pdf_to_markdown(pdf.read_bytes())
    # Trailing-dot subsection headings must render as `###`, not body text.
    for heading in (
        "### 5.1. Participants and design",
        "### 5.3.3. Choice deferral",
        "### 6.1. Participants and design",
        "### 7.3.1. Perception of missing attributes",
    ):
        assert heading in md, f"missing promoted heading: {heading}"
    # And not still sitting as bare body text.
    assert "\n5.1. Participants and design\n" not in md


def test_chen_2021_colon_subsections_promoted():
    pdf = TEST_PDFS / "apa" / "chen_2021_jesp.pdf"
    if not pdf.exists():
        pytest.skip(f"fixture missing: {pdf}")
    md = render_pdf_to_markdown(pdf.read_bytes())
    assert "### 6.1.1. Replication: Retrospective hindsight bias" in md
    assert "### 6.2.4. Replication evaluation: Very close replication" in md


def test_jdm_2023_16_long_descriptive_subsections_promoted():
    """G5b (cycle 13): long descriptive multi-level numbered subsection
    headings — previously demoted to body text by the lowercase-run guard —
    now render as `###` headings."""
    pdf = TEST_PDFS / "apa" / "jdm_.2023.16.pdf"
    if not pdf.exists():
        pytest.skip(f"fixture missing: {pdf}")
    md = render_pdf_to_markdown(pdf.read_bytes())
    for heading in (
        "### 2.4.2.2. Inference of planning strategies and strategy types",
        "### 3.2. H2: Systematic metacognitive reflection improves how and how much people plan",
        "### 3.3.2.1. The quality of planning on the previous trial moderates the effect of reflection",
    ):
        assert heading in md, f"missing promoted heading: {heading}"
    # And not still sitting as bare body text.
    assert "\n2.4.2.2. Inference of planning strategies and strategy types\n" not in md
