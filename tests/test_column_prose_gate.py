"""The two-column reorder reads a page the way it is laid out, or not at all.

The general column correction reads an interleaved page left column first,
then right column. A clean vertical gutter is not proof that the page is one
pair of prose columns. Measured over the 125-paper corpus manifest (each page's
reading order scored against an independent OCR of the page, then every
changed page read against its raster), the whole-page reorder broke three
shapes of page:

* a table whose empty middle column lines up with the gutter (a full-page
  table, a landscape table, a three-column supplementary table): all of its
  left cells came out before all of its right cells, so no row survived;
* a full-width table or block stacked above or below the two columns (a
  descriptive-statistics table under the Results, an author note set in two
  small columns under the body): its left half was run into the left column
  and its right half into the right column;
* two two-column blocks stacked one above the other (references above a
  boxed block of back matter, a two-column figure caption above the body).

``_column_region_plan`` cuts the page body at full-width blank bands and says
how to read it: ``[]`` for one flow of two prose columns, a list of regions
read top to bottom (columns left then right, a table above or below them full
width), or ``None`` when there is no safe reading and the page keeps
pdftotext's order. Bands with text on one side only, or too little to classify,
join the column flow. The synthetic tests pin each shape; the real-PDF tests
pin the corpus pages, with pages the reorder must still correct as controls.
"""
from __future__ import annotations

import pytest

from docpluck.extract import extract_pdf
from docpluck.extract_columns import _column_region_plan
from docpluck.testing import require_corpus_pdf

_W = 600.0
_GUTTER = 300.0
_LH = 10.0


def _word(text: str, x0: float, top: float, width: float | None = None,
          height: float = _LH) -> dict:
    w = width if width is not None else 6.0 * len(text)
    return {"text": text, "x0": x0, "x1": x0 + w, "top": top,
            "bottom": top + height, "upright": True}


def _prose_line(x0: float, x1: float, top: float, height: float = _LH) -> list[dict]:
    """A justified prose line: words separated by ordinary 3pt spaces."""
    out, x = [], x0
    while x + 40 <= x1:
        out.append(_word("words", x, top, width=37.0, height=height))
        x += 40.0
    return out


def _prose_page(rows: int = 40, start: float = 60.0, height: float = _LH,
                step: float = 12.0) -> list[dict]:
    words = []
    for i in range(rows):
        top = start + i * step
        words += _prose_line(50, _GUTTER - 8, top, height)
        words += _prose_line(_GUTTER + 8, _W - 50, top, height)
    return words


def _table_rows(rows: int, start: float) -> list[dict]:
    """Full-width table rows: cells on both sides of the gutter, wide gaps."""
    words = []
    for i in range(rows):
        top = start + i * 12.0
        words.append(_word("Measure", 50, top))
        for x in (150, 210, 330, 410, 490):
            words.append(_word("0.42", x, top, width=24.0))
    return words


def test_two_column_prose_page_is_one_pair_of_columns():
    assert _column_region_plan(_prose_page(), _GUTTER) == []


def test_heading_gap_in_one_column_does_not_split_the_page():
    """A gap in ONE column is ordinary prose, not a full-width band."""
    words = [w for w in _prose_page()
             if not (w["x0"] < _GUTTER and 200 <= w["top"] < 240)]
    assert _column_region_plan(words, _GUTTER) == []


def test_full_page_table_has_no_column_reading():
    """Row labels on the left, numeric cells on the right."""
    words = []
    for i in range(40):
        top = 60 + i * 12.0
        words.append(_word("Label", 50, top))
        words.append(_word("text", 90, top))
        for k, x in enumerate((320, 380, 440, 500)):
            words.append(_word(f"{i}.{k}", x, top, width=24.0))
    assert _column_region_plan(words, _GUTTER) is None


