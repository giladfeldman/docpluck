"""RC-T Layer-2 — raw_text-fallback prose contamination (v2.4.98, 2026-06-22).

When Camelot recovers no cells, ``_extract_table_body_text`` linearizes the
text following a table caption as the ``unstructured-table`` fallback. Its
per-line prose gate (``_line_is_body_prose``, len>=80) cannot see body prose
that pdftotext WRAPPED into short (~48-char) lines, so the region overshoot
swallowed Results/Discussion prose into the block:

  * chan_feldman Table 1 — Discussion prose ("Our main focus was the
    replication …") accumulated AFTER the table's ``Note:`` footnote.
  * chan_feldman Table 9 — the block was ENTIRELY flowing prose ("than
    empathy. We provided full analyses …") duplicating the real ``##
    Discussion`` section verbatim.

Two structural-signature fixes (rule 16), both FP-safe by construction:
  1. Note-anchor: a table's ``Note:`` is its last element — trim everything
     after the note paragraph (T1).
  2. Degenerate-prose guard: suppress a block that STARTS mid-sentence with a
     lowercase multi-letter word AND is majority prose; render then emits a
     clean caption-only table (T9).

Contract tests pin the FP-safe predicate deterministically; real-PDF tests
(rule 0d) confirm on chan_feldman. PDFs are closed-access
(``feedback_no_pdfs_in_repo``); real-PDF tests skip when the fixture is absent.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from docpluck.extract_structured import (
    _join_wrapped_lines,
    _raw_text_is_degenerate_prose,
)
from docpluck.render import render_pdf_to_markdown

from .conftest import pdf_available, pdf_path, requires_pdftotext

_skip_under_xdist = pytest.mark.skipif(
    bool(os.environ.get("PYTEST_XDIST_WORKER")),
    reason="real-PDF Camelot extraction is non-deterministic under parallel "
    "xdist load; runs serially (isolation/serial run is the real gate)",
)


# ── contract tests: the FP-safe degenerate-prose predicate (deterministic) ────

# All-prose block that STARTS mid-sentence (lowercase multi-letter word) — the
# region-overshoot signature. Must be flagged degenerate.
_DEGENERATE = (
    "than empathy. We provided full analyses and results\n"
    "for the comparisons in the supplementary materials\n"
    "section of this paper across all of the conditions.\n"
    "We replicated all of the supported findings of the\n"
    "target article and summarised the results below here."
)
# Hypotheses table (legit, degraded): starts with a single-letter item marker.
_HYPOTHESES = (
    "a There is a positive association between a wronged\n"
    "person's empathy for an offender and reported\n"
    "forgiveness for the offender.\n"
    "b Apology increases the likelihood of forgiving."
)
# Descriptive rows (legit): starts with a Capitalized label.
_DESCRIPTIVE = "Median age (years)\n24.0\nAverage age\n28.8\n(years)\nStandard deviation"
# Instrument-table fragment (legit): starts with a single-letter token "h".
_INSTRUMENT = "h et al., 1997)\nPerceived apology\nEmpathy\nThe offender has apologised?"


def test_degenerate_prose_flagged():
    assert _raw_text_is_degenerate_prose(_DEGENERATE) is True


def test_hypotheses_not_flagged():
    """Single-letter item marker ('a ...') => not a mid-sentence continuation."""
    assert _raw_text_is_degenerate_prose(_HYPOTHESES) is False


def test_descriptive_rows_not_flagged():
    assert _raw_text_is_degenerate_prose(_DESCRIPTIVE) is False


def test_instrument_fragment_not_flagged():
    assert _raw_text_is_degenerate_prose(_INSTRUMENT) is False


def test_short_block_not_flagged():
    assert _raw_text_is_degenerate_prose("than empathy.\nWe provided.") is False


def test_join_wrapped_lines_merges_to_sentence():
    assert _join_wrapped_lines(["a foo", "bar baz.", "next one."]) == [
        "a foo bar baz.",
        "next one.",
    ]


# ── real-PDF tests (chan_feldman) ─────────────────────────────────────────────


def _unstructured_blocks(md: str) -> str:
    """Whitespace-normalized concatenation of every ```unstructured-table``` block."""
    blocks = re.findall(r"```unstructured-table\n(.*?)```", md, re.DOTALL)
    return re.sub(r"\s+", " ", "\n".join(blocks))


@pytest.fixture(scope="module")
def chan_md() -> str:
    key = "10.1080__02699931.2024.2434156"
    if not pdf_available("articlerepo", f"{key}.pdf"):
        pytest.skip(f"closed-access fixture missing: {key}.pdf")
    return render_pdf_to_markdown(Path(pdf_path("articlerepo", f"{key}.pdf")).read_bytes())


@requires_pdftotext
@_skip_under_xdist
def test_t1_note_anchor_trims_trailing_prose(chan_md: str):
    """Table 1: body prose after the ``Note:`` footnote must be trimmed from the
    fallback block (FAIL at HEAD — it was swallowed)."""
    blocks = _unstructured_blocks(chan_md)
    assert "Our main focus was the replication" not in blocks, (
        "chan_feldman T1 still swallows post-Note Discussion prose — the "
        "Note-anchor trim in _extract_table_body_text did not fire."
    )


@requires_pdftotext
@_skip_under_xdist
def test_t1_table_content_and_note_retained(chan_md: str):
    """FP guard: the Note-anchor must KEEP the table content + the note itself
    (hypotheses come before the note; trimming starts after it)."""
    blocks = _unstructured_blocks(chan_md)
    assert "There is a positive association" in blocks, "T1 hypothesis content lost (over-trim)"
    assert "Hypothesis 3 is not included in the replication" in blocks, "T1 Note paragraph lost (over-trim)"


@requires_pdftotext
@_skip_under_xdist
def test_t9_degenerate_block_suppressed_no_duplication(chan_md: str):
    """Table 9: the all-prose fallback (a verbatim duplicate of ## Discussion)
    must be suppressed — the Discussion opener appears exactly once, never inside
    an unstructured-table block."""
    opener = "We conducted a replication and extensions Registered Report"
    assert opener not in _unstructured_blocks(chan_md), (
        "chan_feldman T9 still dumps Discussion prose into an unstructured-table "
        "block — the degenerate-prose guard did not fire."
    )
    assert "### Table 9" in chan_md, "T9 heading lost (table_parity broken)"
    n = len(re.findall(re.escape(opener), chan_md))
    assert n == 1, f"Discussion opener appears {n}x (expected 1 — T9 duplication not resolved)"


@requires_pdftotext
@_skip_under_xdist
def test_t3_legit_fallback_table_survives(chan_md: str):
    """FP guard: Table 3 (a real descriptive table starting with a Capitalized
    label) must keep its fallback block + its Note — never suppressed/over-trimmed."""
    blocks = _unstructured_blocks(chan_md)
    assert "Median age" in blocks, "chan_feldman T3 descriptive fallback wrongly suppressed (FP)"
    assert "Origin was not explicitly mentioned" in blocks, "T3 Note over-trimmed (FP)"
