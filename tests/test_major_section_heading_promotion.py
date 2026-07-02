"""Major-section heading promotion — `## `-level rescue of long Sentence-case
titles that the ≤6-word `### ` promoter leaves as body text.

Background
==========
RR / replication papers (PCI-RR house style especially) write major-section
headings as 5-12 word Sentence-case phrases, e.g.::

    Original hypotheses and findings in the target article
    Extension: examining causal link with empathy manipulation
    Extension: the impact of empathy on forgiveness
    Citation of the target research article

``_promote_isolated_titlecase_subsection_headings`` (and its helper
``_looks_like_titlecase_subsection_label``) only accept ≤6-word / ≤60-char
lines, so these longer titles fall through and stay demoted to plain body
text — the reader sees the whole RR scaffold flattened.

The fix adds a SEPARATE ``## ``-level promoter
(``_promote_isolated_major_section_headings``) keyed on a strict structural
signature (paragraph-isolated + Sentence-case + 5-12 words + <=80 chars + NO
sentence-terminating punctuation except an optional trailing/mid colon +
followed by genuine body prose). It runs AFTER the existing ``### `` promoter
so it only catches what that path left behind, and it never relaxes the
carefully-tuned ≤6-word guards (which protect against B2 over-promotion:
ip_feldman "Supplemental Materials" mid-Method, xiao "KEYWORDS").

Keyed on a STRUCTURAL SIGNATURE (typographic shape + paragraph isolation +
following-prose), never on paper identity — generalises to any PDF whose major
section headings are long Sentence-case phrases. See CLAUDE.md hard rule
"EVERY FIX MUST BE GENERAL".
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from docpluck.render import (
    _looks_like_major_section_label,
    _promote_isolated_major_section_headings,
    render_pdf_to_markdown,
)

try:
    from tests.conftest import pdf_available, pdf_path
except Exception:  # pragma: no cover - direct-invocation fallback
    from conftest import pdf_available, pdf_path


# ── Body prose used as the "following paragraph" in synthetic blocks ──────
_PROSE = (
    "McCullough et al. (1997) conceptualised interpersonal forgiving as the "
    "set of motivational changes whereby a victim becomes less motivated to "
    "retaliate and more motivated to conciliate."
)
_PROSE2 = (
    "We aimed to extend the replication study by manipulating empathy directly "
    "rather than measuring it, testing the proposed causal chain end to end."
)


def _block(*lines: str) -> str:
    return "\n".join(lines)


def _doc(*lines: str) -> str:
    """A synthetic block placed at a realistic MID-document position: a prior
    document title (``# ``) + an earlier ``## `` section sit above, so the
    candidate has a heading above it (the major-section promoter vetoes
    candidates in the pre-title masthead/title zone, where the only heading-
    shaped line is the paper title itself)."""
    return "\n".join(("# Paper Title", "", "## Introduction", "", *lines))


# ── Unit tests on the shape predicate ─────────────────────────────────────


class TestMajorSectionLabelShape:
    @pytest.mark.parametrize(
        "line",
        [
            "Original hypotheses and findings in the target article",  # 8 words
            "Extension: examining causal link with empathy manipulation",  # 7 + colon
            "Extension: the impact of empathy on forgiveness",  # 7 + colon
            "Citation of the target research article",  # 6 words
            "Differences between the replication and the target study",  # 8 words
            "Power analysis and sensitivity to the smallest effect size",  # 9 words
            # complete prepositional tail "of Donation" — NOT a truncation joint
            # ("of" is a preposition heading a complete phrase). Genuine maier
            # heading that a broad "any function word" penult guard wrongly cut.
            "Extension: Perceived Impact of Donation",
            # short heading qualifier "(Johnson & Goldstein, 2003)" (4 tokens) OK
            "Part 1: Replication of Johnson and Goldstein (2003)",
        ],
    )
    def test_positive_shapes(self, line: str) -> None:
        assert _looks_like_major_section_label(line), f"should accept: {line!r}"

    @pytest.mark.parametrize(
        "line",
        [
            # ── ends in a period → a wrapped body sentence, not a heading
            "We then conducted a between-subjects ANOVA on the data.",
            # ── contains a mid-sentence period
            "We follow Smith et al. and report the omnibus test result",
            # ── dangles on a function word → head/tail of a wrapped sentence
            "The calculated effect sizes are summarized in the",
            "We computed the correlation between empathy and forgiveness and",
            # too short for THIS path (the <=6-word ### path owns it)
            "Original hypotheses",
            "Contributor roles taxonomy",  # 3 words
            "Choice of Study",  # 3 words — existing path's job
            # too long (> 12 words)
            "This is a very long sentence fragment that clearly exceeds the "
            "twelve word ceiling for a heading by a wide margin indeed",
            # first word lowercase → grammatical continuation / wrap
            "between apology, empathy and forgiveness in the target sample data",
            # all caps → metadata label, not a Sentence-case heading
            "MATERIALS AND METHODS USED IN THE PRESENT REPLICATION STUDY",
            # figure / table caption prefix
            "Table 1 Means and standard deviations for the forgiveness scale",
            "Figure 2 Path diagram for the empathy model of forgiveness here",
            # ── 2026-07-01: real column-wrap TRUNCATION fragments found in the
            #    canary corpus that over-promoted to `## ` (efendic / maier /
            #    ip_feldman). Each is a wrapped body sentence or a real heading
            #    cut mid-phrase by a two-column page break — none is a complete
            #    title, so all must be rejected (B2 hallucinated-heading guard).
            # clause opener "Both" + unbalanced "(" (efendic Results body)
            "Both studies had a 2 (Between-subject factor--Direction:",
            # dangles "the <Capitalized>" — gold heading continues "Victim Effect…"
            "Reanalysis of a Meta-Analysis on the Identifiable",
            # unbalanced "(" — gold "Affective Reactions (with Perceived Impact Extension)"
            "Affective Reactions (with Perceived Impact",
            # leading ")" tail of a wrapped paren (maier)
            "Condition) Main Effect (without Explicit Learning)",
            # unbalanced "(" trailing (maier)
            "Effects and Interaction on Aggregated Feelings (with",
            # dangles "and <Capitalized>" — gold "…and Explicit Learning…"
            "H1a, H2a, and H3a: Identifiability and Explicit",
            # dangling possessive — gold "…Using Target's <noun>" (ip_feldman)
            "External Analysis: Suppression Using Target's",
            # long descriptive parenthetical (7-word clause) → table caption,
            # not a heading qualifier (ar_apa Results table caption).
            "Positive Expectations Ps (all 17 of whom accepted final offer)",
        ],
    )
    def test_negative_shapes(self, line: str) -> None:
        assert not _looks_like_major_section_label(line), f"should reject: {line!r}"

    def test_affiliation_line_rejected(self) -> None:
        # An affiliation line in the 5-12 word window must NOT be a heading.
        assert not _looks_like_major_section_label(
            "Department of Psychology, Norwegian University of Science and Technology"
        )


# ── Promoter behaviour (synthetic) ────────────────────────────────────────


class TestMajorSectionPromotion:
    def test_promotes_long_sentence_case_title(self) -> None:
        md = _doc(
            "and aiming to test causal relationships in the present design.",
            "",
            "Original hypotheses and findings in the target article",
            _PROSE,
        )
        out = _promote_isolated_major_section_headings(md)
        assert "## Original hypotheses and findings in the target article" in out

    def test_promotes_extension_colon_title(self) -> None:
        md = _doc(
            "described the incident in their own words to the experimenter.",
            "",
            "Extension: examining causal link with empathy manipulation",
            _PROSE2,
        )
        out = _promote_isolated_major_section_headings(md)
        assert "## Extension: examining causal link with empathy manipulation" in out

    def test_promotes_second_extension_colon_title(self) -> None:
        md = _doc(
            "These would be conducted as exploratory analyses only.",
            "",
            "Extension: the impact of empathy on forgiveness",
            "We conducted two between-subjects ANOVAs to examine how apology and "
            "forgiveness differ across the empathy manipulation conditions.",
        )
        out = _promote_isolated_major_section_headings(md)
        assert "## Extension: the impact of empathy on forgiveness" in out

    def test_promotes_when_prose_evidence_is_second_follow_line(self) -> None:
        # "Citation of the target research article" is followed by a reference
        # author-list line (terminated, no lowercase word), then a prose line.
        # The first-2-follow-lines prose probe must admit it.
        md = _doc(
            "Recommended for publication by Peer Community in Registered Reports.",
            "",
            "Citation of the target research article",
            "McCullough, M. E., Worthington, E. L., & Rachal, K. C. (1997).",
            "Interpersonal Forgiving in Close Relationships. Journal of "
            "Personality and Social Psychology, 73, 321-336.",
        )
        out = _promote_isolated_major_section_headings(md)
        assert "## Citation of the target research article" in out

    def test_promotes_after_url_terminated_prior_paragraph(self) -> None:
        # PCI-RR / RR endmatter: a recommendation block ends in a bare DOI URL
        # immediately before the "Citation of the target research article"
        # header. The prior line has no `.`/`!`/`?` terminator (ends in the
        # URL), but a URL is an unambiguous paragraph end.
        md = _doc(
            "Recommended for publication by Peer Community in Registered "
            "Reports. See recommendation on: https://doi.org/10.24072/pci.rr.100444",
            "",
            "Citation of the target research article",
            "McCullough, M. E., Worthington, E. L., & Rachal, K. C. (1997).",
            "Interpersonal Forgiving in Close Relationships. Journal of "
            "Personality and Social Psychology, 73, 321-336.",
        )
        out = _promote_isolated_major_section_headings(md)
        assert "## Citation of the target research article" in out

    def test_promotes_with_blank_after(self) -> None:
        md = _doc(
            "and aiming to test causal relationships in the present design.",
            "",
            "Differences between the replication and the target study",
            "",
            _PROSE,
        )
        out = _promote_isolated_major_section_headings(md)
        assert "## Differences between the replication and the target study" in out


# ── Negative cases the promoter must NOT touch ────────────────────────────


class TestMajorSectionPromotionGuards:
    def test_wrapped_body_sentence_fragment_not_promoted(self) -> None:
        # An 8-word line that is the tail of a wrapped sentence (the PRIOR
        # paragraph did not end with a terminator) must NOT promote.
        md = _block(
            "We computed the correlation between empathy and forgiveness and",
            "found a moderate positive association across all conditions tested",
            _PROSE,
        )
        out = _promote_isolated_major_section_headings(md)
        assert "## " not in out

    def test_line_ending_in_period_not_promoted(self) -> None:
        md = _block(
            "Prior work motivated this design.",
            "",
            "We then examined the impact of empathy on forgiveness directly.",
            _PROSE,
        )
        out = _promote_isolated_major_section_headings(md)
        assert "## " not in out

    def test_affiliation_line_not_promoted(self) -> None:
        md = _block(
            "We thank the participants for their time and effort.",
            "",
            "Department of Psychology, Norwegian University of Science and Technology",
            _PROSE,
        )
        out = _promote_isolated_major_section_headings(md)
        assert "## Department of Psychology" not in out
        # Text preserved as body (guard vetoes promotion, never deletes).
        assert "Department of Psychology" in out

    def test_short_title_left_for_existing_path(self) -> None:
        # A <=6-word Title-Case label is the existing ### path's job; THIS
        # promoter must leave it untouched (no ## emission).
        md = _block(
            "Prior work motivated this design.",
            "",
            "Choice of Study",
            _PROSE,
        )
        out = _promote_isolated_major_section_headings(md)
        assert "## Choice of Study" not in out
        assert "### Choice of Study" not in out  # not our job to ### it either

    def test_supplemental_materials_orphan_no_following_prose_not_promoted(self) -> None:
        # The B2 trap: a label-shaped line orphaned mid-paragraph by a column
        # wrap, with NO genuine following prose paragraph (next line is another
        # short label / cell), must NOT promote.
        md = _block(
            "The calculated effect sizes are summarized in the",
            "",
            "Supplemental analyses and robustness checks reported here",
            "Role",
            "Conceptualisation",
        )
        out = _promote_isolated_major_section_headings(md)
        assert "## " not in out

    def test_does_not_double_promote_existing_h3(self) -> None:
        # A line already turned into ### by the earlier path is skipped.
        md = _block(
            "Prior work motivated this design.",
            "",
            "### Extension: the impact of empathy on forgiveness",
            _PROSE,
        )
        out = _promote_isolated_major_section_headings(md)
        out_lines = out.split("\n")
        # The ### line is preserved verbatim and NO new ## line is emitted
        # (assert on whole lines — "## X" is a substring of "### X").
        assert "### Extension: the impact of empathy on forgiveness" in out_lines
        assert "## Extension: the impact of empathy on forgiveness" not in out_lines

    def test_all_caps_not_promoted(self) -> None:
        md = _block(
            "Prior work motivated this design.",
            "",
            "MATERIALS AND METHODS USED IN THE PRESENT STUDY",
            _PROSE,
        )
        out = _promote_isolated_major_section_headings(md)
        assert "## MATERIALS AND METHODS" not in out

    def test_document_title_not_promoted(self) -> None:
        # The paper TITLE sits in the pre-`# ` masthead/title zone with NO
        # heading above it, followed by its wrapped continuation + author byline
        # (which can read as prose). It must NOT become a ## section — that is
        # the H1's job. (ip_feldman / cog_emo regression: the title line
        # "The link between Empathy and Forgiveness:" was wrongly promoted.)
        md = _block(
            "The link between Empathy and Forgiveness in close relationships",
            "Replication and extensions Registered Report of a classic study",
            "Chi Fung Chan and Gilad Feldman from the University here",
        )
        out = _promote_isolated_major_section_headings(md)
        assert "## " not in out

    def test_wrapped_sentence_head_not_promoted(self) -> None:
        # The candidate is the HEAD of a wrapped sentence: the following line
        # continues it ("(intensity), and correlations in Table 8."). A real
        # heading's body opens a NEW sentence. (ip_feldman regression #2:
        # "We summarized descriptives in Tables 6 (prevalence) and 7".)
        md = _doc(
            "results are reported below in the following subsection.",
            "",
            "We summarized descriptives in Tables 6 prevalence and so on",
            "(intensity), and correlations in Table 8. Consistent with H2a we "
            "found support for an underestimation effect across conditions.",
        )
        out = _promote_isolated_major_section_headings(md)
        assert "## We summarized descriptives" not in out

    def test_paren_qualifier_following_line_still_promotes(self) -> None:
        # A genuine heading whose qualifier "(Extension)" column-wrapped onto
        # its own line is NOT a sentence continuation — promotion must proceed.
        # (ip_feldman regression #5/#6.)
        md = _doc(
            "We conclude the prevalence analyses end here in this subsection.",
            "",
            "Intensity Estimates Associations with Well-Being",
            "(Extension)",
            "We conducted the same analyses on intensity estimates as the ones "
            "reported above for prevalence, summarized in Tables 8 and 10.",
        )
        out = _promote_isolated_major_section_headings(md)
        assert "## Intensity Estimates Associations with Well-Being" in out

    def test_single_short_cell_label_not_promoted(self) -> None:
        # A short single-line non-terminated "paragraph" after the candidate is
        # a table-cell label, not a section body. (ip_feldman regression #4:
        # "Overall positive and negative combined" → "Overall positive: target
        # article (Study 3)".)
        md = _doc(
            "Note. One-sample t-tests, N = 594, df = 593, 95% CI shown below.",
            "",
            "Overall positive and negative combined estimates",
            "Overall positive: target article (Study 3)",
            "",
            "Overall negative: target article (Study 3)",
        )
        out = _promote_isolated_major_section_headings(md)
        assert "## Overall positive and negative combined" not in out

    def test_table_caption_wrapped_first_line_not_promoted(self) -> None:
        # The candidate is the WRAPPED first line of a table caption whose
        # "Table N. …" line follows — not a section heading. (chandrashekar
        # regression: "The results of Study 1 of Johnson & Goldstein (2003)" →
        # "Table S7. The results of Binomial Logistic Regression".)
        md = _doc(
            "We reproduced the results of the original study to pin-point it.",
            "",
            "Summary of Study 1 of Johnson and Goldstein (2003)",
            "Table S7. The results of Binomial Logistic Regression models.",
            "95% Confidence Interval reported for each coefficient below.",
        )
        out = _promote_isolated_major_section_headings(md)
        assert "## Summary of Study 1" not in out

    def test_numbered_list_lead_in_not_promoted(self) -> None:
        # The candidate leads a NUMBERED list (a list lead-in), not a section
        # of flowing prose. (chandrashekar: "Steps for power analysis (…):" →
        # "1. Conducted Binomial Logistic Regression …".)
        md = _doc(
            "We note consistencies related to the power analysis details here.",
            "",
            "Steps for the power analysis reported in the preregistration",
            "1. Conducted Binomial Logistic Regression in Jamovi on the data.",
            "2. Calculated the Odds Ratios of the regression results in Jamovi.",
        )
        out = _promote_isolated_major_section_headings(md)
        assert "## Steps for the power analysis" not in out

    def test_already_h2_unchanged(self) -> None:
        md = _block(
            "Prior work motivated this design.",
            "",
            "## Introduction",
            _PROSE,
        )
        out = _promote_isolated_major_section_headings(md)
        # Exactly one ## Introduction (no duplication / re-emission).
        assert out.count("## Introduction") == 1


# ── Idempotency ───────────────────────────────────────────────────────────


class TestMajorSectionIdempotent:
    def test_idempotent_on_promotion(self) -> None:
        md = _doc(
            "and aiming to test causal relationships in the present design.",
            "",
            "Original hypotheses and findings in the target article",
            _PROSE,
        )
        once = _promote_isolated_major_section_headings(md)
        assert "## Original hypotheses and findings in the target article" in once
        twice = _promote_isolated_major_section_headings(once)
        assert once == twice

    def test_idempotent_on_no_op(self) -> None:
        md = _block("Body text ends here.", "", "## Section", "", "More body text here.")
        once = _promote_isolated_major_section_headings(md)
        twice = _promote_isolated_major_section_headings(once)
        assert once == twice


# ── Real-PDF regression (drives the public render entry point) ─────────────


_REL = ("apa", "chan_feldman_2025_cogemo.pdf")


def _render_cogemo() -> str:
    if not pdf_available("docpluck", *_REL):
        pytest.skip("fixture not available locally: chan_feldman_2025_cogemo.pdf")
    # Headings don't need Camelot — disable it to keep this fast.
    os.environ["DOCPLUCK_DISABLE_CAMELOT"] = "1"
    pdf = Path(pdf_path("docpluck", *_REL))
    return render_pdf_to_markdown(pdf.read_bytes())


class TestCogEmoRealPdf:
    def test_original_hypotheses_promoted(self) -> None:
        md = _render_cogemo()
        assert "## Original hypotheses and findings in the target article" in md

    def test_extension_titles_promoted(self) -> None:
        md = _render_cogemo()
        assert "## Extension: examining causal link with empathy manipulation" in md
        assert "## Extension: the impact of empathy on forgiveness" in md

    def test_citation_of_target_promoted(self) -> None:
        md = _render_cogemo()
        assert "## Citation of the target research article" in md
