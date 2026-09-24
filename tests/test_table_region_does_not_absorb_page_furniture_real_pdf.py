"""Real papers whose tables v2.4.143 emptied, garbled or padded: each region must
stop at its own table.

2c8b0dd (v2.4.143) widened caption-anchored table regions so that wide tables
stopped losing columns -- a real gain, kept. But a wider region also reaches
further into whatever else is printed on the page, and four detectors fed it
things that are not the table. Each was measured on the printed page
(rasterized, ``pdftoppm -png -r 80``) and each shape is keyed below on what the
FILE states, never on the paper:

* ``10.1136/bmjopen-2022-066361`` p6, Table 4 -- the copyright strip rotated
  down the right margin (``upright: False``) widened the region and was then
  taken as the table's note; the region ran to the page bottom and Table 4
  shipped with 0 rows (v2.4.142 had 3 of its 6 columns).
* ``10.1001/jamanetworkopen.2023.48333`` p6, Table 2 -- a ruled table was
  widened by rows that are the side-note column at the same height, and the
  page-footer rule was admitted as a table rule; the Model 1 and Model 2
  hazard-ratio rows came out interleaved glyph by glyph.
* ``10.48550/arxiv.2410.21901`` p6-7, Tables 5 and 6 -- the "note" search took
  the page footer (440pt below) and a figure caption (220pt below); both tables
  shipped EMPTY.
* ``10.1038/s41598-023-50401-z`` p4, Table 1 -- the lattice augmentation
  appended the table's caption (printed below it) and three rows of body prose,
  including the unrelated body p-value ``P = 0.16``.
* ``10.5465/amj.2016.1196`` p19 -- the caption locator took the body sentence
  "presented in Table 4. To test ..." for the "TABLE 4" heading.

Values are asserted on the STRUCTURED table through ``extract_pdf_structured``,
the shipped path: most of these numbers also occur in the body text, so a
whole-document substring check would pass while the table is still wrong.
"""

from __future__ import annotations

import functools

import pytest

from docpluck.testing.corpus import require_corpus_pdf


@functools.lru_cache(maxsize=None)
def _tables(rel: str) -> dict:
    pytest.importorskip("camelot")
    from docpluck.extract_structured import extract_pdf_structured

    tables = extract_pdf_structured(require_corpus_pdf(rel).read_bytes())["tables"]
    return {t.get("label"): t for t in tables}


def _rows(table) -> list[list[str]]:
    by_r: dict[int, list[tuple[int, str]]] = {}
    for c in table.get("cells") or []:
        by_r.setdefault(c["r"], []).append((c["c"], (c.get("text") or "").strip()))
    return [[t for _, t in sorted(v)] for _, v in sorted(by_r.items())]


def _row_starting(table, label: str) -> list[str]:
    for row in _rows(table):
        if row and row[0] == label:
            return row
    raise AssertionError(f"no row starting {label!r}; rows={_rows(table)}")


def test_bmj_open_table4_keeps_all_six_columns():
    t4 = _tables("vancouver/bmj_open_1.pdf").get("Table 4")
    assert t4 is not None and t4.get("cells"), (
        "Table 4 is empty -- the rotated margin strip took the region to the page "
        "bottom (v2.4.143/144)."
    )
    assert t4["n_cols"] == 6, t4["n_cols"]
    # Printed: Anaemia | 7 (22.6) | 1 (3.2) | 8 (25.8) | 2 (6.5) | 0.86
    assert _row_starting(t4, "Anaemia") == [
        "Anaemia", "7 (22.6)", "1 (3.2)", "8 (25.8)", "2 (6.5)", "0.86"
    ]


def test_jama_open_table2_hazard_ratios_are_not_interleaved():
    t2 = _tables("ama/jama_open_2.pdf").get("Table 2")
    assert t2 is not None and t2.get("cells"), "Table 2 not captured"
    # Printed: Model 1b | 1.34 (1.22-1.47) | 0.92 (0.61-1.39) | 1.33 (1.21-1.47) | 1.40 (1.18-1.66)
    assert _row_starting(t2, "Model 1b")[1:] == [
        "1.34 (1.22-1.47)", "0.92 (0.61-1.39)", "1.33 (1.21-1.47)", "1.40 (1.18-1.66)"
    ]
    assert _row_starting(t2, "Model 2c")[1:] == [
        "1.31 (1.20-1.44)", "0.90 (0.59-1.39)", "1.31 (1.19-1.44)", "1.38 (1.17-1.63)"
    ]
    text = " ".join(" ".join(r) for r in _rows(t2))
    assert "Abbreviation" not in text, "the side-note column was pulled into Table 2"


def test_ieee_access_tables5_and_6_are_not_emptied_by_a_distant_note():
    tabs = _tables("ieee/ieee_access_8.pdf")
    t5, t6 = tabs.get("Table 5"), tabs.get("Table 6")
    assert t5 is not None and t5.get("cells"), "Table 5 empty -- footer taken as its note"
    assert t6 is not None and t6.get("cells"), "Table 6 empty -- figure caption taken as its note"
    t5_text = " ".join(" ".join(r) for r in _rows(t5))
    # Printed Table 5 first data row: 9 | 95.95 | 89.79 | 71.83
    for value in ("95.95", "89.79", "71.83"):
        assert value in t5_text, (value, _rows(t5))
    t6_text = " ".join(" ".join(r) for r in _rows(t6))
    for value in ("94.83", "89.92", "71.92"):
        assert value in t6_text, (value, _rows(t6))


def test_sci_rep_table1_carries_no_caption_or_body_prose():
    t1 = _tables("nature/sci_rep_3.pdf").get("Table 1")
    assert t1 is not None and t1.get("cells"), "Table 1 not captured"
    rows = _rows(t1)
    text = " ".join(" ".join(r) for r in rows)
    assert "no significant difference" not in text, "body prose appended to Table 1"
    assert "Discussion" not in text, "a section heading appended to Table 1"
    # The printed table ends at the diagnosis-year row.
    assert rows[-1][0] == "2012–2020", rows[-1]


def test_amj_caption_is_located_on_the_heading_not_the_cross_reference():
    from docpluck.extract import extract_pdf
    from docpluck.extract_layout import extract_pdf_layout
    from docpluck.extract_structured import _join_split_captions, _page_offsets
    from docpluck.tables.captions import find_caption_matches
    from docpluck.tables.detect import _bbox_of_caption_line

    pdf = require_corpus_pdf("aom/amj_1.pdf").read_bytes()
    raw, _ = extract_pdf(pdf)
    rej = _join_split_captions(raw)
    cap = next(c for c in find_caption_matches(rej, _page_offsets(rej))
               if c.kind == "table" and c.label == "Table 4")
    page = extract_pdf_layout(pdf).pages[cap.page - 1]
    x0, top, x1, _ = _bbox_of_caption_line(page, cap)
    # The centred "TABLE 4" heading sits at top ~559pt, x ~279-316. The body
    # sentence "presented in Table 4. To test our first hypothesis" is at
    # top ~500pt, starting at the left margin (x ~46).
    assert top > 550, (top, x0, x1)
    assert x0 > 250, (top, x0, x1)
