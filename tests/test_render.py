"""Tests for docpluck.render — the v2.2.0 markdown render entry point and
its markdown-level post-processors.

Ported from docs/superpowers/plans/spot-checks/splice-spike/test_splice_spike.py
(iter-29 / iter-32 / iter-34 / iter-23 / iter-20 blocks).
"""

from pathlib import Path

import pytest

from docpluck.render import (
    _dedupe_h2_sections,
    _fix_hyphenated_line_breaks,
    _join_multiline_caption_paragraphs,
    _merge_compound_heading_tails,
    _promote_numbered_subsection_headings,
    _reformat_jama_key_points_box,
    _suppress_orphan_table_cell_text,
    _suppress_inline_duplicate_figure_captions,
    _demote_inline_footnotes_to_blockquote,
    _promote_study_subsection_headings,
    _demote_false_single_word_headings,
    _apply_title_rescue,
    _strip_duplicate_title_occurrences,
)


# ── _dedupe_h2_sections ────────────────────────────────────────────────────


def test_dedupe_keeps_first_demotes_rest():
    text = "## Results\n\nbody A\n\n## Results\n\nbody B\n\n## Discussion\n\nfoo"
    out = _dedupe_h2_sections(text)
    assert out.count("## Results") == 1
    assert "body A" in out
    assert "body B" in out  # body of demoted heading still present
    assert "## Discussion" in out


def test_dedupe_exempts_appendix_headings():
    text = "## Figures\n\nfig1\n\n## Figures\n\nfig2"
    out = _dedupe_h2_sections(text)
    assert out.count("## Figures") == 2  # exempt


# ── _merge_compound_heading_tails ──────────────────────────────────────────


def test_merge_conclusions_and_relevance():
    text = "## CONCLUSIONS\n\nAND RELEVANCE This trial found that the protocol worked.\n\nNext paragraph"
    out = _merge_compound_heading_tails(text)
    assert "## CONCLUSIONS AND RELEVANCE" in out
    assert "This trial found that the protocol worked." in out
    assert "AND RELEVANCE This trial" not in out


def test_merge_idempotent_when_no_orphan_tail():
    text = "## CONCLUSIONS\n\nNormal body sentence here.\n\nNext."
    out = _merge_compound_heading_tails(text)
    assert out == text


# ── _promote_numbered_subsection_headings ──────────────────────────────────


def test_promote_numbered_subsection():
    text = (
        "body sentence with the conclusion that.\n"
        "1.2 Above-and-below-average effects\n"
        "In the 1980s, researchers began to assess subjects' self-evaluations."
    )
    out = _promote_numbered_subsection_headings(text)
    assert "### 1.2 Above-and-below-average effects" in out


def test_promote_long_descriptive_subsection_title():
    # G5b (cycle 13): multi-level dotted numbering at line-start is itself a
    # strong section-heading signal. Descriptive subsection titles legitimately
    # run to many lowercase words, so a lowercase-run prose guard mis-rejects
    # real headings and was removed. A long descriptive title IS promoted.
    text = "1.2 Inference of planning strategies and strategy types"
    out = _promote_numbered_subsection_headings(text)
    assert "### 1.2 Inference of planning strategies and strategy types" in out


def test_promote_rejects_sentence_terminator():
    text = "1.2 This is a sentence."
    out = _promote_numbered_subsection_headings(text)
    assert "### 1.2" not in out


def test_promote_idempotent():
    text = "1.2 Background\nbody text"
    once = _promote_numbered_subsection_headings(text)
    twice = _promote_numbered_subsection_headings(once)
    # Once it becomes "### 1.2 Background" the regex no longer matches it.
    assert once == twice


# ── _fix_hyphenated_line_breaks (H1, post-render) ──────────────────────────


def test_h1_joins_compound_word():
    text = "FIGURE 4 Regression Slopes for X Y Z on Meta-\nProcesses (Study 1)"
    out = _fix_hyphenated_line_breaks(text)
    # Hyphen KEPT, newline removed.
    assert "Meta-Processes (Study 1)" in out
    assert "Meta-\nProcesses" not in out


def test_h1_skips_inside_table():
    text = "<table>\n<tr><td>foo-\nbar</td></tr>\n</table>"
    out = _fix_hyphenated_line_breaks(text)
    # Table cells are skipped — hyphen+newline preserved.
    assert "foo-\nbar" in out


def test_h1_skips_headings():
    text = "## Meta-\nProcess"
    out = _fix_hyphenated_line_breaks(text)
    assert "## Meta-" in out


# ── _join_multiline_caption_paragraphs ─────────────────────────────────────


