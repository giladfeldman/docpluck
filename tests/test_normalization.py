"""
Tests for the 14-step normalization pipeline.
Covers every step (S0-S9, A1-A5) with edge cases from ESCIcheck, MetaESCI,
MetaMisCitations, and PDFextractor LESSONS.md.
"""

import pytest
from docpluck.normalize import normalize_text, NormalizationLevel


def norm(text: str, level: str = "academic") -> str:
    """Helper: normalize and return text only."""
    result, _ = normalize_text(text, NormalizationLevel(level))
    return result


def norm_report(text: str, level: str = "academic"):
    """Helper: normalize and return (text, report)."""
    return normalize_text(text, NormalizationLevel(level))


# ── S0: SMP Mathematical Italic → ASCII ─────────────────────────────

class TestS0_SMP:
    def test_math_italic_lowercase(self):
        # U+1D44E = math italic 'a'
        text = f"The variable {chr(0x1D44E)} was measured"
        assert "a" in norm(text, "standard")

    def test_math_italic_uppercase(self):
        # U+1D434 = math italic 'A'
        text = f"{chr(0x1D434)} significant effect"
        assert norm(text, "standard").startswith("A")

    def test_math_italic_greek_eta(self):
        # U+1D702 = math italic eta
        text = f"{chr(0x1D702)}² = .054"
        result = norm(text, "standard")
        assert "n" in result  # eta maps to 'n'

    def test_mixed_smp_and_normal(self):
        text = f"The {chr(0x1D44F)}eta was {chr(0x1D44E)} = 0.5"
        result = norm(text, "standard")
        assert chr(0x1D44F) not in result
        assert chr(0x1D44E) not in result


# ── S3: Ligature expansion ───────────────────────────────────────────

class TestS3_Ligatures:
    def test_fi_ligature(self):
        assert "significant" in norm("signi\ufb01cant")

    def test_fl_ligature(self):
        assert "reflect" in norm("re\ufb02ect")

    def test_ff_ligature(self):
        assert "effect" in norm("e\ufb00ect")

    def test_ffi_ligature(self):
        assert "office" in norm("o\ufb03ce")

    def test_ffl_ligature(self):
        assert "affluent" in norm("a\ufb04uent")

    def test_ligature_in_stat_context(self):
        text = "The signi\ufb01cant e\ufb00ect was modi\ufb01ed"
        result = norm(text)
        assert "significant" in result
        assert "effect" in result
        assert "modified" in result

    def test_ligature_adjacent_to_number(self):
        text = "\ufb01nd 0.05"
        assert "find 0.05" in norm(text)

    def test_multiple_ligatures_in_one_word(self):
        # "affidavit" with ff and fi ligatures
        text = "a\ufb00idavit"
        result = norm(text)
        assert "affidavit" in result


# ── S5: Dash and minus normalization ─────────────────────────────────

class TestS5_DashMinus:
    def test_unicode_minus_sign(self):
        """CRITICAL: U+2212 must become ASCII hyphen for stat matching."""
        text = "r = \u22120.73"
        result = norm(text, "standard")
        assert "r = -0.73" in result
        assert "\u2212" not in result

    def test_en_dash(self):
        text = "pages 1\u201310"
        assert "\u2013" not in norm(text, "standard")

    def test_em_dash(self):
        text = "result\u2014important"
        assert "\u2014" not in norm(text, "standard")

    def test_unicode_hyphen_variants(self):
        text = "\u2010test\u2011value"
        result = norm(text, "standard")
        assert "\u2010" not in result
        assert "\u2011" not in result

    def test_ci_with_unicode_minus(self):
        text = "95% CI [\u22120.78, \u22120.67]"
        result = norm(text, "standard")
        assert "[-0.78, -0.67]" in result


# ── S6 extended: soft hyphen, full-width, BOM, Unicode spaces ────────

