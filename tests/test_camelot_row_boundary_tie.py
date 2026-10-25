"""Camelot 2.0 stream must not discard a textline that sits exactly on a row boundary.

Specimen 10.1136/bmjopen-2022-066361 page 5 (Table 2): the column header
``Imatinib+placebo`` shares its top edge with ``Imatinib+vitamin D3``, whose
subscript ``3`` drops its bottom by 2.18 pt -- past Camelot's ``row_tol`` of 2 --
so the two lines become separate row groups and ``_join_rows`` puts their shared
boundary exactly on the placebo line's centre. ``get_table_index`` tests
``y_bot < y_mid < y_top`` strictly and the line reaches no cell. Mechanism and
the 0.11.0 comparison: ``docpluck/tables/camelot_row_ties.py``.

Two-sided: WITHOUT the scope Camelot still drops the line (so this file notices
if a Camelot release fixes it upstream and the wrapper becomes dead code), and
WITH it the line lands in its own row and only that one cell changes. Plus the
production path: ``extract_pdf_structured`` delivers the header and COUNTS the
assignment.
"""

import pytest

from docpluck.tables import camelot_row_ties
from docpluck.tables.camelot_row_ties import (
    DROP_EVENT,
    MERGE_EVENT,
    MERGE_FAILED_EVENT,
    TIE_EVENT,
    boundary_tie_scope,
    tied_row,
)
from docpluck.telemetry import fallback_scope
from docpluck.testing import require_corpus_pdf

camelot = pytest.importorskip("camelot", reason="camelot not installed (pip install docpluck[all])")

_PAPER = "vancouver/bmj_open_1.pdf"  # 10.1136/bmjopen-2022-066361
_AREA = ["40.42,209.02,554.85,37.35"]  # Table 2, page 5, PDF coordinates


def _grid(path):
    return camelot.read_pdf(str(path), pages="5", flavor="stream",
                            table_areas=_AREA, strip_text="\n")[0].df


def test_tied_row_is_exact_and_half_open():
    rows = [(204.3, 199.8), (199.8, 193.4)]
    assert tied_row(rows, 199.8) == 0          # on row 0's lower edge -> row 0
    assert tied_row(rows, 199.80000001) is None  # not a tie: Camelot decides
    assert tied_row(rows, 204.3) is None       # a top edge is never a tie
    assert tied_row([(5.0, 5.0)], 5.0) is None  # degenerate row has no room


def test_camelot_alone_still_drops_the_header():
    """Negative arm. If this starts FAILING, Camelot fixed the bug upstream:
    re-measure and consider retiring ``camelot_row_ties``."""
    df = _grid(require_corpus_pdf(_PAPER))
    assert not any("Imatinib+placebo" in str(v) for v in df.values.ravel())


def test_scope_restores_the_header_and_changes_nothing_else():
    path = require_corpus_pdf(_PAPER)
    before = _grid(path)
    with fallback_scope() as fb, boundary_tie_scope():
        after = _grid(path)
    assert before.shape == after.shape
    changed = [(i, j, before.iat[i, j], after.iat[i, j])
               for i in range(before.shape[0]) for j in range(before.shape[1])
               if before.iat[i, j] != after.iat[i, j]]
    # Rescued into its own row 0, then JOINED into row 1, the row holding
    # "Imatinib+vitamin D3" -- the header printed beside it on the same line.
    assert changed == [(1, 3, "", "Imatinib+placebo")]
    assert after.iat[1, 2] == "Imatinib+vitamin D3"
    assert fb.counters.get(TIE_EVENT) == 1
    assert fb.counters.get(MERGE_EVENT) == 1
    # And the scope is INERT outside itself: other Camelot callers are untouched.
    assert _grid(path).equals(before)


def test_production_path_delivers_the_header_and_counts_it():
    from docpluck.extract_structured import extract_pdf_structured

    result = extract_pdf_structured(require_corpus_pdf(_PAPER).read_bytes())
    p5_text = " ".join(
        c.get("text", "") for t in result["tables"] if t.get("page") == 5
        for c in t.get("cells", [])
    )
    assert "Imatinib+placebo" in p5_text
    assert result["fallbacks"].get(TIE_EVENT, 0) >= 1