def test_join_multiline_caption():
    # First line must be >= 60 chars per the spike's conservative rule.
    text = (
        "TABLE 1 Summary of How Articles Across the Past Three Decades Have\n"
        "Shaped the Definition of CSR\n\n"
        "next paragraph"
    )
    out = _join_multiline_caption_paragraphs(text)
    assert (
        "TABLE 1 Summary of How Articles Across the Past Three Decades Have"
        " Shaped the Definition of CSR"
    ) in out


def test_join_skips_short_first_line():
    text = "TABLE 1 Short\n(rest)\n\nbody"
    out = _join_multiline_caption_paragraphs(text)
    # First line < 60 chars, no fold.
    assert "TABLE 1 Short\n(rest)" in out


# ── _suppress_orphan_table_cell_text ───────────────────────────────────────


def test_suppress_orphan_table_cell_text_drops_leaked_rows():
    """The chan_feldman_2025_cogemo Table 5 leak: caption followed by short
    orphan cell paragraphs gets italicized and the rows are dropped."""
    text = (
        "We made minor adjustments, summarised below.\n\n"
        "Table 5. Comparison of target article versus replication.\n\n"
        "Target article\n\n"
        "Replication\n\n"
        "Study design\n\n"
        "Sample characteristics\n\n"
        "Procedure\n\n"
        "## Evaluation\n\n"
        "criteria for replication findings"
    )
    out = _suppress_orphan_table_cell_text(text)
    assert "*Table 5. Comparison of target article versus replication.*" in out
    assert "\n\nTarget article\n\n" not in out
    assert "\n\nReplication\n\n" not in out
    assert "\n\nStudy design\n\n" not in out
    assert "\n\nSample characteristics\n\n" not in out
    assert "\n\nProcedure\n\n" not in out
    assert "## Evaluation" in out
    assert "criteria for replication findings" in out


def test_suppress_orphan_table_cell_text_preserves_prose_following_caption():
    """If a caption is followed by normal prose (not orphan cells), the
    caption stays plain and the prose is kept untouched."""
    text = (
        "Table 5. See description below for full breakdown.\n\n"
        "The full breakdown of the comparison between the target article and "
        "our replication is provided in the supplementary materials, where we "
        "describe each design facet in detail and explain the rationale for "
        "the chosen criteria."
    )
    out = _suppress_orphan_table_cell_text(text)
    # No italicization (no 3+ orphan rows follow).
    assert "Table 5. See description below for full breakdown." in out
    assert "*Table 5." not in out
    assert "The full breakdown of the comparison" in out


def test_suppress_orphan_table_cell_text_requires_min_two_orphans():
    """v2.4.11 lowered the threshold from 3 to 2 (catches the
    chan_feldman Table 1 case: Hypothesis + Description). 1 orphan
    should still NOT trigger suppression (too aggressive)."""
    text = (
        "Table 5. Caption here.\n\n"
        "Short one\n\n"
        "Now a paragraph with several function words: the rest of the text "
        "continues here in flowing prose with normal markers and length."
    )
    out = _suppress_orphan_table_cell_text(text)
    # Only 1 orphan → no suppression.
    assert "Table 5. Caption here." in out
    assert "*Table 5." not in out
    assert "Short one" in out


def test_suppress_orphan_table_cell_text_fires_on_two_orphans():
    """Two orphan rows (chan_feldman Table 1 case) IS suppressed."""
    text = (
        "Table 1. Summary of hypotheses of the target article.\n"
        "Hypothesis\n\n"
        "Description\n\n"
        "Empathy mediates relationships between dispositional variables and "
        "their causal effects on forgiving for the offender."
    )
    out = _suppress_orphan_table_cell_text(text)
    assert "*Table 1. Summary of hypotheses of the target article.*" in out
    assert "\nHypothesis\n" not in out
    assert "\nDescription\n" not in out
    assert "Empathy mediates relationships" in out


def test_suppress_orphan_table_cell_text_fires_on_italic_caption():
    """v2.4.11: italic ``*Table N. ...*`` captions emitted by the v2.4.2
    Camelot-0-cells fix are followed by orphan rows just as easily.
    The suppressor now strips those too."""
    text = (
        "*Table 2. Target article: Means, standard deviations, internal "
        "consistency reliabilities and intercorrelations.*\n\n"
        "1. Degree of apology\n2. Empathy\n3. Forgiving\n\n"
        "5.63\n13.22\n16.82\n\n"
        "Note: Apology scores ranged from 2 to 10."
    )
    out = _suppress_orphan_table_cell_text(text)
    assert "*Table 2. Target article" in out
    assert "1. Degree of apology" not in out
    assert "13.22" not in out
    # The Note line is short but starts with "Note" — would be excluded by
    # _is_orphan_cell_paragraph's Note check, so it stays.
    assert "Note: Apology scores" in out


