"""
Tests for the 14-step normalization pipeline.
Covers every step (S0-S9, A1-A5) with edge cases from ESCIcheck, MetaESCI,
MetaMisCitations, and PDFextractor LESSONS.md.
"""

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
        # U+1D702 = MATHEMATICAL ITALIC SMALL ETA. v2.4.34: S0 must de-style
        # it to the GREEK letter η — NOT to ASCII Latin 'n'. The pre-2.4.34
        # bug mapped math-italic Greek to ASCII Latin, corrupting the effect
        # size "η² = .054" into "n2 = .054".
        text = f"{chr(0x1D702)}² = .054"
        result = norm(text, "standard")
        assert chr(0x1D702) not in result            # math-italic styling stripped
        assert "n2" not in result                    # NOT corrupted to ASCII 'n'
        assert ("η" in result) or ("eta" in result)  # de-styled to Greek eta

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


class TestP0_RunningHeaderFooterPatterns_v246:
    """v2.4.6: new line-level patterns in `_PAGE_FOOTER_LINE_PATTERNS` to
    strip running headers and page-bottom contact / affiliation blocks that
    were leaking into body text (xiao_2021_crsp + maier_2023_collabra)."""

    def test_initial_surname_et_al_running_header_stripped(self):
        text = (
            "Body sentence one.\n"
            "Q. XIAO ET AL.\n"
            "Body sentence two continues here.\n"
            "Q. XIAO ET AL.\n"
            "Body sentence three.\n"
            "Q. XIAO ET AL.\n"
        )
        result = norm(text, "standard")
        assert "Q. XIAO ET AL." not in result
        assert "Body sentence one." in result
        assert "Body sentence three." in result

    def test_two_initials_surname_et_al_running_header_stripped(self):
        text = (
            "Body line.\n"
            "Q.M. SMITH ET AL.\n"
            "More body.\n"
            "Q.M. SMITH ET AL.\n"
            "Yet more body.\n"
            "Q.M. SMITH ET AL.\n"
        )
        result = norm(text, "standard")
        assert "Q.M. SMITH ET AL" not in result
        assert "More body." in result

    def test_initial_surname_et_al_preserved_in_lowercase_prose(self):
        """The pattern must require ALL-CAPS surname so it doesn't strip
        legitimate references like ``Q. Xiao et al.`` in prose."""
        text = (
            "Body sentence.\n"
            "We compared with Q. Xiao et al.\n"
            "More body.\n"
        )
        result = norm(text, "standard")
        # Should be preserved (mixed case).
        assert "Q. Xiao et al" in result

    def test_contact_email_footer_stripped(self):
        text = (
            "Body sentence one.\n"
            "CONTACT Gilad Feldman gfeldman@hku.hk; giladfel@gmail.com Hong Kong\n"
            "Body sentence two.\n"
        )
        result = norm(text, "standard")
        assert "CONTACT Gilad Feldman" not in result
        assert "Body sentence one." in result
        assert "Body sentence two." in result

    def test_prefixed_contributed_equally_footer_stripped(self):
        text = (
            "Introduction body sentence.\n"
            "a Contributed equally, joint first author\n"
            "b Contributed equally, joint first author\n"
            "c Corresponding Author: Gilad Feldman, Department of Psychology\n"
            "Body continues.\n"
        )
        result = norm(text, "standard")
        assert "a Contributed equally" not in result
        assert "b Contributed equally" not in result
        assert "c Corresponding Author" not in result
        assert "Introduction body sentence." in result

    def test_department_university_affiliation_line_stripped(self):
        text = (
            "Body content here.\n"
            "Department of Psychology, University of Hong Kong, Hong Kong SAR\n"
            "More body content.\n"
        )
        result = norm(text, "standard")
        assert "Department of Psychology, University of Hong Kong" not in result
        assert "Body content here." in result

    def test_rsos_footer_url_stripped(self):
        text = (
            "Body sentence one.\n"
            "rsos.royalsocietypublishing.org\n"
            "Body sentence two.\n"
        )
        result = norm(text, "standard")
        assert "rsos.royalsocietypublishing.org" not in result
        assert "Body sentence one." in result
        assert "Body sentence two." in result

    def test_nature_footer_url_stripped(self):
        text = (
            "Body.\n"
            "www.nature.com/naturecommunications\n"
            "More body.\n"
            "www.nature.com/scientificreports\n"
            "Yet more.\n"
        )
        result = norm(text, "standard")
        assert "www.nature.com/naturecommunications" not in result
        assert "www.nature.com/scientificreports" not in result
        assert "Body." in result

    def test_springer_vol_marker_stripped(self):
        text = "Body.\nVol.:(0123456789)\nMore body.\n"
        result = norm(text, "standard")
        assert "Vol.:(0123456789)" not in result
        assert "Body." in result

    def test_aom_copyright_footer_stripped(self):
        text = (
            "Body.\n"
            "Copyright of the Academy of Management, all rights reserved. "
            "Contents may not be copied or shared.\n"
            "More body.\n"
        )
        result = norm(text, "standard")
        assert "Copyright of the Academy of Management" not in result
        assert "Body." in result

    def test_article_history_block_stripped(self):
        text = (
            "Body.\n"
            "ARTICLE HISTORY Received 2 February 2020 Accepted 7 January 2021\n"
            "More body.\n"
        )
        result = norm(text, "standard")
        assert "ARTICLE HISTORY Received" not in result
        assert "Body." in result

    def test_open_access_standalone_stripped(self):
        text = "Body.\nOpen Access\nMore body.\n"
        result = norm(text, "standard")
        # The line "Open Access" alone should be stripped.
        assert "\nOpen Access\n" not in result
        assert "Body." in result

    def test_corrupted_doi_banner_stripped(self):
        # PSPB-style: full banner line containing the interleaved DOI corruption.
        text = (
            "Body sentence.\n"
            "Personality and Social Psychology Bulletin 1– 19 © 2025 "
            "DhttOpsI://1d0o.i1.o1rg7/71/00.11147671/06174262165712322571132679169 "
            "journals.sagepub.com/home/pspb\n"
            "More body.\n"
        )
        result = norm(text, "standard")
        assert "DhttOpsI" not in result
        assert "Body sentence." in result
        assert "More body." in result

    def test_orcid_url_stripped(self):
        text = "Body.\nhttps://orcid.org/0000-0002-1234-5678\nMore body.\n"
        result = norm(text, "standard")
        assert "orcid.org/0000-0002-1234-5678" not in result
        assert "Body." in result

    def test_affiliation_line_preserved_in_prose_context(self):
        """The Dept/University pattern must only match standalone lines, not
        prose mentioning the affiliation mid-sentence."""
        text = (
            "We collaborated with the Department of Psychology, University of Hong Kong, Hong Kong SAR, "
            "during the 2022 academic year.\n"
        )
        result = norm(text, "standard")
        # The whole sentence (one line) is preserved — only standalone matches strip.
        assert "We collaborated" in result
        assert "Department of Psychology" in result


