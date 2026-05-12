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


# ── render_pdf_to_markdown smoke (requires test fixture) ──────────────────


def test_render_module_importable():
    from docpluck import render_pdf_to_markdown
    assert callable(render_pdf_to_markdown)
