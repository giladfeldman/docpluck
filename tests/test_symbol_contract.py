"""The published symbol contract is what the code actually does.

`docs/SYMBOL_CONTRACT.md` and `docpluck.symbol_contract()` tell consumers what
docpluck emits for every Greek letter and sub/superscript form. A contract that
drifts from behaviour is worse than no contract, because a consumer builds
patterns against it and cannot see when it stops being true.

So these tests do not restate the table — they assert that the PUBLISHED table
and the SHIPPED behaviour agree, letter by letter, by running normalization.
"""

from __future__ import annotations

import pytest

from docpluck import explain_symbol, symbol_contract
from docpluck.normalize import NormalizationLevel, normalize_text
from docpluck.symbols import (
    GREEK_TO_ASCII,
    GREEK_UPPER_AMBIGUOUS_TO_ASCII,
    SUBSCRIPT_TO_ASCII,
)


def _norm(text: str) -> str:
    out, _ = normalize_text(text, NormalizationLevel.academic)
    return out.strip()


# ── the contract equals the behaviour ───────────────────────────────────

@pytest.mark.parametrize("char,expected", sorted(GREEK_TO_ASCII.items()))
def test_every_published_greek_mapping_is_what_normalization_does(char, expected):
    """Run the letter through the real pipeline and compare to the contract."""
    assert _norm(f"{char} = 1.0") == f"{expected} = 1.0"


@pytest.mark.parametrize("char,expected", sorted(SUBSCRIPT_TO_ASCII.items()))
def test_every_published_subscript_mapping_is_what_normalization_does(char, expected):
    """Contract v2.0: a subscript joins with `_`, it does not fuse."""
    assert _norm(f"M{char} = 1.0") == f"M_{expected} = 1.0"


@pytest.mark.parametrize("char,expected", sorted(GREEK_UPPER_AMBIGUOUS_TO_ASCII.items()))
def test_ambiguous_capitals_map_only_when_standalone(char, expected):
    """Both halves of the published rule, for every member."""
    assert _norm(f"{char} = .31") == f"{expected} = .31"
    # inside a word, and hyphen-joined, it must survive untouched
    assert char in _norm(f"pre{char}post")
    assert char in _norm(f"within-{char} design")


# ── the letters the user named explicitly ───────────────────────────────

def test_the_three_collisions_that_motivated_the_contract():
    assert _norm("β = -.02") == "beta = -.02"
    assert _norm("χ²(2) = 5.10") == "chi2(2) = 5.10"
    assert _norm("ρ = .31") == "rho = .31"
    # and none of the short forms survive anywhere
    for bad in ("ch2(", "b = -.02", "r = .31"):
        assert bad not in _norm("β = -.02 χ²(2) = 5.10 ρ = .31")


def test_the_whole_alphabet_is_covered():
    """No lowercase Greek letter passes through untransliterated."""
    alphabet = "αβγδεζηθικλμνξοπρστυφχψω"
    out = _norm(" ".join(f"{c} = 1.0" for c in alphabet))
    for c in alphabet:
        assert c not in out, f"{c!r} survived academic normalization"


# ── the contract's own shape ────────────────────────────────────────────

def test_contract_exposes_everything_a_consumer_needs():
    c = symbol_contract()
    for key in ("version", "greek", "greek_ambiguous_upper", "superscript",
                "subscript", "positional_rules"):
        assert key in c, key
    assert c["greek"]["χ"] == "chi"
    assert c["subscript"]["ₚ"] == "p"
    # the positional rules are prose, but they must be PRESENT — they are the
    # part no lookup table can express
    assert "superscript_after_digit_is_an_exponent" in c["positional_rules"]
    assert "subscripts_join_with_an_underscore" in c["positional_rules"]
    assert "multiplication_sign_becomes_star" in c["positional_rules"]


def test_contract_is_a_copy_not_the_live_table():
    """A consumer mutating the returned dict must not corrupt the library."""
    c = symbol_contract()
    c["greek"]["χ"] = "WRONG"
    assert symbol_contract()["greek"]["χ"] == "chi"
    assert _norm("χ = 1.0") == "chi = 1.0"


def test_explain_symbol_covers_each_class():
    assert "chi" in explain_symbol("χ")
    assert "standalone" in explain_symbol("Β")
    assert "caret" in explain_symbol("⁹")
    assert "'_p'" in explain_symbol("ₚ")
    assert "not transliterated" in explain_symbol("Z")


def test_the_docs_page_exists_and_names_the_contract_version():
    """The prose contract must not silently fall out of the repo."""
    from pathlib import Path

    doc = Path(__file__).resolve().parents[1] / "docs" / "SYMBOL_CONTRACT.md"
    assert doc.is_file(), "docs/SYMBOL_CONTRACT.md is what consumers are pointed at"
    text = doc.read_text(encoding="utf-8")
    assert symbol_contract()["version"] in text, (
        "the docs page states a different contract version than the code"
    )