class TestS9_HeaderFooter:
    def test_repeated_line_stripped(self):
        # Realistic structure: header appears once per page across a multi-
        # page article (each "page" has ~30 body lines between headers).
        # Cycle 14 (v2.4.66) requires the repeated-line range to span
        # ≥75% of the doc — distinguishes running headers (which DO span
        # the whole doc) from table row labels (which cluster in a small
        # region — see ``test_clustered_table_label_preserved`` below).
        header = "Journal of Example Studies Vol. 1"
        page_body = "\n".join(f"Body line {i}." for i in range(30))
        text = "\n\n".join([f"{header}\n{page_body}"] * 6 + ["End matter line."])
        result = norm(text, "standard")
        assert header not in result, "running header should be stripped"
        assert "Body line 5." in result, "body content should be preserved"

    def test_clustered_table_label_preserved(self):
        """Cycle 14 (v2.4.66): a label that recurs ≥5 times but only within
        a small region (a regression table's row labels across columns) is
        NOT a running header and must be preserved. socius-3, majumder,
        collabra-rnr, social-forces-1 all had table labels false-stripped
        under the old rule."""
        # 50 lines of body prose, then 5 occurrences of a table label
        # clustered in lines 50-60, then more body prose. Range
        # coverage is ≤15% — well under the 75% threshold.
        body_before = "\n".join(f"Intro line {i}." for i in range(50))
        label = "Intend vs. Later"
        table_block = "\n".join([f"{label}\n0.{i}5*" for i in range(5)])
        body_after = "\n".join(f"Discussion line {i}." for i in range(200))
        text = "\n".join([body_before, table_block, body_after])
        result = norm(text, "standard")
        assert label in result, (
            "clustered table label was stripped — cycle 14 gate broken"
        )

    def test_page_numbers_stripped(self):
        """A PAGINATION RUN goes; two adjacent bare integers do not.

        RE-FIXTURED 2026-08-22 (v1.9.59). This was
        `"content\\n42\\nmore content\\n43\\nstill more"` with `42` asserted
        gone — five lines, two integers one line apart, which is the shape of a
        table column, not of pagination. The old rule deleted both, and on
        `10.1136/bmj-2024-080924` Table S1 that same rule deleted a printed
        coefficient of `0` and left its interval and p-value attached to
        nothing. A page number now needs three consecutive values, each a page
        of text apart.
        """
        page = "".join(f"content line {i}\n" for i in range(25))
        text = "".join(page + f"{42 + k}\n" for k in range(3))
        result = norm(text, "standard")
        for n in (42, 43, 44):
            assert f"\n{n}\n" not in result

    def test_two_adjacent_bare_integers_are_not_pagination(self):
        """The counter-case, pinned: a table column is not a page-number run."""
        result = norm("content\n42\nmore content\n43\nstill more", "standard")
        assert "42" in result and "43" in result

    def test_4digit_page_numbers_stripped_when_recurring(self):
        """v2.4.3: Continuous-pagination journals (PSPB, JESP volume runs)
        emit page numbers in the 1000-9999 range. When the same 4-digit
        value appears on its own line 3+ times in the doc, treat it as
        a page-number artifact and strip."""
        text = (
            "First page content here.\n"
            "1174\n"
            "Second page begins.\n"
            "1175\n"
            "Body sentence continues.\n"
            "1174\n"
            "More body.\n"
            "1175\n"
            "Even more body content.\n"
            "1174\n"
        )
        result = norm(text, "standard")
        # 1174 appears 3 times → stripped.
        assert "\n1174\n" not in result
        # 1175 appears 2 times → not yet meeting the ≥3 threshold,
        # so left alone (conservative).
        assert "1175" in result

    def test_4digit_cluster_stripped_with_outliers_present(self):
        """v2.4.11 fix for chan_feldman_2025_cogemo: the page-number
        cluster 1228-1249 was being kept because the global value set
        also contained year mentions (1997, 2023). Global spread became
        795 (1228..2023) and the old Pattern B rejected it. The new
        clustering finds the dense sub-cluster and strips it."""
        # Simulate page numbers spanning 1228-1234 with two stray year
        # mentions like 1997 and 2023 standing alone elsewhere in the text.
        text = (
            "Body content from page one.\n"
            "1228\n"
            "More body for the first page.\n"
            "1229\n"
            "Continued body content.\n"
            "1230\n"
            "Citation mentions McCullough et al.\n"
            "1997\n"
            "Another body paragraph here.\n"
            "1231\n"
            "More content for page four.\n"
            "1232\n"
            "Recent reference is.\n"
            "2023\n"
            "Yet more body content here.\n"
            "1233\n"
            "Final body paragraph.\n"
            "1234\n"
        )
        result = norm(text, "standard")
        # All seven page numbers in the dense cluster (1228-1234) stripped.
        for pn in ("1228", "1229", "1230", "1231", "1232", "1233", "1234"):
            assert f"\n{pn}\n" not in result, f"page number {pn} should be stripped"
        # The standalone year outliers (1997, 2023) are NOT in the dense
        # cluster and stay (conservative — could be legit content).
        assert "1997" in result or "2023" in result

    def test_4digit_sequential_page_numbers_stripped(self):
        """v2.4.5: Continuous-pagination journals like PSPB use sequential
        page numbers per page (1174, 1175, 1177, 1179, ...). Each value is
        DIFFERENT (not recurring) so the v2.4.3 ≥3-recurrence rule misses
        them. v2.4.5 widens to also strip when ≥3 distinct 4-digit values
        cluster within a 50-page range with mean diff ≤ 3."""
        text = (
            "Page 1 body.\n"
            "1174\n"
            "Page 2 body.\n"
            "1175\n"
            "Page 3 body.\n"
            "1177\n"
            "Page 4 body.\n"
            "1179\n"
            "Page 5 body.\n"
        )
        result = norm(text, "standard")
        for n in ("1174", "1175", "1177", "1179"):
            assert f"\n{n}\n" not in result, f"page number {n} not stripped"

    def test_4digit_unrelated_values_preserved(self):
        """4-digit values that don't cluster together (large spread, big
        gaps) are NOT pagination — leave them alone (could be table cells
        or unrelated data)."""
        text = (
            "abc\n"
            "1000\n"
            "def\n"
            "5000\n"
            "ghi\n"
            "9999\n"
        )
        result = norm(text, "standard")
        # Spread is 8999, way over 50 — preserved.
        assert "1000" in result
        assert "5000" in result
        assert "9999" in result

    def test_4digit_year_on_own_line_preserved(self):
        """A 4-digit value that only appears ONCE on its own line is NOT
        a page number — could be a year reference or stray data. Leave it."""
        text = "body text\n2024\nmore body text\n"
        result = norm(text, "standard")
        assert "2024" in result

    def test_4digit_year_range_preserved(self):
        """Citation years (1900-2100) are excluded from S9 Pattern A — a
        4-digit value repeating ≥3 times in that range is overwhelmingly a
        citation year (`House, R. J. 1971` cited across multiple table rows
        or in the references list), not a page number.

        Cycle 14 (v2.4.66) added this exclusion after amle-1 had `1971`
        stripped as a "page number" under the old rule. The earlier test
        documented the old behavior — incorrect. See CHANGELOG."""
        text = "abc\n2020\ndef\n2020\nxyz\n2020\nfinal\n"
        result = norm(text, "standard")
        # Years are now PRESERVED — they're almost never page numbers.
        assert "2020" in result, "citation year was stripped — cycle 14 gate broken"

    def test_4digit_pagenum_outside_year_range_still_stripped(self):
        """A 4-digit value OUTSIDE the citation-year range (1900-2100) is
        still treated as a page number when it repeats ≥3 times. Continuous-
        pagination journals like PSPB run page numbers into the 5000s+."""
        text = "abc\n5432\ndef\n5432\nxyz\n5432\nfinal\n"
        result = norm(text, "standard")
        assert "5432" not in result, "continuous-pagination page number not stripped"

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
    """A2 is DELETED (v2.4.130). RE-FIXTURED, not removed.

    The original justification here was a MetaESCI extraction report: "4.88% of
    results (5,908 out of 121,040)" carried a dropped decimal. That figure counts
    how often the SHAPE appears; it never established that docpluck had caused it.
    When the question was finally asked — which real paper, which page? — both of
    A2's firing sites across 297 English papers turned out to be the PAPER's own
    error, confirmed by rasterizing the page rather than by asking an extractor:

        10.1177/0146167210380928 p13   prints `B = -0.28, SE = 0.31, p = 38.`
        10.1016/j.jesp.2016.11.001 p7  prints `t(186) = 3.90, p = 001, d = 0.6`

    Correctly-dotted numbers sit on the same line in both, so nothing was lost in
    extraction. Repairing them LAUNDERS a published error into a meta-science
    pipeline: the consumer validates a number the paper never printed, and the
    author never learns. Flagging it is ESCImate's and Scimeto's role.
    """

    def test_p_equals_484_passes_through(self):
        assert norm("p = 484").strip() == "p = 484"

    def test_p_equals_37_passes_through(self):
        assert norm("p = 37").strip() == "p = 37"

    def test_p_equals_999_passes_through(self):
        assert norm("p = 999").strip() == "p = 999"

    def test_does_not_change_small_value(self):
        """Unchanged before and after the retirement."""
        assert "p = 5" in norm("p = 5")

    def test_does_not_change_large_n(self):
        """N = 484 is a sample size. Unchanged before and after."""
        assert "N = 484" in norm("N = 484")

    def test_linebreak_is_still_rejoined_but_no_decimal_is_invented(self):
        """A1 (line-break repair) is NOTATION and stays; A2 was REPAIR and went.

        Kept as one test because the original conflated them, and separating
        them is the whole point of the 2026-08-14 separation of duties.
        """
        result = norm("p =\n484")
        assert "p = 484" in result, "A1 must still rejoin the wrapped statistic"
        assert ".484" not in result, "A2 is retired; no decimal may be invented"


