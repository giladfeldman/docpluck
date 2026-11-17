"""A normalization strip step never empties a document silently (ESCImate,
2026-11-16).

10.1037/amp0001385 Preregistration 1.0 and 2.0 (Word files): the text joins
paragraphs with single line breaks, so T0 saw ONE paragraph, found a form blank
"_______" in it, took it for a table-of-contents leader and deleted all 15,838
characters with no event. Mechanism: a strip step's unit (a blank-line
paragraph) can be the whole document. T0 now needs most of a paragraph's lines
to be TOC lines; every step that leaves under half of a text records
`normalization_step_removed_most_text`.
"""
from __future__ import annotations

import pytest

from docpluck.normalize import NormalizationLevel, _strip_toc_dot_leader_block, normalize_text
from docpluck.telemetry import fallback_scope

# The preregistration's shape: prose lines joined by single newlines, one form blank.
WORD_TEXT = "\n".join(
    ["Preregistration Version 1.0, July 1 2022", "Title",
     "Estimating the Prevalence of Replication Studies in Psychology",
     "Signature: _______    Date: _______"]
    + [f"Sentence {i} of the hypotheses and the planned analyses of this study." for i in range(60)])


def test_a_form_blank_does_not_make_a_word_document_a_toc():
    assert _strip_toc_dot_leader_block(WORD_TEXT) == WORD_TEXT


def test_a_real_toc_block_is_still_stripped():
    toc = "Table of Contents\nSupplementary Note 1 ________ 2\nSupplementary Note 2 ________ 5"
    body = "Supplementary Note 1\n\nThe participants were recruited online."
    out = _strip_toc_dot_leader_block(toc + "\n\n" + body)
    assert "________" not in out and "The participants were recruited online." in out


def test_the_normalized_word_document_keeps_its_text():
    out, _ = normalize_text(WORD_TEXT, NormalizationLevel.academic)
    assert "Estimating the Prevalence of Replication Studies" in out
    assert len(out) > 0.8 * len(WORD_TEXT)


@pytest.mark.parametrize("before, after, fires", [
    ("x" * 2000, "x" * 900, True),     # under half left
    ("x" * 2000, "x" * 1100, False),   # most kept
    ("x" * 500, "", False),            # too short to judge
], ids=["under_half", "most_kept", "short"])
def test_any_step_removing_most_of_a_text_is_recorded(before, after, fires):
    from docpluck.normalize import NormalizationReport
    with fallback_scope() as fb:
        NormalizationReport(level="academic", version="t")._track("ZZ_any", before, after, "m")
    assert ("normalization_step_removed_most_text" in fb.counters) is fires


# The lakens2017 selection-plan preregistration (Word): Table 1 lists 54
# meta-analyses as cells joined by single line breaks.
def _word_table(n=25):
    rows = ["Table 1. The 54 studies identified in the literature search.",
            "Journal", "Year", "DOI", "# Studies"]
    for i in range(1, n + 1):
        rows += [str(i), "Psychological Bulletin", "2013", f"10.1037/a00{28600 + i}", str(100 + i)]
    return "\n".join(rows)


def test_a_bare_doi_cell_is_not_joined_to_the_number_cells_under_it():
    from docpluck.normalize import _rejoin_broken_urls
    cells = "10.1037/a0028601\n277\n2\nPsychological Bulletin"
    assert _rejoin_broken_urls(cells) == cells
    # A DOI cut after its reference text still joins its digit tail.
    assert _rejoin_broken_urls("Appetite. doi:10.1093/ije/1234\n567\nNext") == \
        "Appetite. doi:10.1093/ije/1234567\nNext"


def test_a_repeated_table_cell_without_pages_is_kept():
    text = _word_table()
    out, _ = normalize_text(text, NormalizationLevel.academic)
    assert out.count("Psychological Bulletin") == 25
    assert "10.1037/a0028601\n101" in out