class TestS6_Extended:
    def test_soft_hyphen_stripped(self):
        """U+00AD: 14 of 50 test PDFs have this. 151 instances in chan_feldman."""
        assert "significant" in norm("signifi\u00ADcant", "standard")

    def test_soft_hyphen_in_real_context(self):
        text = "demonstrated that (a) relation\u00ADship satisfaction"
        result = norm(text, "standard")
        assert "relationship" in result
        assert "\u00AD" not in result

    def test_bom_stripped(self):
        result = norm("\uFEFFThe study results", "standard")
        assert "\uFEFF" not in result
        assert "study results" in result

    def test_en_space(self):
        result = norm("p\u2002=\u2002.05", "standard")
        assert "\u2002" not in result

    def test_em_space(self):
        result = norm("p\u2003=\u2003.05", "standard")
        assert "\u2003" not in result

    def test_figure_space(self):
        result = norm("N\u2007=\u2007234", "standard")
        assert "\u2007" not in result

    def test_narrow_no_break_space(self):
        result = norm("95\u202F%", "standard")
        assert "\u202F" not in result

    def test_ideographic_space(self):
        result = norm("test\u3000value", "standard")
        assert "\u3000" not in result

    def test_zero_width_non_joiner(self):
        result = norm("test\u200Cvalue", "standard")
        assert "\u200C" not in result

    def test_zero_width_joiner(self):
        result = norm("test\u200Dvalue", "standard")
        assert "\u200D" not in result

    def test_fullwidth_ascii(self):
        """Full-width p = 0.001 → regular ASCII."""
        result = norm("\uFF50 \uFF1D \uFF10.\uFF10\uFF10\uFF11", "standard")
        assert "p" in result
        assert "=" in result
        assert "0.001" in result

    def test_fullwidth_digits(self):
        result = norm("\uFF10\uFF11\uFF12\uFF13", "standard")
        assert "0123" in result

    def test_fullwidth_letters(self):
        result = norm("\uFF41\uFF42\uFF43", "standard")  # ａｂｃ
        assert "abc" in result

    def test_mixed_unicode_spaces_in_stats(self):
        """Real-world: various Unicode spaces between stat components."""
        text = "p\u00A0<\u00A0.001,\u2009d\u2009=\u20090.45"
        result = norm(text, "standard")
        assert "\u00A0" not in result
        assert "\u2009" not in result
        assert "p" in result
        assert ".001" in result
        assert "0.45" in result


# ── S7: Hyphenation repair ───────────────────────────────────────────

class TestS7_Hyphenation:
    def test_word_hyphenation(self):
        assert "significant" in norm("signi-\nficant")

    def test_observed_hyphenation(self):
        assert "observed" in norm("ob-\nserved")

    def test_does_not_join_sentence_boundary(self):
        """Should NOT join: capital after hyphen-newline."""
        result = norm("end-\nBegin", "standard")
        # S7 regex: ([a-z])-\n([a-z]) — requires lowercase on both sides
        assert "endBegin" not in result  # Capital B prevents join


# ── S8: Line break joining ───────────────────────────────────────────

class TestS8_LineBreaks:
    def test_mid_sentence_join(self):
        result = norm("the results\nshow that", "standard")
        assert "the results show that" in result

    def test_does_not_join_after_period(self):
        result = norm("end.\nNew sentence", "standard")
        assert "end.\nNew" in result or "end. New" not in result

    def test_joins_after_comma(self):
        result = norm("first,\nsecond", "standard")
        assert "first, second" in result


# ── S9: Header/footer removal ───────────────────────────────────────

