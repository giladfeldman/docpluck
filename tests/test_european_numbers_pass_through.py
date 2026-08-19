"""docpluck does not convert European numbers. It passes them through.

**USER DIRECTIVE, 2026-08-14 — this is the scope, not a tuning choice:**

> docpluck's focus is **English papers in US locale formatting**. We do not know
> how to handle EU numbers or conversions, and those will be **passed as-is**.
> All "fixes" converting EU to US are to be **stopped**.

So `A3` (European decimal comma, operator-gated) and `A3c` (leading-zero decimal)
are DELETED, joining `A3d` (deleted earlier the same day for firing on nothing).

WHY, beyond the directive — the evidence that produced it:

  * Over **297 English papers** from the custodian, `A3` fired **9 times in 2
    papers and not once correctly**: 8 corruptions of mathematical constraints in
    `10.1515/bpasts-2016-0057` (`|S| >= 2,` -> `|S| >= 2.2,`) and one laundered
    author error in `10.1371/journal.pone.0285114` (`M = 26,21` -> `M = 26.21`).
  * `A3c` fired **once** in the same 297 papers, on a URL, producing a link that
    404s (`10.1177/0146167210380928` p13).
  * Where a comma decimal IS genuine — `10.1177/0956797620935584` Table S2 — the
    values are bare table cells with no operator, which `A3` cannot see anyway.

So the conversion rules were not merely risky, they were **not doing the job they
existed for**, while reliably damaging text that was correct.

WHAT THIS MEANS FOR CONSUMERS, stated plainly: a European decimal now arrives
**verbatim**. `d = 0,45` stays `d = 0,45`. That is a coverage change and it is
communicated in the outbound. It is also *recoverable* — the source token is
intact, so a consumer can decide for itself, which it could not do once we had
already converted.
"""

from __future__ import annotations

import pytest

from docpluck.normalize import NormalizationLevel, normalize_text


def _norm(s: str) -> str:
    return normalize_text(s, NormalizationLevel.academic)[0]


@pytest.mark.parametrize(
    "src",
    [
        # A3's target: an operator immediately before the value.
        "the effect was d = 0,45 overall",
        "the mean was M = 12,34 here",
        "the statistic t = 1234,56 held",
        "p < 0,001 in that test",
        "BF >= 3,20 supported it",
        # A3c's target: a leading-zero decimal, bracketed or bare.
        "the p-value was (0,003) overall",
        "the hazard ratio HR 0,92 was reported",
        "reported as [0,05] in the table",
        # A3d's target, already deleted, pinned here too.
        "p = ,025 was reported",
    ],
)
def test_european_numbers_are_passed_through_verbatim(src):
    assert _norm(src) == src, "docpluck converted a European number"


def test_the_real_corpus_sites_are_no_longer_corrupted():
    """The exact shapes measured over 297 English papers."""
    # 10.1515/bpasts-2016-0057 — a mathematical constraint, 8 sites.
    assert "|S|>=>=2,2," in _norm("|S|≥≥2,2,")
    # 10.1371/journal.pone.0285114 — the author's mixed-separator clause.
    assert "M = 26,21, SD = 28.88" in _norm("M = 26,21, SD = 28.88")
    # 10.1177/0146167210380928 p13 — the reference-list URL.
    assert "article/0,9171,1848755,00.html" in _norm(
        "Retrieved from http://content.time.com/time/specials/"
        "article/0,9171,1848755,00.html"
    )


def test_no_conversion_step_is_tracked_any_more():
    """The steps must not exist, not merely stop firing.

    A rule left in place 'disabled' is dead code the next reader re-enables, and
    a step name that is tracked but never fires reports no work rather than
    failing — the shape this project keeps paying for.
    """
    _out, rep = normalize_text(
        "d = 0,45 and (0,003) and p = ,025", NormalizationLevel.academic
    )
    names = list(rep.steps_applied) + list(rep.steps_changed)
    for gone in ("A3_decimal_comma", "A3c_leading_zero", "A3d_leading_comma"):
        assert not any(gone in n for n in names), f"{gone} is back: {names}"


def test_us_notation_is_untouched_by_the_removal():
    """The removal must not disturb correctly-printed US values."""
    for src in ("d = 0.45", "p < .001", "M = 12.34, SD = 1.02"):
        assert _norm(src) == src
