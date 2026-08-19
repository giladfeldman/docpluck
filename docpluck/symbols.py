"""THE canonical symbol contract: one table, one convention, publicly readable.

Every consumer of docpluck parses flat ASCII. This module defines exactly what
docpluck emits for every Greek letter and every sub/superscript form it
transliterates, so a consumer can build its patterns against a published
contract instead of guessing from samples.

**Why this module exists.** Until v2.4.128 the same Greek letter could leave
docpluck spelled two different ways depending on which extraction path handled
the document:

    codepoint                    extract.py fallback    normalize.py A5
    MATHEMATICAL ITALIC CHI      'ch'                   'chi'
    MATHEMATICAL ITALIC ETA      'n'                    'eta'
    MATHEMATICAL ITALIC BETA     'b'                    'beta'
    MATHEMATICAL ITALIC RHO      'r'                    (unmapped)

Two implementations of one concept, no shared test, and they had diverged on 9
of 9 shared letters. The consequences were silent and three were COLLISIONS with
a different statistic: `chi2(2)` became `ch2(2)` so a consumer matching `chi2(`
never checked that chi-square test; `eta2` became `n2`, colliding with the
sample size; `beta` became `b`, colliding with the unstandardized coefficient —
the very corruption another docpluck module exists to undo.

A library that can convert one input two ways has no contract at all. This
module is the single source of truth, and both paths now read it.

**For consumers.** Call :func:`symbol_contract` to get the whole thing as data:

    >>> from docpluck import symbol_contract
    >>> c = symbol_contract()
    >>> c["greek"]["\\u03c7"]
    'chi'
    >>> c["version"]                                    # doctest: +SKIP
    '2.0'

Build your patterns from that dict rather than hard-coding a copy — a
hand-maintained copy is exactly the drift this module was created to end.
`docs/SYMBOL_CONTRACT.md` is the prose version.
"""

from __future__ import annotations

# Bumped when the contract CHANGES — a consumer can pin or assert on it.
# Independent of the package version: most releases do not touch this.
SYMBOL_CONTRACT_VERSION = "2.0"


# ── Greek ───────────────────────────────────────────────────────────────
#
# Every letter spelled out in full. `chi`, never `ch`; `rho`, never `r`; `beta`,
# never `b`. The short forms are ambiguous against Latin statistical symbols
# that mean something else entirely (b, n, r, s, d are all real statistics), and
# ambiguity in this table is indistinguishable downstream from a real value.
GREEK_LOWER_TO_ASCII = {
    "α": "alpha", "β": "beta", "γ": "gamma", "δ": "delta", "ε": "epsilon",
    "ζ": "zeta", "η": "eta", "θ": "theta", "ι": "iota", "κ": "kappa",
    "λ": "lambda", "μ": "mu", "ν": "nu", "ξ": "xi", "ο": "omicron",
    "π": "pi", "ρ": "rho", "σ": "sigma", "ς": "sigma", "τ": "tau",
    "υ": "upsilon", "φ": "phi", "χ": "chi", "ψ": "psi", "ω": "omega",
}

# Variant codepoints for letters already above. A publisher's font decides which
# one lands in the text, and the SAME statistic must not flatten or survive
# depending on that choice — U+03D5 GREEK PHI SYMBOL is the phi COEFFICIENT and
# was unmapped while U+03C6 GREEK SMALL LETTER PHI was mapped (39 occurrences in
# 3 of 250 corpus papers, including a "95% CI for phi" table header).
GREEK_VARIANT_TO_ASCII = {
    "ϕ": "phi",      # U+03D5 GREEK PHI SYMBOL
    "ϑ": "theta",    # U+03D1 GREEK THETA SYMBOL
    "ϵ": "epsilon",  # U+03F5 GREEK LUNATE EPSILON SYMBOL
    "ϰ": "kappa",    # U+03F0 GREEK KAPPA SYMBOL
    "ϖ": "pi",       # U+03D6 GREEK PI SYMBOL
    "ϱ": "rho",      # U+03F1 GREEK RHO SYMBOL
    "ϐ": "beta",     # U+03D0 GREEK BETA SYMBOL
}