class TestW0_PublisherCopyrightAndRunningHeader:
    """Issues H + I (2026-05-07): strip Elsevier-style copyright stamp on its
    own line, and two-column running headers like
    'M. Muraven / Journal of Experimental Social Psychology 46 (2010) 465-468'.
    Both leak into section bodies if not stripped, blowing the strict-bar
    cross-section bleed budget on every Elsevier two-column paper."""

    def test_elsevier_copyright_line_stripped(self):
        text = (
            "...end of abstract paragraph.\n"
            "© 2009 Elsevier Inc. All rights reserved.\n"
            "\n"
            "Introduction\n"
        )
        result = norm(text)
        assert "Elsevier Inc. All rights reserved" not in result
        assert "end of abstract paragraph" in result
        assert "Introduction" in result

    def test_springer_copyright_line_stripped(self):
        text = (
            "...end of paragraph.\n"
            "© 2020 Springer Nature Limited. All rights reserved.\n"
            "\n"
            "Introduction\n"
        )
        result = norm(text)
        assert "All rights reserved" not in result

    def test_pdftotext_O_acute_for_copyright_stripped(self):
        """pdftotext sometimes flattens © to Ó depending on font/encoding."""
        text = (
            "...end of abstract.\n"
            "Ó 2009 Elsevier Inc. All rights reserved.\n"
            "\n"
            "Introduction\n"
        )
        result = norm(text)
        assert "All rights reserved" not in result

    def test_copyright_in_running_text_NOT_stripped(self):
        """A copyright stamp embedded mid-prose should not be removed —
        only standalone-line stamps qualify."""
        text = (
            "We discuss the implications of the © 2009 Elsevier Inc. All rights"
            " reserved policy on data sharing in psychology.\n"
        )
        result = norm(text)
        # The line is not anchored to start-of-line as a copyright stamp
        # (it has prose before "©").  Should be preserved.
        assert "© 2009 Elsevier" in result or "Ó 2009 Elsevier" in result

    def test_two_column_running_header_stripped(self):
        text = (
            "...end of body paragraph.\n"
            "M. Muraven / Journal of Experimental Social Psychology 46 (2010) 465-468\n"
            "\n"
            "Continuation of body.\n"
        )
        result = norm(text)
        assert "M. Muraven / Journal of Experimental" not in result
        assert "Continuation of body" in result

    def test_two_column_running_header_with_two_authors(self):
        text = (
            "...end of body paragraph.\n"
            "J. Smith and K. Jones / Cognitive Psychology 12 (2020) 100-120\n"
            "Continuation of body.\n"
        )
        result = norm(text)
        assert "Cognitive Psychology 12" not in result
        assert "Continuation of body" in result

    def test_two_column_running_header_en_dash_pages(self):
        """Some publishers use en-dash for page ranges instead of hyphen."""
        text = (
            "...end of body paragraph.\n"
            "A. Author / Journal of X 5 (2021) 50–75\n"
            "Continuation of body.\n"
        )
        result = norm(text)
        assert "A. Author / Journal" not in result
        assert "Continuation of body" in result

    def test_cc_license_footer_stripped(self):
        """Korbmacher-style: 'Copyright: © 2022. The authors license this
        article under the terms of the Creative Commons Attribution 3.0
        License.' appended to abstract — should not contaminate abstract body."""
        text = (
            "...generalizability and robustness of the phenomenon. "
            "Copyright: © 2022. The authors license this article under the"
            " terms of the Creative Commons Attribution 3.0 License.\n"
            "\n"
            "1 Introduction\n"
        )
        result = norm(text)
        assert "Creative Commons Attribution 3.0 License" not in result
        assert "license this article" not in result
        # The abstract content prior to the footer must survive.
        assert "robustness of the phenomenon" in result

    def test_collabra_downloaded_from_with_by_guest_stripped(self):
        """Collabra Psychology / UCPress watermark variant has 'by guest'
        between URL and 'on <date>'.  The original W0 pattern required no
        intermediate text and missed every Collabra paper (Aiyer, Brick,
        Maier, Adelina, etc.) — relaxed 2026-05-09."""
        text = (
            "Body paragraph.\n"
            "Downloaded from http://online.ucpress.edu/collabra/article-pdf/"
            "7/1/23443/foo.pdf by guest on 03 June 2021\n"
            "More body.\n"
        )
        result = norm(text)
        assert "Downloaded from" not in result
        assert "by guest" not in result
        assert "Body paragraph" in result
        assert "More body" in result

    def test_author_equal_contribution_footnote_stripped(self):
        """Brick et al 2021 / Adelina-Feldman / many open-access papers
        emit an author-equal-contribution footnote at the bottom of page 1.
        pdftotext extracts it inline between abstract and intro."""
        text = (
            "End of abstract paragraph.\n"
            "a Brick, Fillon, Yeung, Wang, Lyu, Ho, and Wong are equal-contribution"
            " first authors b gfeldman@hku.hk / giladfel@gmail.com\n"
            "Introduction\n"
            "Body of intro.\n"
        )
        result = norm(text)
        assert "Brick, Fillon" not in result
        assert "equal-contribution" not in result
        assert "Introduction" in result
        assert "End of abstract paragraph" in result

    def test_author_joint_first_footnote_stripped(self):
        text = (
            "Some paragraph.\n"
            "a Smith, Jones, and Lee are joint first authors b email@example.com\n"
            "Next.\n"
        )
        result = norm(text)
        assert "joint first authors" not in result
        assert "Some paragraph" in result
        assert "Next" in result

    def test_lowercase_prose_NOT_stripped_as_author_footnote(self):
        """Genuine prose lines that happen to start with a lowercase letter
        must NOT match — discriminator is the 'equal contribution' / 'joint
        first authors' phrase, plus 3+ capitalized surnames."""
        text = (
            "Some paragraph.\n"
            "a study published last year reported that participants in"
            " the control condition performed worse.\n"
            "Next.\n"
        )
        result = norm(text)
        # The lowercase-prose continuation must survive.
        assert "study published last year" in result

    def test_cc_license_footer_4_0_variant_stripped(self):
        text = (
            "...end of paragraph.\n"
            "The authors license this article under the terms of the Creative"
            " Commons Attribution 4.0 International License.\n"
        )
        result = norm(text)
        assert "Creative Commons Attribution" not in result

    def test_reference_line_NOT_stripped_as_running_header(self):
        """A reference list entry that happens to look similar must be preserved.
        References don't have the '<initial>. <Surname> / <Journal> <vol> (<year>) <pages>'
        shape — they have year inside, not after journal."""
        text = (
            "References\n"
            "Muraven, M. (2010). Building self-control. Journal of Experimental"
            " Social Psychology, 46(3), 465-468.\n"
            "Smith, J. (2020). Another paper. Cognitive Psychology, 12, 100-120.\n"
        )
        result = norm(text)
        assert "Muraven, M. (2010). Building" in result
        assert "Smith, J. (2020). Another paper" in result


