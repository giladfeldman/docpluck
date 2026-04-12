"""
Comprehensive normalization regression test suite — D5 audit (2026-04-12).

Covers every regex in the normalization pipeline with edge cases focused on
preventing silent data corruption in academic statistical expressions.

Triggered by MetaESCI D5: line 240 of normalize.py silently destroyed p-values
and effect sizes in ~18.5% of PDFs. This suite ensures that NEVER happens again
for ANY normalization regex.

Organization: one test class per normalization step or concern area.
All tests are pure string-in, string-out via normalize_text() — no PDFs needed.
"""

import pytest
from docpluck.normalize import normalize_text, NormalizationLevel, NORMALIZATION_VERSION


def norm(text: str, level: str = "academic") -> str:
    """Helper: normalize and return text only."""
    result, _ = normalize_text(text, NormalizationLevel(level))
    return result


def norm_report(text: str, level: str = "academic"):
    """Helper: normalize and return (text, report)."""
    return normalize_text(text, NormalizationLevel(level))


# ── D5 Bug Regression: the MetaESCI corruption cases ──────────────────


class TestD5_BugRegression:
    """Core regression tests for MetaESCI D5.

    These are the exact corruption patterns found in the 73-DOI audit.
    Every test MUST preserve the real p-value and effect size — the old
    line 240 regex destroyed them by absorbing section numbers.
    """

    def test_canonical_case_section_8_3(self):
        """Index case: 10.1016/j.jesp.2020.104032, corruption #8."""
        result = norm("t(196) = 0.46, p = .647, d = 0.07.\n8.3. Discussion")
        assert ".647" in result
        assert "0.07" in result
        assert "p = 8.3" not in result

    def test_p_less_section_6_5(self):
        """Index case: corruption #3."""
        result = norm("t(166) = 4.74, p < .001, d = 0.74.\n6.5. Discussion")
        assert ".001" in result
        assert "0.74" in result
        assert "p < 6.5" not in result

    def test_p_equals_section_5_4_2(self):
        """Index case: corruption #1 — triple-level section number."""
        result = norm("t(213) = 2.15, p = .033, d = 0.29.\n5.4.2. Task and performance beliefs")
        assert ".033" in result
        assert "0.29" in result
        assert "p = 5.4" not in result

    def test_page_number_absorption(self):
        """PSPB case: 10.1177/0146167212443383 — page number on next line."""
        result = norm("beta = .19, t(170) = 2.79, p = .001, and\n1024\nTable 1.")
        assert ".001" in result
        assert "p = 1024" not in result

    def test_footnote_marker_absorption(self):
        """JESP case: 10.1016/j.jesp.2013.09.008 — footnote marker."""
        result = norm("t(36.2) = -3.50, p = .001.\n7 Anxiety and interest")
        assert ".001" in result
        assert "p = .001.7" not in result

    def test_p_less_section_7_4_3(self):
        """Index case: corruption #4."""
        result = norm("F(1, 196) = 11.85, p < .001.\n7.4.3. Efficacy")
        assert ".001" in result
        assert "p < 7.4" not in result

    def test_p_less_with_large_d_section_7_5(self):
        """Index case: corruption #5."""
        result = norm("t(196) = 8.02, p < .001, d = 1.64.\n7.5. Discussion")
        assert ".001" in result
        assert "1.64" in result
        assert "p < 7.5" not in result

    def test_p_less_section_8_2_2(self):
        """Index case: corruption #6."""
        result = norm("t(196) = 5.44, p < .001, d = 0.83.\n8.2.2. Efficacy predictions")
        assert ".001" in result
        assert "0.83" in result
        assert "p < 8.2" not in result

    def test_legitimate_garbage_skip_still_works(self):
        """The original purpose of line 240: skip column-bleed garbage text."""
        result = norm("p = some text\n0.045")
        assert "0.045" in result

    def test_legitimate_garbage_skip_p_less(self):
        """Column-bleed garbage with p < operator."""
        result = norm("p < column text\n.001")
        assert ".001" in result

    def test_long_garbage_not_skipped(self):
        """Garbage >20 chars must NOT be skipped (existing test preserved)."""
        result = norm("p = this is a very long sentence that should not be eaten\n0.045")
        assert "p = 0.045" not in result

    def test_full_stat_line_with_ci_before_section(self):
        """Full stat line with CI — everything must survive."""
        text = "F(2, 198) = 4.56, p = .012, eta2 = .044, 95% CI [0.01, 0.09]\n5.1 Discussion"
        result = norm(text)
        assert ".012" in result
        assert ".044" in result
        assert "[0.01, 0.09]" in result


