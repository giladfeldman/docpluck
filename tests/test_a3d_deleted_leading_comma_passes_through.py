"""A3d is DELETED. A leading-comma value passes through verbatim.

WHY THIS RULE EXISTED, AND WHY IT SHOULD NOT HAVE.

A3d converted the "continental" spelling of an APA leading-zero-free value:

    'p = ,025'   ->   'p = .025'

Its justification was the string `p = ,025`. That string was never observed in a
document. It came from a consumer's spec, was copied into a reply doc, then a
handoff, then the CHANGELOG, then `docs/NORMALIZATION.md`, and then into shipped
code — acquiring the appearance of consensus at every hop while remaining ONE
UNCHECKED STRING. It was described as "reproduced against unfixed code", which is
true and irrelevant: running a constructed string through the pipeline proves what
the CODE does, never that the SHAPE OCCURS.

MEASURED, twice, over real English-language articles from the custodian:

    0 sites / 0 papers  in 297 English papers   (tools/diag/repair_site_scan.py, 2026-08-14)
    0 sites / 0 papers  in a prior 600-paper hunt              (2026-08-13)

A rule with no observed input is pure false-positive surface for no measured
benefit. It is deleted rather than merely retired, and deleting it cannot cost any
consumer coverage: it never fired.

CONSUMER-VISIBLE: this is ESCImate shared-spec rule D1b. Their conformance corpus
carries the constructed case, so that case now fails. That divergence is
deliberate, is reported to them in the outbound, and the reason is that the case
has no attested occurrence in 897 papers between us. If they can produce a real
article — DOI and page — that prints this shape, the rule comes back.

Directive: "every rule, guard and case study must be justified by a shape observed
in a REAL document, cited by DOI and page. Never a hypothetical." (2026-08-13)
"""

from __future__ import annotations

import pytest

from docpluck.normalize import NormalizationLevel, normalize_text


def _norm(s: str) -> str:
    return normalize_text(s, NormalizationLevel.academic)[0]


@pytest.mark.parametrize(
    "src,expect",
    [
        ("p = ,025", "p = ,025"),
        ("p < ,001", "p < ,001"),
        ("the effect was d = ,45 overall", "d = ,45"),
        ("r = ,32, p = ,004", "r = ,32, p = ,004"),
        # `≤`/`≥` are canonicalised to `<=`/`>=` by A5. That is NOTATION — the
        # paper printed a correct operator and we spell it in ASCII — and it is
        # orthogonal to this deletion, so the assertion is on the VALUE, which
        # is what A3d used to rewrite.
        ("p ≤ ,05", "<= ,05"),
        ("p ≥ ,05", ">= ,05"),
    ],
)
def test_leading_comma_value_is_passed_through_verbatim(src, expect):
    """docpluck extracts what is printed. If a paper really prints `p = ,025`
    that is the paper's copyediting error, and flagging it is the consumer's
    job — docpluck has no channel to say it repaired anything, so repairing it
    silently would launder the defect."""
    assert expect in _norm(src)


def test_a3d_step_is_gone_from_the_pipeline():
    """The step must not merely stop firing — it must not exist.

    A rule left in place 'disabled' is dead code that the next reader will
    re-enable, and a step name that is tracked but never fires is exactly the
    'reports no work rather than failing' shape this project keeps paying for.
    """
    _out, rep = normalize_text("p = ,025 and d = 0,45", NormalizationLevel.academic)
    names = list(rep.steps_applied) + list(rep.steps_changed)
    assert not any("A3d" in n for n in names), names


def test_sibling_rules_are_ALSO_retired_now():
    """RE-FIXTURED 2026-08-14.

    When A3d was deleted this asserted that its NEIGHBOURS were unchanged — the
    deletion must not be a stealth change to A3 and A3a. That check was correct
    and it did its job. A3 was then deleted in the same release (v2.4.129) and
    A3a in the next (v2.4.130), each on its own measured evidence rather than
    by association, so the assertion is re-pointed rather than dropped.

    Kept because the INVARIANT still matters: after each retirement, a reader
    must be able to see at a glance what the neighbours now do.
    """
    # A3's former target: an operator immediately before the value.
    assert _norm("the effect was d = 0,45 overall") == "the effect was d = 0,45 overall"
    # A3a's former target: a thousands-grouped count.
    assert _norm("N = 1,182 participants") == "N = 1,182 participants"