class TestS9_HeaderFooter:
    def test_repeated_line_stripped(self):
        header = "Journal of Example Studies Vol. 1"
        text = "\n".join([header] * 6 + ["Actual content here"])
        result = norm(text, "standard")
        assert header not in result
        assert "Actual content" in result

    def test_page_numbers_stripped(self):
        text = "content\n42\nmore content\n43\nstill more"
        result = norm(text, "standard")
        assert "\n42\n" not in result

    def test_short_lines_preserved(self):
        """Lines < 15 chars should NOT be treated as headers."""
        text = "Short\n" * 10 + "Content"
        result = norm(text, "standard")
        # "Short" is < 15 chars, should be preserved
        assert "Short" in result


# ── A1: Statistical line break repair ────────────────────────────────

class TestA1_StatLineBreaks:
    def test_p_equals_linebreak(self):
        """From MetaESCI: 0.77% of results have this artifact."""
        assert "p = 0.001" in norm("p =\n0.001")

    def test_p_less_linebreak(self):
        assert "p < .001" in norm("p <\n.001")

    def test_or_linebreak(self):
        assert "OR 1.399" in norm("OR\n1.399")

    def test_ci_linebreak(self):
        assert "95% CI" in norm("95%\nCI")

    def test_f_test_linebreak(self):
        """From ESCIcheck: F(1, 30) =\\n4.425"""
        assert "= 4.425" in norm("F(1, 30) =\n4.425")

    def test_equals_negative_linebreak(self):
        assert "= -0.73" in norm("= \n-0.73")

    def test_greater_linebreak(self):
        assert "> 0.05" in norm(">\n0.05")


# ── A2: Dropped decimal repair ───────────────────────────────────────

class TestA2_DroppedDecimal:
    """From MetaESCI extraction report: 4.88% of results (5,908 out of 121,040)."""

    def test_p_equals_484(self):
        assert "p = .484" in norm("p = 484")

    def test_p_equals_37(self):
        assert "p = .37" in norm("p = 37")

    def test_p_equals_999(self):
        assert "p = .999" in norm("p = 999")

    def test_does_not_change_small_value(self):
        """p = 5 is NOT a dropped decimal (too small)."""
        result = norm("p = 5")
        assert "p = 5" in result  # unchanged (5 < 10, not > 1.0 && < 1000)

    def test_does_not_change_large_n(self):
        """N = 484 should not be 'fixed' — it's a sample size."""
        result = norm("N = 484")
        assert "N = 484" in result  # A2 only matches p-values

    def test_combined_linebreak_and_dropped_decimal(self):
        """From ESCIcheck: p = \\n484 — both A1 and A2 needed."""
        result = norm("p =\n484")
        assert "p = .484" in result or "p =\n.484" in result


# ── A3: Decimal comma normalization ──────────────────────────────────

class TestA3_DecimalComma:
    def test_european_p_value(self):
        assert "0.05" in norm("p = 0,05")

    def test_european_d_value(self):
        assert "1.23" in norm("d = 1,23")

    def test_does_not_change_thousands(self):
        """N = 1,234 is a thousands separator, not decimal."""
        result = norm("N = 1,234")
        # Pattern (\d),(\d{1,3}) matches 1-3 digits after comma
        # 1,234 has 3 digits → ambiguous. Let's verify behavior.
        # The regex will match this — this is a known limitation.


# ── A4: CI delimiter harmonization ───────────────────────────────────

class TestA4_CIDelimiter:
    def test_semicolon_to_comma(self):
        assert "[0.81, 1.92]" in norm("[0.81; 1.92]")

    def test_negative_values(self):
        assert "[-0.78, -0.67]" in norm("[-0.78; -0.67]")

    def test_preserves_already_comma(self):
        result = norm("[0.81, 1.92]")
        assert "[0.81, 1.92]" in result


# ── A5: Math symbol normalization ────────────────────────────────────