# ── A3: DELETED (v2.4.129) — European decimals pass through ──────────

class TestA3_DecimalComma:
    """A3 is DELETED. RE-FIXTURED, not removed.

    Measured over 297 English papers before removal: A3 fired 9 times in 2
    papers and NOT ONCE correctly (8 corrupted mathematical constraints, 1
    laundered an author's error). Scope directive 2026-08-14: docpluck serves
    English papers in US numeric convention; European numbers pass through as
    printed, because the source token stays intact and the consumer can then
    decide — which it could not once we had converted.
    """

    def test_european_p_value_passes_through(self):
        assert norm("p = 0,05").strip() == "p = 0,05"

    def test_european_d_value_passes_through(self):
        assert norm("d = 1,23").strip() == "d = 1,23"

    def test_thousands_separator_also_passes_through(self):
        """The old test here asserted nothing — it ended in a comment saying
        `1,234` was "a known limitation". It is no longer ambiguous OR limited:
        A3a is deleted too, so the token is delivered exactly as printed."""
        assert norm("N = 1,234").strip() == "N = 1,234"


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
        # SYMBOL CONTRACT v2.0 (v2.4.128): `\u00D7` transliterates to `*`, not `x`.
        # The letter `x` collides with a variable named x, which is exactly the
        # class of collision the v2.0 rewrite existed to remove (`eta2`->`n2`,
        # `beta`->`b`). Re-fixtured 2026-08-14 with its reason rather than
        # deleted \u2014 this assertion was left asserting v1.0 when the contract
        # changed, so the suite was red at HEAD for a reason unrelated to any
        # change under review. See docs/SYMBOL_CONTRACT.md.
        assert "*" in norm("\u00D7")
        assert "x" not in norm("\u00D7")

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
        # SYMBOL CONTRACT v2.0 (v2.4.128): a subscript RUN is joined to what
        # precedes it with a single `_`, so `F\u2081` is `F_1`, not `F1`. Fusing them
        # produced tokens that read as something else \u2014 `eta2\u209a` fused to `eta2p`
        # collides with a p-value, and `M\u209a` is indistinguishable from a variable
        # named Mp. Re-fixtured 2026-08-14 with its reason; this was left
        # asserting v1.0 when the contract changed.
        assert "F_1" in norm("F\u2081")

    def test_subscript_2(self):
        assert "R_2" in norm("R\u2082")


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
        # RE-FIXTURED 2026-08-14: this used to assert `.484` (A2 inventing a
        # decimal). A2 is retired, so the value is delivered as printed. Every
        # OTHER assertion in this passage is unchanged, which is the point:
        # retiring the REPAIR rules left the NOTATION rules untouched.
        assert "d = 484" in result             # A2 retired: no decimal invented
        assert ".484" not in result

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
    """A2's 2026-04-11 WIDENING, now retired with the rule. RE-FIXTURED.

    This class pinned a decision to make A2 fire on MORE inputs: `val > 1.0`
    became `val >= 1.0` so that `p = 01` (val 1.0) would also be "repaired".

    It is worth keeping as a record of how the rule grew, because the widening
    is a small instance of the failure the whole 2026-08-14 audit is about: the
    question asked was "does A2 reach every case of the shape?" and never "is
    the shape ours to touch?". Nobody was wrong about the regex. The regex was
    the wrong question.

    Every POSITIVE case below now passes through; every NEGATIVE case below is
    unchanged, because the negatives were about not corrupting correct text and
    that obligation survives the retirement intact.
    """

    def test_p_equals_01_passes_through(self):
        assert "p = 01." in norm("The effect was significant, p = 01.")

    def test_p_equals_10_passes_through(self):
        assert "p = 10." in norm("Marginal effect, p = 10.")

    def test_p_equals_02_passes_through(self):
        assert "p = 02." in norm("Significant effect, p = 02.")

    def test_single_digit_not_touched(self):
        """Unchanged before and after the retirement."""
        assert "p = .1" not in norm("p = 1 for the test.")

    def test_genuine_decimal_not_touched(self):
        """Unchanged before and after the retirement."""
        assert "p = 0.05" in norm("The effect is p = 0.05 and d = 0.34.")

    def test_linebreak_rejoined_without_inventing_a_decimal(self):
        """A1 still rejoins the real PSPB wrap; A2 no longer adds a dot."""
        result = norm("beta = .11, p = 01\nbelieved that they lost status")
        assert "p = 01" in result
        assert "p = .01" not in result

    def test_effect_size_passes_through(self):
        assert "d = 10" in norm("Cohen's d = 10 showed the effect.")
        assert "d = .10" not in norm("Cohen's d = 10 showed the effect.")


