"""Bundled-cycle tests for the 2026-05-23 residual handoff
(``docs/superpowers/handoffs/2026-05-23-residual-after-iterate-spine-cycles-1-3.md``).

Covers §C P0r-F, §B-new-1..5, §A R3a, §A R3b, §A R5, §A R1, §A R4.
Real-PDF regression tests use the manifest-with-skip pattern: fixtures live
outside this repo per memory ``feedback_no_pdfs_in_repo``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from docpluck.normalize import (
    NORMALIZATION_VERSION,
    _HEADER_BANNER_PATTERNS,
    _detect_column_interleave_pages,
    _looks_like_running_header_or_footer,
    _recover_dropped_minus_in_record,
    recover_dropped_minus_via_ci_pairing,
)
from docpluck.render import (
    _demote_credit_role_headings,
    _demote_italic_label_with_comma_headings,
    _demote_metadata_label_headings,
    _looks_like_metadata_content,
    _looks_like_titlecase_subsection_label,
    _promote_isolated_titlecase_subsection_headings,
    _strip_running_header_lines_in_unstructured_table_fences,
    _suppress_inline_duplicate_figure_captions,
    render_pdf_to_markdown,
)
from docpluck.extract_structured import _is_citation_cell, _is_table_header_like_short_line


_PDF_ROOT = Path(__file__).resolve().parents[1] / ".." / "PDFextractor" / "test-pdfs"


def _maybe_render(rel: str) -> str:
    pdf = (_PDF_ROOT / rel).resolve()
    if not pdf.is_file():
        pytest.skip(f"fixture not available locally: {rel}")
    return render_pdf_to_markdown(pdf.read_bytes())


# ── Version guard ─────────────────────────────────────────────────────────


def test_normalization_version_bumped_to_1_9_23():
    parts = tuple(int(x) for x in NORMALIZATION_VERSION.split("."))
    assert parts >= (1, 9, 23)


# ── §C P0r-F: strip P0r-shape lines inside unstructured-table fences ──────


class TestP0rFenceStrip:
    def test_strips_footer_inside_fence(self):
        text = (
            "Body before.\n\n"
            "```unstructured-table\n"
            "\n"
            "Cell A\n"
            "PLOS Medicine | https://doi.org/10.1371/journal.pmed.1004323 December 28, 2023\n"
            "10 / 16\n"
            "```\n"
            "\nBody after."
        )
        out = _strip_running_header_lines_in_unstructured_table_fences(text)
        assert "PLOS Medicine | https://doi.org" not in out
        assert "Cell A" in out
        assert "10 / 16" in out  # not a P0r-shape, preserved

    def test_preserves_non_footer_cells(self):
        text = (
            "```unstructured-table\n"
            "Mean (SD)\n"
            "0.92 (0.14)\n"
            "<.001\n"
            "```\n"
        )
        out = _strip_running_header_lines_in_unstructured_table_fences(text)
        assert out == text  # nothing matches P0r shapes

    def test_strips_pspb_proof_header_in_fence(self):
        text = (
            "```unstructured-table\n"
            "Personality and Social Psychology Bulletin 00(0)\n"
            "Mean Difference\n"
            "```\n"
        )
        out = _strip_running_header_lines_in_unstructured_table_fences(text)
        assert "Personality and Social Psychology Bulletin 00(0)" not in out
        assert "Mean Difference" in out

    def test_idempotent(self):
        text = (
            "```unstructured-table\n"
            "PLOS MEDICINE\n"
            "value\n"
            "```\n"
        )
        once = _strip_running_header_lines_in_unstructured_table_fences(text)
        twice = _strip_running_header_lines_in_unstructured_table_fences(once)
        assert once == twice

    def test_plos_med_1_no_fence_footer(self):
        # Real-PDF regression (covered also by the existing
        # test_p0r_recurring_running_header_strip.py file, repeated here for
        # local locality with the §C fix).
        md = _maybe_render("vancouver/plos_med_1.pdf")
        leaking = [
            ln for ln in md.split("\n")
            if "PLOS Medicine | https://doi.org" in ln
        ]
        assert leaking == []


# ── §B-new-2 HALLUC-HEAD-3: KEYWORDS metadata-label demote ────────────────


class TestMetadataLabelDemote:
    def test_demote_keywords_followed_by_keyword_list(self):
        text = (
            "## KEYWORDS\n"
            "\n"
            "emotion regulation; cognitive reappraisal; affect; suppression; mood\n"
            "\n"
            "## Introduction\n"
            "We examine ..."
        )
        out = _demote_metadata_label_headings(text)
        assert "## KEYWORDS" not in out
        assert "**KEYWORDS:**" in out
        assert "## Introduction" in out

    def test_preserve_real_section_heading(self):
        # `## Introduction` followed by a sentence — must NOT be demoted by
        # this pass (only the metadata-label shape demotes).
        text = (
            "## Introduction\n"
            "\n"
            "Suppression of emotion regulation is widely studied in the literature."
        )
        out = _demote_metadata_label_headings(text)
        assert out == text

    def test_demote_abbreviations_with_semicolon_list(self):
        text = (
            "## Abbreviations\n"
            "\n"
            "PSPB; SD; CI; ANCOVA; OR; HR; RR\n"
        )
        out = _demote_metadata_label_headings(text)
        assert "**Abbreviations:**" in out

    def test_does_not_demote_when_followed_by_prose(self):
        # If KEYWORDS appears as a heading followed by prose (i.e., it's
        # somehow a real section), no demotion. Conservative.
        text = (
            "## KEYWORDS\n"
            "\n"
            "We selected the keywords based on the systematic review protocol "
            "described in our pre-registration."
        )
        out = _demote_metadata_label_headings(text)
        assert "## KEYWORDS" in out


def test_metadata_shape_recognizer():
    assert _looks_like_metadata_content("emotion; affect; reappraisal; suppression")
    assert _looks_like_metadata_content("PSPB; SD; CI; ANCOVA")
    assert _looks_like_metadata_content("foo, bar, baz, qux")
    # Sentence — has a verb in subject-verb position.
    assert not _looks_like_metadata_content(
        "We examined emotion regulation in 200 participants over three studies."
    )
    # Too long — over 300 chars.
    assert not _looks_like_metadata_content("a; " + "x" * 320)


# ── §B-new-3: PLOS Author-Contributions packed-CRediT extension ───────────


class TestPlosCreditPackedExtension:
    def test_demote_methodology_inside_plos_author_contributions(self):
        # PLOS Author Contributions form: `**Role:** Names.` lines, each
        # with role + colon. `## Methodology` sits inside this block and
        # should be demoted.
        text = (
            "## Author Contributions\n"
            "\n"
            "**Conceptualization:** Smith, Jones.\n"
            "\n"
            "## Methodology\n"
            "\n"
            "Smith, Wong. **Investigation:** Smith. **Data acquisition:** Smith. **Writing - original draft:** Smith."
        )
        out = _demote_credit_role_headings(text)
        assert "## Methodology" not in out

    def test_preserve_real_methodology_section(self):
        text = (
            "## Introduction\n\nBody paragraph here describing prior work.\n\n"
            "## Methodology\n\n"
            "We conducted a between-subjects experiment with 200 participants. "
            "All participants completed informed consent before starting."
        )
        out = _demote_credit_role_headings(text)
        assert "## Methodology" in out


# ── §B-new-4: italic-label-with-comma guard ───────────────────────────────


class TestItalicLabelCommaDemote:
    def test_demote_data_availability_with_continuation_list(self):
        text = (
            "## Data Availability\n"
            "\n"
            "Preregistration, and Open-Science Disclosures.\n"
            "\n"
            "## Results"
        )
        out = _demote_italic_label_with_comma_headings(text)
        assert "## Data Availability" not in out
        assert "*Data Availability, Preregistration, and Open-Science Disclosures.*" in out
        assert "## Results" in out

    def test_preserve_real_section_heading_followed_by_prose(self):
        text = (
            "## Data Availability\n"
            "\n"
            "All study data are publicly available at https://example.org/data."
        )
        out = _demote_italic_label_with_comma_headings(text)
        # Body line has no comma-list shape — must NOT demote.
        assert "## Data Availability" in out

    def test_preserve_heading_when_next_has_no_period(self):
        text = (
            "## Limitations\n"
            "\n"
            "Sampling bias, generalizability constraints\n"
            "\n"
            "are key concerns."
        )
        out = _demote_italic_label_with_comma_headings(text)
        # Continuation line lacks a terminal period — must NOT demote (this
        # is a wrap, not a comma-broken label).
        assert "## Limitations" in out


# ── §B-new-1: generic isolated Title-Case subsection promoter ─────────────


class TestGenericTitleCasePromoter:
    def test_promote_self_control_assessment(self):
        text = (
            "Body of preceding subsection sits here, several lines of prose.\n"
            "\n"
            "Self-control assessment\n"
            "\n"
            "We then asked participants to indicate their tendency to control impulses.\n"
        )
        out = _promote_isolated_titlecase_subsection_headings(text)
        assert "### Self-control assessment" in out

    def test_does_not_promote_when_no_blank_isolation(self):
        text = (
            "Body paragraph.\n"
            "Self-control assessment\n"
            "We then asked participants to indicate impulses.\n"
        )
        out = _promote_isolated_titlecase_subsection_headings(text)
        assert "### Self-control assessment" not in out

    def test_does_not_promote_followed_by_table_cells(self):
        text = (
            "Body.\n"
            "\n"
            "Self-control assessment\n"
            "\n"
            "0.92\n"
        )
        out = _promote_isolated_titlecase_subsection_headings(text)
        assert "### Self-control assessment" not in out

    def test_does_not_promote_when_prev_is_sibling_label(self):
        # Two adjacent short isolated Title-Case lines → glossary / sidebar.
        text = (
            "Body paragraph here describing the experimental design completely.\n"
            "\n"
            "Outcome variables\n"
            "\n"
            "Self-control assessment\n"
            "\n"
            "Participants completed a measure of impulse control across three sessions."
        )
        out = _promote_isolated_titlecase_subsection_headings(text)
        # The second one's prev is the first one (also a short Title-Case
        # isolated line) — guard kicks in, no promotion.
        assert "### Self-control assessment" not in out

    def test_does_not_promote_figure_label(self):
        text = (
            "Body sentence describing the analysis at sufficient length.\n"
            "\n"
            "Figure 3\n"
            "\n"
            "Caption text describing the figure in body prose form here.\n"
        )
        out = _promote_isolated_titlecase_subsection_headings(text)
        assert "### Figure 3" not in out

    def test_does_not_promote_lowercase_line(self):
        text = (
            "Body sentence here long enough to be prose.\n"
            "\n"
            "self-control assessment\n"
            "\n"
            "We then asked participants to indicate impulses on the scale.\n"
        )
        out = _promote_isolated_titlecase_subsection_headings(text)
        assert "### self-control assessment" not in out


def test_titlecase_subsection_label_shape_recognizer():
    assert _looks_like_titlecase_subsection_label("Self-control assessment")
    assert _looks_like_titlecase_subsection_label("Outcome variables")
    assert _looks_like_titlecase_subsection_label("Manipulation check")
    assert _looks_like_titlecase_subsection_label("Sample and Recruitment")
    # Too long.
    assert not _looks_like_titlecase_subsection_label(
        "A very long subsection title with seven or even eight words here"
    )
    # Ends in punctuation (sentence / inline label).
    assert not _looks_like_titlecase_subsection_label("Self-control assessment.")
    assert not _looks_like_titlecase_subsection_label("Self-control:")
    # Pure numeric / no alphabetic word.
    assert not _looks_like_titlecase_subsection_label("3 (2.1)")
    # Known structural prefix.
    assert not _looks_like_titlecase_subsection_label("Table 5")
    assert not _looks_like_titlecase_subsection_label("Figure 3")


# ── §B-new-5: front-matter banner concatenation strip ─────────────────────


class TestFrontMatterBannerConcat:
    def test_pspb_welded_banner_matches_h0_pattern(self):
        line = "PSPXXX10.1177/01461672251327169Personality and Social Psychology BulletinIp and Feldman"
        assert any(p.match(line) for p in _HEADER_BANNER_PATTERNS), (
            "PSPB welded banner should match an H0 banner pattern"
        )

    def test_sage_welded_banner_matches(self):
        line = "ASRXXX10.1177/00031224241253268American Sociological ReviewSmith and Jones"
        assert any(p.match(line) for p in _HEADER_BANNER_PATTERNS)

    def test_does_not_match_normal_doi_url_line(self):
        # A normal DOI URL line should NOT match the welded-banner pattern.
        from docpluck.normalize import _strip_document_header_banners
        text = "https://doi.org/10.1177/01461672251327169\nReal Title Here"
        out = _strip_document_header_banners(text)
        # Normal DOI URL line is matched by the bare-URL pattern (legit
        # banner removal) but our welded-banner addition shouldn't affect
        # this case. The output should still contain the title.
        assert "Real Title Here" in out


# ── §A R3a: et al. / citation-cell signature ──────────────────────────────


class TestCitationCellSignature:
    def test_et_al_citation_is_cell(self):
        assert _is_citation_cell("Small et al. (2007)")
        assert _is_citation_cell("Small et al. (2007a)")

    def test_two_author_citation_is_cell(self):
        assert _is_citation_cell("Smith and Jones (2009)")
        assert _is_citation_cell("Smith & Jones (2009)")

    def test_year_only_is_cell(self):
        assert _is_citation_cell("(2007)")
        assert _is_citation_cell("(1999b)")

    def test_table_header_like_short_line_accepts_citation_cells(self):
        # Citation cells were previously rejected by the >3-word gate.
        assert _is_table_header_like_short_line("Small et al. (2007)")
        assert _is_table_header_like_short_line("(2007)")

    def test_not_a_citation_cell(self):
        assert not _is_citation_cell("Means and SDs")
        assert not _is_citation_cell("0.92")
        assert not _is_citation_cell("Small et al. measured impulse")


# ── §A R3b: FIG-3c-2 prefix-superset suppression ──────────────────────────


class TestFigure3c2PrefixSuperset:
    def test_drops_inline_when_block_caption_is_prefix(self):
        # The block caption is shorter than the inline (block was trimmed
        # earlier). When the inline starts with the block caption text +
        # short sentence-terminated overhang, drop the inline run.
        text = (
            "Body intro.\n"
            "\n"
            "Figure 1. Mean response time by condition across the three trials and the overhang.\n"
            "\n"
            "More body prose continues here describing the analyses.\n"
            "\n"
            "### Figure 1\n"
            "\n"
            "*Figure 1. Mean response time by condition across the three trials*\n"
        )
        out = _suppress_inline_duplicate_figure_captions(text)
        assert "Mean response time by condition across the three trials and the overhang" not in out
        assert "More body prose continues here" in out

    def test_preserves_inline_when_overhang_is_long(self):
        # Long overhang (>120 chars) — probably body prose, not caption.
        # Must NOT drop.
        long_tail = " ".join(["body"] * 50)
        text = (
            "Figure 1. Short caption text\n"
            f"in body prose form continues with very long tail {long_tail}.\n"
            "\n"
            "### Figure 1\n"
            "\n"
            "*Figure 1. Short caption text in body prose form*\n"
        )
        out = _suppress_inline_duplicate_figure_captions(text)
        assert "Short caption text" in out or "Short caption" in out
        # Body prose must survive.
        assert "body body" in out


# ── §A R5: dropped-minus recovery via CI ──────────────────────────────────


class TestDroppedMinusRecovery:
    def test_recovers_when_ci_proves_negative(self):
        record = "b = .022, CI = [-0.04, -0.01]"
        out = _recover_dropped_minus_in_record(record)
        assert "-.022" in out
        assert ".022" not in out.replace("-.022", "")

    def test_does_not_flip_when_literal_in_bracket(self):
        # CI contains both 0.022 and -0.022 — ambiguous → no flip.
        record = "b = .022, CI = [-0.10, 0.10]"
        out = _recover_dropped_minus_in_record(record)
        assert out == record

    def test_does_not_flip_when_bracket_is_strictly_positive(self):
        # CI is [0.01, 0.04] — never flip (lo >= 0 guard).
        record = "b = .022, CI = [0.01, 0.04]"
        out = _recover_dropped_minus_in_record(record)
        assert out == record

    def test_does_not_flip_when_no_bracket(self):
        record = "b = .022 (no CI here)"
        out = _recover_dropped_minus_in_record(record)
        assert out == record

    def test_does_not_touch_token_inside_bracket(self):
        # A CI bound itself like -0.04 must not be re-recovered.
        record = "b = .022, CI = [-0.04, -0.01]"
        out = _recover_dropped_minus_in_record(record)
        # The bracket bounds remain unchanged.
        assert "-0.04" in out
        assert "-0.01" in out

    def test_recovery_via_outer_helper_handles_table_rows(self):
        text = "<tr><td>b</td><td>.022</td><td>[-0.04, -0.01]</td></tr>"
        out = recover_dropped_minus_via_ci_pairing(text)
        assert "-.022" in out

    def test_skip_when_no_bracket_anywhere(self):
        text = "no brackets here at all"
        assert recover_dropped_minus_via_ci_pairing(text) == text


# ── §A R4: column-interleave detector ─────────────────────────────────────


class TestColumnInterleaveDetector:
    def test_detects_interleaved_page(self):
        # Synthesise a page with ≥6 unterminated-line / Title-Case-start
        # pairs. page_offsets = (0,) means single page (offsets[1] = len(text)).
        page = "\n".join([
            "Sentence one continues here",  # no terminator
            "Second sentence opener starts",  # Title-Case start
            "Another unterminated continuation",
            "Another opener begins",
            "More unterminated tail",
            "More openers here",
            "Yet another unterminated",
            "Yet openers continue",
            "Penultimate unterminated tail",
            "Penultimate opener begins",
            "Final unterminated",
            "Final opener line",
        ])
        pages = _detect_column_interleave_pages(page, (0,))
        assert 1 in pages

    def test_no_detection_on_coherent_prose(self):
        page = (
            "We conducted an experiment with 200 participants. "
            "All participants gave consent. "
            "We measured emotion regulation. "
            "The findings replicated."
        )
        pages = _detect_column_interleave_pages(page, (0,))
        assert pages == ()

    def test_no_detection_when_continuation_words(self):
        # Lines ending in continuation words ("of", "the") don't count as
        # flips — they are legitimate soft-wraps.
        page = "\n".join([
            "We measured the impact of",
            "Reading the text continues",
            "the participants in the study of",
            "Reading continues again",
            "the framework that we applied of",
            "Reading still continues",
            "the methodology described of",
            "Reading more text",
        ])
        pages = _detect_column_interleave_pages(page, (0,))
        assert pages == ()

    def test_handles_empty_input(self):
        assert _detect_column_interleave_pages("", ()) == ()
        assert _detect_column_interleave_pages("text", ()) == ()
