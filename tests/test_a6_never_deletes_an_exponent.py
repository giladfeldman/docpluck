"""A6 must never delete a superscript that is an EXPONENT (finding O9).

## The defect, fixed v2.4.133

A6 ("footnote marker removal") deleted a superscript/subscript digit after
``[\\d\\]\\)]``. Its own comment justified the digit case with

    "Note: A5 already converted <superscript-2> -> 2, so we look for isolated
     digits after ] ) or stat values"

**and that premise is false whenever ``preserve_math_glyphs=True``, because A5
is skipped in that mode** — the step trace records
``A5_skipped_preserve_math_glyphs``. A6 then met the raw codepoints and deleted
them, on the one path whose entire contract is not to touch glyphs::

    normalize_text("the value 10⁹", academic, preserve_math_glyphs=True)
        -> "the value 10"        A BILLION-FOLD ERROR
    normalize_text("N = 42³",      academic, preserve_math_glyphs=True)
        -> "N = 42"

...booked as ``footnotes_removed: 1``, so the telemetry asserted a footnote had
been stripped while a published exponent was destroyed. `W0p`'s docstring in the
same file warns "deleting the wrong one loses nine orders of magnitude"; A6 was
doing exactly that, three thousand lines away.

**The inversion is the tell**: a genuine footnote marker after a word
("Smith et al.¹") never matched at all, so the rule spared the case it was
written for and deleted the case it was warned about. Known and written down on
2026-08-13; not fixed until an independent audit reproduced it.

## The contract now

* after ``]`` or ``)`` — delete. Nothing exponentiates a closing bracket, so the
  slot is grammatically impossible for an exponent. That impossibility is the
  only evidence A6 can legitimately claim.
* after a DIGIT — **pass through**. Exponent and footnote marker are
  indistinguishable from the codepoint alone, which is why `W0p` exists and
  reads font size and baseline. A rule with no typographic evidence does not
  get to decide.
"""

from __future__ import annotations

import pytest

from docpluck.normalize import NormalizationLevel, normalize_text


def _norm(text: str, *, preserve: bool) -> str:
    out, _report = normalize_text(
        text, level=NormalizationLevel.academic, preserve_math_glyphs=preserve
    )
    return out


# ── the data loss ──────────────────────────────────────────────────────────

@pytest.mark.parametrize("src", [
    "the value 10⁹",
    "10⁹ cells",
    "N = 42³",
    "M = 4.2²",
    "x = 3².",
    "2,580¹ participants",
])
def test_an_exponent_is_never_deleted_when_glyphs_are_preserved(src: str):
    """`preserve_math_glyphs=True` means DO NOT TOUCH THE GLYPH."""
    assert _norm(src, preserve=True) == src


def test_the_billion_fold_case_specifically():
    """The shape `W0p`'s docstring warns about, by name."""
    assert _norm("the value 10⁹", preserve=True) == "the value 10⁹"
    assert _norm("the value 10⁹", preserve=False) == "the value 10^9"


def test_no_step_claims_to_have_removed_a_footnote_from_an_exponent():
    """The telemetry lied: a destroyed exponent was booked as
    `footnotes_removed: 1`. A false all-clear is worse than silence, because
    silence invites a check."""
    _out, report = normalize_text(
        "the value 10⁹",
        level=NormalizationLevel.academic,
        preserve_math_glyphs=True,
    )
    assert "A6_footnote_removal" not in report.steps_changed
    assert report.changes_made.get("footnotes_removed", 0) == 0


# ── what A6 must still do ──────────────────────────────────────────────────

@pytest.mark.parametrize("src,expected", [
    ("95% CI [0.1, 0.5]²", "95% CI [0.1, 0.5]"),
    ("(M = 3.2)¹", "(M = 3.2)"),
])
def test_a_marker_after_a_closing_bracket_is_still_removed(src, expected):
    """Nothing exponentiates a bracket — the slot is grammatically impossible
    for an exponent, which is the evidence that licenses the deletion."""
    assert _norm(src, preserve=True) == expected


def test_a_marker_after_a_digit_now_passes_through():
    """The deliberate, stated cost of the fix. `p < .001` keeping a visible
    marker is a recoverable cosmetic residue; `10⁹` becoming `10` is an
    unrecoverable error in a published number."""
    assert _norm("p < .001¹", preserve=True) == "p < .001¹"


def test_a_marker_after_a_word_was_never_handled_and_still_is_not():
    """Documents the inversion rather than silently fixing it: the case A6 was
    WRITTEN for has never matched its own pattern."""
    assert _norm("Smith et al.¹ found", preserve=True) == "Smith et al.¹ found"
