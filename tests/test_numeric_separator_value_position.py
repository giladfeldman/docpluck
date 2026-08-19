"""Numeric-separator rules stop guessing outside the value position (v2.4.127).

Every case below was measured on the 101-PDF corpus or comes from ESCImate's
shared conformance corpus (`effectcheck/inst/normalization-spec/conformance.json`,
spec 1.4.0). The defects these pin were all verified END TO END in shipped
output before the fix was written, and every test in this module was watched
FAILING against the unfixed code first.

What was wrong, measured on the corpus (A3 fired 29 times in 13 of 101 papers,
~27 of them on something that is not a decimal):

    'compared with controls.7,8 However'  ->  'controls.7.8 However'
                       Vancouver citation superscripts fused into a decimal
    'estimated to be up to ~25%6,28.'     ->  '...%6.28.'
    'Erik. T. Frank 1,2 , Lucie Kesner 3' ->  'Frank 1.2 ,'   affiliation markers
    'Experiments 1,2 showed'              ->  'Experiments 1.2 showed'
    table cells '9,57' / '9,40'           ->  '9.57' / '9.40'  ANOVA df pairs
    '148 (52,272)'                        ->  '148 (52272)'    an IQR destroyed

The two genuine European decimals in the whole corpus (`sci_rep_3`'s hazard
ratios `0,92` and `0,77`) are leading-zero forms, which A3c converts on its own.

The rule now keys on the VALUE POSITION — an operator immediately before the
number — which is the same discriminator ESCImate's D1b uses, and which is
structural rather than a vocabulary. Outside that position the token is
ambiguous between a decimal, an enumeration, a superscript run and a pair, so
it is preserved verbatim rather than guessed at.
"""

from __future__ import annotations

import pytest

from docpluck.normalize import NormalizationLevel, normalize_text


def _norm(text: str) -> str:
    out, _ = normalize_text(text, NormalizationLevel.academic)
    return out.strip()


# ── The value position: these MUST convert ──────────────────────────────────


class TestValuePositionNoLongerConverts:
    """RE-FIXTURED 2026-08-14, not deleted — these cases still carry their
    corpus knowledge, but the expected answer INVERTED.

    This class used to pin A3's operator gate: `d = 0,45` -> `d = 0.45`. A3 is
    DELETED (with A3c and A3d) under the scope directive of 2026-08-14 —
    docpluck serves English papers in US numeric convention and passes European
    numbers through as printed, because we do not know how to handle them.

    Measured before removing it: over 297 English papers A3 fired 9 times in 2
    papers and **not once correctly**. Full reasoning and the corpus sites:
    `tests/test_european_numbers_pass_through.py`, `docs/SCOPE.md`.
    """

    def test_p_equals_leading_zero(self):
        assert _norm("p = 0,001") == "p = 0,001"

    def test_d_equals_sentence_final(self):
        assert _norm("the effect was d = 0,87.") == "the effect was d = 0,87."

    def test_decimal_followed_by_list_comma(self):
        # ESCImate filed this 2026-08-09 as a divergence when we did NOT
        # convert it. We now deliberately do not, and they are told so.
        assert _norm("t(28) = 2,21, d = 0,45.") == "t(28) = 2,21, d = 0,45."

    def test_two_integer_digits(self):
        assert _norm("The mean was M = 12,34.") == "The mean was M = 12,34."

    def test_four_integer_digits(self):
        assert _norm("the statistic t = 1234,56.") == "the statistic t = 1234,56."

    def test_operator_less_than(self):
        assert _norm("p < 0,001") == "p < 0,001"

    def test_operator_greater_equal(self):
        # S5/A5 still transliterate the OPERATOR glyph — that is NOTATION and
        # is unaffected. Only the VALUE is left alone.
        assert _norm("BF ≥ 3,20") == "BF >= 3,20"

    def test_operator_less_equal_glyph(self):
        assert _norm("p ≤ 0,05") == "p <= 0,05"

    def test_leading_comma_decimal_is_NOT_converted(self):
        """A3d was deleted first (0 sites in 897 papers); A3 followed."""
        assert _norm("t(48) = 2,31, p = ,025, d = 0,74.") == (
            "t(48) = 2,31, p = ,025, d = 0,74."
        )

    def test_leading_comma_decimal_operator_is_NOT_converted(self):
        """The original fixture here was written in GERMAN; rewritten in
        English, since docpluck's scope is English articles and reasoning about
        the separator question from non-English input is what the scope rule
        forbids."""
        assert _norm("The effect was large, p < ,001, d = 1,08.") == (
            "The effect was large, p < ,001, d = 1,08."
        )