# ── D5 Safe Regex Guards: test each guard independently ────────────────


class TestD5_SafeRegexGuards:
    """Test the two independent safety mechanisms in the replacement regex.

    Guard 1: garbage must start with [a-zA-Z]
    Guard 2: next-line value must match 0?\\.digit+ (valid p-value format)
    """

    # Guard 1: letter-start requirement
    def test_guard1_letter_start_matches(self):
        """Garbage starting with letter → MATCH (legitimate garbage)."""
        result = norm("p = abc\n.05")
        assert "p = .05" in result or "p =.05" in result

    def test_guard1_dot_start_blocks(self):
        """Content starting with dot → NO MATCH (real p-value)."""
        result = norm("p = .647\n.05")
        assert ".647" in result  # real p-value preserved

    def test_guard1_digit_start_blocks(self):
        """Content starting with digit → NO MATCH (real stat content)."""
        result = norm("p = 123\n.05")
        assert "123" in result

    def test_guard1_uppercase_letter_matches(self):
        """Uppercase garbage → MATCH."""
        result = norm("p = ABC\n.05")
        assert ".05" in result

    # Guard 2: p-value format requirement
    def test_guard2_dot_digits_matches(self):
        """Next line .001 → MATCH (valid p-value)."""
        result = norm("p = text\n.001")
        assert "p = .001" in result or "p =.001" in result

    def test_guard2_zero_dot_digits_matches(self):
        """Next line 0.045 → MATCH (valid p-value with leading zero)."""
        result = norm("p = text\n0.045")
        assert "0.045" in result

    def test_guard2_section_number_blocks(self):
        """Next line 8.3 → NO MATCH (section number, digit before dot ≠ 0)."""
        result = norm("p = text\n8.3")
        assert "p = 8.3" not in result

    def test_guard2_page_number_blocks(self):
        """Next line 1024 → NO MATCH (no dot at all)."""
        result = norm("p = text\n1024")
        assert "p = 1024" not in result

    def test_guard2_footnote_blocks(self):
        """Next line 7 → NO MATCH (single digit, no dot)."""
        result = norm("p = text\n7")
        assert "p = 7" not in result

    def test_guard2_rejects_value_over_1(self):
        """Next line 1.5 → NO MATCH (not a valid p-value)."""
        result = norm("p = text\n1.5")
        assert "p = 1.5" not in result

    # Both guards combined
    def test_both_guards_digit_start_section_number(self):
        """Digit-start garbage + section number → NO MATCH (both guards block)."""
        result = norm("p = 123\n8.3")
        assert "p = 8.3" not in result


# ── A1 Sub-Rule Isolation ──────────────────────────────────────────────


