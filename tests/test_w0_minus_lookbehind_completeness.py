"""A number that ALREADY carries a minus is never a dropped-minus candidate.

**Every test here was watched FAILING against the unfixed code first.**

Found by the v2.4.128 "sweep for the CLASS, not the instances" pass: three
sibling W0 patterns each guard against re-signing an already-signed number, and
each carried a DIFFERENT exclusion list.

    _CORRUPT_NEG_TOKEN_RE   (?<![\\d.\\-])     hyphen-minus only
    _PROSE_CODING_NEG_RE    (?<![\\d.\\--])    hyphen-minus + U+2212
    _BARE_POS_TOKEN_RE      (?<![\\d.\\-])     hyphen-minus only

Same guard, three spellings, written at three different times — an omission in a
sequence, exactly like the S6 bidi gap fixed in 1.9.50.

REPRODUCED against the production path before the fix, and it is a WRONG NUMBER,
not a cosmetic issue:

    'B = <U+2212>20.09, 95% CI [-0.21, 0.04]'   ->   'B = --0.09, ...'

W0d flips a bare `2X.XX` to `-X.XX` when the recovered reading lands inside the
paired CI and the literal does not. Its guard is meant to stop that when the
token is already signed — but the guard only knew about ASCII hyphen, so a
U+2212 minus sailed past it and the recovery signed the number a SECOND time.
`--0.09` is not merely wrong, it is unparseable: every consumer reads it as a
malformed token or NA.

Reachability, checked rather than assumed: W0d runs at `normalize.py:4278` and
S5 folds U+2212 to ASCII at `:4401`, so W0d sees the raw glyph. The shape needs
the ESTIMATE to carry U+2212 while the CI carries ASCII — which is exactly the
mixed-channel condition this project already has W0g/W0h/W0i for, because a
publisher's math font and its bracket text routinely resolve differently. When
BOTH carry U+2212 the CI parser declines the pairing and nothing fires, which is
why the defect stayed invisible.

The fix replaces all three lists with one shared class, so the next dash form
cannot be missing from one of three places.
"""

from __future__ import annotations

import pytest

from docpluck.normalize import (
    NormalizationLevel,
    normalize_text,
    recover_minus_via_ci_pairing,
)

MINUS = "−"      # MINUS SIGN
EN_DASH = "–"    # EN DASH
NB_HYPHEN = "‑"  # NON-BREAKING HYPHEN


def _norm(text: str) -> str:
    out, _ = normalize_text(text, NormalizationLevel.academic)
    return out.strip()


# ── the defect ──────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "dash,name",
    [(MINUS, "U+2212 MINUS SIGN"),
     (EN_DASH, "U+2013 EN DASH"),
     (NB_HYPHEN, "U+2011 NON-BREAKING HYPHEN")],
)
def test_already_signed_estimate_is_never_signed_again(dash, name):
    """An estimate carrying `dash` must not be re-signed by W0d."""
    src = f"B = {dash}20.09, 95% CI [-0.21, 0.04]"
    out = recover_minus_via_ci_pairing(src)
    assert out == src, f"{name} was treated as an unsigned dropped-minus candidate"


def test_double_minus_never_reaches_the_production_path():
    """The end-to-end shape, through `normalize_text` as consumers call it."""
    out = _norm(f"B = {MINUS}20.09, 95% CI [-0.21, 0.04]")
    assert "--" not in out
    assert f"{MINUS}-" not in out
    # S5 folds U+2212 to ASCII, so the value must arrive as a single-signed -20.09
    assert "-20.09" in out


# ── the recovery this guard must NOT disarm ─────────────────────────────

def test_the_genuine_dropped_minus_recovery_still_fires():
    """A truly UNSIGNED corrupt token still recovers — the guard is not a mute."""
    src = "B = 20.09, 95% CI [-0.21, 0.04]"
    assert recover_minus_via_ci_pairing(src) == "B = -0.09, 95% CI [-0.21, 0.04]"


def test_ascii_hyphen_guard_still_holds():
    """The one dash form the original list did cover."""
    src = "B = -20.09, 95% CI [-0.21, 0.04]"
    assert recover_minus_via_ci_pairing(src) == src


def test_digit_and_dot_guards_still_hold():
    """The rest of the original lookbehind is unchanged."""
    for src in ("B = 120.09, 95% CI [-0.21, 0.04]",
                "B = .20.09, 95% CI [-0.21, 0.04]"):
        assert recover_minus_via_ci_pairing(src) == src