def test_three_column_table_split_inside_one_side_has_no_column_reading():
    """Domain | Preregistered | Changes: the left side holds two table columns
    (a blank strip no row crosses), the right side a wrapped text cell."""
    words = []
    for i in range(30):
        top = 60 + i * 12.0
        if i % 6 == 0:
            words.append(_word("Domain", 50, top, width=40.0))
        words += _prose_line(110, _GUTTER - 8, top)
        words += _prose_line(_GUTTER + 8, _W - 50, top)
    assert _column_region_plan(words, _GUTTER) is None


def test_table_inside_one_column_beside_prose_is_a_pair_of_columns():
    """A numbered list table set in the left column, prose in the right: the
    table is part of the left column, so the page is still read left column
    then right column (a table on one side is not a table across the page)."""
    words = []
    for i in range(30):  # the table runs at its own 10.5pt pitch
        top = 60 + i * 10.5
        words.append(_word(str(i + 1), 50, top, width=10.0, height=8.0))
        words.append(_word("Journal", 80, top, width=40.0, height=8.0))
        words.append(_word("title", 124, top, width=30.0, height=8.0))
    for i in range(30):
        words += _prose_line(_GUTTER + 8, _W - 50, 60 + i * 12.0)
    assert _column_region_plan(words, _GUTTER) == []


def test_table_then_its_notes_beside_one_prose_column_is_one_flow():
    """Left column: a table, a blank band, then the table's notes in smaller
    type; right column: prose straight down, with a heading gap that lines up
    with the band. The right column keeps its type size, so the two bands are
    one column flow: read the whole left column, then the whole right."""
    words = []
    for i in range(20):
        top = 60 + i * 10.5
        words.append(_word(str(i + 1), 50, top, width=10.0, height=8.0))
        words.append(_word("Journal", 80, top, width=40.0, height=8.0))
        words.append(_word("title", 124, top, width=30.0, height=8.0))
    for i in range(10):
        words += _prose_line(50, _GUTTER - 8, 300 + i * 9.0, height=7.0)
    for i in range(18):
        words += _prose_line(_GUTTER + 8, _W - 50, 60 + i * 12.0)
    for i in range(10):
        words += _prose_line(_GUTTER + 8, _W - 50, 300 + i * 12.0)
    assert _column_region_plan(words, _GUTTER) == []


def test_one_text_column_under_a_running_head_has_no_column_reading():
    """A rotated table fills the left half (its words are not upright, so
    they are not body text) and prose fills the right. The only row with
    text on both sides is the running head: that is not a pair of columns,
    so there is nothing to reorder."""
    words = [_word("Article", 50, 30), _word("https://doi.org/x", 400, 30)]
    for i in range(40):
        words += _prose_line(_GUTTER + 8, _W - 50, 60 + i * 12.0)
        words.append(dict(_word("0.42", 100, 60 + i * 12.0), upright=False))
    assert _column_region_plan(words, _GUTTER) is None


def test_running_head_above_the_columns_stays_on_top():
    """A one-line running head on the right, above a blank band: read where
    it stands, before the columns — not as the first line of the right
    column, between the end of the left column and the rest of the text."""
    words = [_word("JOURNAL", 400, 30), _word("1237", 520, 30)] + _prose_page()
    plan = _column_region_plan(words, _GUTTER)
    assert [k for k, _, _ in plan] == ["full", "cols"]


def test_full_width_table_above_prose_is_read_in_place():
    """The table is read full width, then the prose below left then right."""
    words = _table_rows(10, 60.0) + _prose_page(rows=26, start=200.0)
    plan = _column_region_plan(words, _GUTTER)
    assert [k for k, _, _ in plan] == ["full", "cols"]


def test_column_pairs_in_two_type_sizes_have_no_safe_reading():
    """Body in two columns, then a block in smaller type in two columns. It
    may be an author note under the body (read body left, body right, then
    the note) or the column flow moving on to back matter (read the whole
    left column first). The page does not say which, so it keeps its order."""
    words = (_prose_page(rows=30, start=60.0)
             + _prose_page(rows=6, start=440.0, height=7.0, step=9.0))
    assert _column_region_plan(words, _GUTTER) is None