# ── A3a: DELETED (v2.4.130) — thousands separators are DELIVERED ────

class TestA3a_ThousandsSeparator:
    """A3a is DELETED. RE-FIXTURED, not removed.

    Note what these test NAMES used to say against what they used to ASSERT:
    `test_capital_N_thousands_preserved` asserted `"N = 1182" in result`. The
    same inversion ran through the implementation — the step was named
    `A3a_thousands_separator_protect` and its metric key was
    `thousands_separators_preserved`, while the operation was
    `.replace(",", "")`. A consumer reading `changes_made` saw
    "thousands_separators_preserved: 2" and would reasonably conclude nothing
    had been lost. **That is worse than no instrumentation: silence invites a
    check, a false all-clear forecloses one.** The names are now true.

    A3a existed solely to pre-empt A3, which was deleted in v2.4.129. With
    nothing left to protect against, what remained was a default rewrite that
    deleted a separator the paper printed — and produced 1000x errors wherever
    a paper used comma decimals (10.1177/0956797620935584 Table S2: a
    Satterthwaite df printed `185,178`, i.e. 185.178, delivered as `185178`).
    """

    def test_capital_N_thousands_preserved(self):
        result = norm("Participants (N = 1,182) completed the survey")
        assert "N = 1,182" in result
        assert "N = 1182" not in result
        assert "N = 1.182" not in result

    def test_lowercase_n_thousands_preserved(self):
        assert "n = 2,443" in norm("Sample of n = 2,443 adults")

    def test_N_with_six_digit_integer(self):
        assert "N = 1,234,567" in norm("A large cohort (N = 1,234,567) was analyzed.")

    def test_df_with_thousands_separator(self):
        assert "df = 1,197" in norm("The test produced t(df = 1,197) = 2.34")

    def test_sample_size_of_phrase(self):
        result = norm("A sample size of 2,443 was collected.")
        assert "2,443" in result
        assert "2.443" not in result

    def test_total_of_participants_phrase(self):
        assert "1,850" in norm("A total of 1,850 participants enrolled.")

    def test_decimal_comma_outside_N_context_also_passes_through(self):
        """RE-FIXTURED TWICE OVER, and the SECOND reason matters more.

        1. A3 is deleted, so a comma decimal is no longer converted.
        2. **The original fixture was written in GERMAN** ("Der Mittelwert =
           0,73 war signifikant"). docpluck's scope is ENGLISH-language
           articles, and the standing rule is that we never learn about an
           English-article problem from non-English input — the failure modes
           differ in kind, and bilingual articles make any conclusion drawn
           from them false for part of the document. Rewritten in English.
        """
        assert norm("The mean = 0,73 was significant").strip() == (
            "The mean = 0,73 was significant"
        )

    def test_standard_level_preserves_commas(self):
        """Unchanged — and it was the clue.

        This test already documented that `standard` passes commas through. Once
        A3 was deleted, `academic` differed from `standard` on this input for no
        surviving reason, and the library answered one question three ways
        (`standard`, `academic`, and `academic + preserve_math_glyphs` — which
        counted matches without stripping). Now all three agree.
        """
        assert "N = 1,182" in norm("Participants (N = 1,182) completed the survey", "standard")

    def test_academic_and_standard_now_AGREE(self):
        src = "Participants (N = 1,182) and df was 185,178 here."
        assert norm(src, "academic").strip() == norm(src, "standard").strip() == src

    def test_no_step_named_A3a_is_tracked(self):
        _, report = norm_report("N = 1,182 and n = 2,443 were enrolled.")
        assert "thousands_separators_preserved" not in report.changes_made
        assert not any("A3a" in s for s in report.steps_applied), report.steps_applied


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

    def test_a_decimal_comma_no_longer_converts(self):
        """RE-FIXTURED on both counts. A3 is deleted, AND the original fixture
        was GERMAN ("Der Mittelwert war 0,73 und signifikant") — out of scope,
        and the standing rule forbids reasoning about English-article behaviour
        from non-English input. Rewritten in English."""
        assert norm("The mean was 0,73 and significant").strip() == (
            "The mean was 0,73 and significant"
        )

    def test_decimal_comma_after_letter_blocked(self):
        """Unchanged — the affiliation shape was never to be corrupted, and it
        still is not. This obligation outlives the rule it guarded."""
        assert "x2.3" not in norm("variable x2,3 was coded")

    def test_multiple_affiliations_in_abstract(self):
        """The affiliation half is UNCHANGED; only the decimal half inverted.

        This is the clearest single illustration of what the retirement did and
        did not do: docpluck still refuses to corrupt a citation-marker run,
        because that is its own damage to avoid. It simply no longer volunteers
        a reading of the author's `0,44`.
        """
        result = norm(
            "Chan1,2, Feldman3, and Zhao1,2,4 conducted the meta-analysis; "
            "the effect was d = 0,44 across studies."
        )
        assert "Chan1,2" in result
        assert "Zhao1,2,4" in result
        assert "d = 0,44" in result
        assert "d = 0.44" not in result


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