# Uppercase Greek with NO Latin lookalike — unambiguously Greek, always mapped.
GREEK_UPPER_TO_ASCII = {
    "Γ": "Gamma", "Δ": "Delta", "Θ": "Theta", "Λ": "Lambda", "Ξ": "Xi",
    "Π": "Pi", "Σ": "Sigma", "Φ": "Phi", "Ψ": "Psi", "Ω": "Omega",
}

# Uppercase Greek that is VISUALLY IDENTICAL to a Latin capital.
#
# These are mapped ONLY when the character stands alone as a token. A broken
# font encoding that emits Greek Alpha for a Latin A inside a word would
# otherwise turn `ANOVA` into `AlphaNOVA` — corrupting prose to fix a symbol.
# Standalone, the codepoint is the only evidence available and it says Greek:
# an author who meant the letter A would have typed the Latin A.
#
# Measured: 1 occurrence in 40 sampled papers (a `Β` column header for
# standardized coefficients, where `Beta` is the correct reading).
GREEK_UPPER_AMBIGUOUS_TO_ASCII = {
    "Α": "Alpha", "Β": "Beta", "Ε": "Epsilon", "Ζ": "Zeta", "Η": "Eta",
    "Ι": "Iota", "Κ": "Kappa", "Μ": "Mu", "Ν": "Nu", "Ο": "Omicron",
    "Ρ": "Rho", "Τ": "Tau", "Υ": "Upsilon", "Χ": "Chi",
}

#: Everything mapped unconditionally, wherever it appears.
GREEK_TO_ASCII: dict[str, str] = {
    **GREEK_LOWER_TO_ASCII,
    **GREEK_VARIANT_TO_ASCII,
    **GREEK_UPPER_TO_ASCII,
}


# ── sub/superscripts ────────────────────────────────────────────────────

SUPERSCRIPT_TO_ASCII = {
    "⁰": "0", "¹": "1", "²": "2", "³": "3", "⁴": "4",
    "⁵": "5", "⁶": "6", "⁷": "7", "⁸": "8", "⁹": "9",
    "⁺": "+", "⁻": "-",
}

SUBSCRIPT_TO_ASCII = {
    "₀": "0", "₁": "1", "₂": "2", "₃": "3", "₄": "4",
    "₅": "5", "₆": "6", "₇": "7", "₈": "8", "₉": "9",
    # Latin subscript letters, U+2090-U+209C (complete block)
    "ₐ": "a", "ₑ": "e", "ₒ": "o", "ₓ": "x", "ₔ": "e",
    "ₕ": "h", "ₖ": "k", "ₗ": "l", "ₘ": "m", "ₙ": "n",
    "ₚ": "p", "ₛ": "s", "ₜ": "t",
    # Phonetic Latin subscripts, U+1D62-U+1D65
    "ᵢ": "i", "ᵣ": "r", "ᵤ": "u", "ᵥ": "v",
    # Greek subscripts, U+1D66-U+1D6A — Greek spelling, as above
    "ᵦ": "beta", "ᵧ": "gamma", "ᵨ": "rho", "ᵩ": "phi", "ᵪ": "chi",
}


# ── the rules a table cannot express ────────────────────────────────────