def test_headings_level_by_chance_do_not_split_the_column_flow():
    """Each column has a heading and a short line in the same band, with the
    blank band above and below running across the page: two columns'
    contents sharing a band, not a table across it. The page is still one
    pair of columns."""
    words = _prose_page(rows=12, start=60.0)
    words += [_word("Funding", 50, 220), _word("ORCID", _GUTTER + 8, 220),
              _word("Grant", 50, 232),
              _word("Name", _GUTTER + 8, 232), _word("http://orcid.org/x", 420, 232)]
    words += _prose_page(rows=12, start=260.0)
    assert _column_region_plan(words, _GUTTER) == []


def test_same_size_stacked_column_pairs_have_no_safe_reading():
    """Two pairs of prose columns in one type size with a wide blank band
    between them: independent regions, or one flow skipping a figure. The
    page says neither, so it keeps its order."""
    words = _prose_page(rows=15, start=60.0) + _prose_page(rows=15, start=400.0)
    assert _column_region_plan(words, _GUTTER) is None


# ── Real corpus pages ──────────────────────────────────────────────────────

_FLAG = "DOCPLUCK_COLUMN_CORRECT_GENERAL"


def _corrected_pages(method: str) -> set[int]:
    if "+column_corrected:" not in method:
        return set()
    tag = method.split("+column_corrected:")[1].split("+")[0]
    return {int(x) for x in tag.split(",") if x.strip().isdigit()}


# (manifest name, page, shape). Each page was read against its raster: the
# left-then-right reorder breaks it.
_REFUSED = [
    ("vancouver/bmc_pub_health_1.pdf", 4, "full-page table"),
    ("apa/ziano_2021_joep.pdf", 4, "full-page table"),
    ("harvard/bjps_1.pdf", 9, "landscape table, its summary column wrapping"),
    ("vancouver/cmaj_1.pdf", 12,
     "references in two columns above back matter in two columns, other type size"),
    ("nature/nat_comms_4.pdf", 6, "rotated table beside one text column"),
    ("nature/nat_comms_3.pdf", 4,
     "figure caption in two columns, a little smaller, above two columns of text"),
    ("escicheck/xiao_2024_poc.pdf", 2,
     "author note in two small columns under two columns of body"),
    ("escicheck/anvari_2021_jesp.pdf", 23,
     "three-column table: domain, preregistered plan, wrapped changes cell"),
]


@pytest.mark.parametrize("name,page,shape", _REFUSED)
def test_non_prose_page_keeps_its_reading_order(name, page, shape, monkeypatch):
    """The general path leaves the page exactly as it is with the path off
    (a page the reference-inversion path corrects stays corrected that way)."""
    data = require_corpus_pdf(name).read_bytes()
    monkeypatch.setenv(_FLAG, "0")
    off = extract_pdf(data)[0].split("")[page - 1]
    monkeypatch.setenv(_FLAG, "1")
    on = extract_pdf(data)[0].split("")[page - 1]
    assert on == off, f"{name} p{page} ({shape}) was reordered by the general path"


def test_prose_page_with_a_column_table_is_still_corrected(monkeypatch):
    """Control: ip_feldman p15 carries Table 10 inside its left column and must
    still be reordered so that the Discussion (right column) follows it."""
    monkeypatch.setenv(_FLAG, "1")
    text, method = extract_pdf(
        require_corpus_pdf("apa/ip_feldman_2025_pspb.pdf").read_bytes())
    assert 15 in _corrected_pages(method), method
    page = text.split("\f")[14]
    assert page.index("Table 10") < page.index("Discussion")


