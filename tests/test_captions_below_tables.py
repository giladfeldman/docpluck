"""A document that prints its table captions UNDER the tables.

Until 2026-11-16 every caption searched for its grid below first. In
10.48550/arxiv.2406.11713 the caption sits under its table, so "Table 4" on p8
took the grid of Table 5 (printed directly under Table 4's caption) and p7
Table 3 was cut to its bottom nine rows, losing the paper's own model row.

``detect.document_prints_captions_below`` decides once per document, from two
typographic signals (a closing rule directly above every caption, and numeric
rows above and not below at least half of them). The region search then runs
upward only, as far as the previous caption in the same column.

Scientific Reports also prints captions under its tables
(10.1038/s41598-023-50588-1, pages 5-6 read 2026-11-16), but draws each table
as a ruled grid. There the above-caption region tied the ruled (lattice) grid on
columns and won on cell count only because its wrapped row labels were split
off their numbers (Table 2: 43 rows against 25), so a ruled grid keeps the
caption unless the region finds more columns.

Pages 7, 8 and 13 of the arXiv paper were rasterized and read 2026-11-16; the
asserted values are the printed ones. Synthetic words below are invented.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from docpluck.tables.detect import _previous_caption_bottom


def _word(text, x0, top, size=8.0):
    return {"text": text, "x0": x0, "x1": x0 + size * 0.5 * len(text), "top": top,
            "bottom": top + size, "upright": True}


def _layout(words):
    page = SimpleNamespace(words=words, chars=[], lines=[], rects=[], curves=[],
                           width=612.0, height=792.0)
    return SimpleNamespace(pages=[page])


_CAP = SimpleNamespace(page=1)
_CAPTION_BBOX = (50.0, 400.0, 200.0, 408.0)


def test_the_previous_caption_bounds_the_search():
    layout = _layout([_word("Table", 50.0, 100.0), _word("4:", 75.0, 100.0)])
    assert _previous_caption_bottom(layout, _CAP, _CAPTION_BBOX) == pytest.approx(108.0)


def test_a_table_named_mid_sentence_is_not_a_caption():
    layout = _layout([_word("see", 30.0, 200.0), _word("Table", 44.0, 200.0), _word("1,", 69.0, 200.0)])
    assert _previous_caption_bottom(layout, _CAP, _CAPTION_BBOX) is None


def test_a_centred_caption_above_counts_as_the_same_column():
    layout = _layout([_word("Table", 0.0, 150.0), _word("9:", 25.0, 150.0)])
    assert _previous_caption_bottom(layout, _CAP, _CAPTION_BBOX) == pytest.approx(158.0)


def test_a_caption_in_the_other_column_does_not_bound_it():
    layout = _layout([_word("Table", 320.0, 150.0), _word("9:", 345.0, 150.0)])
    assert _previous_caption_bottom(layout, _CAP, _CAPTION_BBOX) is None


def _rows(table):
    rows: dict[int, dict[int, str]] = {}
    for c in table.get("cells") or []:
        rows.setdefault(c["r"], {})[c["c"]] = (c.get("text") or "").strip()
    return [[x for x in (rows[r].get(i, "") for i in range(max(rows[r]) + 1)) if x]
            for r in sorted(rows)]


@pytest.fixture(scope="module")
def arxiv_result():
    from docpluck.extract_structured import extract_pdf_structured
    from docpluck.testing import require_corpus_pdf

    return extract_pdf_structured(require_corpus_pdf("ieee/ieee_access_4.pdf").read_bytes())


def _ours_row(result, label):
    table = next(t for t in result["tables"] if t.get("label") == label)
    return next(row for row in _rows(table) if row and row[0].startswith("Ours"))


def test_the_document_is_marked_captions_below(arxiv_result):
    assert "captions_below_tables" in arxiv_result["method"]


def test_table_3_keeps_the_papers_own_model_row(arxiv_result):
    assert _ours_row(arxiv_result, "Table 3")[1:3] == ["2.98", "0.58"]


@pytest.mark.parametrize("label, values", [
    ("Table 4", ["5.21", "0.40", "0.55 (*)"]),
    ("Table 5", ["4.67", "0.42", "1.02 (*)"]),
])
def test_each_caption_gets_the_table_printed_above_it(arxiv_result, label, values):
    assert _ours_row(arxiv_result, label)[1:4] == values


def test_a_ruled_grid_keeps_its_caption_and_its_wrapped_labels():
    from docpluck.extract_structured import extract_pdf_structured
    from docpluck.testing import require_corpus_pdf

    res = extract_pdf_structured(require_corpus_pdf("nature/sci_rep_2.pdf").read_bytes())
    assert "captions_below_tables" in res["method"]
    t2 = next(t for t in res["tables"] if t.get("label") == "Table 2")
    assert t2.get("camelot_flavor") == "lattice"
    rows = _rows(t2)
    assert ["Alcohol drinking history", "1.568 (1.388–1.773)", "< 0.001",
            "1.364 (1.197–1.554)", "< 0.001", "0.114"] in rows
    assert not any(row and row[0][:1].isdigit() for row in rows)
