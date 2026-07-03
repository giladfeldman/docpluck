"""Regression test for wrapped Results-subsection heading rejoin (C1, v2.4.108).

The 2026-07-03 canary AI-verify found ip_feldman_2025_pspb rendering THREE (four,
incl. "Intensity Estimates Associations…") long Results-subsection headings
mangled: pdftotext column-wrapped each title across 2-3 physical lines with NO
blank between the head, the wrapped tail, and the following body paragraph, e.g.:

    Complementary Analysis: Interaction Between      <- HEAD
    Self and Others in Predicting Well-Being         <- TAIL 1
    (Exploratory Extension)                          <- TAIL 2
    We also explored interactions…                   <- BODY

The downstream promoters then mangled the SAME paper three different ways: the
≤6-word `###` promoter fired on the head alone and stranded the tail in body;
the 5-12-word `##` major promoter grabbed a stranded tail as its OWN
over-promoted heading; or the whole thing fell to body. The gold has each as ONE
`### ` heading.

Fix (v2.4.108): `_rejoin_wrapped_subsection_heading` runs FIRST among the
isolated-heading promoters, rejoins the wrap into one line, and emits it already
promoted to `### `. Strict structural signature (hang-word or paren-qualifier
tail + substantial head + no figure-adjacency), FP-validated across a 16-paper
broad-read + canary set with ZERO prose-merges.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("DOCPLUCK_DISABLE_CAMELOT", "1")

from docpluck.render import render_pdf_to_markdown

TEST_PDFS = Path(__file__).resolve().parents[1].parent / "PDFextractor" / "test-pdfs"

# The four wrapped Results-subsection headings, each as it appears in the gold
# (`reading` view) — one `### ` heading per title.
_WRAPPED_HEADINGS = (
    "Intensity Estimates Associations with Well-Being (Extension)",
    "Complementary Analysis: Self-Reports Associations with Well-Being (Exploratory Extension)",
    "Complementary Analysis: Interaction Between Self and Others in Predicting Well-Being (Exploratory Extension)",
    "External Analysis: Suppression Using Target's Analyses",
)

# Fragments that MUST NOT survive as stranded body lines or over-promoted
# headings (the pre-fix defect shapes).
_STRANDED_FRAGMENTS = (
    "\n## Self and Others in Predicting Well-Being\n",  # tail over-promoted to ##
    "\nSelf and Others in Predicting Well-Being\n",  # tail stranded in body
    "\nAnalyses\n",  # "External Analysis: … Target's" tail stranded
    "\nAssociations with Well-Being (Exploratory\n",  # unjoined wrap line
)


def test_ip_feldman_wrapped_subsection_headings_rejoined():
    """Each wrapped Results-subsection title renders as ONE `### ` heading."""
    pdf = TEST_PDFS / "apa" / "ip_feldman_2025_pspb.pdf"
    if not pdf.exists():
        pytest.skip(f"fixture missing: {pdf}")
    md = render_pdf_to_markdown(pdf.read_bytes())
    for heading in _WRAPPED_HEADINGS:
        assert f"### {heading}" in md, f"{heading!r} not rendered as a single ### heading"


def test_ip_feldman_no_stranded_wrap_fragments():
    """No wrapped-heading tail survives as a stranded body line or an
    over-promoted `## ` heading."""
    pdf = TEST_PDFS / "apa" / "ip_feldman_2025_pspb.pdf"
    if not pdf.exists():
        pytest.skip(f"fixture missing: {pdf}")
    md = render_pdf_to_markdown(pdf.read_bytes())
    for frag in _STRANDED_FRAGMENTS:
        assert frag not in md, f"stranded/over-promoted fragment survived: {frag!r}"


def test_rejoin_helper_joins_hang_word_wrap():
    """Unit contract: a hang-word head + heading-ish tail + body prose joins to
    one `### ` heading."""
    from docpluck.render import _rejoin_wrapped_subsection_heading

    text = (
        "Prior work ended here with a full sentence.\n"
        "\n"
        "Complementary Analysis: Interaction Between\n"
        "Self and Others in Predicting Well-Being\n"
        "(Exploratory Extension)\n"
        "We also explored interactions between one's own experiences and "
        "estimates of others' experiences in predicting well-being.\n"
    )
    out = _rejoin_wrapped_subsection_heading(text)
    assert (
        "### Complementary Analysis: Interaction Between Self and Others in "
        "Predicting Well-Being (Exploratory Extension)"
    ) in out


def test_rejoin_helper_skips_figure_diagram_labels():
    """Unit contract: a 2-word head over a bare word ADJACENT to a figure
    caption (a theoretical-model node-label pair) must NOT be joined."""
    from docpluck.render import _rejoin_wrapped_subsection_heading

    text = (
        "Fig. 1. Overall theoretical model.\n"
        "\n"
        "Support for\n"
        "Leader\n"
        "\n"
        "primary candidates for the party that participants had to decide between.\n"
    )
    out = _rejoin_wrapped_subsection_heading(text)
    assert "### Support for Leader" not in out
    assert "Support for\nLeader" in out  # left untouched


def test_rejoin_helper_skips_complete_short_heading_before_prose():
    """Unit contract: a COMPLETE short heading (no hang, blank BEFORE its body)
    must not absorb the next capitalized line."""
    from docpluck.render import _rejoin_wrapped_subsection_heading

    text = (
        "Prior paragraph ends with a sentence.\n"
        "\n"
        "Background\n"
        "\n"
        "We reviewed the prior literature on this topic in detail here now today.\n"
    )
    out = _rejoin_wrapped_subsection_heading(text)
    # "Background" is a complete short heading — must stay as its own line,
    # not merge with the body.
    assert "### Background We reviewed" not in out
    assert "Background\n" in out
