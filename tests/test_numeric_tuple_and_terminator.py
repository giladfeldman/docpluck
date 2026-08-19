"""Comma-separated numeric runs now pass through — the guard AND its subjects are gone.

RE-FIXTURED 2026-08-14 (v2.4.130), NOT DELETED. Every case below is a REAL CORPUS SITE
found by `tools/diag/locale_gate_blast_radius.py` over 400 papers resolved from
article-finder, and the corpus knowledge is why the file is kept. What inverted is the
expected answer, and the reason it inverted is that both rules these cases were written
against — `A3a` (thousands strip) and `A3c` (leading-zero decimal) — are deleted, along
with the `_in_numeric_tuple` guard that existed only to stop them mangling these shapes.

**A rule and its guard retire together.** Keeping the guard would be dead code the next
reader re-enables; keeping the tests as pass-through assertions keeps the evidence.

## What these cases used to be, and what they are now

1. **A bracket-delimited numeric TUPLE** (`collabra.320`). `'purple (128,0,128), orange
   (255,165,0)'` rendered `'purple (128, 0.128), orange (255165, 0)'` — TWO rules
   corrupting one construct, publishing stimulus colours a replication would show
   participants wrongly. Now preserved because nothing rewrites the run at all.

2. **A significance asterisk ending a value** (`1413-81232020259.16472020`).
   `'IC95% 0,92 - 0,95**'` rendered `'IC95% 0.92 - 0,95**'` — one published interval with
   its lower bound converted and its upper bound not, purely because `*` was missing from
   A3c's terminator class. Now both bounds agree BY STAYING, which is the same invariant
   the original test asserted: **one interval, one convention.**

3. **`1,234,567` still stripping** was A3a's business. A3a is deleted; it passes through.
"""

from __future__ import annotations

import pytest

from docpluck.normalize import NormalizationLevel, normalize_text


def _norm(text: str) -> str:
    out, _ = normalize_text(text, NormalizationLevel.academic)
    return out.strip()


# ── 1. numeric tuples survive — now by default rather than by guard ──────


@pytest.mark.parametrize(
    "src",
    [
        "purple (128,0,128)",
        "orange (255,165,0)",
        "RGB (0,255,0)",
        "the colour was (12,34,56) in that condition",
        "coordinates (1,2,3,4)",
    ],
)
def test_bracket_delimited_integer_tuple_is_preserved(src):
    """An n-tuple is a list of values, never one thousands-grouped number."""
    assert _norm(src) == src


def test_the_real_corpus_line():
    src = "one of the three target colours: purple (128,0,128), orange (255,165,0)"
    assert _norm(src) == src


@pytest.mark.parametrize(
    "src",
    ["(p < 0,001)", "(0,003)", "[0,05]", "(0,0001)"],
)
def test_a_parenthesised_pvalue_is_NEITHER_converted_NOR_split(src):
    """THE SUBJECT OF THIS TEST SURVIVED THE RETIREMENTS — only the answer changed.

    It used to assert `(0,003)` -> `(0.003)`: A3c converting a European p-value, with the
    tuple guard required NOT to mistake it for a 2-tuple and emit `(0, 003)`.

    A3c is deleted, so the conversion is gone. **The splitting hazard is not.** Removing
    A3c EXPOSED a sibling it had been masking: `(0,003)` reached `A4`'s delimiter-spacing
    arm intact for the first time and became `(0, 003)` — a European p-value rendered as a
    two-element pair. A3c had been inventing the DECIMAL reading; A4 invented the
    SEPARATOR reading. Fixed in v2.4.129 (A4's spacing arm now requires a decimal point on
    a bound), and pinned here.

    So this asserts the strongest available property: the token is delivered EXACTLY as
    the paper printed it — not converted, not split, not re-spaced.
    """
    assert _norm(src) == src


def test_thousands_grouped_numbers_pass_through_too():
    """A3a's own target shape. RE-FIXTURED: it used to assert the strip.

    `1,000` is not a problem; it is clearly one thousand. Rewriting it to `1000` repairs
    nothing and REMOVES the evidence a consumer needs to notice a European table — which
    is exactly the evidence the future line-scoped locale guard requires.
    """
    assert _norm("N = 1,234,567 records") == "N = 1,234,567 records"
    assert _norm("we screened 12,345,678 tweets") == "we screened 12,345,678 tweets"
    assert _norm("(12,856 with immigrant backgrounds)") == "(12,856 with immigrant backgrounds)"
    assert _norm("N = (1,234,567)") == "N = (1,234,567)"


