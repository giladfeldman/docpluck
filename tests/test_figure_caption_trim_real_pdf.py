"""Real-PDF regression tests for v2.4.25 figure-caption trim chain.

Covers the three classes of caption corruption surfaced by the cycle-9
handoff (item A) plus the broad-read of amj_1 / ieee_access_2:

1. **Body-prose absorption** (xiao Figure 2 / Figure 3) — pdftotext
   flattened ``"Figure N. <caption>.\\n<inline section heading>
   <body sentence>"`` into a single rejoined paragraph so the
   paragraph-walk in ``_extract_caption_text`` couldn't separate them.
2. **Trailing PMC reprint footer** (ieee_access_2 every figure) —
   ``"IEEE Access. Author manuscript; available in PMC ...."`` absorbed
   at the end.
3. **Duplicate ALL-CAPS label** (amj_1 every figure, ieee_access_2 every
   figure) — pdftotext emits both ``Figure N.`` (title-case caption) and
   ``FIGURE N`` (graphics overlay) so the rendered caption was
   ``"Figure 1. FIGURE 1 Theoretical Framework …"``.

These tests exercise the public structured-extraction entrypoint
(``extract_pdf_structured``) on the actual library code against real
PDF fixtures, per CLAUDE.md hard rule 0d.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from docpluck.extract_structured import (
    _accumulated_is_label_only,
    _strip_duplicate_uppercase_label,
    _strip_leading_pmc_running_header,
    _trim_caption_at_body_prose_boundary,
    _trim_caption_at_running_header_tail,
    extract_pdf_structured,
)


# Disable Camelot for speed — these tests only exercise figure captions,
# which don't depend on table extraction.
os.environ.setdefault("DOCPLUCK_DISABLE_CAMELOT", "1")


TEST_PDFS = Path(__file__).resolve().parents[1].parent / "PDFextractor" / "test-pdfs"


# ---- Contract tests (cheap, pure helpers) ---------------------------------


class TestStripDuplicateUppercaseLabel:
    def test_strip_figure_n_uppercase_no_period(self):
        snippet = "Figure 1. FIGURE 1 Theoretical Framework Direction"
        assert _strip_duplicate_uppercase_label(snippet, "Figure 1") == (
            "Figure 1. Theoretical Framework Direction"
        )

    def test_strip_figure_n_uppercase_with_period(self):
        snippet = "Figure 2. FIGURE 2. Continuous-time, Markov Chain SIRS model"
        assert _strip_duplicate_uppercase_label(snippet, "Figure 2") == (
            "Figure 2. Continuous-time, Markov Chain SIRS model"
        )

    def test_strip_table_n_uppercase(self):
        snippet = "Table 3. TABLE 3 Means and standard deviations"
        assert _strip_duplicate_uppercase_label(snippet, "Table 3") == (
            "Table 3. Means and standard deviations"
        )

    def test_no_duplicate_unchanged(self):
        snippet = "Figure 1. Sample task screens (left: replication; right: original)."
        assert (
            _strip_duplicate_uppercase_label(snippet, "Figure 1") == snippet
        )

    def test_no_label_unchanged(self):
        snippet = "FIGURE 1 Theoretical Framework"
        assert _strip_duplicate_uppercase_label(snippet, "") == snippet


class TestTrimCaptionAtRunningHeaderTail:
    def test_author_etal_tail(self):
        snippet = (
            "Figure 2. Study 1 interaction plots. Exploratory analysis To examine "
            "whether and to what extent participants perceived the decoys to be "
            "less preferable than their targets, we performed paired-samples "
            "t-tests to compare the points 14 Q. XIAO ET AL."
        )
        result = _trim_caption_at_running_header_tail(snippet)
        assert result.endswith("interaction plots."), result
        assert "Q. XIAO" not in result
        assert "Exploratory" not in result

    def test_dyad_page_tail(self):
        snippet = (
            "Figure 3. Regression Slopes for the Interaction. "
            "2020 Kim and Kim 599"
        )
        result = _trim_caption_at_running_header_tail(snippet)
        assert result.endswith("Interaction."), result
        assert "Kim and Kim" not in result

    def test_pmc_reprint_footer(self):
        snippet = (
            "Figure 1. Petri nets model formalism elements. "
            "IEEE Access. Author manuscript; available in PMC 2026 February 25."
        )
        result = _trim_caption_at_running_header_tail(snippet)
        assert result.endswith("formalism elements."), result
        assert "PMC" not in result
        assert "Author manuscript" not in result

    def test_no_running_header_unchanged(self):
        snippet = "Figure 1. Means by condition. Bars represent 95% confidence intervals."
        assert _trim_caption_at_running_header_tail(snippet) == snippet


class TestTrimCaptionAtBodyProseBoundary:
    def test_xiao_figure_2_pattern(self):
        snippet = (
            "Figure 2. Study 1 interaction plots. Exploratory analysis To examine "
            "whether and to what extent participants perceived the decoys."
        )
        result = _trim_caption_at_body_prose_boundary(snippet)
        assert result == "Figure 2. Study 1 interaction plots.", result

    def test_xiao_figure_3_pattern(self):
        snippet = (
            "Figure 3. Target choice rate by condition. Choice regret and "
            "justifiability Connolly et al. (2013) observed that Control "
            "participants indicated that an imagined choice."
        )
        result = _trim_caption_at_body_prose_boundary(snippet)
        assert result == "Figure 3. Target choice rate by condition.", result

    def test_legit_two_sentence_caption_kept(self):
        # Note + caption-continuation opener — must NOT be trimmed.
        snippet = (
            "Figure 1. Means by condition. Note. Error bars represent 95% "
            "confidence intervals."
        )
        result = _trim_caption_at_body_prose_boundary(snippet)
        assert result == snippet, result

    def test_legit_caption_with_panel_kept(self):
        snippet = "Figure 4. Effect of X on Y. Panel A shows the main effect."
        result = _trim_caption_at_body_prose_boundary(snippet)
        assert result == snippet, result

    def test_short_caption_skipped(self):
        snippet = "Figure 1. Means."
        assert _trim_caption_at_body_prose_boundary(snippet) == snippet


# ---- Real-PDF regression tests (rule 0d) ----------------------------------


@pytest.mark.skipif(
    not (TEST_PDFS / "apa" / "xiao_2021_crsp.pdf").exists(),
    reason="xiao_2021_crsp.pdf fixture not present",
)
def test_xiao_figure_2_no_body_prose_absorption():
    """Cycle-9 handoff item A ship-blocker: xiao Figure 2 caption must
    NOT absorb the inline body section heading "Exploratory analysis"
    and the body-prose run that follows it."""
    pdf = TEST_PDFS / "apa" / "xiao_2021_crsp.pdf"
    result = extract_pdf_structured(pdf.read_bytes())
    figs = {f["label"]: f["caption"] for f in result["figures"]}
    assert "Figure 2" in figs
    cap = figs["Figure 2"]
    assert cap == "Figure 2. Study 1 interaction plots.", cap
    # Both the body-prose absorption AND the running-header tail must
    # be gone.
    assert "Exploratory analysis" not in cap
    assert "XIAO" not in cap


@pytest.mark.skipif(
    not (TEST_PDFS / "apa" / "xiao_2021_crsp.pdf").exists(),
    reason="xiao_2021_crsp.pdf fixture not present",
)
def test_xiao_figure_3_no_body_prose_absorption():
    """xiao Figure 3 — same root cause as Figure 2."""
    pdf = TEST_PDFS / "apa" / "xiao_2021_crsp.pdf"
    result = extract_pdf_structured(pdf.read_bytes())
    figs = {f["label"]: f["caption"] for f in result["figures"]}
    assert "Figure 3" in figs
    cap = figs["Figure 3"]
    assert cap == "Figure 3. Target choice rate by condition.", cap
    assert "Choice regret" not in cap
    assert "Connolly" not in cap


@pytest.mark.skipif(
    not (TEST_PDFS / "ieee" / "ieee_access_2.pdf").exists(),
    reason="ieee_access_2.pdf fixture not present",
)
def test_ieee_access_no_pmc_footer_on_captions():
    """Every figure caption in ieee_access_2.pdf used to end with
    'IEEE Access. Author manuscript; available in PMC ...'."""
    pdf = TEST_PDFS / "ieee" / "ieee_access_2.pdf"
    result = extract_pdf_structured(pdf.read_bytes())
    offenders = [
        f["label"] for f in result["figures"]
        if "Author manuscript" in f["caption"]
        or "available in PMC" in f["caption"]
    ]
    assert offenders == [], f"PMC footer in: {offenders}"


@pytest.mark.skipif(
    not (TEST_PDFS / "ieee" / "ieee_access_2.pdf").exists(),
    reason="ieee_access_2.pdf fixture not present",
)
def test_ieee_access_no_duplicate_uppercase_label():
    """Every ieee_access_2 figure used to render as
    'Figure N. FIGURE N. <caption>'."""
    pdf = TEST_PDFS / "ieee" / "ieee_access_2.pdf"
    result = extract_pdf_structured(pdf.read_bytes())
    offenders = [
        f["label"] for f in result["figures"]
        if f["caption"].startswith(f"{f['label']}. FIGURE")
    ]
    assert offenders == [], f"Duplicate uppercase label in: {offenders}"


@pytest.mark.skipif(
    not (TEST_PDFS / "aom" / "amj_1.pdf").exists(),
    reason="amj_1.pdf fixture not present",
)
def test_amj_1_no_duplicate_uppercase_label():
    """Every amj_1 figure used to render as
    'Figure N. FIGURE N <caption>' (no period after FIGURE N)."""
    pdf = TEST_PDFS / "aom" / "amj_1.pdf"
    result = extract_pdf_structured(pdf.read_bytes())
    offenders = [
        f["label"] for f in result["figures"]
        if f["caption"].startswith(f"{f['label']}. FIGURE")
    ]
    assert offenders == [], f"Duplicate uppercase label in: {offenders}"


# ---- Cycle 15n (v2.4.31) ---------------------------------------------------


class TestAccumulatedIsLabelOnly:
    """Pure-helper coverage for the label-only fullmatch predicate the
    paragraph-walk uses to decide whether to keep going past a
    sentence-terminator break.
    """

    def test_uppercase_label_only(self):
        assert _accumulated_is_label_only("FIGURE 1.")

    def test_titlecase_label_only(self):
        assert _accumulated_is_label_only("Figure 12.")

    def test_label_no_period(self):
        assert _accumulated_is_label_only("FIGURE 1")

    def test_duplicate_label_in_two_paragraphs(self):
        assert _accumulated_is_label_only("Figure 1.\n\nFIGURE 1.")

    def test_table_label_only(self):
        assert _accumulated_is_label_only("Table 3.")

    def test_real_caption_rejected(self):
        assert not _accumulated_is_label_only(
            "Figure 1. Petri nets model formalism elements."
        )

    def test_running_header_rejected(self):
        assert not _accumulated_is_label_only("Author Manuscript")

    def test_empty_rejected(self):
        assert not _accumulated_is_label_only("")


class TestStripLeadingPmcRunningHeader:
    def test_single_author_manuscript(self):
        snippet = "Figure 4. Author Manuscript Two options for addressing arcs."
        assert _strip_leading_pmc_running_header(snippet) == (
            "Figure 4. Two options for addressing arcs."
        )

    def test_multiple_author_manuscript(self):
        snippet = (
            "Figure 5. Author Manuscript Author Manuscript Comparison of rounding "
            "method performance."
        )
        assert _strip_leading_pmc_running_header(snippet) == (
            "Figure 5. Comparison of rounding method performance."
        )

    def test_table_label_form(self):
        snippet = "Table 2. Author Manuscript Means by condition."
        assert _strip_leading_pmc_running_header(snippet) == (
            "Table 2. Means by condition."
        )

    def test_no_header_unchanged(self):
        snippet = "Figure 3. Discrete-time, deterministic SIRS model."
        assert _strip_leading_pmc_running_header(snippet) == snippet

    def test_author_manuscript_mid_sentence_not_stripped(self):
        # Don't strip occurrences that are not immediately after the label.
        snippet = "Figure 6. The authors edit the Author Manuscript before submission."
        assert _strip_leading_pmc_running_header(snippet) == snippet


@pytest.mark.skipif(
    not (TEST_PDFS / "ieee" / "ieee_access_2.pdf").exists(),
    reason="ieee_access_2.pdf fixture not present",
)
def test_ieee_access_no_label_only_placeholder_captions():
    """Cycle 15n regression: at v2.4.30 every ieee_access_2 figure
    caption other than Figure 9 rendered as ``Figure N. FIGURE N.`` —
    a label-only placeholder with no description content. The paragraph-
    walk was bailing at the first ``\\n\\n`` after the ALL-CAPS label
    line because the label ends in ``.``. Fix: keep walking past that
    break when the accumulated text is label-only.
    """
    pdf = TEST_PDFS / "ieee" / "ieee_access_2.pdf"
    result = extract_pdf_structured(pdf.read_bytes())
    placeholders = [
        f["label"]
        for f in result["figures"]
        if "FIGURE" in (f["caption"] or "") and len(f["caption"]) < 30
    ]
    assert placeholders == [], f"label-only placeholder captions: {placeholders}"

    # Spot-check Figure 1 — the canonical case from the handoff.
    figs = {f["label"]: f["caption"] for f in result["figures"]}
    assert figs.get("Figure 1") == "Figure 1. Petri nets model formalism elements."


@pytest.mark.skipif(
    not (TEST_PDFS / "ieee" / "ieee_access_2.pdf").exists(),
    reason="ieee_access_2.pdf fixture not present",
)
def test_ieee_access_no_inline_pmc_running_header():
    """Cycle 15n sibling defect: 27/37 ieee_access_2 figure captions had
    a leading ``Author Manuscript`` PMC running header between the
    label and the description (pdftotext interleaved it across the
    blank line that separates the ALL-CAPS label from the description).
    """
    pdf = TEST_PDFS / "ieee" / "ieee_access_2.pdf"
    result = extract_pdf_structured(pdf.read_bytes())
    offenders = [
        f["label"]
        for f in result["figures"]
        if "Author Manuscript" in (f["caption"] or "")
    ]
    assert offenders == [], f"Author Manuscript leak in: {offenders}"


# ---- v2.4.47 figure-caption overflow walk-back ----------------------------
#
# pdftotext joins a figure caption to the following body prose with only a
# single ``\n`` (no ``\n\n`` paragraph break), so the ``_extract_caption_text``
# paragraph-walk can't stop and absorbs body prose up to the 800-char hard
# cap. The old 400-char cap then cut the caption mid-word and appended ``…``.
# ``_trim_overflowing_figure_caption`` walks the overflow back to the last
# real sentence terminator instead. jdm_m.2022.2 Figure 1 absorbed the
# ``H1 :`` hypothesis statement; Figure 3 absorbed a ``(N = 61) performed …``
# body sentence.


from docpluck.extract_structured import _trim_overflowing_figure_caption


class TestTrimOverflowingFigureCaption:
    def test_walks_back_to_last_sentence_terminator(self):
        cap = ("Figure 1. A real caption that ends here. "
               + "Absorbed body prose with no terminator inside the window "
               + "x" * 400)
        out = _trim_overflowing_figure_caption(cap)
        assert out == "Figure 1. A real caption that ends here."
        assert not out.endswith("…")

    def test_skips_abbreviation_periods(self):
        # "vs." must not be treated as a sentence end.
        cap = ("Figure 2. Condition A vs. condition B comparison shown here. "
               + "z" * 400)
        out = _trim_overflowing_figure_caption(cap)
        assert out == (
            "Figure 2. Condition A vs. condition B comparison shown here."
        )

    def test_falls_back_to_ellipsis_when_no_terminator(self):
        # No usable terminator past char 60 → keep the mid-word cap.
        cap = "Figure 3. " + "wordwordword " * 60
        out = _trim_overflowing_figure_caption(cap)
        assert out.endswith("…")
        assert len(out) <= 401

    def test_short_caption_untouched_by_helper(self):
        cap = "Figure 4. Short clean caption."
        # Helper is only called on overflow, but it must be idempotent on
        # a sub-cap caption (returns it unchanged via the terminator walk).
        assert _trim_overflowing_figure_caption(cap) == cap


@pytest.mark.skipif(
    not (TEST_PDFS / "apa" / "jdm_m.2022.2.pdf").exists(),
    reason="jdm_m.2022.2.pdf fixture not present",
)
def test_jdm_m_2022_2_figure_captions_not_truncated():
    """v2.4.47 regression: jdm_m.2022.2 Figure 1 / Figure 3 captions were
    truncated mid-word with ``…`` after absorbing following body prose
    (Figure 1 absorbed the ``H1 :`` hypothesis line; Figure 3 absorbed a
    ``(N = 61) performed …`` body sentence). They must now end cleanly on
    the real caption's sentence terminator, matching the AI gold.
    """
    pdf = TEST_PDFS / "apa" / "jdm_m.2022.2.pdf"
    figs = {
        f["label"]: (f["caption"] or "")
        for f in extract_pdf_structured(pdf.read_bytes())["figures"]
    }
    f1 = figs.get("Figure 1", "")
    assert not f1.endswith("…"), f"Figure 1 still truncated: {f1!r}"
    assert f1.endswith("in a choice task with missing information."), f1
    assert "H1 :" not in f1 and "H1:" not in f1, f"body prose absorbed: {f1!r}"

    f3 = figs.get("Figure 3", "")
    assert not f3.endswith("…"), f"Figure 3 still truncated: {f3!r}"
    assert f3.endswith("(Study 2, air conditioners; N = 169)."), f3
    assert "(N = 61)" not in f3, f"body prose absorbed: {f3!r}"

    # Figures 2 and 4 were already clean — must be unchanged.
    assert figs.get("Figure 2", "").endswith("(Study 1, cable TV plans; N = 114).")
    assert figs.get("Figure 4", "").endswith("(Study 3; N = 238).")


@pytest.mark.skipif(
    not (TEST_PDFS / "apa").exists(),
    reason="apa test-pdf corpus not present",
)
def test_apa_corpus_no_ellipsis_truncated_figure_captions():
    """Structural invariant: no figure caption in the APA corpus may end
    with ``…`` or exceed the 400-char hard cap. An overflow is always
    over-absorbed body prose and must be walked back to a clean sentence
    terminator (v2.4.47).
    """
    offenders = []
    for pdf in sorted((TEST_PDFS / "apa").glob("*.pdf")):
        for f in extract_pdf_structured(pdf.read_bytes())["figures"]:
            cap = f.get("caption") or ""
            if cap.endswith("…") or len(cap) > 400:
                offenders.append(f"{pdf.stem}/{f.get('label')} len={len(cap)}")
    assert offenders == [], f"truncated/overflow figure captions: {offenders}"


# ---- v2.4.48 figure-caption walk stop at period-less complete caption -----
#
# The `_extract_caption_text` paragraph-walk only stopped at a `\n\n` when the
# preceding text ended with a `.!?` terminator. It sailed past the `\n\n` that
# legitimately ends a caption ending WITHOUT a period — an APA Title-Case
# figure title (efendic Figs 4/5) or a trailing significance legend
# (`*** p < .001`, chandrashekar Figs 1/3) — and absorbed the following body
# prose. `_caption_is_complete_without_terminator` adds those two stop shapes.


from docpluck.extract_structured import _caption_is_complete_without_terminator


class TestCaptionCompleteWithoutTerminator:
    def test_apa_title_case_title_is_complete(self):
        acc = ("Figure 4. The Interaction Between Change in Manipulated "
               "Attribute and Pleasure on Change in Non-Manipulated Attribute")
        assert _caption_is_complete_without_terminator(acc, "Figure 4")

    def test_significance_legend_tail_is_complete(self):
        acc = ("Figure 1 Results of direct replications. Note.* p < .05, "
               "** p< .01, *** p < .001")
        assert _caption_is_complete_without_terminator(acc, "Figure 1")

    def test_body_prose_is_not_complete(self):
        # A lowercase content word ⇒ prose, not a period-less title.
        acc = ("Figure 4. manipulated is mainly driven by participants "
               "responses within the Low-Benefit condition")
        assert not _caption_is_complete_without_terminator(acc, "Figure 4")

    def test_label_only_is_not_complete(self):
        assert not _caption_is_complete_without_terminator("Figure 4.", "Figure 4")

    def test_short_phrase_is_not_complete(self):
        # < 4 words and no legend ⇒ not enough to call a complete title.
        assert not _caption_is_complete_without_terminator(
            "Figure 4. The Interaction", "Figure 4"
        )


@pytest.mark.skipif(
    not (TEST_PDFS / "apa" / "efendic_2022_affect.pdf").exists(),
    reason="efendic_2022_affect.pdf fixture not present",
)
def test_efendic_figure_captions_stop_at_titlecase_title():
    """v2.4.48 regression: efendic Figures 4/5 are APA period-less
    Title-Case figure titles; the walk used to sail past the `\n\n`
    after the title and absorb the following body sentence.
    """
    figs = {
        f["label"]: (f["caption"] or "")
        for f in extract_pdf_structured(
            (TEST_PDFS / "apa" / "efendic_2022_affect.pdf").read_bytes()
        )["figures"]
    }
    f4 = figs.get("Figure 4", "")
    assert f4.endswith("on Change in Non-Manipulated Attribute"), f4
    assert "manipulated is mainly driven" not in f4, f"body prose absorbed: {f4!r}"

    f5 = figs.get("Figure 5", "")
    assert f5.endswith("as a Function of Risk/Benefit Manipulations"), f5
    assert "Table S41" not in f5, f"body prose absorbed: {f5!r}"


@pytest.mark.skipif(
    not (TEST_PDFS / "apa" / "chandrashekar_2023_mp.pdf").exists(),
    reason="chandrashekar_2023_mp.pdf fixture not present",
)
def test_chandrashekar_figure_captions_stop_at_significance_legend():
    """v2.4.48 regression: chandrashekar Figures 1/3 captions end with a
    significance legend (`*** p < .001`); the walk used to sail past the
    `\n\n` after the legend and absorb the following ``We …`` body
    sentence.
    """
    figs = {
        f["label"]: (f["caption"] or "")
        for f in extract_pdf_structured(
            (TEST_PDFS / "apa" / "chandrashekar_2023_mp.pdf").read_bytes()
        )["figures"]
    }
    f1 = figs.get("Figure 1", "")
    assert f1.rstrip().endswith("p < .001"), f1
    assert "We proceeded" not in f1, f"body prose absorbed: {f1!r}"

    f3 = figs.get("Figure 3", "")
    assert f3.rstrip().endswith("p < .001"), f3
    assert "We conducted" not in f3, f"body prose absorbed: {f3!r}"
