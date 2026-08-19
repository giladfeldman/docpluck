"""A value that already carries a DETACHED minus must never be signed again.

## The defect

``normalize._ALREADY_SIGNED`` is a one-character negative lookbehind::

    _ALREADY_SIGNED = rf"(?<![\\d.{_SIGNED_DASHES}])"

It correctly refuses to re-sign ``-0.38``, where the dash abuts the digit. It
does **not** refuse ``- 0.38``, because the character immediately before the
token is a SPACE — so ``recover_dropped_minus_via_ci_pairing`` (W0g) reads the
estimate as bare-positive ``0.38``, proves it negative from the CI, and emits::

    d = - 0.38   ->   d = - -0.38

a double-signed effect size that no paper printed. This is a FABRICATED value,
the class the project ranks above every other: a wrong number that looks
published.

The comment above ``_SIGNED_DASHES`` records that this class already caused
``-2.68 -> --.68`` in v2.4.62, and states plainly that *"the fix then covered
the one dash form in front of us"*. It covered the ATTACHED form. The detached
form was never considered.

## How it was found

Not by reading the rule. ``tests/test_normalize_idempotent_real_pdf.py``'s
corpus gate went red on ``chen_2021_jesp`` after an unrelated repair
(W0q) made that paper's CI bracket parseable, which let W0g reach an estimate it
had never been able to see. Pass 1 produced ``d = - 0.38``, pass 2 ``d = - -0.38``.
The idempotency gate is the only check that could have caught this, and it did.

Confirmed against the primary source (`10.1016/j.jesp.2021.104154`, rasterized
p13): the page prints ``d = −0.38, 95% CI [−0.58, −0.18]``. pdftotext detaches
every minus in that sentence.
"""

from __future__ import annotations

import pytest

from docpluck.normalize import (
    NormalizationLevel,
    normalize_text,
    recover_dropped_minus_via_ci_pairing,
)

# Every dash form scientific typography uses as a sign, detached by whitespace.
_DETACHED = [
    "d = - 0.38, 95% CI [-0.58, -0.18]",
    "d = − 0.38, 95% CI [-0.58, -0.18]",
    "d = -  0.38, 95% CI [-0.58, -0.18]",      # two spaces
    "d = -\t0.38, 95% CI [-0.58, -0.18]",      # tab
]
# NOT included: `d = -\n0.38`, a sign left at the end of one line with its digits
# wrapped to the next. These rules process one LINE at a time, so the guard
# cannot see it — recorded as a strict xfail in
# `test_w0_minus_lookbehind_completeness.py`, unfixed because no real paper
# exhibits it (pdftotext does not wrap inside a number). It was briefly in this
# list and PASSED VACUOUSLY: the output `d = -\n-0.38` contains neither `--` nor
# `- -`, so the assertion below could not see the very fabrication it checks for.


@pytest.mark.parametrize("record", _DETACHED)
def test_a_detached_minus_is_never_doubled(record):
    out = recover_dropped_minus_via_ci_pairing(record)
    assert out == record, f"a second minus was fabricated: {record!r} -> {out!r}"


def test_an_attached_minus_is_still_not_doubled():
    """The case v2.4.62 already fixed — pinned so the widening cannot regress it."""
    record = "d = -0.38, 95% CI [-0.58, -0.18]"
    assert recover_dropped_minus_via_ci_pairing(record) == record


def test_a_genuinely_bare_estimate_is_still_recovered():
    """The guard must not disarm the rule. With NO sign at all in front of the
    estimate, the CI still proves the dropped minus and W0g must still fire —
    paired with the tests above so an absence assertion cannot be satisfied by
    switching the rule off."""
    record = "d = 0.38, 95% CI [-0.58, -0.18]"
    out = recover_dropped_minus_via_ci_pairing(record)
    assert "d = -0.38" in out, f"the real recovery was disarmed: {out!r}"


def test_the_whole_pipeline_is_idempotent_on_this_shape():
    """The end-to-end invariant the corpus gate enforces: normalizing twice must
    equal normalizing once."""
    text = (
        "S⋅D = 1.43), t(399) = − 3.79, p < .001, d = − 0.38, "
        "95% CI [− 0.58,\n− 0.18]. Similarly, participants"
    )
    once, _ = normalize_text(text, NormalizationLevel.academic)
    twice, _ = normalize_text(once, NormalizationLevel.academic)
    assert once == twice, (
        f"normalization is not idempotent on this shape:\n once={once!r}\ntwice={twice!r}"
    )
    assert "- -" not in twice and "--" not in twice
