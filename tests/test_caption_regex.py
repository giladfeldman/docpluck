"""Caption-regex pre-scan tests."""

import pytest
from docpluck.tables.captions import (
    TABLE_CAPTION_RE,
    FIGURE_CAPTION_RE,
    find_caption_matches,
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