def test_general_column_correction_is_on_by_default(monkeypatch):
    """With no environment set, ip_feldman p15 is read left column (Table 10)
    and the rest of the Results, then right column (Discussion);
    ``DOCPLUCK_COLUMN_CORRECT_GENERAL=0`` opts out and leaves the page as
    pdftotext emits it, the Discussion heading before the Results subsection
    "SCO (Exploratory Extension)"."""
    data = require_corpus_pdf("apa/ip_feldman_2025_pspb.pdf").read_bytes()
    monkeypatch.delenv(_FLAG, raising=False)
    text, method = extract_pdf(data)
    assert 15 in _corrected_pages(method), method
    page = text.split("\f")[14]
    assert page.index("Table 10") < page.index("Discussion")
    assert page.index("SCO (Exploratory Extension)") < page.index("Discussion")

    monkeypatch.setenv(_FLAG, "0")
    text_off, method_off = extract_pdf(data)
    assert 15 not in _corrected_pages(method_off), method_off
    page_off = text_off.split("\f")[14]
    assert page_off.index("Discussion") < page_off.index("SCO (Exploratory Extension)")


def _page(name: str, page: int, monkeypatch) -> tuple[str, set[int]]:
    monkeypatch.setenv(_FLAG, "1")
    text, method = extract_pdf(require_corpus_pdf(name).read_bytes())
    return text.split("")[page - 1], _corrected_pages(method)


def _in_order(page: str, *landmarks: str) -> bool:
    at = [page.find(m) for m in landmarks]
    return all(i >= 0 for i in at) and at == sorted(at)


def test_full_width_table_above_two_columns_is_read_in_place(monkeypatch):
    """nat_comms_4 p3: Table 1 spans the page above two columns of Results.
    The table comes first, whole and row by row (the Teduglutide age cell
    before the next row); then the left column, then the right."""
    page, fixed = _page("nature/nat_comms_4.pdf", 3, monkeypatch)
    assert 3 in fixed
    assert _in_order(page, "Age (months)", "18 (12,20)", "Sex, female",
                     "Tuberculosis", "All continuous variables shown",
                     "enrolment (n = 1)", "Primary endpoint",
                     "Secondary endpoints", "Assessment of endoscopic biopsies",
                     "Adverse events")


def test_back_matter_under_a_column_table_is_one_column_flow(monkeypatch):
    """chan_feldman p21: the left column runs Discussion end, Disclosure,
    Funding, ..., Contributor roles table; the right column runs that table's
    continuation, ORCID, References. Funding and ORCID sit level in one band
    by chance; the page is still read left column, then right column."""
    page, fixed = _page("apa/chan_feldman_2025_cogemo.pdf", 21, monkeypatch)
    assert 21 in fixed
    assert _in_order(page, "No potential conflict", "The project is supported",
                     "Contributor roles taxonomy", "Continued.", "ORCID",
                     "References", "Agu, S. A.")


def test_table_and_notes_in_one_column_stay_one_column(monkeypatch):
    """annals_2 p10: the left column is Table 2 and its notes (smaller
    type), the right column is prose with a heading gap level with the band
    between table and notes. The page is one pair of columns: the notes
    follow the table, and the right column starts after them."""
    page, _ = _page("aom/annals_2.pdf", 10, monkeypatch)
    assert _in_order(page, "Strategic Management Journal", "Notes: The following",
                     "Equation Modeling.", "EVIDENCE-BASED",
                     "Enhancing Transparency Regarding Theory")


def test_watermark_margin_is_cut_off_when_a_figure_has_a_rotated_axis_title(monkeypatch):
    """psychooncology_1 p8: a rotated download watermark runs down the right
    margin, and the bar chart in the left column has a rotated axis title.
    The axis title is column content; the watermark is the margin and is read
    on its own, so Table 4's caption opens the right column, before the
    table, instead of landing after the watermark at the end of the page."""
    page, fixed = _page("vancouver/psychooncology_1.pdf", 8, monkeypatch)
    assert 8 in fixed
    assert _in_order(page, "post-treatment.", "Table 4. Results of three-way",
                     "Treatment", "Encouragingly, when comparing", "Downloaded from")