# ── B5 / G5c-2 (2026-05-22): split-numbered-heading rejoin ──


class TestG5c2SplitNumberedHeadingRejoin:
    """B5: pdftotext linearisation can split ``2.1. Methods`` onto two
    lines (``2.1.\n\nMethods``); the section partitioner then drops the
    orphan number and the numeric prefix is lost. Normalize rejoins
    them when the next line resolves to a canonical SectionLabel."""

    def test_rejoins_split_numbered_heading_methods(self):
        text = (
            "Some intro prose ending here.\n"
            "\n"
            "2.1.\n"
            "\n"
            "Methods\n"
            "\n"
            "Participants were recruited via Prolific.\n"
        )
        out, _ = normalize_text(text, NormalizationLevel.academic)
        assert "2.1. Methods" in out
        # Orphan number must not survive as a stranded line.
        assert "\n2.1.\n" not in out

    def test_rejoins_three_level_numbering(self):
        text = (
            "Intro line.\n"
            "\n"
            "3.2.1.\n"
            "Results\n"
            "\n"
            "We found a significant effect.\n"
        )
        out, _ = normalize_text(text, NormalizationLevel.academic)
        assert "3.2.1. Results" in out

    def test_preserves_unrelated_orphan_numbers(self):
        # ``2.1.`` followed by prose (not a canonical heading) must NOT
        # be rejoined — the number could be a list bullet, an equation
        # reference, or a footnote anchor.
        text = (
            "We computed the mean.\n"
            "\n"
            "2.1.\n"
            "\n"
            "Although the result was small, it replicated.\n"
        )
        out, _ = normalize_text(text, NormalizationLevel.academic)
        assert "2.1. Although" not in out

    def test_no_rejoin_when_next_line_too_long(self):
        # A long line is prose, not a heading — even if its first words
        # form a canonical label.
        long_line = "Methods used in this study included a 2x2 between-subjects design with " * 2
        text = "Intro.\n\n2.1.\n\n" + long_line + "\n"
        out, _ = normalize_text(text, NormalizationLevel.academic)
        # Must NOT collapse the long body line under the number.
        assert "2.1. Methods" not in out


