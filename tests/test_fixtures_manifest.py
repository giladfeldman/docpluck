"""Smoke fixture manifest — well-formed and references real PDFs (skipping when missing)."""

import json
import os
from pathlib import Path

import pytest


_HERE = Path(__file__).parent
_FIXTURES_DIR = _HERE / "fixtures" / "structured"
_MANIFEST = _FIXTURES_DIR / "MANIFEST.json"
_VIBE = Path(os.path.expanduser("~")) / "Dropbox" / "Vibe"


def _load_manifest() -> dict:
    if not _MANIFEST.is_file():
        return {"fixtures": []}
    return json.loads(_MANIFEST.read_text(encoding="utf-8"))


def _resolve(entry: dict) -> Path:
    src = entry["source_path"]
    base = _VIBE if _load_manifest().get("vibe_relative") else Path("/")
    return base / src


def test_fixtures_directory_exists():
    assert _FIXTURES_DIR.is_dir(), f"Missing: {_FIXTURES_DIR}"


def test_manifest_exists_and_is_json():
    assert _MANIFEST.is_file(), f"Missing: {_MANIFEST}"
    json.loads(_MANIFEST.read_text(encoding="utf-8"))


def test_manifest_top_level_schema():
    data = _load_manifest()
    assert "version" in data
    assert "fixtures" in data
    assert isinstance(data["fixtures"], list)
    assert len(data["fixtures"]) >= 8, "expect ≥8 fixtures collected"


def test_each_fixture_entry_has_required_fields():
    data = _load_manifest()
    valid_categories = {
        "lattice_table", "apa_lineless", "nature_minimal_rule",
        "figure_only", "negative_no_tables_no_figures",
        "table_of_contents_negative", "uncaptioned_table",
    }
    for entry in data["fixtures"]:
        assert "id" in entry
        assert "category" in entry
        assert entry["category"] in valid_categories, (
            f"Unknown category: {entry['category']} (entry: {entry['id']})"
        )
        assert "source_path" in entry
        assert "expected_tables" in entry
        assert "expected_figures" in entry


def test_fixture_ids_are_unique():
    data = _load_manifest()
    ids = [e["id"] for e in data["fixtures"]]
    assert len(set(ids)) == len(ids), f"Duplicate fixture ids: {ids}"


@pytest.mark.parametrize(
    "entry",
    _load_manifest()["fixtures"],
    ids=lambda e: e.get("id", "?"),
)
def test_fixture_source_path_resolves_to_real_pdf(entry):
    """Per-fixture: source_path resolves to an existing PDF (or test SKIPs)."""
    path = _resolve(entry)
    if not path.is_file():
        pytest.skip(f"Source PDF not present locally: {path}")
    head = path.read_bytes()[:5]
    assert head[:4] == b"%PDF", f"Not a PDF: {path}"
