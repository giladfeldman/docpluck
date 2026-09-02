"""`changes_made` counts MINUS SIGNS by contract, not by a whitespace coincidence.

## What this is, and what it is NOT

It is **not** a fix for a wrong published number. Measured over the 21-paper
strided corpus, the sign-recovery family fires on exactly one paper and reports
`signs=6, delta=6` — they agree, and **zero papers diverge**. No consumer figure
was ever wrong from this.

It is the closure ESCImate asked for. Their 2026-08-22 notice accepted that the
value was correct and named the risk precisely:

    "Exactness here rests on a property of the RULES, not of the metric ...
     If any sign-recovery rule ever changes more than one character per
     occurrence, the delta silently stops equalling the count and nothing would
     fail. Recommended: docpluck wires an explicit count= at W0g/W0q/W0h so the
     guarantee is stated rather than emergent."

## The coincidence, and where it breaks

`_track` filled `changes_made` with `abs(len(before) - len(after))`. For this
family that is the WHITESPACE NORMALISATION, which equals the number of minus
signs re-attached only when there is exactly one stray space per bound.
Measured on `recover_dropped_minus_ci_upper_in_text`:

=========================  ======  ======  ==========================
input bracket              delta   signs
=========================  ======  ======  ==========================
``[- 0.58, - 0.18]``          2       2    agrees — the observed shape
``[- 0.58 , - 0.18]``         3       2    a space before the comma
``[- 0.58,   - 0.18]``        4       2    extra spaces after it
=========================  ======  ======  ==========================

All three brackets on `10.1016/j.jesp.2021.104154` — the paper W0q was built
on — are the first shape. So its published **6 was right, by luck**.

The last two rows are **arithmetic probes, not prevalence claims.** Neither
shape was found in the corpus; the divergence is latent, and the point of
wiring the count is that a latent divergence would never announce itself.

## Two units, both wrong

- The **character delta** over-reports as soon as a bracket carries stray
  whitespace (rows 2-3).
- A **per-firing count** under-reports: one W0q firing repairs one bracket and
  can attach TWO minus signs, so it reports 3 on the paper above where the
  truth is 6. This was drafted first and is the mirror error.

The unit is **minus signs attached to a numeral**, uniform across W0g / W0q /
W0h, because `upstream_sign_rewrites` is what effectcheck shows a reader.

`_track` never INVENTS a count: a call site supplies one, or the character
delta stands unchanged.

Written 2026-08-27.
"""

from __future__ import annotations

import pytest

from docpluck.normalize import (
    NormalizationLevel,
    NormalizationReport,
    normalize_text,
    recover_dropped_minus_ci_upper_in_text,
    recover_dropped_minus_via_ci_pairing,
)

from .conftest import pdf_available, pdf_path

_JESP_2021 = "10.1016__j.jesp.2021.104154.pdf"


# ---------------------------------------------------------------------------
# The unit: minus signs, not firings, not characters
# ---------------------------------------------------------------------------

def test_one_bracket_can_attach_two_signs():
    """The observed shape. A per-firing count would report 1 here."""
    src = "d = -0.38, 95% CI [- 0.58, - 0.18]"
    n = [0]
    out = recover_dropped_minus_ci_upper_in_text(src, n)

    assert out != src, "W0q did not fire — the rest of this test would be vacuous"
    assert n[0] == 2, "two minus signs were re-attached in one bracket repair"
    assert abs(len(src) - len(out)) == 2, "on THIS shape the delta happens to agree"


@pytest.mark.parametrize(
    "src, expected_delta",
    [
        ("d = -0.38, 95% CI [- 0.58 , - 0.18]", 3),    # space before the comma
        ("d = -0.38, 95% CI [- 0.58,   - 0.18]", 4),   # extra spaces after it
    ],
)
def test_the_delta_stops_matching_when_the_bracket_carries_stray_whitespace(
    src: str, expected_delta: int
):
    """The coincidence broken — the whole reason the count is now wired.

    ARITHMETIC PROBE, NOT A PREVALENCE CLAIM: neither shape was found in the
    corpus. That is the point. A latent divergence never announces itself, and
    the old metric would have published the delta with nothing failing.
    """
    n = [0]
    out = recover_dropped_minus_ci_upper_in_text(src, n)

    assert out != src, "the rule did not fire; this probe proves nothing"
    assert n[0] == 2, "still two signs"
    assert abs(len(src) - len(out)) == expected_delta, (
        "the character delta tracks whitespace, not signs"
    )
    assert n[0] != abs(len(src) - len(out)), (
        "this case exists precisely because the two numbers differ"
    )


