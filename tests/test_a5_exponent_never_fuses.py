"""A5 never fuses a superscript digit into the number in front of it.

**Every test here was watched FAILING against the unfixed code first.**

THE DEFECT, reproduced against the shipped production path:

    'leucocyte count (×10⁹/L)'        ->  'leucocyte count (x109/L)'
    '∼5×10⁶ possible architectures'   ->  '∼5x106 possible architectures'
    '130×10³ variations'              ->  '130x103 variations'
    'p < .001¹'                       ->  'p < .0011'
    'N = 42³'                         ->  'N = 423'

A5 flattens superscript digits to ASCII so downstream regexes can match
`eta2`/`chi2`. After a LETTER that is exactly right — `η²` is one symbol whose
flat spelling is `eta2`. After a DIGIT it is catastrophic: the superscript is an
EXPONENT, and flattening fuses it into the mantissa. `×10⁹/L` becoming `x109/L`
is a clinical lab value nine orders of magnitude wrong, and unrecoverable — no
consumer can tell `109` from a fused `10⁹`.

HOW IT HID. `docs/FINDINGS_2026-08-13` analysed exactly these tokens
(`×10⁹/L`, `∼5×10⁶`, `130×10³`) as the reason decision D4 must NOT delete
superscript digits from body text — "deleting the 9 loses nine orders of
magnitude". The analysis was correct and the decision was right, but it examined
a PROPOSED deletion rule while the SHIPPED flattening rule was already doing
equivalent damage to the same tokens. The hazard was named, the existing
behaviour was never checked against it.

Compounding it: A6 (`A6_footnote_removal`) exists to strip exactly these markers
and its comment gives `'p < .001¹' -> 'p < .001'` as its worked example. Its
regex looks for a UNICODE superscript, but A5 has already converted every one of
them to ASCII, so in the academic path A6 can never match. A step that documents
a behaviour it cannot perform is the "no pretending" rule's exact target — and
it is why the fusion went unnoticed, since the step that was supposed to catch
it reported no work rather than failing.

THE RULE, minimal and structural: a superscript run IMMEDIATELY PRECEDED BY AN
ASCII DIGIT becomes caret notation and is never fused. Everything else keeps
today's behaviour, so `η²`/`χ²`/`R²adj` are untouched and the blast radius is
exactly the tokens that were being corrupted.

Caret is the right target rather than "leave the Unicode": it is flat ASCII, it
is unambiguous, and it is what the consumer already produces internally —
effectcheck's own normalizer folds Unicode superscripts into caret notation
before its extraction regexes run, so `10^9` is a form it already understands. (Contract v2.0 also emits `*` rather than
the letter `x` for U+00D7, so the shipped form is `*10^9/L`.)

A residual ambiguity, stated rather than hidden: `N = 42³` may be a footnote
marker rather than 42-cubed, and nothing in the text channel decides which.
`42^3` keeps both readings recoverable where `423` destroys them — the same
principle A3 uses for an ambiguous comma.
"""

from __future__ import annotations

import pytest

from docpluck.normalize import NormalizationLevel, normalize_text


def _norm(text: str) -> str:
    out, _ = normalize_text(text, NormalizationLevel.academic)
    return out.strip()


# ── the wrong numbers ───────────────────────────────────────────────────

@pytest.mark.parametrize(
    "src,expected",
    [
        ("leucocyte count (×10⁹/L)", "leucocyte count (*10^9/L)"),
        ("∼5×10⁶ possible architectures", "∼5*10^6 possible architectures"),
        ("130×10³ variations", "130*10^3 variations"),
        ("a rate of 2×10⁻⁶ per year", "a rate of 2*10^-6 per year"),
        ("10¹² operations", "10^12 operations"),
    ],
)
def test_scientific_notation_keeps_its_magnitude(src, expected):
    assert _norm(src) == expected


def test_footnote_marker_after_a_pvalue_does_not_change_the_pvalue():
    """`.0011` is a different p-value from `.001`. `.001^1` is not."""
    out = _norm("p < .001¹ and the effect held")
    assert ".0011" not in out
    assert ".001" in out


def test_footnote_marker_after_a_sample_size_does_not_change_it():
    out = _norm("N = 42³")
    assert "423" not in out
    assert "42" in out


# ── what must NOT change: the case A5 exists for ────────────────────────

@pytest.mark.parametrize(
    "src,expected",
    [
        ("η² = 0.005", "eta2 = 0.005"),
        ("χ²(2) = 5.10", "chi2(2) = 5.10"),
        ("ω² = 0.12", "omega2 = 0.12"),
        ("R²adj = .31", "R2adj = .31"),
        ("the x² term", "the x2 term"),
    ],
)
def test_letter_preceded_superscripts_still_flatten(src, expected):
    """A superscript after a LETTER is part of the symbol's name, not an
    exponent — this is the behaviour A5 was written for and it is unchanged."""
    assert _norm(src) == expected


def test_subscripts_take_the_underscore_rule_not_the_caret_rule():
    """A different Unicode block and a different meaning — no interaction.

    Contract v2.0 joins a subscript with `_`; the caret rule is superscript-
    only. Pinned together so the two positional rules cannot be conflated.
    """
    assert _norm("BF₀₁ = 3.2") == "BF_01 = 3.2"
    assert _norm("M₁ = 4.5") == "M_1 = 4.5"


def test_render_path_still_preserves_source_glyphs():
    out, _ = normalize_text(
        "leucocyte count (×10⁹/L)",
        NormalizationLevel.academic,
        preserve_math_glyphs=True,
    )
    assert out.strip() == "leucocyte count (×10⁹/L)"


def test_idempotent():
    once = _norm("count (×10⁹/L), 5×10⁶ cells, η² = 0.005")
    assert _norm(once) == once


def test_no_bare_superscript_survives_the_academic_path():
    """The flattening contract still holds — nothing is left as a live glyph."""
    out = _norm("count (×10⁹/L) and η² = 0.005 and 2×10⁻⁶")
    for ch in "⁰¹²³⁴⁵⁶⁷⁸⁹⁻⁺":
        assert ch not in out, f"{ch!r} survived academic normalization"