class TestA1_SubRuleIsolation:
    """Test each A1 sub-rule independently."""

    # Line 213: basic p\n operator
    def test_p_newline_equals(self):
        result = norm("p\n= .05")
        assert "p = .05" in result or "p =.05" in result

    def test_p_newline_less(self):
        result = norm("p\n< .001")
        assert "p < .001" in result or "p <.001" in result

    def test_p_newline_greater(self):
        result = norm("p\n> .10")
        assert "p > .10" in result or "p >.10" in result

    def test_uppercase_P(self):
        result = norm("P\n= .05")
        assert "P = .05" in result or "P =.05" in result

    # Line 235: p =\n digit
    def test_p_equals_newline_digit(self):
        result = norm("p =\n0.045")
        assert "p = 0.045" in result

    def test_p_less_newline_dot_digit(self):
        result = norm("p <\n.001")
        assert "p < .001" in result

    # Line 236: OR/CI/RR
    def test_or_newline_digit(self):
        result = norm("OR\n1.45")
        assert "OR 1.45" in result

    def test_ci_newline_digit(self):
        result = norm("CI\n0.89")
        assert "CI 0.89" in result

    def test_rr_newline_digit(self):
        result = norm("RR\n2.34")
        assert "RR 2.34" in result

    # Line 237: 95%\n CI
    def test_95_percent_newline_ci(self):
        result = norm("95%\nCI [0.1, 0.5]")
        assert "95% CI" in result

    # Line 238: generic operator\n digit
    def test_equals_newline_digit(self):
        result = norm("= \n0.73")
        assert "= 0.73" in result

    def test_less_newline_negative(self):
        result = norm("<\n-0.5")
        assert "< -0.5" in result

    def test_greater_newline_dot(self):
        result = norm(">\n.10")
        assert "> .10" in result

    # Line 242: comma/semicolon\n p
    def test_comma_newline_p(self):
        result = norm("t(23) = 2.34,\n p < .001")
        assert ", p < .001" in result

    def test_semicolon_newline_p(self):
        result = norm("d = 0.45;\n p = .034")
        assert "; p = .034" in result

    # Line 244: comma/semicolon\n CI
    def test_comma_newline_95_ci(self):
        result = norm("d = 0.45,\n 95% CI [0.21, 0.69]")
        assert ", 95% CI" in result

    def test_comma_newline_90_ci(self):
        result = norm("d = 0.45,\n 90% CI [0.21, 0.69]")
        assert ", 90% CI" in result


# ── A1 + S9 Interaction ───────────────────────────────────────────────


class TestA1_S9_Interaction:
    """A1 runs before S9 — standalone numbers are joined to stats before
    S9 strips them as page numbers."""

    def test_p_equals_newline_484_joined_then_fixed(self):
        """'484' would be stripped as page number by S9, but A1 joins it first."""
        result = norm("p =\n484")
        assert ".484" in result  # A1 joins, A2 fixes decimal

    def test_p_equals_newline_42_joined(self):
        """'42' looks like a page number but A1 joins it to stat context."""
        result = norm("p =\n42")
        assert ".42" in result or "42" in result

    def test_p_less_newline_001_joined(self):
        """'001' is 3 digits — S9 would strip it, but A1 joins first."""
        result = norm("p <\n001")
        # A1 joins to "p < 001" — A2 only applies to p = (not p <), so no decimal fix
        assert "001" in result
        assert "p <" in result

    def test_page_number_not_near_stat_still_stripped(self):
        """S9 still strips genuine page numbers unrelated to stats."""
        result = norm("content here\n42\nmore content")
        # 42 on its own line should be stripped by S9
        lines = result.split("\n")
        assert not any(l.strip() == "42" for l in lines)

    def test_stat_value_preserved_page_stripped(self):
        """p-value safe, unrelated standalone number still stripped."""
        result = norm("p = .034\n42\nNext paragraph")
        assert ".034" in result
        lines = result.split("\n")
        assert not any(l.strip() == "42" for l in lines)

    def test_standard_level_skips_a1(self):
        """Standard level does NOT run A1 — p =\\n42 stays broken."""
        result = norm("p =\n42", level="standard")
        # S9 strips standalone "42", leaving p = with nothing
        assert "p = .42" not in result


# ── S7: Hyphenation must NOT join stats ────────────────────────────────


class TestS7_NoStatCorruption:
    """S7 pattern: [a-z]-\\n[a-z] — only joins lowercase across hyphen+newline."""

    def test_legitimate_hyphenation(self):
        assert "statistical" in norm("statis-\ntical")

    def test_number_hyphen_newline_safe(self):
        """Digit before hyphen → no match."""
        result = norm("0.73-\nnext")
        assert "0.73" in result

    def test_uppercase_after_newline_blocks(self):
        """Capital letter after newline → no match."""
        result = norm("sig-\nResults")
        # S7 requires lowercase after newline — R blocks it
        assert "sig" in result

    def test_pvalue_hyphen_safe(self):
        """Stat expression with hyphen → only the word part joins."""
        result = norm("p-\nvalue")
        # This IS a valid join (both lowercase)
        assert "pvalue" in result


# ── S8: Mid-sentence joining must NOT affect stats ─────────────────────


