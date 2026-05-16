"""Caption-regex pre-scan tests."""

import pytest
from docpluck.tables.captions import (
    TABLE_CAPTION_RE,
    FIGURE_CAPTION_RE,
    find_caption_matches,
    caption_anchor_is_in_text_reference,
    CaptionMatch,
)


@pytest.mark.parametrize("line, num", [
    ("Table 1. Descriptive statistics", 1),
    ("Table 2: Correlation matrix", 2),
    ("Table 12 Means and standard deviations", 12),
    ("    Table 3. Indented caption", 3),
    ("Table 1.", 1),
])
def test_table_caption_re_matches(line, num):
    m = TABLE_CAPTION_RE.search(line)
    assert m is not None
    assert int(m.group("num")) == num


@pytest.mark.parametrize("line", [
    "the table shows that",            # no number
    "Tabular form of",                  # not "Table"
    "see Table",                        # no number
    "Table A1",                         # appendix-numbered, deferred to level-C
])
def test_table_caption_re_does_not_match(line):
    assert TABLE_CAPTION_RE.search(line) is None


@pytest.mark.parametrize("line, num", [
    ("Figure 1. Mean reaction time", 1),
    ("Figure 2: Forest plot of effects", 2),
    ("Fig. 3 Bar chart", 3),
    ("Fig 4. Histogram", 4),
])
def test_figure_caption_re_matches(line, num):
    m = FIGURE_CAPTION_RE.search(line)
    assert m is not None
    assert int(m.group("num")) == num


def test_find_caption_matches_with_page_offsets():
    """find_caption_matches: regex over raw_text + page-offset list -> CaptionMatch list."""
    raw_text = (
        "Page 1 prose text that has nothing\n"
        "Just normal sentences here.\n"
        "\f"  # form-feed = pdftotext page break
        "Page 2 introduction paragraph...\n"
        "Table 1. Descriptive statistics\n"
        "Variable  M  SD\n"
        "\f"
        "Page 3 results section\n"
        "Figure 2. Bar chart of conditions\n"
    )
    # page_offsets: list of char-offsets where each page starts (1-indexed)
    page_offsets = [0, 67, 142]   # values are illustrative — test structure, not exact offsets

    matches = find_caption_matches(raw_text, page_offsets)
    assert len(matches) == 2
    table_match = next(m for m in matches if m.kind == "table")
    figure_match = next(m for m in matches if m.kind == "figure")
    assert table_match.number == 1
    assert table_match.label == "Table 1"
    assert figure_match.number == 2
    assert figure_match.label == "Figure 2"
    # Both should have a non-None page assigned
    assert table_match.page >= 1
    assert figure_match.page >= 1


def test_caption_match_dataclass_shape():
    m = CaptionMatch(
        kind="table",
        number=1,
        label="Table 1",
        page=3,
        char_start=100,
        char_end=130,
        line_text="Table 1. Descriptive statistics",
    )
    assert m.kind == "table"
    assert m.number == 1


# ---- FIG-3b: caption_anchor_is_in_text_reference --------------------------


def _anchor(raw_text, kind="figure"):
    """Find the (single) caption match in raw_text for the helper tests."""
    matches = find_caption_matches(raw_text, [0])
    return raw_text, next(m for m in matches if m.kind == kind)


def test_in_text_reference_after_lowercase_word():
    # chan_feldman Figure 10 shape: a body sentence "… the effects in
    # Figure 10." line-wraps so "Figure 10." starts a line.
    raw = (
        "We summarised the mediation effects in\n"
        "Figure 10.\n"
        "We found support for the effect of perceived apology.\n"
    )
    text, cap = _anchor(raw)
    assert caption_anchor_is_in_text_reference(text, cap) is True


def test_real_caption_after_blank_line_not_reference():
    # A real caption set off by a paragraph break (blank line).
    raw = (
        "higher values indicate a stronger perceived apology.\n"
        "\n"
        "Figure 10. Exploratory mediation analyses in the control condition.\n"
    )
    text, cap = _anchor(raw)
    assert caption_anchor_is_in_text_reference(text, cap) is False


def test_real_caption_after_sentence_terminator_not_reference():
    raw = (
        "This concludes the analysis.\n"
        "Figure 3. Mean ratings by condition.\n"
    )
    text, cap = _anchor(raw)
    assert caption_anchor_is_in_text_reference(text, cap) is False


def test_caption_with_blank_lines_absorbed_by_regex_not_reference():
    # FIGURE_CAPTION_RE's `^\s*` absorbs the blank line, so char_start
    # sits ABOVE the real token — the helper must advance to the token
    # before inspecting the previous line (ieee_access_7 TABLE 1 shape).
    raw = (
        "the network was trained end to end.\n"
        "\n"
        "TABLE 1: Model configuration\n"
    )
    text, cap = _anchor(raw, kind="table")
    assert caption_anchor_is_in_text_reference(text, cap) is False


def test_in_text_reference_after_comma():
    raw = (
        "As shown for both conditions,\n"
        "Figure 2. depicts the interaction across all groups here.\n"
    )
    text, cap = _anchor(raw)
    assert caption_anchor_is_in_text_reference(text, cap) is True


def test_caption_on_first_line_not_reference():
    raw = "Figure 1. Study design overview across the three conditions.\n"
    text, cap = _anchor(raw)
    assert caption_anchor_is_in_text_reference(text, cap) is False