def test_the_pair_cases_still_survive():
    """v2.4.127's cases must not regress — they now survive by default."""
    assert "52272" not in _norm("Median (Q1,Q3) 148 (52,272)")
    assert "1197" not in _norm("t(1,197) = 2.0")


# ── 2. a significance marker no longer needs to terminate anything ───────


@pytest.mark.parametrize(
    "src",
    [
        "IC95% 0,92 - 0,95**",
        "0,93 - 0,95**",
        "0,37 - 0,96*",
        "r = 0,45†",
        "beta = 0,31‡",
        "value 0,88§",
    ],
)
def test_significance_and_footnote_marked_values_pass_through(src):
    """The terminator class was A3c's problem. A3c is gone, so is the problem."""
    assert _norm(src) == src


def test_both_bounds_of_a_published_interval_agree():
    """The defect's actual injury was ONE INTERVAL, TWO CONVENTIONS. Still asserted.

    The invariant is unchanged and is the reason this test is kept rather than deleted:
    a consumer must never receive an interval whose bounds were normalized differently.
    v2.4.129 satisfied it by converting neither, instead of by converting both.
    """
    out = _norm("IC95% 0,92 - 0,95**")
    assert out == "IC95% 0,92 - 0,95**"
    assert "0.92" not in out, "a bound was converted beside an unconverted one"


# ── 3. the DISSENT, recorded rather than erased ──────────────────────────


def test_a3c_retirement_costs_real_coverage_and_we_are_not_hiding_it():
    """**A MEASURED ARGUMENT AGAINST THE RETIREMENT, kept deliberately.**

    This test used to assert that A3c SHOULD fire, on this evidence: over 400 papers it
    found 6 sites in 4 papers and A3c was RIGHT in all 6 — single continental decimals
    leaking into otherwise-US papers (a typo, or a table pasted from a comma-locale
    machine). A design review proposing to suppress A3c under a `decisive_us` verdict was
    REJECTED on exactly this measurement.

    That evidence was never refuted. It is not the reason A3c was retired.

    A3c was retired under the 2026-08-14 scope directive — docpluck serves English papers
    in US numeric convention and does not convert European numbers, full stop — and under
    the separation of duties: deciding what `-0,26` means needs the parsed statistic and
    its context, which the consumer holds and we do not.

    **The cost is real and is stated so nobody has to rediscover it.** Left alone,
    `-0,26` is read by a naive parser as `-0`. Worse, and measured: ESCImate's `pat_CI3`
    does not match `[-0.60, -0,26]` at all, so the whole interval SILENTLY VANISHES from
    their record rather than misparsing — a coverage loss their users cannot see. That is
    why this retirement shipped with a comprehensive consumer report (LESSONS.md L-028)
    rather than a changelog line.

    If a later decision restores a LINE- or TABLE-scoped version of this rule, these two
    lines are its regression corpus.
    """
    assert _norm("d = -0.43, 95% CI = [-0.60, -0,26]") == "d = -0.43, 95% CI = [-0.60, -0,26]"
    assert _norm("beta = .04, t = 0,76, p > .010") == "beta = .04, t = 0,76, p > .010"


def test_the_guard_symbols_are_gone_not_merely_unused():
    """A guard left in place after its rules retire is dead code (the A3d precedent)."""
    import docpluck.normalize as N

    for sym in (
        "_in_numeric_tuple",
        "_a3c_leading_zero_sub",
        "_NUMERIC_RUN_RE",
        "_THOUSANDS_GROUPED_RE",
        "_VALUE_END_MARKERS",
    ):
        assert not hasattr(N, sym), sym


def test_idempotent():
    for src in (
        "purple (128,0,128)",
        "IC95% 0,92 - 0,95**",
        "RGB (0,255,0)",
        "N = 1,234,567 records",
    ):
        once = _norm(src)
        assert _norm(once) == once, src