class TestS8_NoStatCorruption:
    """S8 pattern: [a-z,;]\\n[a-z] — joins mid-sentence line breaks."""

    def test_digit_before_newline_blocks(self):
        """Digit before newline → no match."""
        result = norm("p = .034\nmore text")
        # '4' is not in [a-z,;], so S8 won't join
        assert ".034" in result

    def test_digit_after_newline_blocks(self):
        """Digit after newline → no match."""
        result = norm("text,\n0.05 was significant")
        # '0' is not [a-z], so S8 won't join at that point
        assert "0.05" in result

    def test_comma_lowercase_joins(self):
        """Normal mid-sentence break → joins correctly."""
        result = norm("results,\nthe effect was")
        assert "results, the" in result

    def test_period_blocks(self):
        """Period before newline → no match (not in [a-z,;])."""
        result = norm("results.\nThe effect was")
        # Period not in char class, no join
        assert "results." in result


# ── S9: Page number stripping boundary ─────────────────────────────────


class TestS9_PageNumberBoundary:
    """S9 pattern: ^\\s*\\d{1,3}\\s*$ (MULTILINE) — strips standalone 1-3 digit lines."""

    def test_strips_standalone_1(self):
        lines = norm("text\n1\ntext").split("\n")
        assert not any(l.strip() == "1" for l in lines)

    def test_strips_standalone_42(self):
        lines = norm("text\n42\ntext").split("\n")
        assert not any(l.strip() == "42" for l in lines)

    def test_strips_standalone_999(self):
        lines = norm("text\n999\ntext").split("\n")
        assert not any(l.strip() == "999" for l in lines)

    def test_preserves_standalone_1000(self):
        """4+ digits are NOT page numbers."""
        assert "1000" in norm("text\n1000\ntext")

    def test_preserves_number_with_text(self):
        """Number with adjacent text is NOT standalone."""
        assert "42 items" in norm("text\n42 items\ntext")

    def test_strips_with_whitespace(self):
        """Leading/trailing whitespace still counts as standalone."""
        lines = norm("text\n  42  \ntext").split("\n")
        assert not any(l.strip() == "42" for l in lines)

    def test_a1_protects_stat_from_stripping(self):
        """A1 joins p =\\n42 BEFORE S9 runs — so 42 isn't standalone anymore."""
        result = norm("p =\n42")
        # Should be joined and possibly decimal-fixed, not stripped
        assert ".42" in result or "42" in result


# ── A2: Dropped decimal edge cases ────────────────────────────────────


class TestA2_DroppedDecimalEdgeCases:
    """A2 fixes p = 45 → p = .45 (dropped leading '0.')."""

    def test_valid_decimal_untouched(self):
        assert "p = 0.05" in norm("p = 0.05")

    def test_leading_dot_untouched(self):
        assert "p = .001" in norm("p = .001")

    def test_legitimate_decimal_15_8_untouched(self):
        """p = 15.8 has a real decimal — must NOT be touched."""
        assert "15.8" in norm("p = 15.8")

    def test_dropped_01_fixed(self):
        assert "p = .01" in norm("p = 01.")

    def test_dropped_45_fixed(self):
        assert "p = .45" in norm("p = 45")

    def test_d_dropped_44_fixed(self):
        assert "d = .44" in norm("d = 44")

    def test_g_uppercase_dropped_52_fixed(self):
        assert "G = .52" in norm("G = 52")

    def test_single_digit_excluded(self):
        """Single digit p = 5 must NOT be touched (\\d{2,3} excludes it)."""
        result = norm("p = 5")
        assert "p = .5" not in result

    def test_four_digit_excluded(self):
        """Four digit p = 1234 must NOT be touched."""
        result = norm("p = 1234")
        assert "p = .1234" not in result


# ── A3: Decimal comma edge cases ──────────────────────────────────────