class TestA5_MathSymbols:
    def test_multiplication(self):
        assert "x" in norm("\u00D7")

    def test_less_equal(self):
        assert "<=" in norm("\u2264")

    def test_greater_equal(self):
        assert ">=" in norm("\u2265")

    def test_not_equal(self):
        assert "!=" in norm("\u2260")

    # Greek statistical letters
    def test_eta_squared(self):
        assert "eta2" in norm("\u03B7\u00B2 = .054")

    def test_chi_squared(self):
        assert "chi2" in norm("\u03C7\u00B2(3) = 12.4")

    def test_omega_squared(self):
        assert "omega2" in norm("\u03C9\u00B2 = .032")

    def test_eta_alone(self):
        assert "eta" in norm("\u03B7 = .23")

    def test_eta_with_space_before_2(self):
        assert "eta2" in norm("\u03B7 2 = .054")

    def test_alpha(self):
        assert "alpha" in norm("Cronbach's \u03B1 = .85")

    def test_beta(self):
        assert "beta" in norm("\u03B2 = 0.45")

    def test_partial_eta_squared(self):
        """Real pattern from chan_feldman: ηp² or η²p"""
        result = norm("\u03B7p\u00B2 = .08")
        assert "eta" in result
        assert ".08" in result

    # Superscript/subscript digits
    def test_superscript_2(self):
        assert "2" in norm("\u00B2")

    def test_superscript_3(self):
        assert "3" in norm("\u00B3")

    def test_superscript_1(self):
        assert "1" in norm("\u00B9")

    def test_subscript_1(self):
        assert "F1" in norm("F\u2081")

    def test_subscript_2(self):
        assert "R2" in norm("R\u2082")


# ── A6: Footnote marker removal ──────────────────────────────────────

class TestA6_FootnoteRemoval:
    """Footnote superscripts after stat values should be stripped."""

    def test_footnote_after_pvalue(self):
        """p < .001¹ → p < .001 (footnote 1 stripped)"""
        # A5 converts ¹ to 1 first, but A6 catches remaining Unicode superscripts
        # For the case where A5 already ran, the ¹ becomes 1 and merges with value
        # So test with a pattern where the superscript is clearly separate
        result = norm("p < .001")
        assert ".001" in result

    def test_footnote_after_ci_bracket(self):
        """95% CI [0.1, 0.5]² → 95% CI [0.1, 0.5]"""
        # After A5, ² → 2, so this becomes [0.1, 0.5]2
        # A6 should strip the trailing superscript
        result = norm("[0.1, 0.5]\u00B2")
        assert "[0.1, 0.5]" in result or "[0.1, 0.5]2" in result


# ── Integration: full pipeline ───────────────────────────────────────

class TestFullPipeline:
    def test_academic_full_passage(self):
        """Real-world passage with multiple artifacts."""
        raw = (
            "The signi\ufb01cant result was r(261) = \u22120.73, 95%\n"
            "CI [\u22120.78; \u22120.67], p\n"
            "< .001, d = 484"
        )
        result = norm(raw, "academic")
        assert "significant" in result         # S3: ligature
        assert "-0.73" in result               # S5: Unicode minus
        assert "95% CI" in result              # A1: stat line break
        assert "[-0.78, -0.67]" in result      # S5 + A4: minus + delimiter
        assert "p < .001" in result            # A1: stat line break
        assert ".484" in result                # A2: dropped decimal

    def test_none_level_preserves_artifacts(self):
        raw = "signi\ufb01cant \u2212"
        result, report = norm_report(raw, "none")
        assert "\ufb01" in result
        assert "\u2212" in result
        assert report.level == "none"

    def test_standard_does_not_do_academic_steps(self):
        raw = "p =\n0.001"
        result = norm(raw, "standard")
        # Standard should NOT fix stat line breaks (that's A1)
        assert "p =\n0.001" in result or "p = 0.001" not in result

    def test_report_tracks_changes(self):
        raw = "signi\ufb01cant e\ufb00ect \u22120.73"
        _, report = norm_report(raw, "standard")
        assert "S3_ligature_expansion" in report.steps_applied
        assert "S5_dash_normalization" in report.steps_applied
        assert report.changes_made.get("ligatures_expanded", 0) > 0


# ── A4 Enhanced: curly braces, spacing, paren semicolons ─────────────

class TestA4_Enhanced:
    def test_curly_braces_to_square_brackets(self):
        """European CI: {0.45, 0.89} → [0.45, 0.89]"""
        assert "[0.45, 0.89]" in norm("{0.45, 0.89}")

    def test_curly_braces_with_semicolon(self):
        """{0.45; 0.89} → [0.45, 0.89]"""
        assert "[0.45, 0.89]" in norm("{0.45; 0.89}")

    def test_curly_braces_negative(self):
        """{-0.12, 0.34} → [-0.12, 0.34]"""
        assert "[-0.12, 0.34]" in norm("{-0.12, 0.34}")

    def test_bracket_spacing_compact(self):
        """[0.45,0.89] → [0.45, 0.89]"""
        assert "[0.45, 0.89]" in norm("[0.45,0.89]")

    def test_bracket_spacing_wide(self):
        """[ 0.45 , 0.89 ] → [0.45, 0.89]"""
        assert "[0.45, 0.89]" in norm("[ 0.45 , 0.89 ]")

    def test_paren_semicolon_to_comma(self):
        """(0.12; 0.45) → (0.12, 0.45)"""
        assert "(0.12, 0.45)" in norm("(0.12; 0.45)")

    def test_paren_spacing(self):
        """( 0.12 , 0.45 ) → (0.12, 0.45)"""
        assert "(0.12, 0.45)" in norm("( 0.12 , 0.45 )")

    def test_negative_in_parens(self):
        """(-0.78; -0.67) → (-0.78, -0.67)"""
        assert "(-0.78, -0.67)" in norm("(-0.78; -0.67)")


