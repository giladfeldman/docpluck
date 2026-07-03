"""Regression test for the body author-affiliation footnote strip (v2.4.107).

The cycle-1 canary AI-verify found efendic_2022_affect leaking its author
affiliation + corresponding-author block into the MIDDLE of an Introduction
paragraph — the block is a page-1 bottom footnote that pdftotext serialised in
reading order, splitting a sentence: "…can be far easier--more" │ <Maastricht
University … Contributed equally … Gilad Feldman, … Pok Fo Lam Road …> │
"efficient--than weighing…".

Fix (v2.4.107): `_strip_body_affiliation_block` removes a run of ≥3 consecutive
affiliation-shaped lines appearing in the body, reconnecting the split
paragraph. Strictly block-level, so a single body sentence that merely mentions
a university is never touched (verified by the unit FP tests + a corpus scan).
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("DOCPLUCK_DISABLE_CAMELOT", "1")

from docpluck.render import _strip_body_affiliation_block, render_pdf_to_markdown

REPO = Path.home() / "Dropbox" / "Vibe" / "ArticleRepository" / "fulltext"


# ── Unit tests on the block strip ───────────────────────────────────────────

def test_strips_body_affiliation_block_and_reconnects():
    text = (
        "## Introduction\n\n"
        "impression can be far easier--more\n\n"
        "Maastricht University, School of Business and Economics, Department of\n"
        "Marketing and Supply Chain Management, the Netherlands\n\n"
        "Hong Kong Metropolitan University, Hong Kong\n\n"
        "The University of Hong Kong, Hong Kong\n"
        "*\n"
        "Contributed equally, joint first authors.\n"
        "Gilad Feldman, Department of Psychology, The University of Hong Kong,\n"
        "Pok Fo Lam Road, Hong Kong 999077.\n\n"
        "efficient--than weighing the pros and cons.\n"
    )
    out = _strip_body_affiliation_block(text)
    assert "Maastricht University" not in out
    assert "Contributed equally" not in out
    assert "Pok Fo Lam Road" not in out
    # The split sentence's two halves survive (reconnected across the removed block).
    assert "can be far easier--more" in out
    assert "efficient--than weighing" in out


def test_leaves_single_body_university_mention():
    # A lone body sentence naming a university is NOT a ≥3-line affiliation run.
    text = (
        "## Funding\n\n"
        "This research was supported by the University of Hong Kong seed funding "
        "awarded to the first author, who thanks the department for its support.\n"
    )
    assert _strip_body_affiliation_block(text) == text


def test_leaves_two_affiliation_lines_below_threshold():
    # Only 2 affiliation-shaped lines — below the ≥3 run threshold, so untouched
    # (avoids stripping a short byline that legitimately survived).
    text = (
        "## Method\n\n"
        "Stanford University, United States\n"
        "Northwestern University, United States\n\n"
        "Participants were 200 undergraduates who completed the task online.\n"
    )
    assert _strip_body_affiliation_block(text) == text


def test_leaves_reference_list_block():
    # CRITICAL: a References block is a run of author-year-title lines that
    # superficially match affiliation grammar (journal names contain
    # "University"/"Press", author lists have commas). The citation guard MUST
    # keep the whole block. Corpus content-loss scan caught this FP on 5 papers.
    text = (
        "## References\n\n"
        "Eschleman, K. J., Bowling, N. A., Michel, J. S., & Burns, G. N. (2014). "
        "Something about work. Journal of Applied Psychology, 99(1), 1-10.\n"
        "Egloff, B., & Gruhn, A. J. (1996). Personality and endurance sports. "
        "Personality and Individual Differences, 21, 223-229.\n"
        "Finkel, S. E. (1995). Causal analysis with panel data. Sage University "
        "Press.\n"
        "Van Manen, M. (2007). Phenomenology of practice. Phenomenology & "
        "Practice, 1(1), 11-30.\n"
    )
    out = _strip_body_affiliation_block(text)
    assert out == text, "reference-list block was wrongly stripped as affiliations"
    assert "Eschleman" in out and "Van Manen" in out


# ── Real-PDF regression test ────────────────────────────────────────────────

def test_efendic_affiliation_not_in_body():
    pdf = REPO / "10.1177__19485506211056761.pdf"
    if not pdf.exists():
        pytest.skip(f"fixture missing: {pdf}")
    md = render_pdf_to_markdown(pdf.read_bytes())
    intro = md[: md.find("Reliance on affect is a general process")]
    # The affiliation footnote must not sit inside the Introduction paragraph.
    assert "Contributed equally, joint first authors." not in intro
    assert "Pok Fo Lam Road, Hong Kong 999077." not in intro
    # The split Introduction sentence is reconnected.
    assert "can be far easier--more" in md and "efficient--than weighing" in md
