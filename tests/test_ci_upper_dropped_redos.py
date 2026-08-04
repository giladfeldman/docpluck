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


def test_normalize_scales_sub_quadratically_on_pathological_input():
    """End-to-end complexity check for the shape that surfaced this defect.

    Deliberately measures SCALING, not an absolute wall-clock budget. A budgeted
    variant of this test was written first and was itself flaky: `normalize_text` on
    this input runs 2.5-4.1s warm on this machine, so a 5s budget passed alone and
    failed under `pytest -n 10` parallel load — the same false-alarm class as the
    `test_regex_no_catastrophic_backtracking` test that started this investigation.
    A ratio is load-independent: contention inflates both measurements together.
    """
    from docpluck.normalize import NormalizationLevel, normalize_text

    level = NormalizationLevel("academic")
    small = "p = " + "9" * 5000 + " end"
    large = "p = " + "9" * 10000 + " end"
    t_small = _elapsed(lambda: normalize_text(small, level))
    t_large = _elapsed(lambda: normalize_text(large, level))
    # Linear => ~2x for a doubled input. The pre-fix pattern was ~4.6x per doubling.
    # Allow generous slack for scheduler noise; a genuine quadratic regression fails.
    assert t_large < max(t_small * 3.0, 0.5), (
        f"superlinear scaling in normalize_text: {t_small:.3f}s -> {t_large:.3f}s"
    )


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


# --- second quadratic pattern: the RSOS running-footer (found 2026-08-04) --------
# Fixing _CI_UPPER_DROPPED_RE alone did NOT make normalize_text linear: it still
# scaled ~4-5x per doubling. Instrumenting every COMPILED pattern's .sub() (a
# module-level sweep misses these — they live inside a list literal) attributed
# 3.165s of 3.7s at n=20000 to the RSOS running-footer pattern, whose leading
# UNBOUNDED \d+ starts a match attempt at every digit of the run and then fails.
# Bounding it to \d{1,6} (a page number is never longer) is ~1370x faster
# (4.53s -> 0.0033s) and matches both real header forms identically.


def test_rsos_running_footer_pattern_is_linear():
    """The RSOS footer pattern must not scan quadratically on a long digit run."""
    from docpluck.normalize import _WATERMARK_PATTERNS

    rsos = [p for p in _WATERMARK_PATTERNS if "royalsocietypublishing" in p.pattern]
    assert rsos, "RSOS running-footer pattern not found — has the list been renamed?"
    text = "p = " + "9" * 20000 + " end"
    for pat in rsos:
        assert _elapsed(lambda: pat.sub("", text)) < 0.5, f"quadratic: {pat.pattern[:60]}"


def test_rsos_running_footer_still_stripped():
    """Behaviour unchanged: both real RSOS footer forms are still matched."""
    from docpluck.normalize import _WATERMARK_PATTERNS

    rsos = [p for p in _WATERMARK_PATTERNS if "royalsocietypublishing" in p.pattern][0]
    for real in (
        "41royalsocietypublishing.org/journal/rsos R. Soc. Open Sci. 12: 250979",
        "12 royalsocietypublishing.org/journal/rsos R. Soc. Open Sci. 8: 2011",
    ):
        assert rsos.sub("<S>", real) == "<S>", f"no longer stripped: {real!r}"
