"""One library, one Greek convention. The SMP recovery table had its own.

**Every test here was watched FAILING against the unfixed code first.**

`extract.py::recover_via_pdfplumber` is a fallback for PDFs whose fonts encode
text in the Unicode SMP math-italic planes — pdftotext emits U+FFFD for those,
pdfminer decodes them. It carries a Greek-to-ASCII table, and its docstring says
that table exists

    "so downstream regex patterns work normally"

It did the opposite. Measured, 9 of 9 shared letters disagreed with A5, the
normalization step that defines this library's Greek convention everywhere else:

    codepoint                     extract.py    A5
    U+1D6FC MATH ITALIC ALPHA     'a'           'alpha'
    U+1D6FD MATH ITALIC BETA      'b'           'beta'
    U+1D6FF MATH ITALIC DELTA     'd'           'delta'
    U+1D702 MATH ITALIC ETA       'n'           'eta'
    U+1D707 MATH ITALIC MU        'm'           'mu'
    U+1D70C MATH ITALIC RHO       'r'           (unmapped)
    U+1D70E MATH ITALIC SIGMA     's'           'sigma'
    U+1D711 MATH ITALIC PHI       'ph'          'phi'
    U+1D712 MATH ITALIC CHI       'ch'          'chi'

Every disagreement is a silent failure downstream, and three are collisions with
a DIFFERENT statistic:

    chi2(2) = 5.10  ->  'ch2(2) = 5.10'   effectcheck matches `chi2(`; this
                                          matches nothing, so a chi-square test
                                          is silently never checked
    eta2            ->  'n2'              collides with n, the SAMPLE SIZE
    beta = -.02     ->  'b = -.02'        collides with b, the UNSTANDARDIZED
                                          coefficient — which is precisely the
                                          corruption W0m (v2.4.117) was written
                                          to detect and undo using layout font
                                          evidence. One path manufactured the
                                          defect another path exists to repair.
    rho = .31       ->  'r = .31'         collides with r, the CORRELATION

Found by an adversarial disambiguation analysis (Sonnet, 2026-08-13) and
reproduced here against the unfixed table before changing anything.

The table now spells the letters out, matching A5. That is the convention every
consumer already parses, and it is what the docstring always claimed.

Scope: this path fires only on SMP-encoded PDFs (the math-italic font families
used by some Nature/Cell-family journals), so the blast radius is exactly those
documents — where the current output is wrong.
"""

from __future__ import annotations

import pytest

from docpluck.extract import _SMP_GREEK_TO_ASCII
from docpluck.normalize import NormalizationLevel, normalize_text

# Each math-italic codepoint paired with the plain Greek letter it IS, so the
# two tables can be compared through the same lens rather than by eye.
MATH_ITALIC_TO_PLAIN = {
    0x1D6FC: "α", 0x1D6FD: "β", 0x1D6FE: "γ", 0x1D6FF: "δ",
    0x1D700: "ε", 0x1D701: "ζ", 0x1D702: "η", 0x1D703: "θ",
    0x1D707: "μ", 0x1D70B: "π", 0x1D70C: "ρ", 0x1D70E: "σ",
    0x1D711: "φ", 0x1D712: "χ", 0x1D713: "ψ",
}


def _a5(ch: str) -> str:
    out, _ = normalize_text(ch, NormalizationLevel.academic)
    return out.strip()


@pytest.mark.parametrize(
    "codepoint,expected",
    [
        (0x1D6FC, "alpha"), (0x1D6FD, "beta"), (0x1D6FE, "gamma"),
        (0x1D6FF, "delta"), (0x1D700, "epsilon"), (0x1D701, "zeta"),
        (0x1D702, "eta"), (0x1D703, "theta"), (0x1D707, "mu"),
        (0x1D70B, "pi"), (0x1D70C, "rho"), (0x1D70E, "sigma"),
        (0x1D711, "phi"), (0x1D712, "chi"), (0x1D713, "psi"),
    ],
)
def test_smp_greek_spells_the_letter_out(codepoint, expected):
    assert _SMP_GREEK_TO_ASCII[chr(codepoint)] == expected


@pytest.mark.parametrize(
    "codepoint,plain",
    sorted((cp, ch) for cp, ch in MATH_ITALIC_TO_PLAIN.items()
           if ch in "αβδημσφχ"),  # the letters A5 itself maps
)
def test_the_two_tables_now_AGREE(codepoint, plain):
    """The invariant, stated as an invariant rather than as 15 constants.

    Two implementations of one rule, with no shared test, WILL diverge — in
    both directions. This test is the shared test.
    """
    assert _SMP_GREEK_TO_ASCII[chr(codepoint)] == _a5(plain)


def test_the_three_collisions_are_gone():
    """Each of these used to produce a DIFFERENT statistic's symbol."""
    assert _SMP_GREEK_TO_ASCII[chr(0x1D702)] != "n", "eta collided with sample size n"
    assert _SMP_GREEK_TO_ASCII[chr(0x1D6FD)] != "b", "beta collided with coefficient b"
    assert _SMP_GREEK_TO_ASCII[chr(0x1D70C)] != "r", "rho collided with correlation r"


def test_chi_square_survives_the_smp_path_into_a_matchable_token():
    """End to end: the shape effectcheck actually looks for."""
    smp = chr(0x1D712) + "2(2) = 5.10, p = .078"
    recovered = "".join(_SMP_GREEK_TO_ASCII.get(c, c) for c in smp)
    out, _ = normalize_text(recovered, NormalizationLevel.academic)
    assert "chi2(2)" in out


def test_latin_math_italic_letters_are_unchanged():
    """The table's Latin half was never in question — pin it so it stays."""
    from docpluck.extract import _smp_to_ascii_map

    m = _smp_to_ascii_map()
    assert m[chr(0x1D434)] == "A"   # MATHEMATICAL ITALIC CAPITAL A
    assert m[chr(0x1D44E)] == "a"   # MATHEMATICAL ITALIC SMALL A
    assert m[chr(0x1D467)] == "z"   # MATHEMATICAL ITALIC SMALL Z