# --- the row join, on a real table, both directions ---------------------------
#
# 10.1177/23780231251314667 (asa/socius_4). Page 35, Table 1: every unstarred value
# and every row label shared its printed line with a starred value and was dropped;
# rescued, it sat on a row of its own above the starred values. Page 38: Camelot
# built 6 grid columns for 10 printed ones, so a rescued row and its starred row
# COLLIDE in a column and must stay split.

_SOCIUS4 = "asa/socius_4.pdf"


def _page_grid(rel, page):
    with fallback_scope() as fb, boundary_tie_scope():
        tables = camelot.read_pdf(str(require_corpus_pdf(rel)), pages=str(page),
                                  flavor="stream", strip_text="\n")
    # The join edits Camelot's cells AND its already-built df; they must agree.
    assert tables[0].data == tables[0].df.values.tolist()
    return tables[0].df.values.tolist(), fb


def test_join_rebuilds_the_printed_row():
    rows, fb = _page_grid(_SOCIUS4, 35)
    # Read off the page raster (100 dpi): "Total housework 18.5 17.8* 17.8*
    # 17.8* 17.9+ 17.2** 18.8 18.1 17.7+".
    assert ["Total housework", "18.5", "17.8*", "17.8*", "17.8*", "17.9+",
            "17.2**", "18.8", "18.1", "17.7+"] in rows
    assert fb.counters.get(MERGE_EVENT, 0) >= 1


def test_join_refuses_a_column_collision():
    rows, _ = _page_grid(_SOCIUS4, 38)
    # Three printed year columns share grid column 2, so the rescued unstarred
    # values and the starred ones would both need that cell: left split.
    assert ["Garden and animal care", "2.1", "2.02.01.9", "2.2", "2.12.2", "2.0"] in rows
    assert ["", "", "", "", "1.7+", ""] in rows


def test_an_unrescued_drop_is_counted(monkeypatch):
    """With the tie test disabled, the same specimen line is dropped -- and the
    drop must reach `fallbacks`, not vanish."""
    monkeypatch.setattr(camelot_row_ties, "tied_row", lambda rows, y_mid: None)
    with fallback_scope() as fb, boundary_tie_scope():
        df = _grid(require_corpus_pdf(_PAPER))
    assert not any("Imatinib+placebo" in str(v) for v in df.values.ravel())
    assert "p5:Imatinib+placebo" in fb.details.get(DROP_EVENT, {})
    # Two-sided: the unmodified module rescues it and records no drop.
    monkeypatch.undo()
    with fallback_scope() as fb2, boundary_tie_scope():
        _grid(require_corpus_pdf(_PAPER))
    assert DROP_EVENT not in fb2.counters


def test_a_failed_join_is_recorded_and_leaves_the_grid():
    class _Broken:
        page = 7

        @property
        def cells(self):
            raise RuntimeError("boom")

    with fallback_scope() as fb:
        camelot_row_ties._join_tie_split_rows([(_Broken(), 0, {0}, 7, "x")])
    assert fb.counters.get(MERGE_FAILED_EVENT) == 1
    assert MERGE_EVENT not in fb.counters


def test_join_never_moves_a_cell_camelot_placed_itself():
    """Consult round 2 (Sonnet, 2026-09-26): the row-level rule would move EVERY
    filled cell of a tied row. On the corpus that moved 0 cells not placed by a
    tie in 852 moves; the rule is now per cell so it cannot. A stub grid, because
    no real paper produces the case -- this pins the rule, not a prevalence."""

    class _Cell:
        def __init__(self, text):
            self._text = text

        @property
        def text(self):
            return self._text

    class _Table:
        rows = ((30.0, 20.0), (20.0, 10.0))

        def __init__(self, upper, lower):
            self.cells = [[_Cell(t) for t in upper], [_Cell(t) for t in lower]]
            self.df = None

    both_tied = _Table(["Label", "1.0", ""], ["", "", "2.0*"])
    assert camelot_row_ties.join_tie_split_rows(both_tied, {0: {0, 1}}) == [0]
    assert [c.text for c in both_tied.cells[1]] == ["Label", "1.0", "2.0*"]

    one_untied = _Table(["Label", "1.0", ""], ["", "", "2.0*"])
    assert camelot_row_ties.join_tie_split_rows(one_untied, {0: {1}}) == []
    assert [c.text for c in one_untied.cells[0]] == ["Label", "1.0", ""]