def test_w0g_attaches_one_sign_per_rewrite():
    """The two-sided control: on W0g the units coincide, provably.

    W0g prepends exactly one `-`, so signs, firings and delta are all 1. That
    is why the divergence went unnoticed — it lives in only one of the three
    rules that write the key.
    """
    src = "b = .022, 95% CI [-0.05, -0.01]"
    n = [0]
    out = recover_dropped_minus_via_ci_pairing(src, n)

    assert out != src, "W0g did not fire — a zero here is an instrument claim"
    assert n[0] == 1
    assert abs(len(src) - len(out)) == 1


def test_a_rule_that_declines_reports_nothing():
    src = "d = 0.38, 95% CI [0.18, 0.58]"
    n_q, n_g = [0], [0]
    assert recover_dropped_minus_ci_upper_in_text(src, n_q) == src
    assert recover_dropped_minus_via_ci_pairing(src, n_g) == src
    assert n_q[0] == 0
    assert n_g[0] == 0


# ---------------------------------------------------------------------------
# _track's contract: it never invents a count
# ---------------------------------------------------------------------------

def test_track_uses_the_wired_count_not_the_delta():
    rep = NormalizationReport(level="academic")
    rep._track("X_step", "aaaaaaaa", "aa", "things_done", count=3)
    assert rep.changes_made["things_done"] == 3, "the wired count wins"
    assert rep.changes_made_by_step["X_step"] == 6, (
        "changes_made_by_step stays a character delta, as documented"
    )


def test_track_counts_a_length_neutral_rewrite_when_the_count_is_wired():
    """The `if diff:` guard dropped exactly the rewrites this metric exists for.

    A glyph substitution (`2` -> `-`) has a delta of zero, so an un-wired call
    site records nothing at all — ESCImate's false ZERO. A wired count is
    authoritative even at zero delta.
    """
    rep = NormalizationReport(level="academic")
    rep._track("X_step", "2.50", "-.50", "signs_recovered", count=1)
    assert rep.changes_made["signs_recovered"] == 1


def test_track_falls_back_to_the_delta_when_no_count_is_supplied():
    """Un-wired call sites are UNCHANGED — this is additive, not a sweep."""
    rep = NormalizationReport(level="academic")
    rep._track("X_step", "aaaaaaaa", "aa", "things_done")
    assert rep.changes_made["things_done"] == 6


def test_track_accumulates_wired_counts_across_rules():
    """Three rules write one key; the sum is what effectcheck publishes."""
    rep = NormalizationReport(level="academic")
    rep._track("W0g", "a", "ab", "dropped_minus_signs_recovered", count=2)
    rep._track("W0q", "ab", "abc", "dropped_minus_signs_recovered", count=3)
    assert rep.changes_made["dropped_minus_signs_recovered"] == 5


# ---------------------------------------------------------------------------
# The real paper — the number effectcheck actually publishes
# ---------------------------------------------------------------------------

@pytest.mark.skipif(
    not pdf_available("articlerepo", _JESP_2021),
    reason=(
        "shared article repository not present — "
        "python ~/.claude/skills/article-finder/find-pdf.py 10.1016/j.jesp.2021.104154"
    ),
)
def test_the_real_paper_still_publishes_six():
    """Its three brackets each carry two detached bounds: six signs.

    This value is UNCHANGED by wiring the count — it agreed before and agrees
    now. It is pinned so that a future rule which attaches a different number of
    signs per bracket moves this number visibly instead of silently.

    The paper is reached through the shared article repository (article-finder
    is the sole custodian); nothing is copied into this repo.
    """
    from docpluck.extract import extract_pdf

    raw, _method = extract_pdf(open(pdf_path("articlerepo", _JESP_2021), "rb").read())
    assert len(raw) > 10_000, (
        "extraction returned almost nothing — a green result from an empty "
        "input is a false green, so this asserts the input before the output"
    )

    _out, report = normalize_text(raw, NormalizationLevel("academic"))

    assert report.changes_made.get("dropped_minus_signs_recovered") == 6, (
        "three CI brackets, both bounds detached in each: six minus signs "
        "re-attached. effectcheck publishes this as upstream_sign_rewrites"
    )
    assert report.changes_made_by_step.get("W0q_ci_upper_detached_minus") == 6, (
        "the character delta for W0q on this paper — pinned separately so that "
        "if the two ever stop agreeing, this test says WHICH one moved"
    )
