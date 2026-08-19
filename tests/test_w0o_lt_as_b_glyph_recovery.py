"""W0o: the '<' operator that some AdvTT fonts extract as the letter 'b'.

RASTER-VERIFIED, and it is OURS. `10.1016/j.jesp.2016.11.001` page 4 **prints**
`p < 0.001` in `BFDKFC+AdvTT94c8263f.I` — the same broken-ToUnicode AdvTT family
behind W0n's Dong case — and pdftotext yields `p b 0.001`. The page is correct and
our extraction is not, so this is docpluck's to fix under the ONE EXCEPTION to the
separation-of-duties directive: a defect our own pipeline introduced, where the
source is intact underneath.

**HOW IT WENT UNFIXED, which is the more useful half of this file.** The 2026-08-14
handoff recorded, of this exact site: *"That one is ours (`W0c` owns it) and stays."*
Checked against the source, `recover_corrupted_lt_operator` (W0c) recovers
`<`-as-BACKSLASH only, and **nothing anywhere handled `<`-as-`b`**. The claim was
copied forward unverified and read as settled — the L-027 failure mode in miniature,
inside the very run whose purpose was to stop exactly that. It was caught only
because a test asserting the claim was written, and it failed.

MEASURED before shipping (`tools/diag/b_for_lt_scan.py`):

    31 hits in 10.1016/j.jesp.2016.11.001 — every one a real `p < 0.001`
     0 hits across the 26-paper baseline corpus            (no false positives)
    17 legitimate `b` uses in the affected paper           (all untouched)

**Note the denominator.** The affected paper is NOT in the baseline corpus, so
"0 in 26" describes the absence of FALSE POSITIVES and says nothing about
prevalence. A denominator that excludes the known case cannot speak to how often
the shape occurs.

WHY THE SIGNATURE IS THE OPERATOR SLOT. Unlike a backslash — which never
legitimately touches a numeral in extracted academic text — **`b` is a real
statistical symbol**, the unstandardized regression coefficient, and the same paper
carries 17 of them (`b = 2.73`, `b = -3.26`, `b = 4.98`). So the discriminator is
structural rather than a vocabulary: a statistic ALWAYS has an operator between its
symbol and its value, and `b` is NEVER an operator. A bare `b` in that slot cannot
be a coefficient, because a coefficient carries its own `=`.

CONSUMER IMPACT: 31 published p-values that no `p\\s*<` regex could match, in one
paper — a silent coverage loss, not a visible corruption.
"""

from __future__ import annotations

import re

import pytest

from docpluck.normalize import (
    NormalizationLevel,
    normalize_text,
    recover_lt_as_b_operator,
)

from .conftest import pdf_available, pdf_path

_PAPER = "10.1016__j.jesp.2016.11.001.pdf"


def _norm(text: str) -> str:
    out, _ = normalize_text(text, NormalizationLevel.academic)
    return out


# ── the corruption is recovered ─────────────────────────────────────────


@pytest.mark.parametrize(
    "src,expected",
    [
        # Every one of these is a REAL line from the affected paper.
        ("z = 7.48, p b 0.001. Based on", "z = 7.48, p < 0.001. Based on"),
        ("t(69) = 4.37, p b 0.001. This", "t(69) = 4.37, p < 0.001. This"),
        ("F(4,268) = 90.79, p b 0.001, ", "F(4,268) = 90.79, p < 0.001, "),
        ("(a = 0.82, r = 0.69, p b 0.001)", "(a = 0.82, r = 0.69, p < 0.001)"),
    ],
)
def test_the_operator_is_recovered(src, expected):
    assert recover_lt_as_b_operator(src) == expected


# ── a coefficient `b` is never touched ──────────────────────────────────


@pytest.mark.parametrize(
    "src",
    [
        # All real, from the SAME paper — this is why the guard cannot be
        # "a b near a number".
        "linear contrast (b = 2.73, SE = 0.72,",
        "strong linear contrast (b = -3.26, SE = 0.83,",
        "the expected linear contrast, b = 4.98, SE = 0.200,",
        "b = 0.36 was not significant",
        # Shapes the signature must also leave alone.
        "the b1 coefficient was estimated",
        "beta = 0.31 in the model",
        "b(24) = 1.9 for that contrast",
        "we observed b 0.5 units of drift",  # no statistic symbol before it
        "a b 0.5 rating",                     # ditto
    ],
)
def test_a_legitimate_b_is_untouched(src):
    assert recover_lt_as_b_operator(src) == src


def test_a_coefficient_and_a_corrupted_operator_in_ONE_line():
    """The decisive case, and a real corpus line.

    `(b = 2.73, SE = 0.72, p b 0.001, ...)` carries both in the same
    parenthetical. The coefficient must survive and the operator must recover.
    """
    src = "es showed a linear contrast (b = 2.73, SE = 0.72, p b 0.001, CI95% [1.30; 4.17])"
    out = recover_lt_as_b_operator(src)
    assert "b = 2.73" in out
    assert "p < 0.001" in out
    assert "p b 0.001" not in out


# ── wired into the pipeline, not merely defined ─────────────────────────


def test_it_is_REACHABLE_through_normalize_text():
    """A capability nothing invokes is not shipped."""
    out, report = normalize_text(
        "t(69) = 4.37, p b 0.001. This suggests", NormalizationLevel.academic
    )
    assert "p < 0.001" in out
    assert "W0o_lt_as_b_recovery" in report.steps_changed


def test_it_is_wired_into_all_THREE_channels():
    """A repair in two channels of three makes a body sentence and a table cell
    disagree about the same input (LESSONS.md L-024)."""
    import docpluck.render as R
    import docpluck.tables.cell_cleaning as C

    assert hasattr(R, "recover_lt_as_b_operator")
    assert hasattr(C, "recover_lt_as_b_operator")


def test_idempotent():
    src = "t(69) = 4.37, p b 0.001."
    once = _norm(src)
    assert _norm(once) == once


# ── the real paper, end to end ──────────────────────────────────────────


@pytest.mark.skipif(
    not pdf_available("articlerepo", _PAPER), reason=f"custodian has no {_PAPER}"
)
def test_all_31_sites_recovered_and_no_coefficient_harmed_real_pdf():
    from pathlib import Path

    from docpluck.extract import extract_pdf

    raw, _engine = extract_pdf(Path(pdf_path("articlerepo", _PAPER)).read_bytes())
    assert len(re.findall(r"\bp b \d", raw)) == 31, "the fixture changed"

    fixed = recover_lt_as_b_operator(raw)
    assert len(re.findall(r"\bp b \d", fixed)) == 0
    assert len(re.findall(r"\bp < \d", fixed)) == 31
    # W0o ALONE must not change the coefficient count. (Through the full
    # pipeline the count rises, because A1 rejoins `b =\n2.73` across a column
    # break and S5 normalizes a U+2212 sign — both pre-existing and unrelated.)
    assert len(re.findall(r"\bb = [-−]?\d", fixed)) == len(
        re.findall(r"\bb = [-−]?\d", raw)
    )