def test_idempotent():
    once = _norm(f"B = {MINUS}20.09, 95% CI [-0.21, 0.04]")
    assert _norm(once) == once


# ── the SAME class again, one release later: the sign may be DETACHED ────
#
# v2.4.134 fixed `- 0.38` -> `- -0.38` at W0g and **only at W0g**, which is the
# same mistake this file was created to end: the v2.4.62 comment above
# `_SIGNED_DASHES` laments that "the fix then covered the one dash form in front
# of us", and the sequel was *the fix covered the one RULE in front of us*.
# Found by an independent review, reproduced on this tree:
#
#     recover_minus_via_ci_pairing('M = - 20.54, SD=0.04, CI = [-0.61, -0.47]')
#         -> 'M = - -0.54, ...'                                    (W0d)
#     recover_prose_two_for_minus('direction: - 20.5 = low, + 0.5 = high')
#         -> 'direction: - -0.5 = low, ...'                        (W0j sig. A)
#
# A one-character lookbehind cannot see past the space, and a DETACHED sign is
# exactly what the fonts these rules exist for produce — `10.1016/j.jesp.2021.104154`
# detaches every minus on its page. So the guard is now a FUNCTION applied at
# each substitution site (`_already_carries_a_sign`), not a lookbehind, because
# the gap is an unbounded whitespace run and Python lookbehinds are fixed-width.

_DETACHED_DASHES = ["-", MINUS, EN_DASH, NB_HYPHEN]


@pytest.mark.parametrize("dash", _DETACHED_DASHES)
@pytest.mark.parametrize("gap", [" ", "  ", "\t"])
def test_w0d_never_signs_a_detached_minus_twice(dash, gap):
    src = f"M = {dash}{gap}20.54, SD=0.04, CI = [-0.61, -0.47]"
    out = recover_minus_via_ci_pairing(src)
    assert out == src, f"W0d re-signed an already-signed estimate: {out!r}"


@pytest.mark.xfail(
    strict=True,
    reason=(
        "KNOWN, UNMEASURED GAP, recorded rather than fixed. These rules process "
        "one LINE at a time, so a sign left at the end of one line with its "
        "digits wrapped to the next is invisible to `_already_carries_a_sign`. "
        "No real paper exhibiting `M = -\\n20.54` has been found — pdftotext does "
        "not wrap inside a number — and this project does not build machinery for "
        "an unobserved shape. STRICT, so that if a future change closes it by "
        "accident this test says so instead of staying quietly green."
    ),
)
def test_a_sign_left_on_the_previous_line_is_not_yet_seen():
    src = "M = -\n20.54, SD=0.04, CI = [-0.61, -0.47]"
    assert recover_minus_via_ci_pairing(src) == src


@pytest.mark.parametrize("dash", _DETACHED_DASHES)
def test_w0j_contrast_note_never_signs_a_detached_minus_twice(dash):
    from docpluck.normalize import recover_prose_two_for_minus

    src = f"direction: {dash} 20.5 = low, + 0.5 = high"
    out = recover_prose_two_for_minus(src)
    assert out == src, f"W0j signature A re-signed an already-signed value: {out!r}"


def test_no_rule_emits_a_double_sign_end_to_end():
    """Through `normalize_text`, as consumers call it. One assertion covering
    every rule, so the next sibling cannot be missed by writing a per-rule test
    for only the rule in front of us."""
    sources = [
        "M = - 20.54, SD = 0.04, CI = [-0.61, -0.47]",
        f"B = {MINUS} 20.09, 95% CI [-0.21, 0.04]",
        "direction: - 20.5 = low, + 0.5 = high",
        "d = - 0.38, 95% CI [-0.58, -0.18]",
    ]
    for src in sources:
        out = _norm(src)
        for bad in ("--", "- -", f"{MINUS}-", f"-{MINUS}"):
            assert bad not in out, f"{src!r} -> {out!r} contains {bad!r}"


@pytest.mark.parametrize("dash", _DETACHED_DASHES)
def test_the_detached_guard_does_not_disarm_the_real_recovery(dash):
    """A genuinely UNSIGNED token still recovers even when a dash appears
    elsewhere on the line — the guard must key on what precedes THIS token, not
    on the line containing a dash anywhere."""
    src = f"Age {dash} related: B = 20.09, 95% CI [-0.21, 0.04]"
    out = recover_minus_via_ci_pairing(src)
    assert "B = -0.09" in out, f"the real recovery was disarmed: {out!r}"
