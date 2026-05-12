"""Tests for docpluck.render — the v2.2.0 markdown render entry point and
its markdown-level post-processors.

Ported from docs/superpowers/plans/spot-checks/splice-spike/test_splice_spike.py
(iter-29 / iter-32 / iter-34 / iter-23 / iter-20 blocks).
"""

import pytest

from docpluck.render import (
    _dedupe_h2_sections,
    _fix_hyphenated_line_breaks,
    _join_multiline_caption_paragraphs,
    _merge_compound_heading_tails,
    _promote_numbered_subsection_headings,
    _reformat_jama_key_points_box,
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


def test_promote_rejects_prose_with_long_lowercase_run():
    text = "1.2 The quick brown fox jumps over the lazy dog"
    out = _promote_numbered_subsection_headings(text)
    assert "### 1.2" not in out


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
    """When Camelot returned no cells (no html), the renderer should NOT
    emit a bare `### Table N` heading in the body — that promises
    structured content that isn't there. Instead, the caption renders as
    a plain italic paragraph so the table reference is still visible.
    Regression target for v2.4.2 H-tag failures (bjps_4,
    ar_apa_j_jesp_2009_12_011)."""
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


# ── render_pdf_to_markdown smoke (requires test fixture) ──────────────────


def test_render_module_importable():
    from docpluck import render_pdf_to_markdown
    assert callable(render_pdf_to_markdown)
