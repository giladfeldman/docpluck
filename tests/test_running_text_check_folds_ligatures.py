"""A prose grid is recognised as its page's running text across a ligature (d-58ce8d).

The text channel keeps U+FB01 / U+FB00 where Camelot's pdfminer spells the
letters out. On 10.1017/s1930297500003193 p6, a grid line holding "first" was
therefore not found in its page (where it reads with U+FB01), and a copy of
body prose shipped as an uncaptioned table candidate. The sentences below are
invented, not the paper's. Failed on v2.4.159.
"""
from __future__ import annotations

from docpluck.extract_structured import (
    _candidate_is_page_running_text,
    _grid_words_covered_by_text,
    _line_found_in_page,
    _page_word_strings,
)

FI, FF = "ﬁ", "ﬀ"
LINE1 = "the sample was drawn from two cohorts and {o}ers a test of whether the order effects are"
LINE2 = "stable across sessions. Each block was presented {f}rst in a random order for every participant"
PAGE = (LINE1.format(o=f"o{FF}") + "\n" + LINE2.format(f=FI) + "\n"
        "and the remaining blocks followed in a fixed sequence for all of the sessions.\n")


def test_line_with_spelled_out_ligature_is_found():
    (pw,) = _page_word_strings(PAGE)
    assert _line_found_in_page("Each block was presented first in a random order", pw)
    assert _line_found_in_page("two cohorts and offers a test of whether the order", pw)


def test_prose_grid_is_running_text():
    cells = [
        {"r": 0, "c": 0, "text": LINE1.format(o="off")},
        {"r": 1, "c": 0, "text": LINE2.format(f="fi")},
    ]
    (pw,) = _page_word_strings(PAGE)
    assert _candidate_is_page_running_text({"cells": cells, "page": 1}, pw, PAGE)


def test_grid_coverage_counts_ligature_words():
    td = {"cells": [{"text": "offers first"}]}
    assert _grid_words_covered_by_text(td, f"o{FF}ers {FI}rst") == 1.0