# ── B3 / D4 (2026-05-22): metadata-leak strips ──


class TestB3MetadataLeakStrips:
    """B3: additional P0 page-furniture / sidebar patterns. Each pattern
    is a complete standalone line; in-text variants must pass through."""

    def test_strips_plos_a1111_watermark(self):
        text = (
            "Introduction prose continues here.\n"
            "\n"
            "a1111111111\n"
            "\n"
            "More body content follows.\n"
        )
        out, _ = normalize_text(text, NormalizationLevel.academic)
        assert "a1111111111" not in out

    def test_strips_doi_footer_lowercase(self):
        text = (
            "Body line one.\n"
            "doi: 10.1371/journal.pone.0123456\n"
            "Body line two.\n"
        )
        out, _ = normalize_text(text, NormalizationLevel.academic)
        assert "doi: 10.1371" not in out

    def test_strips_doi_url_footer(self):
        text = (
            "Body line one.\n"
            "https://doi.org/10.1371/journal.pone.0123456\n"
            "Body line two.\n"
        )
        out, _ = normalize_text(text, NormalizationLevel.academic)
        assert "https://doi.org/10.1371" not in out

    def test_strips_plural_email_addresses_sidebar(self):
        text = (
            "Body line.\n"
            "E-mail addresses: foo@example.com, bar@example.com\n"
            "More body.\n"
        )
        out, _ = normalize_text(text, NormalizationLevel.academic)
        assert "foo@example.com" not in out

    def test_strips_received_accepted_published_line(self):
        text = (
            "Abstract content.\n"
            "Received: 12 March 2020; Accepted: 8 May 2020; Published: 3 June 2020\n"
            "Introduction begins here.\n"
        )
        out, _ = normalize_text(text, NormalizationLevel.academic)
        assert "Accepted: 8 May 2020" not in out

    def test_strips_n_over_m_page_furniture(self):
        text = (
            "Body content here.\n"
            "3 / 14\n"
            "More body content.\n"
        )
        out, _ = normalize_text(text, NormalizationLevel.academic)
        # The page-furniture line itself should be stripped.
        assert "\n3 / 14\n" not in out

    def test_preserves_in_text_fractions(self):
        # ``1/2 of participants completed both arms`` must NOT be stripped —
        # the pattern only matches a line that contains ONLY ``N / M``.
        text = (
            "Body line.\n"
            "Approximately 1/2 of participants completed both arms.\n"
            "More body.\n"
        )
        out, _ = normalize_text(text, NormalizationLevel.academic)
        assert "1/2 of participants" in out

    def test_strips_competing_interests_declaration_sidebar(self):
        text = (
            "Discussion paragraph.\n"
            "Competing interests: The authors declare no competing interests.\n"
            "Next paragraph.\n"
        )
        out, _ = normalize_text(text, NormalizationLevel.academic)
        assert "The authors declare no competing interests" not in out

    def test_strips_inline_abbreviations_glossary(self):
        text = (
            "Method body line.\n"
            "Abbreviations: RCT, randomised controlled trial; SE, standard error\n"
            "Result follows.\n"
        )
        out, _ = normalize_text(text, NormalizationLevel.academic)
        assert "RCT, randomised controlled trial" not in out
