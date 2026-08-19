"""Contract + real-PDF regression tests for v2.4.28 A3c leading-zero
decimal recovery (cycle 14, HANDOFF_2026-05-14 deferred item D).

A3's lookbehind ``(?<![a-zA-Z,0-9\\[\\(])`` blocks legitimate
European-decimal p-values inside parens or brackets — e.g.
``(0,003)`` stays as ``(0,003)`` instead of normalizing to
``(0.003)``. This is because A3 also needs to protect df-bracket
forms like ``F(2,42)`` and citation superscripts like ``Smith1,3``.

A3c adds a more targeted rule that handles ONLY the leading-zero
decimal form (``0,XX``-``0,XXXX``) regardless of lookbehind, since
that pattern is unambiguous: df values never start with 0, citation
superscripts never start with 0.
"""

from __future__ import annotations

from docpluck.normalize import NormalizationLevel, normalize_text


def _normalize(text: str) -> str:
    out, _ = normalize_text(text, NormalizationLevel.academic)
    return out.strip()


# ---- A3c positive cases ----------------------------------------------------


class TestA3cLeadingZeroPositive:
    """A3c's former POSITIVE cases. Every one now passes through UNCHANGED.

    These also pin the v2.4.129 fix for a sibling A3c had been MASKING: with
    A3c gone, ``(0,003)`` reached A4's delimiter-spacing arm intact for the
    first time and became ``(0, 003)`` — a European p-value rendered as a
    two-element pair. A3c had been inventing the DECIMAL reading; A4 invented
    the SEPARATOR reading. Removing a rule can expose one it was masking, so
    the assertions below are exact equality, not substring.
    """

    def test_paren_p_value_three_digit(self):
        assert _normalize("(0,003)") == "(0,003)"

    def test_paren_p_value_two_digit(self):
        assert _normalize("(0,05)") == "(0,05)"

    def test_paren_p_value_four_digit(self):
        assert _normalize("(0,0001)") == "(0,0001)"

    def test_bracket_form(self):
        assert _normalize("[0,05]") == "[0,05]"

    def test_paren_with_p_less_than(self):
        assert _normalize("(p < 0,001)") == "(p < 0,001)"

    def test_unbracketed_also_passes_through(self):
        # A3 (not A3c) used to handle this; A3 is deleted too.
        assert _normalize("p = 0,003") == "p = 0,003"

    def test_after_comma_in_citation_context(self):
        assert _normalize("Smith, 0,003") == "Smith, 0,003"


# ---- A3c negative cases (must NOT fire) -----------------------------------


class TestA3cLeadingZeroNegative:
    def test_df_bracket_not_touched(self):
        # F(2,42) — first digit is 2, A3c requires leading zero.
        # (Note: an unrelated punctuation-cleanup step adds a space
        # after the comma. Important point is the digits aren't
        # re-arranged as decimals.)
        result = _normalize("F(2,42)")
        assert "F(2" in result
        assert "0.42" not in result and "2.42" not in result

    def test_single_digit_after_comma_skipped(self):
        # [0,5] is ambiguous (range vs decimal) — A3c skips it.
        result = _normalize("[0,5]")
        assert "0.5" not in result

    def test_five_plus_digits_after_comma_skipped(self):
        # 0,12345 — unlikely to be a p-value (would be written
        # scientific notation); A3c's max 4 digits skips it.
        result = _normalize("0,12345 something")
        assert "0.12345" not in result

    def test_non_leading_zero_skipped(self):
        # "1,003 participants" — handled by A3a thousands-separator
        # protection, not A3c.
        result = _normalize("1,003 participants")
        assert "1.003" not in result
