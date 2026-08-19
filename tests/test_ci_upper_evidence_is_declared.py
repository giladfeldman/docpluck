"""Every CI-upper minus recovery must declare WHICH evidence it rested on.

## The defect (register O5)

``normalize._CI_UPPER_DROPPED_RE`` CAPTURES a detached dash before the upper
bound as group 5 — ``[−0.78,  –  0.67]``, a dash glyph separated from its digit
by spaces — and ``recover_dropped_minus_ci_upper_in_text._sub`` **never read
it**. Every rewrite was decided by ``recover_dropped_minus_ci_upper``, pure
estimate-containment arithmetic. So the one case carrying real typographic
evidence was adjudicated as though it had none, and the register's Plan Step D
(keep the dash, retire the arithmetic) was never implemented.

## Why the arithmetic was NOT retired

Both reviewers checked the primary source independently on 2026-08-15 and found
the same thing in ``chan_feldman_2025_cogemo`` Table 9:

    row 2bi   `[−0.78,  –  0.67]`   detached dash present -> TYPOGRAPHIC
    row 2bii  `[−0.52,  0.33]`      no dash at all        -> INFERENTIAL only

Row 2bii's published upper bound is ``−0.33`` and the arithmetic is the only
mechanism that recovers it. Retiring it would delete a repair with a real-DOI
justification and flip a published number back to wrong. So both arms stay, and
each one now RECORDS which evidence it used — the doctrine's stated reason for
handing inferential calls to consumers is that docpluck had no channel to
announce a guess, and that channel now exists.

## Why the dash counts as typographic

The dash is a glyph the renderer emitted; only its READING was ever inferential.
The comma settles the reading: in ``[lo, – hi]`` the comma already occupies the
separator role, so the dash cannot be a range separator (``0.19–0.45``) and can
only be a sign that lost its kerning. ``_CI_UPPER_DROPPED_RE`` requires that
comma, so the gate inherits the condition instead of assuming it.
"""

from __future__ import annotations

from docpluck.normalize import recover_dropped_minus_ci_upper_in_text
from docpluck.telemetry import fallback_scope

# The two real shapes, as they extract from the source PDF.
_TYPOGRAPHIC = "r = -.73, 95% CI [-0.78,  -  0.67]"
_INFERENTIAL = "r = -.43, 95% CI [-0.52,  0.33]"


def test_detached_dash_is_repaired_and_recorded_as_typographic():
    with fallback_scope() as fb:
        out = recover_dropped_minus_ci_upper_in_text(_TYPOGRAPHIC)
    assert "[-0.78, -0.67]" in out, out
    assert "ci_upper_minus_reattached_from_detached_dash" in fb.counters, (
        f"a typographic repair was booked as something else: {fb.counters}"
    )
    assert "ci_upper_minus_inferred_from_containment" not in fb.counters


def test_fully_dropped_minus_is_repaired_and_recorded_as_inferential():
    """The repair is KEPT — it recovers a published -0.33 — but it is declared,
    so a consumer can find every guess and re-check it against the paper."""
    with fallback_scope() as fb:
        out = recover_dropped_minus_ci_upper_in_text(_INFERENTIAL)
    assert "[-0.52, -0.33]" in out, out
    assert "ci_upper_minus_inferred_from_containment" in fb.counters, (
        f"an INFERENTIAL rewrite shipped undeclared: {fb.counters}"
    )
    assert "ci_upper_minus_reattached_from_detached_dash" not in fb.counters


def test_a_correct_interval_is_untouched_and_records_nothing():
    """No churn on rows that were never corrupt — an event on a clean row would
    make the telemetry useless by drowning the real ones."""
    clean = "r = -.73, 95% CI [-0.78, -0.67]"
    with fallback_scope() as fb:
        assert recover_dropped_minus_ci_upper_in_text(clean) == clean
    assert fb.counters == {}


def test_a_genuine_zero_straddling_ci_is_still_left_alone():
    """The self-guard that keeps a real null result intact. `d = -0.02` sits
    outside `[-0.19, -0.15]`, so the flip is refused."""
    null_row = "d = -0.02, 95% CI [-0.19, 0.15]"
    with fallback_scope() as fb:
        assert recover_dropped_minus_ci_upper_in_text(null_row) == null_row
    assert fb.counters == {}


def test_the_dash_path_refuses_to_emit_a_backwards_interval():
    """Reattaching the dash must not manufacture a bracket that runs backwards.
    That is a well-formedness test on the RESULT, not estimate arithmetic, so it
    belongs on the typographic path."""
    backwards = "r = -.90, 95% CI [-0.20,  -  0.95]"
    out = recover_dropped_minus_ci_upper_in_text(backwards)
    assert "[-0.20, -0.95]" not in out, (
        f"emitted a descending interval: {out}"
    )