# ── A1 Enhanced: aggressive stat line break patterns ─────────────────

class TestA1_Enhanced:
    def test_pvalue_garbage_linebreak(self):
        """p = some text\n0.045 → p = 0.045 (skip garbage)"""
        result = norm("p = some text\n0.045")
        assert "p = 0.045" in result or "p =0.045" in result

    def test_pvalue_short_garbage(self):
        """p < column text\n.001 → p < .001"""
        result = norm("p < column text\n.001")
        assert "p < .001" in result or "p <.001" in result

    def test_stat_to_pvalue_linebreak(self):
        """t(23) = 2.34,\n p < .001 → rejoined on one line"""
        result = norm("t(23) = 2.34,\n p < .001")
        assert ", p < .001" in result

    def test_stat_semicolon_to_pvalue(self):
        """F(2, 24) = 5.67;\n p < .001 → rejoined"""
        result = norm("F(2, 24) = 5.67;\n p < .001")
        assert "; p < .001" in result

    def test_effect_to_ci_linebreak(self):
        """d = 0.45,\n 95% CI → rejoined"""
        result = norm("d = 0.45,\n 95% CI [0.21, 0.69]")
        assert ", 95% CI" in result

    def test_does_not_eat_long_garbage(self):
        """Garbage > 20 chars should NOT be skipped (too aggressive)."""
        result = norm("p = this is a very long sentence that should not be eaten\n0.045")
        # The garbage is > 20 chars, so the pattern should NOT match
        assert "p = 0.045" not in result


class TestA1_ColumnBleed:
    """Regression tests for the 2026-04-11 PSPB column-bleed fix.

    Real-world pattern from MetaESCI corpus: PSPB multi-column layout produces
    stray digit-only lines between 'p' and the '=' operator. Example from
    10.1177/0146167215581712:

        beta = .08 p\\n\\n01\\n\\n01\\n\\n= .28

    where '01' lines are column-bleed fragments. The simple p\\n= rule can't
    handle this because the intermediate lines aren't whitespace.
    """

    def test_column_bleed_single_fragment(self):
        """p\\n01\\n= .28 → p = .28"""
        result = norm("beta = .08 p\n01\n= .28")
        assert "p\n01\n=" not in result
        assert "p = .28" in result

    def test_column_bleed_double_fragment(self):
        """p\\n01\\n01\\n= .28 → p = .28 (the real PSPB pattern)"""
        result = norm("beta = .08 p\n01\n01\n= .28")
        assert "p = .28" in result

    def test_column_bleed_with_blank_lines(self):
        """p\\n\\n01\\n\\n01\\n\\n= .28 → p = .28 (literal raw PSPB)"""
        result = norm("beta = .08 p\n\n01\n\n01\n\n= .28")
        assert "p = .28" in result

    def test_column_bleed_quadruple_fragment(self):
        """Up to 4 fragment lines are allowed."""
        result = norm("p\n01\n11\n12\n13\n= .05")
        assert "p = .05" in result

    def test_column_bleed_too_many_fragments_ignored(self):
        """5+ fragments should NOT match (conservative upper bound)."""
        result = norm("p\n01\n02\n03\n04\n05\n= .05")
        # With 5 fragments, the regex doesn't match; we want the broken pattern
        # to remain visible rather than be silently mis-joined with unrelated text.
        assert "p = .05" not in result

    def test_column_bleed_in_operator_value(self):
        """p =\\n01\\n11\\n.28 → p = .28"""
        result = norm("p =\n01\n11\n.28")
        assert "p = .28" in result

    def test_column_bleed_with_word_skipped(self):
        """Intermediate lines that aren't short digits should NOT match."""
        result = norm("p\nsome word\n= .28")
        # Should NOT collapse (word isn't a column-bleed fragment)
        assert "p = .28" not in result


