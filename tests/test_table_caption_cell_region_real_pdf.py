"""Real-PDF regression tests for cycle 15f-1 (v2.4.32, G4b).

The `_extract_caption_text` paragraph-walk has no sentence terminator to
stop at when a TABLE caption's title lacks a trailing period (common in
AOM / management journals: "Table 1. Most Cited Sources in
Organizational Behavior Textbooks"). It walked straight through the
pdftotext-linearized cell content (column headers, then "Yes"/"No",
then numbers) until the 400-char hard cap — so every such table's
`caption` field became 400 chars of cell garbage.

The TRIAGE_2026-05-14 G4 block (re-scoped in cycle 15f investigation)
calls this G4b. Fix: a table-specific trim
(`_trim_table_caption_at_cell_region`) that cuts the raw caption region
at the start of the linearized cell content — either at the end of a
sentence-terminated first line, or at the first run of >=3 consecutive
header-like short lines.

Ground truth for the expected captions is the AI-multimodal `reading`
gold in the shared article repository
(`~/ArticleRepository/ai_gold/<key>/reading.md`), per CLAUDE.md's
ground-truth hard rule.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from docpluck.extract_structured import (
    _is_table_header_like_short_line,
    _trim_table_caption_at_cell_region,
    extract_pdf_structured,
)


os.environ.setdefault("DOCPLUCK_DISABLE_CAMELOT", "1")

TEST_PDFS = Path(__file__).resolve().parents[1].parent / "PDFextractor" / "test-pdfs"


# ---- Contract tests (pure helpers) ----------------------------------------


class TestIsTableHeaderLikeShortLine:
    def test_single_word_header(self):
        assert _is_table_header_like_short_line("Rank")

    def test_two_word_header(self):
        assert _is_table_header_like_short_line("Academic Rank")

    def test_three_word_header(self):
        assert _is_table_header_like_short_line("Number of Citations")

    def test_numeric_cell(self):
        assert _is_table_header_like_short_line("1,675")

    def test_yes_no_cell(self):
        assert _is_table_header_like_short_line("Yes")

    def test_long_line_rejected(self):
        # A 4+-word capitalised line is a wrapped title, not a header.
        assert not _is_table_header_like_short_line(
            "General Management (GM) Textbooks Analyzed"
        )

    def test_lowercase_continuation_rejected(self):
        assert not _is_table_header_like_short_line("by condition")

    def test_conjunction_tail_rejected(self):
        assert not _is_table_header_like_short_line("Means and SDs and")

    def test_empty_rejected(self):
        assert not _is_table_header_like_short_line("")


class TestTrimTableCaptionAtCellRegion:
    def test_label_only_first_line_three_run(self):
        region = (
            "TABLE 1\n"
            "Most Cited Sources in Organizational Behavior Textbooks\n"
            "Rank\n\nAcademic\nSource\n\nYes\nYes\nNo\n"
        )
        out = _trim_table_caption_at_cell_region(region)
        assert out == (
            "TABLE 1\nMost Cited Sources in Organizational Behavior Textbooks"
        ), out

    def test_terminated_first_line_cuts_after_title(self):
        region = (
            "Table 6. Study 2 descriptive statistics.\n"
            "Choice of the target option\nRegret\nJustifiability\n"
            "Target\nM\nSD\n"
        )
        out = _trim_table_caption_at_cell_region(region)
        assert out == "Table 6. Study 2 descriptive statistics.", out

    def test_short_single_word_title_not_truncated(self):
        # nonblank[1] is a short one-word title — must be preserved by
        # the index-2 floor of the cell-run detector.
        region = (
            "Table 3\nCorrelations\nVariable\nM\nSD\nr\n1\n2\n3\n"
        )
        out = _trim_table_caption_at_cell_region(region)
        assert "Correlations" in out, out

    def test_too_few_lines_unchanged(self):
        region = "Table 1. Means.\nVariable\nM\n"
        assert _trim_table_caption_at_cell_region(region) == region


# ---- Real-PDF regression tests (rule 0d) ----------------------------------


@pytest.mark.skipif(
    not (TEST_PDFS / "aom" / "amle_1.pdf").exists(),
    reason="amle_1.pdf fixture not present",
)
def test_amle_1_table_captions_not_cell_garbage():
    """Every amle_1 table caption used to be 400 chars of linearized
    cell content. After the fix each caption is a clean title."""
    pdf = TEST_PDFS / "aom" / "amle_1.pdf"
    result = extract_pdf_structured(pdf.read_bytes())
    caps = {t["label"]: (t.get("caption") or "") for t in result["tables"]}
    assert len(caps) == 13, caps.keys()

    # Canonical check against the AI-gold `reading` view.
    assert caps["Table 1"] == (
        "Table 1. Most Cited Sources in Organizational Behavior Textbooks"
    ), caps["Table 1"]
    assert caps["Table 9"] == (
        "Table 9. Most Cited Authors in Organizational Behavior Textbooks"
    ), caps["Table 9"]

    # No caption should carry the linearized-cell signature: a run of
    # standalone "Yes"/"No" tokens or a long digit spew.
    for label, cap in caps.items():
        assert " Yes Yes " not in cap, f"{label} caption has cell spew: {cap!r}"
        assert " No Yes No " not in cap, f"{label} caption has cell spew: {cap!r}"
        # Tables 1-12 are single-line titles — comfortably under 200 chars.
        # Table 13 is a genuine 2-line title (~236 chars); allow it.
        if label != "Table 13":
            assert len(cap) < 200, f"{label} caption too long ({len(cap)}): {cap!r}"


@pytest.mark.skipif(
    not (TEST_PDFS / "apa" / "xiao_2021_crsp.pdf").exists(),
    reason="xiao_2021_crsp.pdf fixture not present",
)
def test_xiao_table_captions_stop_at_title():
    """xiao tables have period-terminated titles on the caption line;
    the caption must stop at the period, not absorb column headers."""
    pdf = TEST_PDFS / "apa" / "xiao_2021_crsp.pdf"
    result = extract_pdf_structured(pdf.read_bytes())
    caps = {t["label"]: (t.get("caption") or "") for t in result["tables"]}
    assert caps["Table 1"] == (
        "Table 1. Descriptions of the items used in Study 1."
    ), caps["Table 1"]
    assert caps["Table 6"] == "Table 6. Study 2 descriptive statistics.", caps[
        "Table 6"
    ]
    # No column-header leak past the terminating period.
    assert "Item B" not in caps["Table 1"], caps["Table 1"]
    assert "Product category" not in caps.get("Table 3", ""), caps.get("Table 3")


@pytest.mark.skipif(
    not (TEST_PDFS / "aom" / "amj_1.pdf").exists(),
    reason="amj_1.pdf fixture not present",
)
def test_amj_1_table_captions_clean():
    """amj_1 table captions are clean titles (no cell absorption)."""
    pdf = TEST_PDFS / "aom" / "amj_1.pdf"
    result = extract_pdf_structured(pdf.read_bytes())
    caps = {t["label"]: (t.get("caption") or "") for t in result["tables"]}
    assert caps["Table 2"] == (
        "Table 2. Means, Standard Deviations, and Correlations of Variables in Study 1"
    ), caps["Table 2"]
    for label, cap in caps.items():
        assert len(cap) < 200, f"{label} caption too long ({len(cap)}): {cap!r}"
