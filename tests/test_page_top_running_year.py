"""A bare year printed as the running head of every verso page is furniture.

Academy of Management journals print "2020   Kim and Kim   585" across the top
of each verso page (page raster, 10.5465/amj.2016.1196 p2). pdftotext emits the
three parts as separate lines; the names and the folio were already stripped,
the year stayed as a line of its own at the top of 13 pages (14 in
10.5465/amle.2017.0488). A digit-only line is never matched by the
repeated-line strip, because a year is also a table cell: amle prints 44 year
cells in its tables, and those must stay.
"""

import re
from pathlib import Path

from docpluck import NormalizationLevel, extract_pdf, normalize_text
from docpluck.normalize import _strip_page_top_running_year
from docpluck.testing.corpus import require_corpus_pdf

_PAGE_TOP_YEAR = re.compile(r"(?m)^\f(?:19|20)\d\d$")
_YEAR_LINE = re.compile(r"(?m)^(?:19|20)\d\d$")


def _norm(rel):
    raw, _ = extract_pdf(Path(require_corpus_pdf(rel)).read_bytes())
    return raw, normalize_text(raw, NormalizationLevel.academic)[0]


def test_verso_year_heads_are_stripped_and_table_years_kept():
    raw, out = _norm("aom/amle_1.pdf")
    assert len(_PAGE_TOP_YEAR.findall(raw)) >= 14, "positive control: the verso year heads are in the raw text"
    table_years = len(_YEAR_LINE.findall(raw))
    assert table_years >= 40, "positive control: the tables print year cells"
    assert _PAGE_TOP_YEAR.findall(out) == []
    assert len(_YEAR_LINE.findall(out)) == table_years, "a year cell inside a table was removed"


def test_amj_verso_year_heads_are_stripped():
    raw, out = _norm("aom/amj_1.pdf")
    assert len(_PAGE_TOP_YEAR.findall(raw)) >= 13
    assert _PAGE_TOP_YEAR.findall(out) == []


def _pages(tops):
    return "\f".join(f"{top}\n\nBody text of the page, with a sentence.\n" for top in tops)


def test_a_year_on_top_of_two_pages_is_not_a_running_head():
    text = "Title\n\n" + _pages(["2019", "2019", "Other"])
    assert _strip_page_top_running_year(text) == text


def test_different_years_on_page_tops_are_not_a_running_head():
    text = "Title\n\n" + _pages(["2017", "2018", "2019", "2020"])
    assert _strip_page_top_running_year(text) == text


def test_repeated_page_top_year_is_stripped_but_the_page_break_stays():
    text = "Title\n\n" + _pages(["Cover", "2020", "Kim", "2020", "Kim", "2020"])
    out = _strip_page_top_running_year(text)
    assert not _PAGE_TOP_YEAR.search(out)
    assert out.count("\f") == text.count("\f")
    assert out.count("Body text of the page") == 6
    assert out.count("Kim") == 2
