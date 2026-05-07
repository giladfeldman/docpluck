"""Whitespace (column-gap) cell clustering for lineless tables."""

import json
import os
from pathlib import Path

import pytest


_HERE = Path(__file__).parent
_MANIFEST = _HERE / "fixtures" / "structured" / "MANIFEST.json"
_VIBE = Path(os.path.expanduser("~")) / "Dropbox" / "Vibe"


def _resolve_fixture(fixture_id: str) -> Path:
    if not _MANIFEST.is_file():
        pytest.skip("MANIFEST.json missing")
    data = json.loads(_MANIFEST.read_text(encoding="utf-8"))
    base = _VIBE if data.get("vibe_relative") else Path("/")
    for entry in data["fixtures"]:
        if entry["id"] == fixture_id:
            path = base / entry["source_path"]
            if not path.is_file():
                pytest.skip(f"Fixture not available: {fixture_id} -> {path}")
            return path
    pytest.skip(f"Fixture id not in manifest: {fixture_id}")


def _layout(fixture_id: str):
    pdf = _resolve_fixture(fixture_id)
    from docpluck.extract_layout import extract_pdf_layout
    return extract_pdf_layout(pdf.read_bytes())


def test_imports_ok():
    from docpluck.tables.whitespace import whitespace_cells
    assert whitespace_cells is not None


def test_apa_lineless_yields_grid():
    layout = _layout("apa_chan_feldman_lineless")
    from docpluck.tables.detect import find_table_regions
    from docpluck.tables.whitespace import whitespace_cells
    regions = [r for r in find_table_regions(layout) if r.geometry_signal == "whitespace"]
    if not regions:
        pytest.skip("no whitespace region detected on this fixture")
    cells = whitespace_cells(layout, region=regions[0])
    if not cells:
        pytest.skip("whitespace clustering produced no cells")
    rows = {c["r"] for c in cells}
    cols = {c["c"] for c in cells}
    assert len(rows) >= 3
    assert len(cols) >= 2


def test_whitespace_returns_empty_on_no_words():
    from docpluck.tables.whitespace import whitespace_cells
    from docpluck.tables.detect import CandidateRegion
    layout = _layout("apa_chan_feldman_lineless")
    region = CandidateRegion(
        label=None, page=1, bbox=(0.0, 0.0, 5.0, 5.0),
        caption=None, footnote=None,
        geometry_signal="whitespace", caption_match=None,
    )
    cells = whitespace_cells(layout, region=region)
    assert cells == []


def test_whitespace_cells_have_required_typeddict_fields():
    layout = _layout("apa_chan_feldman_lineless")
    from docpluck.tables.detect import find_table_regions
    from docpluck.tables.whitespace import whitespace_cells
    regions = [r for r in find_table_regions(layout) if r.geometry_signal == "whitespace"]
    if not regions:
        pytest.skip("no whitespace region detected")
    cells = whitespace_cells(layout, region=regions[0])
    if not cells:
        pytest.skip("no cells emitted")
    sample = cells[0]
    for key in ("r", "c", "rowspan", "colspan", "text", "is_header", "bbox"):
        assert key in sample
    assert sample["rowspan"] == 1
    assert sample["colspan"] == 1
    assert isinstance(sample["text"], str)
    assert isinstance(sample["is_header"], bool)