def test_suppress_orphan_table_cell_text_skips_already_italic_caption():
    """The v2.4.2 ``*Table N. ...*`` caption-only emission is never followed
    by orphan rows; we must not touch it."""
    text = (
        "*Table 3. Difference and similarities between target article and replication.*\n\n"
        "*Table 4. Replication and extension experimental design.*\n\n"
        "## Evaluation"
    )
    out = _suppress_orphan_table_cell_text(text)
    # Unchanged.
    assert out == text


def test_suppress_orphan_table_cell_text_stops_at_next_caption():
    """A run of orphan paragraphs ends when the next caption is reached;
    the second caption is preserved as-is in its original form."""
    text = (
        "Table 5. First caption.\n\n"
        "Cell a\n\n"
        "Cell b\n\n"
        "Cell c\n\n"
        "Table 6. Second caption.\n\n"
        "The discussion paragraph here is regular prose with the and of words."
    )
    out = _suppress_orphan_table_cell_text(text)
    assert "*Table 5. First caption.*" in out
    assert "Cell a" not in out
    assert "Cell b" not in out
    assert "Cell c" not in out
    # Second caption preserved (no orphans after it).
    assert "Table 6. Second caption." in out
    assert "*Table 6." not in out


def test_suppress_orphan_table_cell_text_idempotent():
    text = (
        "Table 5. Caption.\n\n"
        "Cell a\n\n"
        "Cell b\n\n"
        "Cell c\n\n"
        "## Next"
    )
    once = _suppress_orphan_table_cell_text(text)
    twice = _suppress_orphan_table_cell_text(once)
    assert once == twice


def test_suppress_orphan_table_cell_text_noop_when_no_table_caption():
    text = "## Methods\n\nWe ran the analysis.\n\nResults follow."
    assert _suppress_orphan_table_cell_text(text) == text


def test_suppress_orphan_table_cell_text_poppler_single_newline_format():
    """v2.4.10 regression-fix test: poppler-utils 25.03+ (Railway prod
    pdftotext) joins cell-content runs with single ``\\n`` rather than
    ``\\n\\n``. Earlier paragraph-level split missed prod's structure.

    Real example from chan_feldman_2025_cogemo on the Railway service:
        "Table 5. Comparison of target article versus replication.\\n"
        "Study design\\nSample characteristics\\nProcedure\\n\\n"
        "Statistical analysis\\n\\nConditions\\n\\n..."
    All on consecutive single-newline-separated lines; the caption and
    the first 3 orphan rows are a single paragraph in `\\n\\n+`-split.
    """
    text = (
        "Some intro about table 5.\n\n"
        "Table 5. Comparison of target article versus replication.\n"
        "Study design\n"
        "Sample characteristics\n"
        "Procedure\n\n"
        "Statistical analysis\n\n"
        "Conditions\n\n"
        "After this paragraph the prose continues and is long enough to be"
        " recognized as normal body content, not an orphan cell row.\n"
    )
    out = _suppress_orphan_table_cell_text(text)
    assert "*Table 5. Comparison of target article versus replication.*" in out
    assert "\nStudy design\n" not in out
    assert "\nSample characteristics\n" not in out
    assert "\nProcedure\n" not in out
    assert "After this paragraph the prose continues" in out


# ── _demote_inline_footnotes_to_blockquote ──────────────────────────────────


def test_footnote_demoted_to_blockquote():
    text = (
        "Body prose paragraph one.\n\n"
        "1 Though we note a recent failed replication of the Kogut and "
        "Ritov (2005) by Majumder et al. (2023).\n\n"
        "Body prose paragraph two."
    )
    out = _demote_inline_footnotes_to_blockquote(text)
    assert "> 1 Though we note a recent failed replication" in out
    assert "Body prose paragraph one." in out
    assert "Body prose paragraph two." in out


def test_footnote_demoter_preserves_real_numbered_list_item():
    text = (
        "Some context.\n\n"
        "1. First numbered point in a list.\n\n"
        "More prose."
    )
    out = _demote_inline_footnotes_to_blockquote(text)
    # Numbered list item has `1.` (with period), pattern expects `1 Word`.
    assert "1. First numbered point" in out
    assert "> 1. First numbered point" not in out


def test_footnote_demoter_skips_short_paragraphs():
    text = "Context.\n\n2 Note.\n\nMore."
    out = _demote_inline_footnotes_to_blockquote(text)
    # Under 30 chars — not enough to qualify as a footnote.
    assert out == text


def test_footnote_demoter_idempotent():
    text = (
        "Body.\n\n"
        "1 Though we note this is a footnote that has been demoted already "
        "by a previous pass through the pipeline.\n\n"
        "More body."
    )
    once = _demote_inline_footnotes_to_blockquote(text)
    twice = _demote_inline_footnotes_to_blockquote(once)
    # After first pass, the line starts with "> ", so doesn't match `^\d`.
    assert once == twice


# ── _promote_study_subsection_headings ──────────────────────────────────────