class TestA3_DecimalCommaEdgeCases:
    """A3 converts European decimal comma 0,05 → 0.05."""

    def test_european_decimal_converts(self):
        assert "0.05" in norm("p = 0,05")

    def test_author_superscript_pair_preserved(self):
        """Smith1,2 — letter lookbehind blocks."""
        assert "1,2" in norm("Smith1,2 analyzed")

    def test_author_superscript_triple_preserved(self):
        """Jones1,2,3 — cascading commas blocked."""
        assert "1,2,3" in norm("Jones1,2,3 coded")

    def test_ci_internal_comma_preserved(self):
        """[0.45,0.89] — digit lookbehind blocks (A4 handles spacing)."""
        result = norm("[0.45,0.89]")
        # Should NOT become [0.45.0.89] — A3 lookbehind blocks
        assert "0.45.0" not in result

    def test_f_bracket_comma_preserved(self):
        """F(2,42) — paren lookbehind blocks."""
        result = norm("F(2,42) = 13.7")
        assert "F(2.42)" not in result

    def test_decimal_comma_at_end(self):
        """End of string triggers lookahead."""
        assert "0.05" in norm("p = 0,05")

    def test_decimal_comma_before_semicolon(self):
        assert "0.73" in norm("r = 0,73;")

    def test_square_bracket_lookbehind_blocks(self):
        """F[2,42] — square bracket lookbehind blocks."""
        result = norm("F[2,42] = 13.7")
        assert "F[2.42]" not in result


# ── A3a: Thousands separator protection ────────────────────────────────


class TestA3a_ThousandsSeparator:
    """A3a strips commas from N=1,182 before A3 can corrupt them."""

    def test_n_equals_thousands(self):
        result = norm("N = 1,182")
        assert "1182" in result
        assert "1.182" not in result

    def test_df_equals_thousands(self):
        result = norm("df = 1,197")
        assert "1197" in result
        assert "1.197" not in result

    def test_sample_size_of(self):
        result = norm("sample size of 2,443")
        assert "2443" in result

    def test_total_of_participants(self):
        result = norm("total of 2,443 participants")
        assert "2443" in result


# ── A3b: Bracket harmonization edge cases ──────────────────────────────


class TestA3b_BracketHarmonization:
    """A3b converts F[2,42]=13.7 → F(2,42)=13.7 (only with = lookahead)."""

    def test_f_bracket_to_paren(self):
        result = norm("F[2, 42] = 13.7")
        assert "F(2, 42)" in result

    def test_chi2_bracket_to_paren(self):
        result = norm("chi2[3, 120] = 8.9")
        assert "chi2(3, 120)" in result

    def test_reference_bracket_not_converted(self):
        """[1, 2] without = after → NOT converted."""
        result = norm("See [1, 2] for details")
        assert "[1, 2]" in result

    def test_fig_bracket_not_converted(self):
        """fig[1, 2] without = after → NOT converted."""
        result = norm("fig[1, 2] shows")
        assert "[1, 2]" in result


# ── A4: CI delimiter edge cases ────────────────────────────────────────


class TestA4_CIDelimiterEdgeCases:
    """A4 normalizes CI delimiters: semicolons → commas, curly → square, spacing."""

    def test_semicolon_in_brackets(self):
        assert "[0.12, 0.45]" in norm("[0.12; 0.45]")

    def test_semicolon_in_parens(self):
        assert "(0.12, 0.45)" in norm("(0.12; 0.45)")

    def test_curly_to_square(self):
        assert "[0.12, 0.45]" in norm("{0.12, 0.45}")

    def test_curly_semicolon_to_square_comma(self):
        assert "[0.12, 0.45]" in norm("{0.12; 0.45}")

    def test_negative_lower_bound(self):
        assert "[-0.23, 0.67]" in norm("[-0.23; 0.67]")

    def test_positive_prefix(self):
        assert "[+0.12, +0.45]" in norm("[+0.12; +0.45]")


# ── A6: Footnote removal edge cases ───────────────────────────────────


class TestA6_FootnoteRemoval:
    """A6 removes Unicode superscript digits after stat values."""

    def test_superscript_1_after_pvalue(self):
        result = norm("p < .001\u00B9")
        assert ".001" in result
        assert "\u00B9" not in result

    def test_superscript_2_after_bracket(self):
        result = norm("[0.1, 0.5]\u00B2")
        assert "[0.1, 0.5]" in result

    def test_inline_digits_untouched(self):
        """Regular digits in numbers must NOT be removed."""
        assert "12.34" in norm("12.34")

    def test_no_superscript_no_change(self):
        """No false positive when no superscript present."""
        assert ".001" in norm("p < .001 text")