#: Behaviour that is positional rather than per-character. Published so a
#: consumer can reproduce docpluck's output exactly rather than approximating it.
POSITIONAL_RULES = {
    "superscript_after_digit_is_an_exponent": (
        "A superscript run directly after an ASCII digit is an EXPONENT and "
        "becomes caret notation, never a bare digit: '10⁹' -> '10^9'. "
        "Flattening it would FUSE it into the mantissa ('×10⁹/L' -> 'x109/L', "
        "nine orders of magnitude, unrecoverable). After a LETTER it is a "
        "symbol suffix and does flatten: 'η²' -> 'eta2'."
    ),
    "ambiguous_uppercase_greek_needs_a_standalone_token": (
        "The Greek capitals that look identical to Latin capitals (see "
        "GREEK_UPPER_AMBIGUOUS_TO_ASCII) are transliterated ONLY when the "
        "character stands alone as a token, so a broken font encoding cannot "
        "turn 'ANOVA' into 'AlphaNOVA'."
    ),
    "subscripts_join_with_an_underscore": (
        "A subscript RUN becomes '_' + its ASCII, attached to the token before "
        "it: 'eta2_p', 'M_p', 'H_a', 'M_beta', 'BF_01'. ONE underscore per run, "
        "not per character. Contract v1.0 FUSED subscripts ('eta2p', 'Mp', "
        "'Mbeta'), which produced tokens that read as something else -- the 'p' "
        "of partial eta-squared collides with a p-value, and 'Mp' is "
        "indistinguishable from a variable of that name. The underscore is "
        "inserted only when the run follows a word character."
    ),
    "multiplication_sign_becomes_star": (
        "U+00D7 becomes '*': '2 × 3 design' -> '2 * 3 design', "
        "'×10⁹/L' -> '*10^9/L'. Contract v1.0 used the letter 'x', "
        "which is indistinguishable from a variable named x. A significance "
        "star is positionally distinct -- it TRAILS a value, it never sits "
        "between two operands."
    ),
    "render_path_preserves_source_glyphs": (
        "None of this applies when preserve_math_glyphs=True (the /render "
        "path), which is deliberately source-faithful. The transliterations "
        "here describe the `academic` normalization level that statistics "
        "consumers read."
    ),
}


def symbol_contract() -> dict:
    """The whole contract as plain data, for consumers to build patterns from.

    Returns a dict with keys ``version``, ``greek``, ``greek_ambiguous_upper``,
    ``superscript``, ``subscript`` and ``positional_rules``.

    Prefer this over hard-coding a copy of any table. A hand-maintained copy in
    a consumer is the same drift this module was created to end — citelink
    already keeps its own copy of docpluck's ligature map, and effectcheck its
    own locale inference.
    """
    return {
        "version": SYMBOL_CONTRACT_VERSION,
        "greek": dict(GREEK_TO_ASCII),
        "greek_ambiguous_upper": dict(GREEK_UPPER_AMBIGUOUS_TO_ASCII),
        "superscript": dict(SUPERSCRIPT_TO_ASCII),
        "subscript": dict(SUBSCRIPT_TO_ASCII),
        "positional_rules": dict(POSITIONAL_RULES),
    }


def explain_symbol(char: str) -> str:
    """Human-readable answer to "what does docpluck do with this character?".

    Intended for consumer developers debugging a pattern that did not match.

        >>> explain_symbol("\\u03c7")
        "U+03C7 GREEK SMALL LETTER CHI -> 'chi' (always)"
    """
    import unicodedata

    if not char:
        return "empty input"
    ch = char[0]
    name = unicodedata.name(ch, f"U+{ord(ch):04X}")
    label = f"U+{ord(ch):04X} {name}"
    if ch in GREEK_TO_ASCII:
        return f"{label} -> {GREEK_TO_ASCII[ch]!r} (always)"
    if ch in GREEK_UPPER_AMBIGUOUS_TO_ASCII:
        return (
            f"{label} -> {GREEK_UPPER_AMBIGUOUS_TO_ASCII[ch]!r} ONLY as a "
            "standalone token; left alone inside a word (it is visually "
            "identical to a Latin capital)"
        )
    if ch in SUPERSCRIPT_TO_ASCII:
        return (
            f"{label} -> {SUPERSCRIPT_TO_ASCII[ch]!r} after a letter; after a "
            f"DIGIT the run becomes caret notation ('10⁹' -> '10^9')"
        )
    if ch in SUBSCRIPT_TO_ASCII:
        return (
            f"{label} -> '_{SUBSCRIPT_TO_ASCII[ch]}' — a subscript run joins the "
            f"token before it with a single underscore (BF01 -> 'BF_01')"
        )
    return f"{label} -> not transliterated; passes through unchanged"