def test_study_subsection_heading_promoted():
    text = (
        "Some intro.\n\n"
        "Study 1 Design and Findings\n\n"
        "In Study 1 we examined..."
    )
    out = _promote_study_subsection_headings(text)
    assert "### Study 1 Design and Findings" in out
    assert "In Study 1 we examined" in out


def test_study_subsection_multiple_variants_promoted():
    text = (
        "x\n\n"
        "Study 3 Design and Findings\n\n"
        "y\n\n"
        "Study 2 Results\n\n"
        "z\n\n"
        "Overview of the Replication and Extension\n\n"
        "w"
    )
    out = _promote_study_subsection_headings(text)
    assert "### Study 3 Design and Findings" in out
    assert "### Study 2 Results" in out
    assert "### Overview of the Replication and Extension" in out


def test_study_subsection_skip_existing_heading():
    text = "### Study 1 Design and Findings\n\nbody"
    out = _promote_study_subsection_headings(text)
    # Already a heading; do not double-prefix.
    assert "### ### Study 1" not in out
    assert "### Study 1 Design and Findings" in out


def test_study_subsection_skip_unrelated_prose():
    text = (
        "We summarize Study 1 design and the procedure used in our work.\n\n"
        "More prose."
    )
    out = _promote_study_subsection_headings(text)
    # Mid-prose mention is NOT a heading; pattern requires the line to be
    # the entire paragraph and start with capital-S "Study N <token>".
    assert "### We summarize" not in out
    assert out == text


# ── _demote_false_single_word_headings ──────────────────────────────────────


def test_strong_section_heading_results_preserved_with_continuation_text():
    """v2.4.9 regression fix: ``## Results`` is a strong canonical section;
    even if pdftotext rendered the body starting with lowercase ``of Study 1``,
    the heading stays — the body keeps its (slightly weird) opening, but the
    section structure survives."""
    text = "## Results\n\nof Study 1 showed significant effects."
    out = _demote_false_single_word_headings(text)
    assert "## Results" in out


def test_strong_section_heading_discussion_preserved():
    text = "## Discussion\n\nof this study apparently present evidence against."
    out = _demote_false_single_word_headings(text)
    assert "## Discussion" in out


def test_strong_section_heading_references_preserved_with_numbered_list():
    text = "## References\n\n1. Öhman A, Lundqvist D, Esteves F. 2001 The face in the crowd."
    out = _demote_false_single_word_headings(text)
    assert "## References" in out


def test_false_heading_demoted_for_non_canonical_word():
    """A non-canonical single-word heading (``## Theory``) followed by
    lowercase continuation IS demoted (v2.4.8 behavior preserved)."""
    text = "### Theory\n\nof the firm: managerial implications follow."
    out = _demote_false_single_word_headings(text)
    assert "### Theory" not in out
    assert "Theory of the firm" in out


def test_legit_heading_preserved_when_next_line_capitalized_sentence():
    text = "## Results\n\nWe found a significant effect of condition."
    out = _demote_false_single_word_headings(text)
    # "We" is capitalized AND not a continuation particle — heading stays.
    assert "## Results" in out


def test_legit_heading_preserved_with_following_sentence():
    text = "## Methods\n\nParticipants were 100 undergraduates."
    out = _demote_false_single_word_headings(text)
    assert "## Methods" in out


def test_false_heading_h3_also_demoted():
    text = "### Theory\n\nof the firm: managerial implications follow."
    out = _demote_false_single_word_headings(text)
    assert "### Theory" not in out
    assert "Theory of the firm" in out


def test_false_heading_demoter_idempotent():
    text = "## Results\n\nof Study 1."
    once = _demote_false_single_word_headings(text)
    twice = _demote_false_single_word_headings(once)
    assert once == twice


def test_false_heading_preserved_when_next_line_is_numbered_subsection():
    """v2.4.9 regression fix: RSOS-style ``## Methods\\n\\n3.1. Subjects``
    must keep the heading + numbered subsection intact. Demoting here
    would destroy the section structure."""
    text = "## Methods\n\n3.1. Subjects and study site\n\nWe sampled..."
    out = _demote_false_single_word_headings(text)
    assert "## Methods" in out
    assert "3.1. Subjects and study site" in out


def test_false_heading_preserved_with_4digit_numbered_subsection():
    text = "## Results\n\n4.1. Do seasonal challenges affect...\n\nResults follow."
    out = _demote_false_single_word_headings(text)
    assert "## Results" in out
    assert "4.1. Do seasonal challenges affect..." in out


# ── _reformat_jama_key_points_box ──────────────────────────────────────────