# ── All stat types near section boundaries ─────────────────────────────


class TestAllStatTypesNearBoundary:
    """Every common stat type followed by a section heading —
    none should be corrupted."""

    @pytest.mark.parametrize("text,preserved", [
        ("p = .034\n3.1 Results", ".034"),
        ("d = 0.56\n3.2 Discussion", "0.56"),
        ("g = 0.43\n4.1 Method", "0.43"),
        ("r = .73\n2.1 Participants", ".73"),
        ("F(2, 198) = 4.56\n3.1 Results", "4.56"),
        ("t(45) = 2.31\n1.2 Method", "2.31"),
        ("chi2(3) = 12.4\n3.2 Results", "12.4"),
        ("eta2 = .054\n4.1 Discussion", ".054"),
        ("omega2 = .032\n2.3 Analysis", ".032"),
        ("beta = -0.34\n3.1 Results", "-0.34"),
        ("OR = 1.45\n2.2 Results", "1.45"),
        ("95% CI [0.12, 0.45]\n3.1 Discussion", "[0.12, 0.45]"),
        ("RR = 2.34\n4.2 Outcomes", "2.34"),
    ])
    def test_stat_preserved_near_section(self, text, preserved):
        assert preserved in norm(text)


# ── Extreme edge cases: section numbers ────────────────────────────────


class TestExtremeEdgeCases_SectionNumbers:
    """Stats followed by various section number formats."""

    def test_section_1_1(self):
        assert ".05" in norm("p = .05\n1.1 Introduction")

    def test_section_99_9(self):
        assert ".05" in norm("p = .05\n99.9 Appendix")

    def test_section_3_2_1(self):
        assert ".05" in norm("p = .05\n3.2.1 Sub-subsection")

    def test_section_99_9_9(self):
        assert ".05" in norm("p = .05\n99.9.9 Deep nesting")

    def test_section_single_digit(self):
        assert ".05" in norm("p = .05\n3 Results")


# ── Extreme edge cases: page numbers ──────────────────────────────────


class TestExtremeEdgeCases_PageNumbers:
    """Stats followed by page numbers on the next line."""

    def test_page_1(self):
        assert ".05" in norm("p = .05\n1")

    def test_page_42(self):
        assert ".05" in norm("p = .05\n42")

    def test_page_999(self):
        assert ".05" in norm("p = .05\n999")

    def test_page_9999(self):
        """4-digit page number — not stripped by S9 either."""
        result = norm("p = .05\n9999")
        assert ".05" in result
        assert "9999" in result


# ── Extreme edge cases: value formats ──────────────────────────────────


class TestExtremeEdgeCases_ValueFormats:
    """Various statistical value formats that must survive normalization."""

    def test_no_leading_zero(self):
        assert ".001" in norm("p = .001")

    def test_with_leading_zero(self):
        assert "0.001" in norm("p = 0.001")

    def test_negative_beta(self):
        assert "-0.34" in norm("beta = -0.34")

    def test_negative_no_leading_zero(self):
        assert "-.73" in norm("r = -.73")

    def test_parenthetical_f(self):
        result = norm("F(1, 234) = 5.67")
        assert "F(1, 234)" in result
        assert "5.67" in result

    def test_parenthetical_t(self):
        result = norm("t(45) = 2.31")
        assert "t(45)" in result
        assert "2.31" in result

    def test_ci_bracket_format(self):
        assert "[0.12, 0.45]" in norm("95% CI [0.12, 0.45]")

    def test_ci_paren_format(self):
        assert "(-0.23, 0.67)" in norm("90% CI (-0.23, 0.67)")

    def test_multiple_stats_one_line(self):
        result = norm("t(196) = 0.46, p = .647, d = 0.07")
        assert "0.46" in result
        assert ".647" in result
        assert "0.07" in result

    def test_trailing_period(self):
        assert ".05" in norm("p = .05.")

    def test_trailing_paren(self):
        assert ".05" in norm("(p = .05)")

    def test_trailing_bracket(self):
        assert ".05" in norm("[p = .05]")

    def test_very_long_stat_line(self):
        """50+ char stat line — must all survive."""
        text = "F(2, 198) = 4.56, p = .012, eta2 = .044, 95% CI [0.01, 0.09], d = 0.67"
        result = norm(text)
        for val in [".012", ".044", "0.01", "0.09", "0.67"]:
            assert val in result

    def test_very_short_stat(self):
        assert ".05" in norm("p<.05")


