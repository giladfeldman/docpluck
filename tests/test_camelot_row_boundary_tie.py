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

from docpluck.tables.camelot_row_ties import TIE_EVENT, boundary_tie_scope, tied_row
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
    assert changed == [(0, 3, "", "Imatinib+placebo")]
    assert fb.counters.get(TIE_EVENT) == 1
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