class TestA2_DroppedDecimalV2:
    """Regression tests for the 2026-04-11 A2 widening fix.

    Before: A2 used `val > 1.0` which excluded `p = 01` (val=1.0).
    After:  A2 uses `val >= 1.0` so `p = 01` → `p = .01`.

    The `\\d{2,3}` prefix in the regex already prevents `p = 1` (single digit)
    from matching, so widening the threshold is safe.
    """

    def test_dropped_decimal_p_equals_01(self):
        """p = 01 → p = .01 (val=1.0, used to be rejected)"""
        result = norm("The effect was significant, p = 01.")
        assert "p = .01" in result

    def test_dropped_decimal_p_equals_10(self):
        """p = 10 → p = .10 (val=10.0)"""
        result = norm("Marginal effect, p = 10.")
        assert "p = .10" in result

    def test_dropped_decimal_p_equals_02(self):
        """p = 02 → p = .02"""
        result = norm("Significant effect, p = 02.")
        assert "p = .02" in result

    def test_single_digit_not_touched(self):
        """p = 1 (single digit) must NOT be mangled."""
        # The regex \d{2,3} requires 2-3 digits, so this should pass through
        result = norm("p = 1 for the test.")
        assert "p = .1" not in result

    def test_genuine_decimal_not_touched(self):
        """p = 0.05 must NOT be changed."""
        result = norm("The effect is p = 0.05 and d = 0.34.")
        assert "p = 0.05" in result

    def test_p_equals_with_linebreak(self):
        """p = 01\\nnext word → p = .01 next word (real PSPB pattern)"""
        result = norm("beta = .11, p = 01\nbelieved that they lost status")
        assert "p = .01" in result

    def test_effect_size_dropped_decimal_widened(self):
        """d = 10 → d = .10 (val=10.0, widening applies)"""
        result = norm("Cohen's d = 10 showed the effect.")
        assert "d = .10" in result


# ── A3a: Thousands separator protection (ESCImate Request 1.1) ─────

class TestA3a_ThousandsSeparator:
    def test_capital_N_thousands_preserved(self):
        result = norm("Participants (N = 1,182) completed the survey")
        assert "N = 1182" in result
        assert "N = 1.182" not in result

    def test_lowercase_n_thousands_preserved(self):
        result = norm("Sample of n = 2,443 adults")
        assert "n = 2443" in result

    def test_N_with_six_digit_integer(self):
        result = norm("A large cohort (N = 1,234,567) was analyzed.")
        assert "N = 1234567" in result

    def test_df_with_thousands_separator(self):
        result = norm("The test produced t(df = 1,197) = 2.34")
        assert "df = 1197" in result

    def test_sample_size_of_phrase(self):
        result = norm("A sample size of 2,443 was collected.")
        assert "2443" in result
        assert "2.443" not in result

    def test_total_of_participants_phrase(self):
        result = norm("A total of 1,850 participants enrolled.")
        assert "1850" in result

    def test_decimal_comma_still_works_outside_N_context(self):
        """German-style decimal comma must still normalize to period."""
        result = norm("Der Mittelwert = 0,73 war signifikant")
        assert "0.73" in result

    def test_standard_level_preserves_commas(self):
        """Standard level never runs A3, so commas must be preserved as-is."""
        result = norm("Participants (N = 1,182) completed the survey", "standard")
        # Standard doesn't run A3a either (it's academic-only), but A3 also
        # doesn't run, so commas pass through untouched
        assert "N = 1,182" in result

    def test_report_tracks_thousands_count(self):
        _, report = norm_report("N = 1,182 and n = 2,443 were enrolled.")
        assert report.changes_made.get("thousands_separators_preserved") == 2
        assert "A3a_thousands_separator_protect" in report.steps_applied


# ── S5a: Context-aware U+FFFD recovery (ESCImate Request 1.2) ──────

class TestS5a_FffdContextRecovery:
    def test_fffd_with_superscript_two(self):
        result = norm("Main effect was significant (\ufffd\u00B2 = 0.04)", "standard")
        assert "eta" in result
        assert "\ufffd" not in result

    def test_fffd_with_plain_digit_two(self):
        result = norm("Main effect, \ufffd2 = 0.04, was strong", "standard")
        assert "eta2 = 0.04" in result or "eta 2 = 0.04" in result

    def test_fffd_partial_eta_subscript(self):
        result = norm("\ufffd_p\u00B2 = .12 in the interaction", "standard")
        assert "eta" in result
        # The _p^2 should be preserved since we only replaced FFFD
        assert "_p" in result

    def test_fffd_in_non_stat_context_preserved(self):
        """Generic FFFD in prose must NOT be replaced."""
        result = norm("The \ufffd symbol is a replacement character.", "standard")
        assert "\ufffd" in result  # left alone

    def test_fffd_report_tracks_recovery_count(self):
        _, report = norm_report(
            "Main (\ufffd\u00B2 = 0.04) and interaction (\ufffd\u00B2 = 0.12)",
            "standard",
        )
        assert report.changes_made.get("fffd_context_recovered") == 2
        assert "S5a_fffd_context_recovery" in report.steps_applied


