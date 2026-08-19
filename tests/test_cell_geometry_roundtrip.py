"""Per-cell geometry is real, is verified, and REFUSES rather than guessing.

Register A1 / G6a. Camelot held real per-cell coordinates all along and
``camelot_extract`` discarded them for a ``(0.0, 0.0, 0.0, 0.0)`` literal. Wiring
them up is a two-line change; the reason G4 deferred it for two releases is that
every known trap produces **wrong** geometry rather than empty, and a wrong bbox
is worse than none because it answers plausibly.

So the tests that matter here are not "does it emit numbers". They are:

  * a KNOWN POSITIVE -- geometry really is emitted on a real paper, so a future
    all-refused run cannot read as "this corpus is clean" (the instrument-zero
    this project has been burned by three times);
  * the guard REFUSES when the code it guards is broken -- verified by breaking
    it, per the standing rule that a regression test which has never failed
    against the real defect is decoration;
  * the shipped cells round-trip END TO END, which is the only thing that can
    catch trap T3 (row indices drift because docpluck trims rows before emitting
    cells, so an emitted ``r`` is not Camelot's df row).

The T5 traps (Camelot rotating a sideways-text page, and page-size disagreement)
are asserted on synthetic doubles because the corpus positives --
``10.1001/jamanetworkopen.2023.39337`` p8 and ``10.1017/s0007123424000024`` p6 --
live in the private article repository and this repo may never hold a paper.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from docpluck.extract_layout import extract_pdf_layout
from docpluck.tables import cell_geometry
from docpluck.tables.bbox_utils import chars_in_bbox
from docpluck.tables.cell_geometry import ZERO_BBOX, camelot_cell_bboxes

_CORPUS = Path(__file__).resolve().parents[2] / "PDFextractor" / "test-pdfs" / "apa"
_PDF = _CORPUS / "efendic_2022_affect.pdf"

pytestmark = pytest.mark.skipif(not _PDF.is_file(), reason=f"fixture not available: {_PDF}")


# --------------------------------------------------------------------------
# synthetic doubles for the refusal paths whose corpus positives are private
# --------------------------------------------------------------------------

class _FakeCell:
    def __init__(self, x1, y1, x2, y2):
        self.x1, self.y1, self.x2, self.y2 = x1, y1, x2, y2


class _FakeDF:
    def __init__(self, grid):
        self._grid = grid
        self.columns = list(range(len(grid[0]))) if grid else []

    def __len__(self):
        return len(self._grid)

    @property
    def iloc(self):
        grid = self._grid

        class _ILoc:
            def __getitem__(self, rc):
                r, c = rc
                return grid[r][c]

        return _ILoc()


class _FakeTable:
    def __init__(self, grid, *, page=1, rotation="", pdf_size=None):
        self.df = _FakeDF(grid)
        self.page = page
        self.rotation = rotation
        # DEFAULT TO THE REAL PAGE'S SIZE, never a hardcoded Letter. An earlier
        # draft hardcoded (612, 792); this fixture's page is 603x783, so every
        # synthetic case refused with `page_size_disagreement` before reaching
        # the condition it was written to exercise — the assertions passed for
        # the wrong reason until one of them asserted on the reason string.
        self.pdf_size = pdf_size if pdf_size is not None else _page_size()
        self.cells = [
            [_FakeCell(10.0 + 50 * c, 700.0 - 20 * r, 55.0 + 50 * c, 715.0 - 20 * r)
             for c in range(len(grid[0]))]
            for r in range(len(grid))
        ]


def _layout():
    return extract_pdf_layout(_PDF.read_bytes())


def _page_size(page: int = 1) -> tuple[float, float]:
    pg = _layout().pages[page - 1]
    return (float(pg.width), float(pg.height))


def _first_camelot_table():
    import camelot

    tables = list(camelot.read_pdf(str(_PDF), pages="all", flavor="stream", suppress_stdout=True))
    assert tables, "no camelot tables — the assertions below would be vacuous"
    return tables


# --------------------------------------------------------------------------
# 1. KNOWN POSITIVE — the guard passes on real geometry and returns real boxes
# --------------------------------------------------------------------------

def test_a_real_paper_yields_verified_cell_geometry():
    """Without this, an all-refused corpus run reads as 'nothing to see here'."""
    layout = _layout()
    verified = 0
    for ct in _first_camelot_table():
        matrix, reason = camelot_cell_bboxes(ct, layout=layout, page=int(ct.page))
        if matrix is not None:
            assert reason.startswith("verified:"), reason
            assert any(b != ZERO_BBOX for row in matrix for b in row), \
                "verified geometry that is entirely zeros is a false all-clear"
            verified += 1
    assert verified > 0, (
        "no table on a real paper produced verified geometry — either the wiring "
        "is dead or the guard is refusing everything; both read identically in "
        "a census, which is why this assertion exists"
    )


def test_verified_boxes_are_pdfplumber_top_down_and_on_the_page():
    """The convention must match ``tables/whitespace.py``, which already emits
    real boxes — one concept, one coordinate space."""
    layout = _layout()
    checked = 0
    for ct in _first_camelot_table():
        page = int(ct.page)
        matrix, reason = camelot_cell_bboxes(ct, layout=layout, page=page)
        if matrix is None:
            continue
        pg = layout.pages[page - 1]
        for row in matrix:
            for (x0, top, x1, bottom) in row:
                if (x0, top, x1, bottom) == ZERO_BBOX:
                    continue
                assert top < bottom, "top-down convention: top must be above bottom"
                assert 0.0 <= top and bottom <= pg.height + 1.0, f"off-page y: {(top, bottom)}"
                assert 0.0 <= x0 < x1 <= pg.width + 1.0, f"off-page x: {(x0, x1)}"
                checked += 1
    assert checked > 0, "no boxes checked — vacuous"


def test_verified_cells_actually_contain_their_own_characters():
    """The end-to-end round trip. This is the assertion that catches T3 (row
    index drift) — a shifted index still produces well-formed boxes on the page,
    so shape assertions alone would pass while every box named the wrong row."""
    layout = _layout()
    hits = misses = 0
    for ct in _first_camelot_table():
        page = int(ct.page)
        matrix, _ = camelot_cell_bboxes(ct, layout=layout, page=page)
        if matrix is None:
            continue
        df = ct.df
        for r in range(len(df)):
            for c in range(len(df.columns)):
                want = "".join(str(df.iloc[r, c]).split())
                if len(want) < 4:
                    continue
                bbox = matrix[r][c]
                if bbox == ZERO_BBOX:
                    continue
                got = "".join(
                    ch.get("text", "") for ch in chars_in_bbox(layout, bbox=bbox, page=page)
                )
                got = "".join(got.split())
                if cell_geometry._containment(got, want) >= cell_geometry.CELL_CONTAINMENT_OK:
                    hits += 1
                else:
                    misses += 1
    assert hits > 0, "no verified cell round-tripped — vacuous"
    assert hits / float(hits + misses) >= cell_geometry.TABLE_PASS_FRACTION, (
        f"only {hits}/{hits + misses} verified cells contain their own text"
    )


# --------------------------------------------------------------------------
# 2. BREAK THE CODE THE GUARD GUARDS — the guard must notice
# --------------------------------------------------------------------------

@pytest.mark.parametrize("break_it", ["flip_axis", "page_plus_one"])
def test_the_guard_refuses_when_the_transform_is_broken(monkeypatch, break_it):
    """A guard that has never failed against the real defect is decoration.

    Measured over the render baseline, every one of 200 tables scores below 0.30
    under each of these two transforms while correct geometry sits at a median of
    0.98 — so a refusal here is the guard working, not a tuned threshold.
    """
    layout = _layout()
    real_recovered = cell_geometry._recovered_text

    if break_it == "flip_axis":
        def broken(lay, page, bbox):
            x0, top, x1, bottom = bbox
            h = lay.pages[page - 1].height
            return real_recovered(lay, page, (x0, h - bottom, x1, h - top))
    else:
        def broken(lay, page, bbox):
            nxt = page + 1 if page < len(lay.pages) else page - 1
            return real_recovered(lay, nxt, bbox)

    monkeypatch.setattr(cell_geometry, "_recovered_text", broken)

    verified_under_break = 0
    considered = 0
    for ct in _first_camelot_table():
        matrix, reason = camelot_cell_bboxes(ct, layout=layout, page=int(ct.page))
        considered += 1
        if matrix is not None:
            verified_under_break += 1
    assert considered > 0, "no tables considered — vacuous"
    assert verified_under_break == 0, (
        f"{verified_under_break} table(s) still passed the round-trip guard with the "
        f"{break_it} defect injected — the guard does not guard"
    )


# --------------------------------------------------------------------------
# 3. NAMED REFUSALS — each cause is reported, never inferred from a low score
# --------------------------------------------------------------------------

def test_no_layout_is_refused_by_name():
    matrix, reason = camelot_cell_bboxes(_FakeTable([["a", "b"], ["1", "2"]]), layout=None, page=1)
    assert matrix is None
    assert reason == "no_layout"


def test_a_camelot_rotated_page_is_refused_by_name():
    """T5, and it is NOT one of register G4's four traps.

    ``10.1001/jamanetworkopen.2023.39337`` p8: Camelot reports
    ``rotation='anticlockwise'`` and ``pdf_size=(792.0, 612.0)`` with a table
    bbox reaching x=730.7, while pdfplumber reports the page 612x792 unrotated.
    Camelot's coordinates are in a plane pdfplumber never sees.
    """
    ct = _FakeTable([["a", "b"], ["1", "2"]], rotation="anticlockwise")
    matrix, reason = camelot_cell_bboxes(ct, layout=_layout(), page=1)
    assert matrix is None
    assert reason.startswith("camelot_rotated_page:anticlockwise"), reason


def test_page_size_disagreement_is_refused_by_name():
    """T5's other face: camelot reporting a page size pdfplumber does not agree
    with means the two are not describing the same frame, whatever the cause."""
    w, h = _page_size()
    ct = _FakeTable([["a", "b"], ["1", "2"]], pdf_size=(h, w))  # transposed
    matrix, reason = camelot_cell_bboxes(ct, layout=_layout(), page=1)
    assert matrix is None
    assert reason.startswith("page_size_disagreement:"), reason


def test_a_page_outside_the_layout_is_refused_by_name():
    layout = _layout()
    ct = _FakeTable([["a", "b"], ["1", "2"]])
    matrix, reason = camelot_cell_bboxes(ct, layout=layout, page=len(layout.pages) + 5)
    assert matrix is None
    assert reason.startswith("page_out_of_range:"), reason


def test_too_few_verifiable_cells_is_refused_rather_than_blessed():
    """Three cells passing is not evidence; the fraction is noise below the floor."""
    ct = _FakeTable([["ab", "cd"]])
    matrix, reason = camelot_cell_bboxes(ct, layout=_layout(), page=1)
    assert matrix is None
    assert reason.startswith("too_few_verifiable_cells:"), reason
