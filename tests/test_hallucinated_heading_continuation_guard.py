"""Tests for HALLUC-HEAD-2 / G5d-2 — demote `## <Title>` when the prior
line ends in a continuation word (soft-wrap split false-promotion).

Added 2026-05-23 cycle 3 of the docpluck-iterate gate run. Targets the
ip_feldman_2025_pspb `## Supplemental Materials` mid-Method hallucination
that triggered the user's original screenshot-4 complaint.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from docpluck.render import _demote_continuation_promoted_headings
from docpluck.render import render_pdf_to_markdown


_PDF_ROOT = Path(__file__).resolve().parents[1] / ".." / "PDFextractor" / "test-pdfs"


def _maybe_render(rel: str) -> str:
    pdf = (_PDF_ROOT / rel).resolve()
    if not pdf.is_file():
        pytest.skip(f"fixture not available locally: {rel}")
    return render_pdf_to_markdown(pdf.read_bytes())


# ── Contract tests (synthetic) ─────────────────────────────────────────


class TestContinuationDemotion:
    def test_demotes_after_the(self):
        # The canonical cycle-3 case from ip_feldman.
        md = "\n".join([
            "The calculated effect sizes are summarized in the",
            "",
            "## Supplemental Materials",
            "",
            "There were several issues with the target article's effects.",
        ])
        out = _demote_continuation_promoted_headings(md)
        assert "## Supplemental Materials" not in out
        assert "Supplemental Materials" in out
        # Body preserved
        assert "There were several issues" in out

    def test_demotes_after_of(self):
        md = "We summarized the comparison of\n\n## Target Article"
        out = _demote_continuation_promoted_headings(md)
        assert "## Target Article" not in out
        assert "Target Article" in out

    def test_demotes_after_in(self):
        md = "Materials and procedures are listed in\n\n## Supplemental Tables"
        out = _demote_continuation_promoted_headings(md)
        assert "## Supplemental Tables" not in out

    def test_demotes_after_and(self):
        md = "Reliability was assessed using Cronbach's alpha and\n\n## Composite Scores"
        out = _demote_continuation_promoted_headings(md)
        assert "## Composite Scores" not in out

    def test_demotes_after_a(self):
        md = "We then conducted a\n\n## Power Analysis"
        out = _demote_continuation_promoted_headings(md)
        assert "## Power Analysis" not in out

    def test_h3_NOT_demoted_to_avoid_label_false_positives(self):
        # h3+ have lower over-promotion risk + would false-positive on
        # label headings like `### Table 1` that legitimately follow a
        # continuation-word context. Conservative: scope to h2 only.
        # See `### Table 1` in chandrashekar_2023_mp cycle-3 first attempt.
        md = "The results are summarized in the\n\n### Below Table"
        out = _demote_continuation_promoted_headings(md)
        assert "### Below Table" in out


class TestContinuationRejoin:
    """v2.4.79 — the demoted continuation is rejoined to the prior line it
    grammatically continues, not left as an orphan bare line (which reads as
    a hallucinated fragment to the AI verifier). ip_feldman canary finding #2.
    """

    def test_rejoins_to_prior_line_no_orphan(self):
        md = "\n".join([
            "The calculated effect sizes are summarized in the",
            "",
            "## Supplemental Materials",
            "",
            "There were several issues with the target article's effects.",
        ])
        out = _demote_continuation_promoted_headings(md)
        # The phrase is joined onto the prior line — no standalone bare line.
        assert "summarized in the Supplemental Materials" in out
        assert "\nSupplemental Materials\n" not in out, "orphan bare line remains"
        # Body after the join is preserved on its own paragraph.
        assert "There were several issues" in out

    def test_restores_terminal_period_when_sentence_final(self):
        # Next line starts a new sentence (capital) → restore the period the
        # heading-promotion stripped.
        md = "summarized in the\n\n## Supplemental Materials\n\nThere were issues."
        out = _demote_continuation_promoted_headings(md)
        assert "summarized in the Supplemental Materials." in out

    def test_no_double_period(self):
        # If the heading text already ends in punctuation, don't add another.
        md = "we cite Smith et al. in\n\n## the Appendix.\n\nNext sentence."
        out = _demote_continuation_promoted_headings(md)
        assert "the Appendix.." not in out

    def test_no_period_when_followed_by_lowercase_continuation(self):
        # Next line continues lowercase → the phrase is NOT sentence-final,
        # so no period is injected mid-sentence.
        md = "we discuss this in the\n\n## Supplemental Materials\n\nsection below."
        out = _demote_continuation_promoted_headings(md)
        assert "in the Supplemental Materials section below." in out or (
            "in the Supplemental Materials" in out
            and "Supplemental Materials." not in out
        )


class TestContinuationGuardsAgainstFalsePositives:
    def test_does_not_demote_after_period(self):
        # Prior line ends in `.` — sentence terminator, NOT a continuation.
        md = "The study is complete.\n\n## Conclusion\n\nWe found that..."
        out = _demote_continuation_promoted_headings(md)
        assert "## Conclusion" in out

    def test_does_not_demote_after_colon(self):
        # Prior line ends in `:` — sentence-like terminator.
        md = "We present the following:\n\n## Results"
        out = _demote_continuation_promoted_headings(md)
        assert "## Results" in out

    def test_does_not_demote_after_question_mark(self):
        md = "What did we find?\n\n## Discussion"
        out = _demote_continuation_promoted_headings(md)
        assert "## Discussion" in out

    def test_does_not_demote_after_close_paren(self):
        md = "We follow Smith et al. (2009)\n\n## Method"
        out = _demote_continuation_promoted_headings(md)
        assert "## Method" in out

    def test_does_not_demote_after_close_paren_with_period(self):
        # "(2009)." is a sentence-like terminator.
        md = "We follow Smith et al. (2009).\n\n## Method"
        out = _demote_continuation_promoted_headings(md)
        assert "## Method" in out

    def test_does_not_demote_at_document_start(self):
        # No prior line at all.
        md = "## Abstract\n\nWe report..."
        out = _demote_continuation_promoted_headings(md)
        assert "## Abstract" in out

    def test_does_not_demote_after_table(self):
        # Structural prior (HTML close tag) — NOT a soft-wrap target.
        md = "</table>\n\n## Discussion\n\nWe discuss..."
        out = _demote_continuation_promoted_headings(md)
        assert "## Discussion" in out

    def test_does_not_demote_after_heading(self):
        # Two ## in a row — second one is legitimate.
        md = "## Section A\n\n## Section B"
        out = _demote_continuation_promoted_headings(md)
        assert "## Section A" in out
        assert "## Section B" in out

    def test_does_not_demote_after_list_item(self):
        md = "- bullet\n- another bullet\n\n## Discussion"
        out = _demote_continuation_promoted_headings(md)
        assert "## Discussion" in out

    def test_does_not_demote_after_caption(self):
        # Italic caption markers `*Table N.` should NOT trigger demotion.
        md = "*Table 1. Summary of findings.*\n\n## Method"
        out = _demote_continuation_promoted_headings(md)
        assert "## Method" in out

    def test_does_not_demote_after_blockquote(self):
        md = "> quoted text\n\n## Discussion"
        out = _demote_continuation_promoted_headings(md)
        assert "## Discussion" in out

    def test_does_not_demote_after_but(self):
        # "but" can legitimately end a sentence stylistically.
        # Conservative: only common continuations demote.
        md = "We tried hard but\n\n## Conclusion"
        out = _demote_continuation_promoted_headings(md)
        # "but" not in our set — should NOT demote.
        assert "## Conclusion" in out

    def test_does_not_demote_after_however(self):
        # Common adverb / discourse marker — NOT in our set.
        md = "Results were unclear however\n\n## Discussion"
        out = _demote_continuation_promoted_headings(md)
        assert "## Discussion" in out

    def test_does_not_demote_when_last_char_is_dash(self):
        # em-dash / en-dash sentence boundary.
        md = "Some text—\n\n## Section"
        out = _demote_continuation_promoted_headings(md)
        assert "## Section" in out

    def test_does_not_demote_after_numeric(self):
        # Page numbers, stats, etc.
        md = "Sample size was N = 200\n\n## Method"
        out = _demote_continuation_promoted_headings(md)
        # last_word_match grabs 'N' — not in our set.
        assert "## Method" in out


# ── Idempotency ────────────────────────────────────────────────────────


class TestIdempotent:
    def test_idempotent_on_demotion(self):
        md = "The calculated effect sizes are summarized in the\n\n## Supplemental Materials"
        once = _demote_continuation_promoted_headings(md)
        twice = _demote_continuation_promoted_headings(once)
        assert once == twice

    def test_idempotent_on_no_op(self):
        md = "Body text.\n\n## Section\n\nMore body."
        once = _demote_continuation_promoted_headings(md)
        twice = _demote_continuation_promoted_headings(once)
        assert once == twice


# ── Real-PDF regression ────────────────────────────────────────────────


class TestG5d2RealPdfRegression:
    def test_ip_feldman_no_supplemental_materials_heading_mid_method(self):
        md = _maybe_render("apa/ip_feldman_2025_pspb.pdf")
        # The hallucinated `## Supplemental Materials` mid-Method heading
        # from cycle 2 must be gone. The endmatter `## Supplemental Material`
        # (singular) is legitimate and should remain.
        lines = md.split("\n")
        plural_heading_lines = [
            i for i, ln in enumerate(lines)
            if ln.strip() == "## Supplemental Materials"
        ]
        assert len(plural_heading_lines) == 0, (
            f"Found `## Supplemental Materials` at line(s) {plural_heading_lines} — "
            "should have been demoted by HALLUC-HEAD-2 guard."
        )
        # Endmatter `## Supplemental Material` (singular) IS legitimate; do
        # not require it to be gone.

    def test_ip_feldman_supplemental_materials_text_preserved_as_body(self):
        # After demotion, "Supplemental Materials" must still appear in the
        # rendered output (as bare body text), so the demote doesn't drop
        # the words entirely.
        md = _maybe_render("apa/ip_feldman_2025_pspb.pdf")
        assert "Supplemental Materials" in md or "Supplemental Material" in md

    def test_ip_feldman_effect_sizes_sentence_rejoined(self):
        # v2.4.79 finding #2: the demoted continuation must be rejoined into
        # one continuous sentence matching the gold, not split across a blank
        # line as an orphan fragment.
        md = _maybe_render("apa/ip_feldman_2025_pspb.pdf")
        assert "The calculated effect sizes are summarized in the Supplemental Materials." in md, (
            "effect-sizes sentence should be rejoined into one continuous line"
        )
        # No orphan bare "Supplemental Materials" line surrounded by blanks.
        assert "\n\nSupplemental Materials\n\n" not in md
