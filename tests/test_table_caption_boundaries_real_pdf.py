"""A table caption ends where the caption ends -- not in the header row below it.

Three defects, one concern: which printed text belongs to a table's caption.
Each was read off the rasterized page before it was fixed.

1. **A lone statistic symbol read as a wrapped title word.**
   10.1525/collabra.90203 p12, Table 8 prints the header row
   ``F | p | BF01 | ηp2 | 95% CI`` under the title. pdftotext emits ``F`` and
   ``p`` on their own lines; ``p`` is lowercase, so the cell-run detector took
   it for a title continuation and the caption came out as
   ``... Identifiability and Explicit Learning F p``.

2. **A symbol-font glyph filed as a line of its own.**
   10.1016/j.evolhumbehav.2016.06.001 p4, Table 1 prints
   ``Summary of means, standard deviations, and Cronbach's α for the AAQ, AGS,
   Mini-K, and HKSS.``. The ``α`` comes from a symbol-font subset whose glyph
   top sits 1.4 pt above its line, and the column rebuild grouped chars by
   ``round(top)``: the caption became ``Table 1 α Summary ... Cronbach's for
   ... HKSS. α`` -- the first ``α`` moved out of its sentence and the header
   row's ``α`` appended. The caption then matched nothing in the body, so a
   correctly extracted 18-row grid was exiled to the appendix.

3. **A ligature on one side of a comparison only.**
   The same paper's Tables 4 and 6 captions keep ``coefﬁcients`` (U+FB01)
   while the normalized body reads ``coefficients``, so their anchors never
   matched either and both tables were exiled too.
"""
from __future__ import annotations

import pytest

from docpluck.extract_structured import (
    _is_table_header_like_short_line,
    extract_pdf_structured,
)
from docpluck.render import _locate_caption_anchor
from docpluck.testing import require_corpus_pdf

from .conftest import pdf_available, pdf_path

_HURST = "10.1016__j.evolhumbehav.2016.06.001.pdf"


# -- unit contracts -----------------------------------------------------------


@pytest.mark.parametrize("line", ["p", "t", "d", "n", "df", "ηp2", "α", "χ2"])
def test_a_lone_statistic_symbol_is_a_header_cell(line):
    assert _is_table_header_like_short_line(line)


@pytest.mark.parametrize("line", ["a", "by condition", "age", "and", "p value"])
def test_a_title_wrap_is_still_a_title_wrap(line):
    assert not _is_table_header_like_short_line(line)


def test_the_anchor_compares_ligatures_the_way_the_body_was_normalized():
    body = "Intro.\n\nTable 4 Correlation coefficients for attachment, aggression and more\n"
    cap = "Table 4 Correlation coefﬁcients for attachment, aggression and more"
    assert _locate_caption_anchor(body, "Table 4", cap) == body.index("Table 4")


# -- real papers --------------------------------------------------------------


def _table(result, label):
    t = next((t for t in result["tables"] if t.get("label") == label), None)
    assert t is not None, f"{label} not extracted"
    return t


def test_collabra_90203_table8_caption_stops_before_the_header_row():
    r = extract_pdf_structured(require_corpus_pdf("apa/maier_2023_collabra.pdf").read_bytes())
    assert _table(r, "Table 8")["caption"] == (
        "Table 8. Hypothetical Donations: Statistical Tests for "
        "Identifiability and Explicit Learning"
    )


@pytest.fixture(scope="module")
def hurst_bytes():
    if not pdf_available("articlerepo", _HURST):
        pytest.skip("10.1016/j.evolhumbehav.2016.06.001 not held in the article repository")
    with open(pdf_path("articlerepo", _HURST), "rb") as fh:
        return fh.read()


def test_hurst_table1_caption_keeps_alpha_in_its_sentence(hurst_bytes):
    r = extract_pdf_structured(hurst_bytes)
    assert _table(r, "Table 1")["caption"] == (
        "Table 1 Summary of means, standard deviations, and Cronbach's α "
        "for the AAQ, AGS, Mini-K, and HKSS."
    )


def test_hurst_every_table_is_placed_in_the_body(hurst_bytes):
    from docpluck.render import render_pdf_to_markdown

    md = render_pdf_to_markdown(hurst_bytes)
    assert "Tables (unlocated in body)" not in md
    # A wrapped caption keeps its hyphen and loses only the line break.
    assert "self- harm" not in md


def test_ieee_access_8_table2_caption_stops_at_the_blank_band():
    # 10.48550/arxiv.2410.21901 p5: the header row `Class Class Class Class`
    # sits 12.5 pt below the title's last line, with nothing between.
    r = extract_pdf_structured(require_corpus_pdf("ieee/ieee_access_8.pdf").read_bytes())
    assert _table(r, "Table 2")["caption"].endswith("during training for datasets used")


def test_a_label_alone_on_its_line_keeps_its_title_across_the_gap():
    # 10.15626/mp.2022.3108 p7: `Table 3`, a blank gap, then the title; Table 4
    # sits beside it in the right column.
    r = extract_pdf_structured(require_corpus_pdf("apa/chandrashekar_2023_mp.pdf").read_bytes())
    assert _table(r, "Table 3")["caption"] == (
        "Table 3 Study stimuli for the on conceptual replication of Johnson et al. (2002)"
    )
