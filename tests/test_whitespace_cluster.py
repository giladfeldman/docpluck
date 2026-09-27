"""Whitespace (column-gap) cell clustering for lineless tables."""


from tests.structured_fixtures import resolve_fixture as _resolve_fixture


def _layout(fixture_id: str):
    pdf = _resolve_fixture(fixture_id)
    from docpluck.extract_layout import extract_pdf_layout
    return extract_pdf_layout(pdf.read_bytes())


def test_imports_ok():
    from docpluck.tables.whitespace import whitespace_cells
    assert whitespace_cells is not None


def _known_positive_cells():
    """A table the whitespace path DOES grid, so the tests below assert rather
    than skip.

    Until 2026-09-25 they took the first "whitespace" region of the
    ``apa_chan_feldman_lineless`` fixture and skipped when it produced no
    cells -- which it did on every run, so both tests asserted nothing (the
    skip read as green). The known positive is 10.1001/jamanetworkopen.2023.39337
    Table 1 (p6), caption-anchored the way the pipeline does it.
    """
    from docpluck import extract_structured as ES
    from docpluck.extract import extract_pdf
    from docpluck.extract_layout import extract_pdf_layout
    from docpluck.tables.captions import find_caption_matches
    from docpluck.tables.detect import _region_for_caption
    from docpluck.tables.whitespace import whitespace_cells
    from docpluck.testing import require_corpus_pdf

    data = require_corpus_pdf("ama/jama_open_1.pdf").read_bytes()
    raw = ES._join_split_captions(extract_pdf(data)[0])
    cap = next(
        c for c in find_caption_matches(raw, ES._page_offsets(raw))
        if c.kind == "table" and c.label == "Table 1"
    )
    layout = extract_pdf_layout(data)
    region = _region_for_caption(layout, cap)
    assert region is not None
    return whitespace_cells(layout, region=region)


def test_a_real_lineless_region_yields_grid():
    cells = _known_positive_cells()
    rows = {c["r"] for c in cells}
    cols = {c["c"] for c in cells}
    assert len(rows) >= 3
    assert len(cols) >= 2


def test_whitespace_returns_empty_on_no_words():
    from docpluck.tables.detect import CandidateRegion
    from docpluck.tables.whitespace import whitespace_cells
    layout = _layout("apa_chan_feldman_lineless")
    region = CandidateRegion(
        label=None, page=1, bbox=(0.0, 0.0, 5.0, 5.0),
        geometry_signal="whitespace", caption_match=None,
    )
    cells = whitespace_cells(layout, region=region)
    assert cells == []


def test_whitespace_cells_have_required_typeddict_fields():
    cells = _known_positive_cells()
    assert cells
    sample = cells[0]
    for key in ("r", "c", "rowspan", "colspan", "text", "is_header", "bbox"):
        assert key in sample
    assert sample["rowspan"] == 1
    assert sample["colspan"] == 1
    assert isinstance(sample["text"], str)
    assert isinstance(sample["is_header"], bool)
