"""Cycle 4 redux (2026-06-06): front-matter masthead-block strip +
wrapped-title-duplicate demoter regression tests.

Two render-level passes added to close ip_feldman_2025_pspb canary
finding #1 (METADATA-LEAK @ lines 1-17) without re-introducing the
wrapped-title duplicate that forced the original Cluster E revert
(Run-11 cycle 4):

1. ``_demote_wrapped_title_duplicate`` — strips a ``### {prefix-of-H1}``
   + continuation block immediately under the H1 (pdftotext emits the
   title twice on PSPB/Sage column layouts). Token-prefix match against
   the H1, >=75% coverage gate.
2. ``_strip_frontmatter_masthead_block`` — strips the residual publisher
   masthead (author+superscript, journal-name wraps, page range,
   copyright tail, DOI: label, bare DOI) between the H1 and the first
   ``## `` heading. Self-limiting >=2-hard-marker gate; prose-break
   guard preserves an undetected abstract.

Both fixes are GENERAL — keyed on structural shapes (token-prefix of H1,
DOI grammar, page-range grammar, name+trailing-affiliation-digit, ©),
never on paper identity. Per rule 0d, the real-PDF case exercises the
public entry point on the actual fixture; the synthetic cases lock the
gate behavior.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from docpluck.render import (
    _demote_wrapped_title_duplicate,
    _is_frontmatter_prose_line,
    _looks_like_masthead_hard_marker,
    _nearest_h2_parent_label,
    _promote_isolated_titlecase_subsection_headings,
    _repair_column_wrapped_headings,
    _strip_frontmatter_masthead_block,
    _strip_pre_title_heading_noise,
    render_pdf_to_markdown,
)


_PDF_ROOT = Path(__file__).resolve().parents[1] / ".." / "PDFextractor" / "test-pdfs"


def _maybe_render(rel: str) -> str:
    pdf = (_PDF_ROOT / rel).resolve()
    if not pdf.is_file():
        pytest.skip(f"fixture not available locally: {rel}")
    return render_pdf_to_markdown(pdf.read_bytes())


# ── wrapped-title-duplicate demoter ─────────────────────────────────────


def test_wrapped_title_duplicate_stripped():
    """The classic PSPB shape: H1 + a `### {prefix}` + continuation lines
    that reconstruct the H1's token sequence. The `### ` block is stripped,
    the H1 preserved."""
    text = (
        "# The Complex Misestimation of Others Emotions: Underestimation "
        "of Emotional Prevalence and Their Associations with Well-Being\n\n"
        "### The Complex Misestimation of Others\n\n"
        "Emotions: Underestimation of Emotional\n"
        "Prevalence and Their Associations with Well-Being\n\n"
        "Ho Ching Ip1\n"
    )
    out = _demote_wrapped_title_duplicate(text)
    assert "### The Complex Misestimation" not in out
    assert out.count("# The Complex Misestimation") == 1  # only the H1
    assert "Ho Ching Ip1" in out  # non-duplicate content preserved


def test_wrapped_title_duplicate_low_coverage_preserved():
    """A short `### ` heading whose token prefix covers < 75% of a long
    H1 is a real subsection, not a title duplicate — preserve it."""
    text = (
        "# A Very Long Title About Many Different Things In Great Detail "
        "Across Numerous Subtopics And Domains\n\n"
        "### A Very\n\n"
        "Some body prose follows the short heading here as real content.\n"
    )
    out = _demote_wrapped_title_duplicate(text)
    assert "### A Very" in out  # 2/16 tokens = 12.5% coverage → preserved


def test_wrapped_title_duplicate_divergent_tokens_preserved():
    """A `### ` heading that is NOT an ordered prefix of the H1 tokens is
    a real heading — preserve it."""
    text = (
        "# The Complex Misestimation of Others Emotions and Well-Being "
        "Across Many Studies\n\n"
        "### Background and Prior Work\n\n"
        "Body prose continues here as genuine content well past eighty.\n"
    )
    out = _demote_wrapped_title_duplicate(text)
    assert "### Background and Prior Work" in out


def test_wrapped_title_duplicate_short_title_skipped():
    """An H1 with < 4 tokens is too risky to fingerprint — skip."""
    text = "# Short Title\n\n### Short Title\n\nbody.\n"
    out = _demote_wrapped_title_duplicate(text)
    assert "### Short Title" in out  # not stripped (H1 has 2 tokens)


# ── masthead hard-marker classifier ─────────────────────────────────────


def test_masthead_hard_marker_classifications():
    positives = [
        "10.1177/01461672251327169",          # bare DOI
        "DOI:",                                 # DOI label
        "https://doi.org/10.1177/01461672251327169",
        "1-19",                                 # page range
        "Ho Ching Ip1",                         # author + superscript
        "and Gilad Feldman1",                   # led author
        "© 2025 by the Society for Personality",
        "and Social Psychology, Inc",           # copyright tail
    ]
    for p in positives:
        assert _looks_like_masthead_hard_marker(p), f"should be hard marker: {p!r}"

    negatives = [
        "Personality and Social",               # journal wrap (soft, not hard)
        "A growing body of literature has documented misperceptions.",
        "Background",                            # subsection label
        "## Abstract",
    ]
    for ngt in negatives:
        assert not _looks_like_masthead_hard_marker(ngt), (
            f"should NOT be hard marker: {ngt!r}"
        )


def test_frontmatter_prose_line():
    assert _is_frontmatter_prose_line(
        "Jordan et al., 2011, demonstrated that people underestimated the "
        "prevalence of others' negative emotional experiences."
    )
    assert not _is_frontmatter_prose_line("Ho Ching Ip1")
    assert not _is_frontmatter_prose_line("Personality and Social")
    # Long but no terminator → not prose (could be a wrapped heading)
    assert not _is_frontmatter_prose_line(
        "A Title That Happens To Be Quite Long But Has No Terminating "
        "Period At All As It Wraps"
    )


# ── masthead-block strip: gate behavior ─────────────────────────────────


def test_masthead_block_stripped_with_two_hard_markers():
    text = (
        "# A Study of Emotional Misestimation in Social Contexts\n\n"
        "Ho Ching Ip1\n\n"
        "Personality and Social\n"
        "Psychology Bulletin\n"
        "1-19\n"
        "and Social Psychology, Inc\n"
        "DOI:\n"
        "10.1177/01461672251327169\n\n"
        "and Gilad Feldman1\n\n"
        "## Abstract\n\n"
        "Jordan et al demonstrated that people underestimated things here.\n"
    )
    out = _strip_frontmatter_masthead_block(text)
    for leak in (
        "Ho Ching Ip1", "and Gilad Feldman1", "Personality and Social",
        "Psychology Bulletin", "1-19", "and Social Psychology, Inc",
        "DOI:", "10.1177/01461672251327169",
    ):
        assert leak not in out, f"masthead leak survived: {leak!r}"
    assert "## Abstract" in out
    assert "Jordan et al demonstrated" in out
    # H1 → Abstract should be adjacent (modulo one blank line)
    head = out.split("## Abstract")[0]
    assert head.count("\n\n") <= 2


def test_masthead_block_abstract_as_body_preserved():
    """No `## Abstract` heading; abstract is body prose right after the
    title. The prose-break guard must preserve it (zero strips)."""
    abstract = (
        "This is a long abstract paragraph that runs as body text "
        "immediately after the title without any heading, and it is well "
        "over eighty characters so it counts as prose and must survive."
    )
    text = f"# A Study of Things\n\n{abstract}\n\n## Introduction\n\nBody.\n"
    out = _strip_frontmatter_masthead_block(text)
    assert out == text


def test_masthead_block_single_marker_no_fire():
    """< 2 hard markers → no-op (a lone author line is not enough to
    confirm a masthead block)."""
    text = "# A Study of Things\n\nJane Smith1\n\n## Abstract\n\nBody.\n"
    out = _strip_frontmatter_masthead_block(text)
    assert out == text


def test_masthead_block_no_h1_no_fire():
    text = "## Abstract\n\nBody text here that is the document.\n"
    out = _strip_frontmatter_masthead_block(text)
    assert out == text


def test_masthead_block_two_authors_fire():
    """Two author+superscript lines = 2 hard markers → fire."""
    text = (
        "# Title About Several Interesting Research Questions\n\n"
        "Jane Smith1\n\n"
        "and John Doe2\n\n"
        "## Abstract\n\n"
        "Body text here.\n"
    )
    out = _strip_frontmatter_masthead_block(text)
    assert "Jane Smith1" not in out
    assert "and John Doe2" not in out
    assert "## Abstract" in out and "Body text here." in out


# ── real-PDF integration (rule 0d) ──────────────────────────────────────


# ── column-wrapped subsection-heading repair (findings #3 + #4) ─────────


def test_rule_a_citation_wrap_promote():
    """Rule A: a body `{Title} et al.` line + a bare `(YYYY)` line + prose
    promotes to `### {Title} et al. (YYYY)` (canary finding #3)."""
    text = (
        "Body paragraph ends here with a sentence long enough to be prose.\n\n"
        "Choice of Study for Replication: Jordan et al.\n"
        "(2011)\n\n"
        "We aimed to revisit the classic phenomenon to examine "
        "reproducibility and replicability of the findings.\n"
    )
    out = _repair_column_wrapped_headings(text)
    assert "### Choice of Study for Replication: Jordan et al. (2011)" in out


def test_rule_a_year_glued_to_text_not_promoted():
    """Rule A must NOT fire when the year is glued to following body text
    (the bare-year-alone signal is what distinguishes a heading wrap)."""
    text = (
        "Prior work here is described.\n\n"
        "This finding was consistent with Jordan et al.\n"
        "(2011) who showed similar results across multiple replication "
        "studies done in the area over time.\n"
    )
    out = _repair_column_wrapped_headings(text)
    assert "###" not in out


def test_rule_a_followed_by_heading_not_promoted():
    """Rule A requires body prose after the year; a heading after must not
    trigger a promotion."""
    text = (
        "Body.\n\n"
        "Choice of Study for Replication: Jordan et al.\n"
        "(2011)\n\n"
        "## Method\n"
    )
    out = _repair_column_wrapped_headings(text)
    assert "### Choice" not in out


def test_rule_b_orphan_tail_reattach():
    """Rule B: a heading split mid-title gets its short colon-led orphan
    tail reattached (canary finding #4)."""
    text = (
        "## Introduction\n\n"
        "Some intro body text that is plenty long to count as prose here.\n\n"
        "### Original Hypotheses and Findings in Target\n\n"
        "Article: Jordan et al. (2011)\n"
        "Jordan et al. (2011) empirical work consisted of four studies and "
        "we focused on two of them.\n"
    )
    out = _repair_column_wrapped_headings(text)
    assert (
        "### Original Hypotheses and Findings in Target Article: "
        "Jordan et al. (2011)" in out
    )
    # The orphan tail line is gone (not left as standalone body).
    assert "\nArticle: Jordan et al. (2011)\n" not in out


def test_rule_b_two_sibling_headings_not_merged():
    """Rule B must NOT merge two consecutive real headings."""
    text = (
        "### Methods\n\n"
        "### Results\n\n"
        "We found significant effects across all conditions in the study.\n"
    )
    out = _repair_column_wrapped_headings(text)
    assert out.count("###") == 2  # both headings preserved, not merged


def test_rule_b_tail_is_sentence_not_merged():
    """A colon-led line that is a full sentence (ends with a terminator)
    is not a heading tail — do not merge."""
    text = (
        "### Background\n\n"
        "Note: this is a complete sentence.\n"
        "The body continues here with plenty of words to be prose content.\n"
    )
    out = _repair_column_wrapped_headings(text)
    assert "### Background Note:" not in out


def test_ip_feldman_findings_3_and_4_real_pdf():
    """ip_feldman_2025_pspb canary findings #3 + #4: both citation-bearing
    subsection headings render as single complete `### ` headings."""
    md = _maybe_render("apa/ip_feldman_2025_pspb.pdf")
    assert "### Choice of Study for Replication: Jordan et al. (2011)" in md, (
        "finding #3: 'Choice of Study' heading not promoted/rejoined"
    )
    assert (
        "### Original Hypotheses and Findings in Target Article: "
        "Jordan et al. (2011)" in md
    ), "finding #4: 'Original Hypotheses' heading not reattached"
    # The #4 orphan tail must not survive as standalone body.
    import re as _re
    assert not _re.search(r"(?m)^Article: Jordan et al\. \(2011\)\s*$", md)


# ── run-11 promoter guards: pre-H1, blacklist-parent, lowercase-body ────


def test_pre_title_heading_noise_stripped():
    """A heading above the document H1 (journal-section label promoted to
    a heading) is stripped (ar_apa `### FlashReport`)."""
    text = "### FlashReport\n\n# The Real Title of the Paper\n\nBody prose here."
    out = _strip_pre_title_heading_noise(text)
    assert "### FlashReport" not in out
    assert "# The Real Title of the Paper" in out


def test_pre_title_strip_noop_after_title():
    """Headings AFTER the title are preserved (no-op)."""
    text = "# Title\n\n## Introduction\n\n### Background\n\nbody"
    assert _strip_pre_title_heading_noise(text) == text


def test_pre_title_strip_noop_no_h1():
    text = "## Abstract\n\nbody text without any H1 title at all here."
    assert _strip_pre_title_heading_noise(text) == text


def test_nearest_h2_parent_label():
    lines = "## Author Contributions\n\nsome text\n\nMethodology\n\nJohn wrote it.".split("\n")
    idx = lines.index("Methodology")
    assert _nearest_h2_parent_label(lines, idx) == "Author Contributions"
    # H1 between candidate and any ## → None
    lines2 = "# Title\n\nMethodology\n\nbody".split("\n")
    assert _nearest_h2_parent_label(lines2, lines2.index("Methodology")) is None


def test_promoter_rejects_credit_role_under_author_contributions():
    """A CRediT role label under `## Author Contributions` (reached via the
    regular path) is NOT promoted (plos_med `### Methodology`)."""
    text = (
        "## Author Contributions\n\n"
        "The authors contributed as follows to this large collaborative work.\n\n"
        "Methodology\n\n"
        "Jane Smith and John Doe designed and executed the analysis plan.\n"
    )
    out = _promote_isolated_titlecase_subsection_headings(text)
    assert "### Methodology" not in out


def test_promoter_rejects_lowercase_body_fragment():
    """A candidate whose following body starts lowercase is a torn fragment,
    not a heading (chan_feldman `### Close replication`)."""
    text = (
        "## Method\n\n"
        "We describe the design in detail across the following paragraphs here.\n\n"
        "Close replication\n\n"
        "testing the proposed causal chain as specified in the preregistration.\n"
    )
    out = _promote_isolated_titlecase_subsection_headings(text)
    assert "### Close replication" not in out


def test_promoter_still_promotes_real_subsection_capital_body():
    """A genuine subsection (body opens with a Capital, non-blacklisted
    parent) is still promoted — guards don't over-reject."""
    text = (
        "## Introduction\n\n"
        "We open the introduction with a full sentence of context here today.\n\n"
        "Background\n\n"
        "Prior work has documented this phenomenon across many studies and years.\n"
    )
    out = _promote_isolated_titlecase_subsection_headings(text)
    assert "### Background" in out


def test_ar_apa_flashreport_cleared_real_pdf():
    """ar_apa_j_jesp_2009_12_011: `### FlashReport` (journal-section label
    above the title) is gone after the pre-title strip."""
    md = _maybe_render("apa/ar_apa_j_jesp_2009_12_011.pdf")
    assert "### FlashReport" not in md


def test_ip_feldman_masthead_fully_cleared_real_pdf():
    """ip_feldman_2025_pspb canary finding #1 (METADATA-LEAK @ lines 1-17):
    after Cycle 4 redux the doc flows `# Title` → `## Abstract` with no
    masthead residue in between."""
    md = _maybe_render("apa/ip_feldman_2025_pspb.pdf")

    # First non-blank line is the title H1.
    first_nonblank = next((line for line in md.split("\n") if line.strip()), "")
    assert first_nonblank.startswith("# ")

    # Slice between H1 and first `## ` heading must be empty of masthead.
    after_h1 = md.split("\n", 1)[1] if "\n" in md else ""
    head_zone = after_h1.split("## ", 1)[0]
    for leak in (
        "Ho Ching Ip1", "and Gilad Feldman1", "Psychology Bulletin",
        "and Social Psychology, Inc", "DOI:",
    ):
        assert leak not in head_zone, (
            f"masthead leak {leak!r} still present between H1 and first ##"
        )
    # Bare article ID + DOI line not standalone in the head zone.
    import re as _re
    assert not _re.search(r"(?m)^10\.1177/01461672251327169\s*$", head_zone)
    assert not _re.search(r"(?m)^1327169\s*$", md)