class TestNonValuePositionPreserved:
    def test_vancouver_citation_superscripts(self):
        # jama_open_1 and 9 other corpus papers.
        assert "controls.7,8" in _norm(
            "increased time spent in the euglycemic range compared with controls.7,8 However,"
        )

    def test_citation_superscripts_after_percent(self):
        # nathumbeh_2.
        assert "%6,28" in _norm("estimated to be up to ~25%6,28. However, prior studies")

    def test_author_affiliation_markers(self):
        # nat_comms_1..5: the FIRST element of a superscript run is
        # space-preceded, so only the trailing lookahead protected it.
        assert "Frank 1,2" in _norm("Erik. T. Frank 1,2 , Lucie Kesner 3, Joanito Liberti 1,3")

    def test_enumeration_experiments(self):
        assert _norm("Experiments 1,2 showed the effect.") == "Experiments 1,2 showed the effect."

    def test_enumeration_table(self):
        assert _norm("Table 1,2 and 3 summarise this.") == "Table 1,2 and 3 summarise this."

    def test_enumeration_items(self):
        assert _norm("items 1,5 and 7 were reversed") == "items 1,5 and 7 were reversed"

    def test_coded_binary(self):
        assert _norm("gender was coded 0,1") == "gender was coded 0,1"

    def test_operator_coded_enumeration_not_converted(self):
        # Adversarial review, 2026-08-12, reproduced: admitting a list comma
        # into A3's lookahead ALSO fired on an `=`-coded categorical
        # enumeration, which is a value position but not a value:
        #     'Group = 1,2,3' -> 'Group = 1.2,3'
        # The discriminator is the same one A2 uses: a list comma in prose is
        # followed by a space, a digit-run separator by a digit.
        assert _norm("Group = 1,2,3 in the between-subjects design.") == (
            "Group = 1,2,3 in the between-subjects design."
        )

    def test_operator_coded_enumeration_four_levels(self):
        assert _norm("Levels = 1,2,3,4") == "Levels = 1,2,3,4"

    def test_study_list_with_trailing_comma(self):
        # The counter-example that refuted BOTH proposed lookahead widenings
        # (adversarial pass, 2026-08-12): a list comma in English prose is
        # followed by whitespace, so "comma + space" is not a discriminator.
        assert _norm("Studies 1,2, and 3 replicated the effect.") == (
            "Studies 1,2, and 3 replicated the effect."
        )


# ── Bracket-delimited pairs are pairs, not numbers ──────────────────────────


class TestBracketDelimitedPairs:
    def test_iqr_pair_preserved(self):
        # nat_comms_2, verified end to end: 'Median (Q1,Q3) ... 148 (52,272)'
        # rendered '148 (52272)', fusing an interquartile range into one
        # number, while the adjacent row '8 (4,14)' survived as '(4, 14)'.
        # What must survive is the SEPARATOR; A4's space after it is the
        # existing, deliberate spacing normalization.
        out = _norm("Median (Q1,Q3) 8 (4,14) 148 (52,272)")
        assert "(52, 272)" in out or "(52,272)" in out, out
        assert "52272" not in out, out

    def test_single_df_bracket_preserved(self):
        # ESCImate SPEC rule T1: "T1 deliberately protects ALL X(...) brackets,
        # because deciding which are pairs requires knowing the test" - their
        # T2 strips single-df ones downstream, where the test arity is known.
        # docpluck used to strip this one, because its guard only recognised a
        # single UPPERCASE label.
        out = _norm("t(1,197) = 2.31, p = .02")
        assert "(1, 197)" in out or "(1,197)" in out, out
        assert "1197" not in out, out

    def test_f_df_pair_still_protected(self):
        # A3b re-spaces the bracket (`F(7,140)` -> `F(7, 140)`), which is
        # deliberate; what must survive is the PAIR, i.e. the comma between
        # the two df values.
        out = _norm("The effect held, F(7,140) = 4.31, p = .038.")
        assert "F(7, 140)" in out or "F(7,140)" in out, out

    def test_f_df_pair_brackets_still_protected(self):
        # MetaESCI D2 (2026-04-11): corrupting this to F[2.42] made the
        # downstream parser fail to match the row at all. A3b harmonizes the
        # brackets to parens, which is what that fix was for.
        out = _norm("The effect held, F[2,42] = 13.689, p = .001.")
        assert "(2, 42)" in out or "[2,42]" in out or "(2,42)" in out, out

    def test_ci_pair_not_a_decimal(self):
        assert "0.45" in _norm("The interval was [0.45,0.89].")
        assert "0.89" in _norm("The interval was [0.45,0.89].")

    def test_thousands_inside_parenthesised_prose_passes_through(self):
        # demography_2. RE-FIXTURED 2026-08-14: A3a used to strip this because
        # the bracket opens a PHRASE rather than delimiting a tuple. A3a is
        # deleted, so the distinction no longer has any consequence — every
        # form passes through, which is the point of retiring it.
        out = _norm("participate (12,856 with immigrant backgrounds and others)")
        assert "12,856" in out
        assert "12856" not in out