def test_reformat_key_points_emits_blockquote_and_stitches():
    text = (
        "## CONCLUSIONS AND RELEVANCE\n\n"
        "This trial found that a TRE diet strategy was more effective than compared with\n\n"
        "Key Points Question Is time-restricted eating (TRE) effective for weight loss in adults with T2D?\n\n"
        "## Findings\n\n"
        "In a 6-month trial involving 75 adults with T2D, TRE was more effective for weight loss.\n"
        "Meaning These findings suggest that time-restricted eating may be an effective strategy.\n\n"
        "daily calorie counting in a sample of adults with T2D. These findings need confirmation."
    )
    out = _reformat_jama_key_points_box(text)
    assert "> **Key Points**" in out
    assert "> **Question:** Is time-restricted" in out
    assert "> **Findings:** In a 6-month trial" in out
    assert "> **Meaning:** These findings suggest" in out
    # Stitched: "compared with daily calorie counting" should appear as one sentence.
    assert "compared with daily calorie counting in a sample of adults" in out
    # The literal "## Findings" heading wedge is gone.
    assert "## Findings\n\nIn a 6-month" not in out


def test_reformat_key_points_no_op_when_not_present():
    text = "Some regular paper without a JAMA Key Points sidebar."
    out = _reformat_jama_key_points_box(text)
    assert out == text


# ── _apply_title_rescue ────────────────────────────────────────────────────


def test_title_rescue_prepends_when_missing():
    out = _apply_title_rescue("## Abstract\n\nbody body body", "An Interesting Paper About Cats")
    assert out.startswith("# An Interesting Paper About Cats")
    assert "## Abstract" in out


def test_title_rescue_no_op_when_title_already_present():
    text = "# Existing Title\n\n## Abstract\n\nbody"
    out = _apply_title_rescue(text, "Some Other Title")
    assert out == text


def test_title_rescue_strips_title_swept_into_abstract():
    text = "## Abstract\n\nAn Interesting Paper About Cats With Lots Of Words And More\nbody body body"
    out = _apply_title_rescue(text, "An Interesting Paper About Cats With Lots Of Words And More")
    # Title prepended at top, removed from inside abstract.
    assert out.startswith("# An Interesting Paper About Cats")
    assert "Abstract\n\nbody body body" in out or "Abstract\n\n\nbody body body" in out


# ── v2.4.0: Nature-style duplicate-title sweep ───────────────────────────


def test_strip_duplicate_title_removes_repeated_body_block():
    """Nature Communications pattern: title placed at top, then repeated
    as plain body paragraphs (broken across short lines because of column
    layout). The sweep should remove the duplicate block."""
    title = "Targeted treatment of injured nestmates with antimicrobial compounds"
    text = (
        f"# {title}\n"
        "\n"
        "Targeted treatment of injured nestmates\n"
        "with antimicrobial compounds\n"
        "\n"
        "Real body sentence about ant social immunity studies.\n"
    )
    out = _strip_duplicate_title_occurrences(text, title, start_offset_lines=2)
    # Title at top still present, duplicate block removed.
    assert out.startswith("# Targeted treatment")
    assert "Real body sentence" in out
    assert "Targeted treatment of injured nestmates\nwith antimicrobial" not in out


def test_strip_duplicate_title_keeps_unrelated_paragraphs():
    """Sweep should not touch paragraphs that don't densely overlap the
    title's token set, even if they share a few common words."""
    title = "Effects of antimicrobial peptides on bacterial cell walls"
    text = (
        f"# {title}\n"
        "\n"
        "Smith J, Doe A, Roe B\n"
        "Department of Biology, University X\n"
        "\n"
        "Antimicrobial peptides are short chains of amino acids that "
        "have evolved across diverse organisms; their interaction with "
        "bacterial membranes is widely studied.\n"
    )
    out = _strip_duplicate_title_occurrences(text, title, start_offset_lines=2)
    # Authors line and body sentence both survive — neither densely matches title tokens.
    assert "Smith J, Doe A, Roe B" in out
    assert "Antimicrobial peptides are short chains" in out


def test_apply_title_rescue_sweeps_secondary_duplicate():
    """End-to-end: a Nature-style document with the title appearing twice
    (once at large font caught by the first rescue, once as a small-font
    body duplicate) should have both occurrences cleaned up."""
    title = "Brain injury persists after viral infection in cohort follow-up"
    text = (
        "RESEARCH ARTICLE\n"
        "\n"
        "Brain injury persists after viral infection in cohort\n"
        "follow-up\n"
        "\n"
        "## Abstract\n"
        "\n"
        "Brain injury persists after viral infection in cohort follow-up\n"
        "\n"
        "Body of the abstract describing the cohort study and its outcomes.\n"
    )
    out = _apply_title_rescue(text, title)
    # Title placed at top.
    assert out.count("# Brain injury persists after viral infection") >= 1
    # Title H1 is the only line starting with "# Brain injury..." — the body
    # duplicate (which would have been bare prose) is gone.
    title_word_block_count = out.count(
        "Brain injury persists after viral infection in cohort follow-up"
    )
    assert title_word_block_count <= 2  # H1 itself counts as 1; H1+body=3 would fail