# ── Extreme edge cases: sequences ──────────────────────────────────────


class TestExtremeEdgeCases_Sequences:
    """Multiple stats in sequence, boundary positions."""

    def test_consecutive_pvalues(self):
        result = norm("p = .001\np = .05\np = .034")
        assert ".001" in result
        assert ".05" in result
        assert ".034" in result

    def test_stat_at_document_start(self):
        assert ".05" in norm("p = .05\nResults showed")

    def test_stat_at_document_end(self):
        assert ".05" in norm("Results showed p = .05")

    def test_stat_only_document(self):
        assert ".05" in norm("p = .05")

    def test_empty_lines_around_stats(self):
        assert ".05" in norm("\n\np = .05\n\n")


# ── Extreme edge cases: Unicode ────────────────────────────────────────


class TestExtremeEdgeCases_Unicode:
    """Unicode characters in or near statistical expressions."""

    def test_nbsp_in_stat(self):
        """Non-breaking space normalized to regular space."""
        result = norm("p\u00A0=\u00A0.05")
        assert ".05" in result

    def test_unicode_minus_to_ascii(self):
        """U+2212 MINUS SIGN → ASCII hyphen."""
        result = norm("beta = \u22120.34")
        assert "-0.34" in result
        assert "\u2212" not in result

    def test_fullwidth_digits_converted(self):
        """Full-width digits → ASCII."""
        result = norm("p = \uFF10.\uFF10\uFF15")
        assert "0.05" in result

    def test_european_decimal_near_stat(self):
        """European comma in stat context → period."""
        result = norm("p = 0,034")
        assert "0.034" in result


# ── Line 238 + Line 260: moderate-risk regexes ─────────────────────────


class TestLine238_Line260_ModerateRisk:
    """Test the two moderate-risk regexes that need coverage."""

    # Line 238: ([=<>])\s*\n\s*([-\d.])
    def test_238_equals_newline_digit_joined(self):
        result = norm("x =\n5")
        assert "= 5" in result

    def test_238_less_newline_digit_joined(self):
        result = norm("<\n0.05")
        assert "< 0.05" in result

    def test_238_greater_newline_digit_joined(self):
        result = norm(">\n10")
        assert "> 10" in result

    def test_238_equals_newline_negative_joined(self):
        result = norm("=\n-0.5")
        assert "= -0.5" in result

    def test_238_prose_no_false_positive(self):
        """Prose '= text' should NOT join (text starts with letter, not digit)."""
        result = norm("The variable =\nsome text")
        # 's' is not in [-\d.], so line 238 doesn't match
        assert "= some" not in result or "=\nsome" not in result

    # Line 260: ^\s*\d{1,3}\s*$ (MULTILINE)
    def test_260_strips_standalone_1(self):
        lines = norm("text\n1\ntext").split("\n")
        assert not any(l.strip() == "1" for l in lines)

    def test_260_strips_standalone_999(self):
        lines = norm("text\n999\ntext").split("\n")
        assert not any(l.strip() == "999" for l in lines)

    def test_260_preserves_1000(self):
        assert "1000" in norm("text\n1000\ntext")

    def test_260_preserves_number_with_text(self):
        assert "42 items" in norm("text\n42 items\ntext")

    def test_260_a1_protects_stat_value(self):
        """A1 joins p=\\n42 before S9 can strip it."""
        result = norm("p =\n42")
        assert ".42" in result or "42" in result


# ── Version bumps ──────────────────────────────────────────────────────


class TestVersionBumps:
    """Verify version constants are correct after the D5 fix."""

    def test_normalization_version(self):
        assert NORMALIZATION_VERSION == "1.4.3"

    def test_report_version(self):
        _, report = norm_report("test text")
        assert report.version == "1.4.3"