# ── Thousands separators are DELIVERED, not stripped (v2.4.130) ─────────────


class TestThousandsSeparatorsPassThrough:
    """RE-FIXTURED 2026-08-14, not deleted — every case is a real corpus site.

    This class used to pin A3a, which stripped a thousands separator so that A3
    would not misread `N = 1,182` as the decimal 1.182. A3 was deleted in
    v2.4.129 and A3a therefore had nothing left to protect against; it was
    deleted in v2.4.130.

    The separator now reaches the consumer as the paper printed it. That is not
    merely harmless — it is the ONLY evidence a consumer has that a table might
    be European, and A3a was destroying it while reporting the metric key
    `thousands_separators_preserved`.
    """

    def test_n_context(self):
        assert _norm("Participants (N = 1,182) completed the survey") == (
            "Participants (N = 1,182) completed the survey"
        )

    def test_body_integer(self):
        assert _norm("1,001 participants were recruited") == "1,001 participants were recruited"

    def test_u_statistic(self):
        # The consumer-visible harm this shape caused while A3a lived: a
        # consumer read `U = 55,890` as `55.89` and published a rank-biserial
        # of 0.99938 where the truth is 0.38275.
        assert _norm("A Mann-Whitney test, U = 12,345, z = -2.10, p = .036.") == (
            "A Mann-Whitney test, U = 12,345, z = -2.10, p = .036."
        )

    def test_clinical_arm_counts_both_sides(self):
        # ESCImate conformance case `thousands-clinical-arm-counts`. The
        # invariant it was written for still holds and is what matters: the two
        # arm counts must be treated IDENTICALLY. v2.4.130 satisfies it by
        # touching neither, instead of by stripping both.
        assert _norm("Events in 1,234/5,678 (21.7%) versus 987/5,432 (18.2%).") == (
            "Events in 1,234/5,678 (21.7%) versus 987/5,432 (18.2%)."
        )

    def test_the_satterthwaite_df_that_forced_the_decision(self):
        """10.1177/0956797620935584 Table S2 p24, rasterized twice.

        A Satterthwaite df is FRACTIONAL by construction, so `185,178` means
        185.178. A3a delivered `185178` — a 1000x error on a published
        statistic, and structural rather than a tail case: its discriminator
        ("every group after the first is exactly 3 digits") is satisfied BY
        CONSTRUCTION for any comma-locale number with a 3-digit integer part
        and 3-decimal precision, so an affected table collided on EVERY row.
        """
        src = "df- satterthwaite 185,178 31,836 188,193"
        assert _norm(src) == src


# ── A2 must not "repair" a number that has not finished ─────────────────────