# ── v2.4.0: heading-body separation in rendered output ───────────────────


def _make_section(text: str, *, heading_text: str = "Abstract", label_value: str = "abstract"):
    """Tiny helper: build a Section + SectionedDocument fixture for render tests."""
    from docpluck.sections.types import Section, SectionedDocument
    from docpluck.sections.taxonomy import SectionLabel

    sec = Section(
        label=label_value,
        canonical_label=SectionLabel(label_value),
        text=text,
        char_start=0,
        char_end=len(text),
        pages=(1,),
        confidence="high",
        detected_via="layout",
        heading_text=heading_text,
    )
    return SectionedDocument(
        sections=(sec,),
        normalized_text=text,
        sectioning_version="test",
        source_format="pdf",
    )


def test_render_emits_blank_line_between_heading_and_body():
    """Section markdown should be ``## Heading\\n\\n<body>`` so downstream
    markdown renderers treat heading and body as separate blocks. Prior to
    v2.4.0 only a single ``\\n`` separated them, which caused the workspace
    to render ``## Abstract Lynching remains...`` as one paragraph."""
    from docpluck.render import _render_sections_to_markdown

    sectioned = _make_section("Lynching remains a common form of collective punishment.")
    md = _render_sections_to_markdown(sectioned, tables=[], figures=[])
    assert "## Abstract\n\nLynching remains" in md


def test_render_strips_duplicate_heading_word_from_body():
    """When the section detector leaves the heading word in the body
    (common for Abstract/Keywords sections), the renderer should drop it
    so output doesn't read ``## Abstract Abstract Lynching ...``."""
    from docpluck.render import _render_sections_to_markdown

    sectioned = _make_section(
        "Abstract Lynching remains a common form of collective punishment."
    )
    md = _render_sections_to_markdown(sectioned, tables=[], figures=[])
    # The body should start with "Lynching", not "Abstract Lynching".
    assert "## Abstract\n\nLynching" in md
    assert "Abstract Lynching" not in md


# ── v2.4.2: H tag fix — no `### Table N` heading when html is empty ──────


def _make_section_with_caption_text(caption_text: str, label_value: str = "results"):
    """Build a Section + SectionedDocument where the body contains a table
    caption that the renderer will splice on.
    """
    from docpluck.sections.types import Section, SectionedDocument
    from docpluck.sections.taxonomy import SectionLabel

    body = (
        "Results showed strong evidence for the hypothesis.\n"
        f"\n{caption_text}\n\n"
        "The remainder of the body continues here.\n"
    )
    sec = Section(
        label=label_value,
        canonical_label=SectionLabel(label_value),
        text=body,
        char_start=0,
        char_end=len(body),
        pages=(1,),
        confidence="high",
        detected_via="layout",
        heading_text="Results",
    )
    return SectionedDocument(
        sections=(sec,),
        normalized_text=body,
        sectioning_version="test",
        source_format="pdf",
    )


def test_render_skips_table_heading_when_html_empty():
    """When Camelot returned no cells (no html) AND there is no
    ``raw_text`` fallback either, the renderer should NOT emit a bare
    `### Table N` heading in the body — that promises structured content
    that isn't there. Instead, the caption renders as a plain italic
    paragraph so the table reference is still visible.

    Regression target for v2.4.2 H-tag failures (bjps_4,
    ar_apa_j_jesp_2009_12_011). v2.4.14 keeps this behavior for the
    truly-empty case; when raw_text IS populated the new fenced
    ``unstructured-table`` path runs instead — see
    ``test_render_emits_raw_text_block_when_html_empty_but_raw_text_present``.
    """
    from docpluck.render import _render_sections_to_markdown

    caption = "Table 1. Summary of predictions across conditions."
    sectioned = _make_section_with_caption_text(caption)
    tables = [{
        "label": "Table 1",
        "caption": caption,
        "cells": [],     # Camelot found no structured cells.
        "html": "",      # No HTML emitted.
        "page": 1,
    }]
    md = _render_sections_to_markdown(sectioned, tables=tables, figures=[])
    # No bare `### Table 1` heading.
    assert "### Table 1" not in md
    # The caption is preserved as an italicized paragraph.
    assert "*Table 1. Summary of predictions across conditions.*" in md


def test_render_keeps_table_heading_when_html_present():
    """When Camelot DID extract cells (html present), the renderer keeps
    the `### Table N` heading + caption + html block intact. This is the
    happy path and must not regress."""
    from docpluck.render import _render_sections_to_markdown

    caption = "Table 1. Summary of predictions across conditions."
    sectioned = _make_section_with_caption_text(caption)
    tables = [{
        "label": "Table 1",
        "caption": caption,
        "cells": [],
        "html": "<table><tr><td>cell</td></tr></table>",
        "page": 1,
    }]
    md = _render_sections_to_markdown(sectioned, tables=tables, figures=[])
    assert "### Table 1" in md
    assert "<table>" in md


