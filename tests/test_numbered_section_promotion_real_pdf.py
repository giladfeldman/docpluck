"""Regression test for G5a single-level numbered section-heading demotion
(cycle 11, v2.4.43).

Single-level top-level numbered headings (`2. Omission neglect`,
`3. Choice deferral`, `1. Hindsight bias`) were rendered as plain body
text when the title is not a canonical section word.

Fix (v2.4.43): `render.py::_promote_numbered_section_headings` promotes a
single-level `N. Title` line to `## N. Title`, gated on a
document-internal-consistency rule — the document must already number its
sections, and the candidate's number must fall in a contiguous integer
run that connects to a proven section number. Enumerated lists (exclusion
criteria, analysis steps) are NOT promoted: their numbers do not connect
to the section range, they carry terminal punctuation, they sit adjacent
to sibling numbered lines, and a restarting list breaks the uniqueness
test.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("DOCPLUCK_DISABLE_CAMELOT", "1")

from docpluck.render import _promote_numbered_section_headings, render_pdf_to_markdown

TEST_PDFS = Path(__file__).resolve().parents[1].parent / "PDFextractor" / "test-pdfs"


# ── Unit tests on _promote_numbered_section_headings ────────────────────

def test_promotes_single_level_in_numbered_document():
    text = "## 1. Introduction\n\nbody prose here.\n\n2. Omission neglect\nmore body prose.\n\n## 3. Choice deferral\n"
    out = _promote_numbered_section_headings(text)
    assert "## 2. Omission neglect" in out


def test_no_promotion_without_numbered_anchor():
    # No existing #/##/### numbered heading -> no numbering scheme -> no-op.
    text = "## Introduction\n\nbody.\n\n2. Omission neglect\nbody.\n"
    assert _promote_numbered_section_headings(text) == text


def test_enumerated_list_not_promoted():
    # A numbered LIST: items adjacent to siblings + terminal punctuation +
    # numbers far from the section range -> never promoted.
    text = (
        "## 32. Appendix A\n\nbody.\n\n"
        "1. Subjects with low proficiency;\n"
        "2. Subjects not serious;\n"
        "3. Subjects who guessed the hypothesis;\n"
    )
    out = _promote_numbered_section_headings(text)
    assert "## 1. Subjects" not in out
    assert "## 2. Subjects" not in out
    assert "## 3. Subjects" not in out


def test_repeated_number_not_promoted():
    # A number that appears more than once is a restarting list, not a
    # section sequence -> excluded by the uniqueness test.
    text = (
        "## 1. Introduction\n\nbody.\n\n"
        "2. Main Task\nbody.\n\n"
        "## 3. Results\n\nbody.\n\n"
        "2. Debrief Task\nbody.\n"
    )
    out = _promote_numbered_section_headings(text)
    assert "## 2. Main Task" not in out
    assert "## 2. Debrief Task" not in out


def test_terminal_punctuation_not_promoted():
    text = "## 1. Introduction\n\nbody.\n\n2. We then ran the analysis.\nbody.\n"
    out = _promote_numbered_section_headings(text)
    assert "## 2. We then" not in out


# ── Real-PDF regression test ────────────────────────────────────────────

def test_jdm_m_2022_2_single_level_sections_promoted():
    pdf = TEST_PDFS / "apa" / "jdm_m.2022.2.pdf"
    if not pdf.exists():
        pytest.skip(f"fixture missing: {pdf}")
    md = render_pdf_to_markdown(pdf.read_bytes())
    for heading in ("## 2. Omission neglect", "## 3. Choice deferral", "## 5. Study 1"):
        assert heading in md, f"missing promoted section heading: {heading}"


def test_chandrashekar_exclusion_list_not_promoted():
    """The exclusion-criteria enumerated list (1.-6.) must NOT be promoted to
    `## N.` headings — it is a list, not a section sequence."""
    pdf = TEST_PDFS / "apa" / "chandrashekar_2023_mp.pdf"
    if not pdf.exists():
        pytest.skip(f"fixture missing: {pdf}")
    md = render_pdf_to_markdown(pdf.read_bytes())
    assert "## 1. Subjects indicating" not in md
    assert "## 4. Have seen or done the survey" not in md
