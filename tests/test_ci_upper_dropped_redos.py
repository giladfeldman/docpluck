"""ReDoS guard for ``_CI_UPPER_DROPPED_RE`` (found 2026-08-04, RC-T cycle 4 run).

``tests/test_edge_cases.py::test_regex_no_catastrophic_backtracking`` began failing
intermittently in the full ``-n 10`` suite. It was recorded in the run-4 handoff as a
merely load-sensitive perf test ("passes alone in 1.43s of a 5s budget"). Re-measuring
UNLOADED showed that is no longer true: ``norm()`` on the test's own input took
2.3–6.9s across six consecutive runs, blowing the 5.0s budget on three of them with no
parallel load at all.

Profiling attributed 3.17s of 3.33s to ``re.Pattern.sub``, and a per-pattern sweep
isolated ``_CI_UPPER_DROPPED_RE`` at 0.487s for a SINGLE pass over a 10k-digit run
(``normalize_text`` applies it across several channels, multiplying that to seconds).

Root cause: the "decoration" gap between the point estimate and the bracketed CI was
``[^\\[\\]\\n]*?`` — UNBOUNDED and lazy. For each of ~n candidate estimate positions the
engine scans forward to end-of-text hunting for a ``[``, which is quadratic. Measured
scaling before the fix (digit-run length → seconds), ~4.6x per doubling:

    n= 1250  0.007s      n= 5000  0.151s      n=20000  2.269s
    n= 2500  0.032s      n=10000  0.493s

The decoration the pattern is documented to skip is short (``***``, ``<br>``, spaces).
An empirical sweep of every match across the dropped-minus test fixtures found a MAXIMUM
real gap of 54 characters, so the bound below carries >2x headroom and cannot change any
real recovery — pinned by ``test_wide_but_bounded_decoration_still_recovers``.

These tests are perf-BUDGETED rather than timing-flaky: the bounded pattern is linear, so
it completes in milliseconds and a generous budget still fails loudly if the quantifier
ever becomes unbounded again.
"""

from __future__ import annotations

import time

import pytest

from docpluck.normalize import (
    _CI_UPPER_DROPPED_RE,
    recover_dropped_minus_ci_upper_in_text,
)


def _elapsed(fn) -> float:
    start = time.perf_counter()
    fn()
    return time.perf_counter() - start


def test_ci_upper_pattern_is_linear_on_long_digit_runs():
    """A long digit run must not blow up the estimate→bracket scan.

    Pre-fix this took ~0.49s for one pass at n=10000 (and ~2.3s at n=20000);
    bounded, it is milliseconds. The budget is deliberately loose so this fails
    only on a genuine complexity regression, not on machine speed.
    """
    text = "p = " + "9" * 20000 + " end"
    assert _elapsed(lambda: _CI_UPPER_DROPPED_RE.sub("X", text)) < 0.5


def test_ci_upper_pattern_scales_sub_quadratically():
    """Doubling the input must not ~4x the time (the pre-fix signature)."""
    small = "p = " + "9" * 10000 + " end"
    large = "p = " + "9" * 20000 + " end"
    t_small = _elapsed(lambda: _CI_UPPER_DROPPED_RE.sub("X", small))
    t_large = _elapsed(lambda: _CI_UPPER_DROPPED_RE.sub("X", large))
    # Linear ⇒ ~2x. Allow generous slack for timer noise on a fast, tiny workload,
    # but 4.6x (the measured pre-fix ratio) must fail.
    assert t_large < max(t_small * 3.0, 0.5), (
        f"superlinear scaling: {t_small:.4f}s → {t_large:.4f}s"
    )


def test_normalize_stays_within_budget_on_pathological_input():
    """The end-to-end shape of the edge-case test that surfaced this."""
    from docpluck.normalize import NormalizationLevel, normalize_text

    text = "p = " + "9" * 10000 + " end"
    assert _elapsed(lambda: normalize_text(text, NormalizationLevel("academic"))) < 5.0


# --- behaviour must be unchanged -------------------------------------------------


def test_dropped_minus_upper_bound_still_recovers():
    """The bound must not cost a real recovery (estimate-containment invariant)."""
    out = recover_dropped_minus_ci_upper_in_text("r = -0.72 [-0.78, 0.67]")
    assert "[-0.78, -0.67]" in out


def test_wide_but_bounded_decoration_still_recovers():
    """Decoration well past the widest real fixture gap (54 chars) still matches."""
    decoration = "*** " + "<br> " * 12  # ~64 chars, inside the bound
    out = recover_dropped_minus_ci_upper_in_text(f"r = -0.72 {decoration}[-0.78, 0.67]")
    assert "[-0.78, -0.67]" in out


def test_genuine_positive_upper_bound_untouched():
    """A legitimately positive upper bound is never flipped."""
    s = "r = 0.40 [0.21, 0.59]"
    assert recover_dropped_minus_ci_upper_in_text(s) == s