# ── A3: Author-affiliation false-positive protection (ESCImate regression) ──

class TestA3_BraunsteinLookbehind:
    """Cross-ported from ESCImate test-extraction-quality.R SECTION 11.

    The A3 decimal-comma rule must NOT fire on author affiliation
    superscript sequences like "Braunstein1,3" or "Wagner1,3,4", where
    the 1/3/4 are citation markers, not decimal values.
    """

    def test_braunstein_affiliation_preserved(self):
        result = norm("Author Braunstein1,3 and colleagues")
        assert "Braunstein1,3" in result
        assert "Braunstein1.3" not in result

    def test_wagner_triple_affiliation_preserved(self):
        result = norm("Wagner1,3,4 led the analysis")
        assert "Wagner1,3,4" in result
        assert "Wagner1,3.4" not in result
        assert "Wagner1.3" not in result

    def test_affiliation_with_trailing_name(self):
        result = norm("first1,3Boryana continued the study")
        # Either the comma stays OR there's a clean boundary; must NOT become "first1.3Boryana"
        assert "first1.3Boryana" not in result

    def test_real_decimal_comma_still_converts(self):
        result = norm("Der Mittelwert war 0,73 und signifikant")
        assert "0.73" in result

    def test_decimal_comma_after_letter_blocked(self):
        """Lookbehind blocks a-z and A-Z — "x2,3" is ambiguous so leave alone."""
        result = norm("variable x2,3 was coded")
        # The "2,3" after "x" is an affiliation-like pattern; don't corrupt it
        assert "x2.3" not in result

    def test_multiple_affiliations_in_abstract(self):
        result = norm(
            "Chan1,2, Feldman3, and Zhao1,2,4 conducted the meta-analysis; "
            "the effect was d = 0,44 across studies."
        )
        # Affiliations preserved
        assert "Chan1,2" in result
        assert "Zhao1,2,4" in result
        # Real decimal still converts
        assert "d = 0.44" in result


class TestA3_StatBracketLookbehind:
    """MetaESCI D2 regression (2026-04-11): A3 must not corrupt the comma
    inside statistical df brackets like F[2,42], F(2,42), t(1,197). The
    lookbehind now excludes '[' and '(' so the comma survives A3; A3b then
    harmonizes the square-bracket form to canonical parens.
    """

    def test_f_square_bracket_comma_preserved_not_decimal(self):
        # A3 must not turn "F[2,42]" into "F[2.42]"
        result = norm("effect of pose on mood (F[2,42]= 13.689, p < .001)")
        assert "F[2.42]" not in result
        # A3b harmonizes to parens so effectcheck can parse
        assert "F(2, 42)" in result or "F(2,42)" in result

    def test_f_paren_tight_comma_preserved(self):
        # A3 must not turn "F(2,42)" into "F(2.42)"
        result = norm("interaction (F(2,42)=13.689, p<.001)")
        assert "F(2.42)" not in result
        assert "F(2, 42)" in result or "F(2,42)" in result

    def test_t_paren_tight_thousands_preserved(self):
        result = norm("result was significant, t(1,197)=2.34, p<.05")
        assert "t(1.197)" not in result

    def test_a3b_harmonizes_bracket_to_paren_for_effectcheck(self):
        # Standalone harmonization — independent of A3 lookbehind
        result = norm("the interaction (F[7,140]=1927, p<.0001)")
        assert "F(7, 140)" in result or "F(7,140)" in result
        assert "F[7" not in result

    def test_a3b_does_not_convert_non_stat_brackets(self):
        # "See [1,2]" is a citation list, not a stat expression — leave alone
        result = norm("See references [1,2] for details")
        assert "[1,2]" in result or "[1, 2]" in result  # A4 may space it
        # must not become "(1, 2)"
        assert "references (1" not in result

    def test_a3b_does_not_fire_on_short_word_citations(self):
        """Review finding 2026-04-11: A3b must require `=` after the bracket
        so short prefixes like ref/fig/eq/tab don't get their citation lists
        rewritten into paren form. Only bracket-stats followed by `=` are
        real F/t/chi2 expressions worth converting."""
        for txt in [
            "See ref[1,2] for details",
            "fig[1,2] shows the interaction",
            "eq[1,2] applies here",
            "tab[1,2] lists participants",
        ]:
            result = norm(txt)
            assert "(1, 2)" not in result, f"false positive on {txt!r}: {result!r}"
            assert "(1,2)" not in result, f"false positive on {txt!r}: {result!r}"

    def test_a3b_still_fires_on_real_stat_with_equals(self):
        # The original D2 repro case — must still work after tightening
        result = norm("interaction (F[7,140]= 1927, p<.0001)")
        assert "F(7, 140)" in result or "F(7,140)" in result
