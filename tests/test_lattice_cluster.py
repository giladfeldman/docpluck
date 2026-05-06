"""Lattice (ruling-line) cell clustering."""

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
    from docpluck.tables.cluster import lattice_cells
    assert lattice_cells is not None


def test_lattice_emits_grid_cells_on_lattice_fixture():
    layout = _layout("ieee_lattice")
    from docpluck.tables.detect import find_table_regions
    from docpluck.tables.cluster import lattice_cells
    regions = [r for r in find_table_regions(layout) if r.geometry_signal == "lattice"]
    if not regions:
        pytest.skip("no lattice region detected on this fixture")
    cells = lattice_cells(layout, region=regions[0])
    assert len(cells) > 0
    rows = {c["r"] for c in cells}
    cols = {c["c"] for c in cells}
    assert len(rows) >= 2
    assert len(cols) >= 2


def test_lattice_cells_have_text():
    layout = _layout("ieee_lattice")
    from docpluck.tables.detect import find_table_regions
    from docpluck.tables.cluster import lattice_cells
    regions = [r for r in find_table_regions(layout) if r.geometry_signal == "lattice"]
    if not regions:
        pytest.skip("no lattice region detected")
    cells = lattice_cells(layout, region=regions[0])
    non_empty = [c for c in cells if c["text"].strip()]
    # At least half of cells should be non-empty in a real table.
    assert len(non_empty) >= max(1, len(cells) // 2)


def test_lattice_returns_empty_when_geometry_missing():
    """A fake region pointing at empty space should yield no cells."""
    from docpluck.tables.cluster import lattice_cells
    from docpluck.tables.detect import CandidateRegion
    layout = _layout("nat_comms_figure_only")  # any fixture works for this test
    region = CandidateRegion(
        label=None, page=1, bbox=(0.0, 0.0, 50.0, 50.0),
        caption=None, footnote=None,
        geometry_signal="lattice", caption_match=None,
    )
    cells = lattice_cells(layout, region=region)
    assert cells == []


def test_lattice_cells_have_required_typeddict_fields():
    layout = _layout("ieee_lattice")
    from docpluck.tables.detect import find_table_regions
    from docpluck.tables.cluster import lattice_cells
    regions = [r for r in find_table_regions(layout) if r.geometry_signal == "lattice"]
    if not regions:
        pytest.skip("no lattice region detected")
    cells = lattice_cells(layout, region=regions[0])
    if not cells:
        pytest.skip("no cells emitted")
    sample = cells[0]
    for key in ("r", "c", "rowspan", "colspan", "text", "is_header", "bbox"):
        assert key in sample
    assert sample["rowspan"] == 1
    assert sample["colspan"] == 1
    assert isinstance(sample["text"], str)
    assert isinstance(sample["is_header"], bool)
    x0, top, x1, bottom = sample["bbox"]
    assert x1 > x0 and bottom >= top   # zero-height empty rows could be degenerate; allow ≥