def test_render_emits_raw_text_block_when_html_empty_but_raw_text_present():
    """v2.4.14: when Camelot returns no cells (no html) but
    ``_extract_table_body_text`` populated ``raw_text`` with the cells
    linearized by pdftotext, the renderer emits a `### Table N` heading
    + caption + a fenced ``unstructured-table`` block under a brief notice.

    Without this fix, isolated tables disappeared entirely from the
    rendered .md view — only the italicized caption from the body flow
    survived. Tables tab in the SaaS UI already used raw_text; the
    Rendered tab is now consistent with it.
    """
    from docpluck.render import _render_sections_to_markdown

    caption = "Table 1. Hypotheses of the target article."
    sectioned = _make_section_with_caption_text(caption)
    tables = [{
        "label": "Table 1",
        "caption": caption,
        "cells": [],
        "html": "",
        "raw_text": "Hypothesis\nDescription\n1\nEmpathy mediates ...",
        "page": 1,
    }]
    md = _render_sections_to_markdown(sectioned, tables=tables, figures=[])
    assert "### Table 1" in md
    assert "*Table 1. Hypotheses of the target article.*" in md
    assert "```unstructured-table" in md
    assert "Hypothesis" in md
    assert "Could not reconstruct a structured grid" in md


def test_render_unlocated_table_appendix_emits_raw_text_block():
    """v2.4.14: the unlocated-tables appendix mirrors the inline path —
    a table with raw_text but no html still surfaces its content under
    a fenced ``unstructured-table`` block, not just a caption stub.
    """
    from docpluck.render import _render_sections_to_markdown

    # Body that does NOT mention "Table 1" so the renderer can't anchor
    # the table inline; it lands in the appendix.
    sectioned = _make_section_with_caption_text("body sentence only.")
    tables = [{
        "label": "Table 1",
        "caption": "Table 1. Demographics.",
        "cells": [],
        "html": "",
        "raw_text": "Age\n42\nGender\nF",
        "page": 99,
    }]
    md = _render_sections_to_markdown(sectioned, tables=tables, figures=[])
    assert "## Tables (unlocated in body)" in md
    assert "### Table 1" in md
    assert "```unstructured-table" in md
    assert "Age" in md


def test_render_unlocated_table_skipped_when_no_caption_no_html():
    """An unlocated table with neither caption nor cells/html should not
    produce a bare `### Table` stub in the appendix — it's an empty
    placeholder that confuses readers."""
    from docpluck.render import _render_sections_to_markdown

    sectioned = _make_section_with_caption_text("body sentence only.")
    tables = [{
        "label": "Table 1",
        "caption": "",     # No caption.
        "cells": [],
        "html": "",
        "page": 1,
    }]
    md = _render_sections_to_markdown(sectioned, tables=tables, figures=[])
    # Should not produce a "Tables (unlocated in body)" appendix at all
    # when the only candidate has nothing to show.
    assert "## Tables (unlocated in body)" not in md
    assert "### Table 1" not in md


def test_render_uppercases_lowercase_canonical_heading():
    """When the section detector emits a heading like ``abstract`` (lowercase,
    from Elsevier letter-spaced ``a b s t r a c t`` typography that pdftotext
    flattens), the renderer should use the canonical Title-Case form so
    the rendered .md doesn't mix ``## abstract`` with ``## Methods``.
    Regression target for v2.4.2 cosmetic fix on JESP/Cognition/JEP papers."""
    from docpluck.render import _render_sections_to_markdown

    sectioned = _make_section(
        "Self-control performance may be improved by regular practice.",
        heading_text="abstract",
        label_value="abstract",
    )
    md = _render_sections_to_markdown(sectioned, tables=[], figures=[])
    assert "## Abstract" in md
    assert "## abstract" not in md


def test_render_keeps_custom_heading_text_when_titlecase():
    """When the section detector emits a properly Title-Case canonical
    heading like ``Methods``, do not touch it — the pretty-case fix
    should be a no-op in the happy case."""
    from docpluck.render import _render_sections_to_markdown

    sectioned = _make_section(
        "Body of the methods section.",
        heading_text="Materials and Methods",
        label_value="methods",
    )
    md = _render_sections_to_markdown(sectioned, tables=[], figures=[])
    # Should keep the publisher-specific heading verbatim.
    assert "## Materials and Methods" in md


