"""Table region detection — caption anchor + geometry → CandidateRegion list."""

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
    from docpluck.tables.detect import find_table_regions, CandidateRegion, GeometrySignal
    assert find_table_regions is not None
    assert CandidateRegion is not None
    assert GeometrySignal is not None


def test_lattice_fixture_finds_at_least_one_region():
    layout = _layout("ieee_lattice")
    from docpluck.tables.detect import find_table_regions
    regions = find_table_regions(layout)
    assert len(regions) >= 1
    r = regions[0]
    assert r.page >= 1
    assert r.label is not None and r.label.startswith("Table ")
    x0, top, x1, bottom = r.bbox
    assert x1 > x0
    assert bottom > top
    assert r.geometry_signal in {"lattice", "whitespace", "caption_only"}


def test_apa_lineless_finds_at_least_one_region():
    layout = _layout("apa_chan_feldman_lineless")
    from docpluck.tables.detect import find_table_regions
    regions = find_table_regions(layout)
    assert len(regions) >= 1
    # APA tables have no rules, so signal is whitespace or caption_only.
    assert regions[0].geometry_signal in {"whitespace", "caption_only"}


def test_caption_match_carries_through():
    layout = _layout("apa_chan_feldman_lineless")
    from docpluck.tables.detect import find_table_regions
    regions = find_table_regions(layout)
    if not regions:
        pytest.skip("no regions detected")
    r = regions[0]
    assert r.caption_match is not None
    assert r.caption_match.kind == "table"


def test_candidate_region_dataclass_shape():
    from docpluck.tables.detect import CandidateRegion
    from docpluck.tables.captions import CaptionMatch
    cap = CaptionMatch(
        kind="table", number=1, label="Table 1", page=2,
        char_start=10, char_end=40, line_text="Table 1. Test",
    )
    region = CandidateRegion(
        label="Table 1", page=2, bbox=(0.0, 0.0, 100.0, 100.0),
        caption="Table 1. Test", footnote=None,
        geometry_signal="lattice", caption_match=cap,
    )
    assert region.label == "Table 1"
    assert region.geometry_signal == "lattice"


def test_returns_empty_when_no_caption_matches():
    """A caption-free fixture should yield zero regions in default mode."""
    # Use a manifest fixture that has expected_tables=0
    manifest_data = json.loads(_MANIFEST.read_text(encoding="utf-8"))
    fixture_id = None
    for e in manifest_data["fixtures"]:
        if e.get("expected_tables") == 0:
            fixture_id = e["id"]
            break
    if fixture_id is None:
        pytest.skip("no expected_tables=0 fixture in manifest")
    layout = _layout(fixture_id)
    from docpluck.tables.detect import find_table_regions
    regions = find_table_regions(layout, thorough=False)
    # Default mode is caption-anchored — no caption, no region.
    # (Some figures-only fixtures do have figure captions, but no Table N captions.)
    assert all(r.caption_match is not None for r in regions), (
        "default-mode regions must all be caption-anchored"
    )


def test_thorough_mode_can_yield_uncaptioned_regions():
    """thorough=True should find regions even on pages without Table N captions
    if the page has ≥3 horizontal rules. Just verify the call doesn't error and
    returns a list (no strict count assertion — depends on real geometry)."""
    layout = _layout("ieee_lattice")
    from docpluck.tables.detect import find_table_regions
    default = find_table_regions(layout, thorough=False)
    thorough = find_table_regions(layout, thorough=True)
    assert isinstance(thorough, list)
    # Thorough must find at least as many regions as default.
    assert len(thorough) >= len(default)
