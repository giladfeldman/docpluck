"""CLI: docpluck extract --structured ..."""

import json
import os
import subprocess
import sys
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


def _run(*args: str, timeout: int = 120) -> subprocess.CompletedProcess:
    cmd = [sys.executable, "-m", "docpluck", *args]
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", timeout=timeout)


def test_structured_flag_outputs_json():
    pdf = _resolve_fixture("apa_chan_feldman_lineless")
    result = _run("extract", str(pdf), "--structured")
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert "tables" in data
    assert "figures" in data
    assert "text" in data
    assert "method" in data
    assert "page_count" in data


def test_thorough_flag():
    pdf = _resolve_fixture("apa_chan_feldman_lineless")
    result = _run("extract", str(pdf), "--structured", "--thorough")
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert "thorough" in data["method"]


def test_text_mode_placeholder_flag():
    pdf = _resolve_fixture("apa_chan_feldman_lineless")
    result = _run("extract", str(pdf), "--structured", "--text-mode", "placeholder")
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    if data["tables"] or data["figures"]:
        assert "[Table" in data["text"] or "[Figure" in data["text"]


def test_tables_only_omits_figures():
    pdf = _resolve_fixture("apa_chan_feldman_lineless")
    result = _run("extract", str(pdf), "--structured", "--tables-only")
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert data["figures"] == []


def test_figures_only_omits_tables():
    pdf = _resolve_fixture("apa_chan_feldman_lineless")
    result = _run("extract", str(pdf), "--structured", "--figures-only")
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert data["tables"] == []


def test_existing_extract_no_flags_unchanged():
    """extract <file> without --structured emits plain text, not JSON."""
    pdf = _resolve_fixture("apa_chan_feldman_lineless")
    result = _run("extract", str(pdf))
    assert result.returncode == 0, result.stderr
    # First non-whitespace char should NOT be { (which would indicate JSON)
    stripped = result.stdout.lstrip()
    assert not stripped.startswith("{"), "plain extract should not emit JSON"


def test_html_tables_to_writes_html_files(tmp_path):
    pdf = _resolve_fixture("apa_chan_feldman_lineless")
    out_dir = tmp_path / "html_out"
    result = _run(
        "extract", str(pdf), "--structured", "--html-tables-to", str(out_dir)
    )
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    structured_tables = [t for t in data["tables"] if t["kind"] == "structured"]
    if not structured_tables:
        pytest.skip("no structured tables in this fixture")
    # Each structured table should have a corresponding .html file
    for t in structured_tables:
        out_file = out_dir / f"{t['id']}.html"
        assert out_file.is_file(), f"missing {out_file}"
        contents = out_file.read_text(encoding="utf-8")
        assert "<table>" in contents