def test_render_unlocated_table_kept_when_caption_present():
    """An unlocated table with a caption but no cells still has useful
    info — keep the appendix entry."""
    from docpluck.render import _render_sections_to_markdown

    sectioned = _make_section_with_caption_text("body sentence only.")
    tables = [{
        "label": "Table 1",
        "caption": "Table 1. A useful summary.",
        "cells": [],
        "html": "",
        "page": 1,
    }]
    md = _render_sections_to_markdown(sectioned, tables=tables, figures=[])
    assert "## Tables (unlocated in body)" in md
    assert "Table 1. A useful summary." in md


# ── _suppress_inline_duplicate_figure_captions (FIG-3c) ────────────────────


def test_suppress_inline_dup_figure_caption_exact():
    # The figure caption appears once inline in body prose and once as
    # the spliced "### Figure N" block — the inline copy is dropped.
    md = (
        "increased empathy for\n"
        "\n"
        "Figure 1. Empathy model of forgiveness reconstructed from McCullough et al.\n"
        "\n"
        "the offender and (b) forgiving is uniquely related to behaviour.\n"
        "\n"
        "### Figure 1\n"
        "\n"
        "*Figure 1. Empathy model of forgiveness reconstructed from McCullough et al.*\n"
    )
    out = _suppress_inline_duplicate_figure_captions(md)
    # Inline body copy gone; the block + its *caption* survive.
    assert out.count("Empathy model of forgiveness reconstructed") == 1
    assert "### Figure 1" in out
    assert "*Figure 1. Empathy model of forgiveness reconstructed" in out
    assert "increased empathy for" in out
    assert "the offender and (b)" in out


def test_suppress_inline_dup_block_covers_body():
    # The block caption is a superset of the inline run (block absorbed a
    # continuation line) — still safe to drop the inline copy.
    md = (
        "Figure 2. Mean ratings by condition\n"
        "\n"
        "### Figure 2\n"
        "\n"
        "*Figure 2. Mean ratings by condition across the three studies.*\n"
    )
    out = _suppress_inline_duplicate_figure_captions(md)
    assert out.count("Mean ratings by condition") == 1
    assert "*Figure 2. Mean ratings by condition across the three studies.*" in out


def test_suppress_inline_dup_keeps_body_exceeding_block():
    # The inline run EXCEEDS the block caption (the block caption was
    # trimmed shorter) — dropping the inline copy would lose text, so it
    # must be KEPT.
    md = (
        "Figure 3. Scatterplot of the correlation. interaction between "
        "scenario and scores (F(1, 96) = 4.58).\n"
        "\n"
        "### Figure 3\n"
        "\n"
        "*Figure 3. Scatterplot of the correlation.*\n"
    )
    out = _suppress_inline_duplicate_figure_captions(md)
    # Inline copy retained (text-loss guard).
    assert out.count("interaction between scenario") == 1
    assert "Figure 3. Scatterplot of the correlation. interaction" in out


def test_suppress_inline_dup_keeps_body_reference():
    # A body sentence merely *referencing* a figure ("...in Figure 1, the
    # results...") must never be removed.
    md = (
        "Figure 1 below illustrates the design used in the study.\n"
        "\n"
        "### Figure 1\n"
        "\n"
        "*Figure 1. Study design overview across the three conditions.*\n"
    )
    out = _suppress_inline_duplicate_figure_captions(md)
    assert "Figure 1 below illustrates the design" in out


def test_suppress_inline_dup_noop_without_blocks():
    md = "Some body text.\n\nFigure 1. A caption-shaped line with no block.\n"
    assert _suppress_inline_duplicate_figure_captions(md) == md


# ── render_pdf_to_markdown smoke (requires test fixture) ──────────────────


def test_render_module_importable():
    from docpluck import render_pdf_to_markdown
    assert callable(render_pdf_to_markdown)


_TEST_PDFS = Path(__file__).resolve().parents[1].parent / "PDFextractor" / "test-pdfs"


@pytest.mark.skipif(
    not (_TEST_PDFS / "apa" / "chan_feldman_2025_cogemo.pdf").exists(),
    reason="chan_feldman_2025_cogemo.pdf fixture not present",
)
def test_chan_feldman_figure_captions_not_double_emitted():
    """FIG-3c real-PDF: chan_feldman's figure captions are linearized by
    pdftotext into the body text AND spliced as ``### Figure N`` blocks.
    Each caption must appear exactly once in the rendered .md."""
    from docpluck import render_pdf_to_markdown

    md = render_pdf_to_markdown(
        (_TEST_PDFS / "apa" / "chan_feldman_2025_cogemo.pdf").read_bytes()
    )
    # Figure 1's caption text must not be double-emitted.
    assert md.count("Empathy model of forgiveness reconstructed from") == 1, (
        "Figure 1 caption double-emitted"
    )
    # Figure 7's caption (with a Note) likewise.
    assert md.count("Empathy (manipulation check): Comparison of empathy") == 1, (
        "Figure 7 caption double-emitted"
    )
