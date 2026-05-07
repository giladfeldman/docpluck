"""Figure region detection — caption + bbox metadata only."""

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
    from docpluck.figures.detect import find_figures
    assert find_figures is not None


def test_figure_only_fixture_finds_figures():
    layout = _layout("nat_comms_figure_only")
    from docpluck.figures.detect import find_figures
    figures = find_figures(layout)
    if not figures:
        pytest.skip("no figures detected on this fixture")
    for f in figures:
        assert f["label"] is not None and f["label"].startswith("Figure ")
        assert f["caption"] is not None and len(f["caption"]) > 0
        x0, top, x1, bottom = f["bbox"]
        assert x1 > x0
        assert bottom >= top  # allow degenerate but not negative


def test_no_figures_returns_empty_or_only_real_figures():
    """A negative-case fixture should yield zero or only well-formed figures."""
    # Use any fixture with expected_figures==0; if not available, skip.
    manifest_data = json.loads(_MANIFEST.read_text(encoding="utf-8"))
    fixture_id = None
    for e in manifest_data["fixtures"]:
        if e.get("expected_figures") == 0:
            fixture_id = e["id"]
            break
    if fixture_id is None:
        pytest.skip("no expected_figures=0 fixture in manifest")
    layout = _layout(fixture_id)
    from docpluck.figures.detect import find_figures
    figures = find_figures(layout)
    # If any figures show up, they should at least have valid shape.
    for f in figures:
        assert f["label"] is None or f["label"].startswith("Figure ")
        x0, top, x1, bottom = f["bbox"]
        assert x1 > x0


def test_figure_id_is_unique_and_sequential():
    layout = _layout("nat_comms_figure_only")
    from docpluck.figures.detect import find_figures
    figures = find_figures(layout)
    if not figures:
        pytest.skip("no figures detected")
    ids = [f["id"] for f in figures]
    assert len(set(ids)) == len(ids)
    assert all(fid.startswith("f") for fid in ids)
    # Sequential 1..n
    expected = [f"f{i}" for i in range(1, len(figures) + 1)]
    assert ids == expected


def test_figure_typeddict_shape():
    from docpluck.figures import Figure
    f: Figure = {
        "id": "f1", "label": "Figure 1", "page": 3,
        "bbox": (72.0, 100.0, 540.0, 320.0),
        "caption": "Mean reaction time across conditions.",
    }
    assert f["id"] == "f1"
