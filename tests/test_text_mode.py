"""table_text_mode='raw' vs 'placeholder' behavior."""

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


def _read(fixture_id: str) -> bytes:
    return _resolve_fixture(fixture_id).read_bytes()


def test_raw_mode_text_byte_identical_to_extract_pdf():
    """Default raw mode must equal extract_pdf()'s text exactly (backwards-compat)."""
    from docpluck import extract_pdf, extract_pdf_structured
    data = _read("apa_chan_feldman_lineless")
    plain_text, _ = extract_pdf(data)
    raw_result = extract_pdf_structured(data, table_text_mode="raw")
    assert raw_result["text"] == plain_text


def test_placeholder_mode_inserts_table_markers():
    from docpluck import extract_pdf_structured
    data = _read("apa_chan_feldman_lineless")
    result = extract_pdf_structured(data, table_text_mode="placeholder")
    # If any tables detected, expect at least one [Table marker in the text.
    if not result["tables"]:
        pytest.skip("no tables detected")
    assert "[Table" in result["text"]


def test_placeholder_mode_text_changes_only_when_regions_detected():
    """Placeholder text differs from raw only if there's at least one table or figure."""
    from docpluck import extract_pdf_structured
    data = _read("apa_chan_feldman_lineless")
    raw = extract_pdf_structured(data, table_text_mode="raw")
    placeholder = extract_pdf_structured(data, table_text_mode="placeholder")
    if not (raw["tables"] or raw["figures"]):
        assert placeholder["text"] == raw["text"]
    else:
        assert placeholder["text"] != raw["text"] or len(raw["tables"]) + len(raw["figures"]) == 0


def test_placeholder_marker_format_includes_label_and_caption_when_present():
    from docpluck import extract_pdf_structured
    data = _read("apa_chan_feldman_lineless")
    result = extract_pdf_structured(data, table_text_mode="placeholder")
    if not result["tables"]:
        pytest.skip("no tables detected")
    t = result["tables"][0]
    if t.get("label") and t.get("caption"):
        # Marker should be "[Label: caption]"
        expected_substring = f"[{t['label']}: "
        assert expected_substring in result["text"]


def test_placeholder_with_figures_inserts_figure_markers():
    from docpluck import extract_pdf_structured
    data = _read("nat_comms_figure_only")
    result = extract_pdf_structured(data, table_text_mode="placeholder")
    if not result["figures"]:
        pytest.skip("no figures detected")
    assert "[Figure" in result["text"]


def test_placeholder_does_not_explode_text_length():
    """Replacing a table region with a short marker shouldn't grow text dramatically."""
    from docpluck import extract_pdf_structured
    data = _read("apa_chan_feldman_lineless")
    raw = extract_pdf_structured(data, table_text_mode="raw")
    placeholder = extract_pdf_structured(data, table_text_mode="placeholder")
    # Allow modest growth (markers add ~50-200 chars per table) — guard against catastrophic
    # explosion (>2x raw length).
    assert len(placeholder["text"]) <= len(raw["text"]) * 2
