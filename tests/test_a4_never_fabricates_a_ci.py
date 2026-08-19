"""A4 must never MANUFACTURE a confidence interval out of a section reference.

REAL-PAPER EVIDENCE (DOI + page, per the directive of 2026-08-13):

    10.3389/fpsyg.2023.1214699 — Frontiers in Psychology, English.
        '...regarding the semantic annotation (3.2.2.1)'   ->  '(3.2, 2.1)'
        '...and the quantification (3.2.2.2) of lexemes'   ->  '(3.2, 2.2)'

    Found 2026-08-14 by `tools/diag/non_statistic_corpus_scan.py` on its FIRST
    run — the gate added the same day precisely because the A3c URL corruption
    had reached production without anything ever asking this question.

WHY THIS ONE IS WORSE THAN AN ORDINARY CORRUPTION. A4a exists to repair a CI
whose comma was rendered as a period (`[0.25.0.54]` -> `[0.25, 0.54]`). Applied
to a four-level section cross-reference it does not merely damage the token — it
**fabricates a statistic that is not in the paper**, and the fabricated token
`(3.2, 2.1)` has its bounds in DESCENDING order, i.e. it looks exactly like a
*reversed confidence interval*. Reversed CIs are one of the defect classes our
consumers are being asked to build detectors for. docpluck would be
manufacturing the very defect the downstream tool exists to catch, in a paper
that does not contain it.

Ownership is unambiguous: the page prints `(3.2.2.1)` correctly and docpluck
broke it. **Ours**, and therefore fixed rather than passed through — the
separation-of-duties directive retires repairs of the PAPER's defects, not
repairs of our own.

WHY THE EXISTING GUARD MISSED IT. A4a's comment says the `\\d+\\.\\d+` on each
side "blocks false-positives on section refs like `[1.2.3]` where the trailing
token has no decimal". True for THREE components. A FOUR-component reference has
a decimal on both sides and sails straight through. The same
"what is not on this list?" failure as every other defect in this family — an
enumeration of the shapes that must not match is never complete.

THE REMEDY IS POSITIVE, not another exclusion: A4a rewrites only when the
bracket is in **confidence-interval context**. The rule is named for the CI; if
nothing establishes that it IS one, it does not fire. Where the evidence is
absent, pass through — the source stays intact and both readings recoverable.
"""

from __future__ import annotations

import pytest

from docpluck.normalize import NormalizationLevel, normalize_text


def _norm(s: str) -> str:
    return normalize_text(s, NormalizationLevel.academic)[0]


@pytest.mark.parametrize(
    "src",
    [
        # The two real sites, verbatim from 10.3389/fpsyg.2023.1214699.
        "researcher needs to make regarding the semantic annotation (3.2.2.1)",
        "and the quantification (3.2.2.2) of lexemes incorporated in a",
        # Same shape, other bracket and other depths.
        "see [1.2.3.4] for details",
        "as in (10.1.2.3) of the manual",
        "refer to section (2.10.1.5) above",
    ],
)
def test_hierarchical_reference_is_never_turned_into_a_ci(src):
    assert _norm(src) == src, "A4 fabricated an interval from a section reference"


@pytest.mark.parametrize(
    "src,expect",
    [
        # Context form (a) — the words.
        ("d = 0.42, 95% CI [0.25.0.54]", "[0.25, 0.54]"),
        ("the 95% CI (0.25.0.54) excluded zero", "(0.25, 0.54)"),
        ("95% confidence interval [1.20.3.40]", "[1.20, 3.40]"),
        # Context form (b) — the ESTIMATE, with NO 'CI' text anywhere. This is
        # the shape A4a was actually built for (collabra_57785 abstract), and a
        # first draft of this guard that required the words BROKE it. Pinned so
        # a future tightening cannot silently do that again.
        ("Effect was d=0.39 [0.25.0.54] across replications.", "[0.25, 0.54]"),
        ("Abstract: d=0.39[0.25.0.54]", "[0.25, 0.54]"),
        ("d = 0.04 [-0.19.0.27] H1.", "[-0.19, 0.27]"),
    ],
)
def test_genuine_fused_ci_still_repairs(src, expect):
    """The repair A4a was built for must survive the guard.

    This is a defect OUR channel introduces — the source prints a comma and the
    font substitution renders it as a period — so it stays fixed.
    """
    assert expect in _norm(src)


def test_a_bare_integer_before_the_bracket_is_not_an_estimate():
    """The estimate context requires a DECIMAL, not any digit.

    'in Experiment 2 (3.2.2.1)' must not fire: a bare integer is a label, an
    estimate carries a decimal point. This is the line between the two context
    forms and it is the guard's whole discrimination.
    """
    src = "as reported in Experiment 2 (3.2.2.1) above"
    assert _norm(src) == src


def test_three_component_reference_still_untouched():
    """The pre-existing guard's own case, pinned so the fix cannot regress it."""
    assert _norm("see section [1.2.3] for details") == "see section [1.2.3] for details"
    assert _norm("see section (1.2.3) for details") == "see section (1.2.3) for details"


def test_ordinary_ci_spacing_arm_is_unaffected():
    """A4's OTHER arm — comma present, spacing added — is a different rule and
    the most-fired step in the pipeline (1017 sites / 92 of 297 English papers).
    Nothing here may touch it."""
    assert "[7.77, 31.28]" in _norm("95% CI [7.77,31.28]")