class TestA2NoLongerRepairsADroppedDecimal:
    """A2 is DELETED (v2.4.130). RE-FIXTURED, not removed — these are real shapes.

    A2 restored a decimal point it believed the PDF had lost (`d = 12` ->
    `d = .12`). It had NO CITED PAPER anywhere in its code, and when one was
    finally demanded both of its firing sites across 297 English papers turned
    out to be the PAPER's own error, confirmed by rasterizing:

        10.1177/0146167210380928 p13   prints `B = -0.28, SE = 0.31, p = 38.`
        10.1016/j.jesp.2016.11.001 p7  prints `t(186) = 3.90, p = 001, d = 0.6`

    In both, correctly-dotted numbers sit on the SAME LINE, so the text layer
    dropped nothing — the author did. A2 was rewriting a published typo into a
    plausible statistic, 2 sites out of 2. Directive 2026-08-13: docpluck
    extracts and normalizes what is PRINTED; flagging a suspected author error
    belongs to ESCImate and Scimeto, which have the UI and the mandate.

    The guard cases below (`d = 12,5` never becoming `.12,5`) are kept because
    they now hold TRIVIALLY, and a reader must be able to see that the
    fabricated-hybrid output is impossible rather than merely unobserved.
    """

    def test_d_with_european_decimal_is_not_split(self):
        assert _norm("d = 12,5 was found") == "d = 12,5 was found"

    def test_g_with_european_decimal_is_not_split(self):
        assert _norm("g = 45,2 units") == "g = 45,2 units"

    def test_percentage_form(self):
        assert _norm("d = 12,5% of variance") == "d = 12,5% of variance"

    def test_a_dropped_decimal_is_no_longer_invented(self):
        """RE-FIXTURED: this used to assert `d = 12, p = .03` -> `d = .12, ...`.

        docpluck cannot tell a decimal IT lost from one the AUTHOR never typed,
        and the same run proved the ambiguity is irreducible: the identical
        `p < 05` shape is the paper's error in one real article and our OCR
        loss in another (see tests/test_p_threshold_decimal_real_pdf.py). Under
        irreducible ambiguity the default is pass-through, because pass-through
        is reversible for the consumer and a repair is not.
        """
        assert _norm("d = 12, p = .03") == "d = 12, p = .03"

    def test_end_of_clause_form_also_passes_through(self):
        assert _norm("The effect was d = 12") == "The effect was d = 12"

    def test_the_two_rasterized_corpus_sites(self):
        """Both A2 firing sites in 297 English papers, delivered as printed."""
        assert _norm("B = -0.28, SE = 0.31, p = 38.") == "B = -0.28, SE = 0.31, p = 38."
        assert _norm("t(186) = 3.90, p = 001, d = 0.6") == "t(186) = 3.90, p = 001, d = 0.6"

    def test_our_OWN_glyph_corruption_in_the_same_sentence_IS_fixed(self):
        """`10.1016/j.jesp.2016.11.001` carries one defect of EACH kind, and the
        two owners get opposite treatment. This is the separation of duties in a
        single line of a real paper.

        Beside the AUTHOR's `p = 001` — which we now pass through, above — sits
        `p b 0.001`, an Elsevier `<`-rendered-as-`b` glyph corruption. That one
        is **OURS**: page 4 PRINTS `p < 0.001` (rasterized, font
        `BFDKFC+AdvTT94c8263f.I`) and our text layer produced `b`. Under the ONE
        EXCEPTION to the directive it is exactly the class docpluck MUST fix,
        because docpluck caused it and the source is intact underneath.

        **This test was written as a KNOWN-GAP pin and then went red, which is
        how the gap got closed.** The 2026-08-14 handoff recorded "that one is
        ours (`W0c` owns it) and stays"; checked against the source, W0c
        (`recover_corrupted_lt_operator`) recovers `<`-as-BACKSLASH only and
        nothing handled `<`-as-`b`. The claim had been copied forward unverified
        — the L-027 failure mode inside the very run meant to stop it. `W0o` now
        recovers it; see tests/test_w0o_lt_as_b_glyph_recovery.py for the
        measurement (31 sites in that paper, 0 false positives in 26 others,
        17 legitimate coefficient `b`s in the same paper untouched).
        """
        out = _norm("t(186) = 3.90, p b 0.001, d = 0.6")
        # OURS -> fixed.
        assert "p < 0.001" in out
        # THE PAPER'S -> passed through, in the same sentence.
        assert _norm("t(186) = 3.90, p = 001, d = 0.6") == "t(186) = 3.90, p = 001, d = 0.6"


# ── Invariants ──────────────────────────────────────────────────────────────


class TestSeparatorInvariants:
    @pytest.mark.parametrize(
        "text",
        [
            "p = 0,05 and d = 0,87.",
            "controls.7,8 However,",
            "148 (52,272)",
            "Events in 1,234/5,678 (21.7%)",
            "t(28) = 2,21, d = 0,45.",
        ],
    )
    def test_idempotent(self, text):
        once = _norm(text)
        twice = _norm(once)
        assert once == twice, f"not idempotent: {once!r} -> {twice!r}"

    @pytest.mark.parametrize(
        "text",
        [
            "Experiments 1,2 showed the effect.",
            "controls.7,8 However,",
            "148 (52,272)",
            "t(1,197) = 2.31",
        ],
    )
    def test_no_digit_is_invented_or_lost(self, text):
        """A separator rule may re-punctuate; it may never change the digits."""
        digits_before = [c for c in text if c.isdigit()]
        digits_after = [c for c in _norm(text) if c.isdigit()]
        assert digits_before == digits_after
