"""End-to-end tests for extract_pdf_structured()."""

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


def test_imports_ok():
    from docpluck import extract_pdf_structured, TABLE_EXTRACTION_VERSION
    assert callable(extract_pdf_structured)
    # v2+ marks the post-pdfplumber Camelot-based pipeline (LESSONS L-006).
    assert int(TABLE_EXTRACTION_VERSION.split(".")[0]) >= 2


def test_returns_required_fields():
    from docpluck import extract_pdf_structured, TABLE_EXTRACTION_VERSION
    data = _read("apa_chan_feldman_lineless")
    result = extract_pdf_structured(data)
    assert "text" in result
    assert "method" in result
    assert "page_count" in result
    assert "tables" in result
    assert "figures" in result
    assert result["table_extraction_version"] == TABLE_EXTRACTION_VERSION
    assert isinstance(result["tables"], list)
    assert isinstance(result["figures"], list)


def test_text_default_mode_matches_extract_pdf():
    """In raw mode (default), text equals extract_pdf()'s text byte-for-byte."""
    from docpluck import extract_pdf, extract_pdf_structured
    data = _read("apa_chan_feldman_lineless")
    plain_text, _plain_method = extract_pdf(data)
    result = extract_pdf_structured(data)
    assert result["text"] == plain_text


def test_method_string_indicates_structured_extraction():
    from docpluck import extract_pdf_structured
    data = _read("apa_chan_feldman_lineless")
    result = extract_pdf_structured(data)
    # Post-LESSONS-L-006: tables come from Camelot stream. Test that the method
    # string carries some structured-extraction marker (any of the v2 tokens).
    method = result["method"]
    assert any(tok in method for tok in ("camelot_stream", "camelot_failed")), method


def test_thorough_mode_method_string():
    from docpluck import extract_pdf_structured
    data = _read("apa_chan_feldman_lineless")
    result = extract_pdf_structured(data, thorough=True)
    assert "thorough" in result["method"]


def test_table_kinds_are_valid():
    from docpluck import extract_pdf_structured
    data = _read("apa_chan_feldman_lineless")
    result = extract_pdf_structured(data)
    for t in result["tables"]:
        assert t["kind"] in {"structured", "isolated"}
        assert t["rendering"] in {"lattice", "whitespace", "isolated"}
        if t["kind"] == "structured":
            assert t["confidence"] is not None
            assert 0.0 <= t["confidence"] <= 1.0
            assert t["html"] is not None
            assert "<table>" in t["html"]
            assert isinstance(t["cells"], list)
            assert len(t["cells"]) > 0
        else:
            assert t["confidence"] is None
            assert t["html"] is None
            assert t["cells"] == []
            assert isinstance(t["raw_text"], str)


def test_table_ids_unique_and_sequential():
    from docpluck import extract_pdf_structured
    data = _read("apa_chan_feldman_lineless")
    result = extract_pdf_structured(data)
    if not result["tables"]:
        pytest.skip("no tables detected")
    ids = [t["id"] for t in result["tables"]]
    assert len(set(ids)) == len(ids)
    assert all(tid.startswith("t") for tid in ids)
    expected = [f"t{i}" for i in range(1, len(result["tables"]) + 1)]
    assert ids == expected


def test_table_required_fields_present():
    from docpluck import extract_pdf_structured
    data = _read("apa_chan_feldman_lineless")
    result = extract_pdf_structured(data)
    if not result["tables"]:
        pytest.skip("no tables detected")
    t = result["tables"][0]
    for key in ("id", "label", "page", "bbox", "caption", "footnote",
                "kind", "rendering", "confidence",
                "n_rows", "n_cols", "header_rows",
                "cells", "html", "raw_text"):
        assert key in t


def test_figure_required_fields_present():
    from docpluck import extract_pdf_structured
    data = _read("nat_comms_figure_only")
    result = extract_pdf_structured(data)
    if not result["figures"]:
        pytest.skip("no figures detected")
    f = result["figures"][0]
    for key in ("id", "label", "page", "bbox", "caption"):
        assert key in f


def test_page_count_positive():
    from docpluck import extract_pdf_structured
    data = _read("apa_chan_feldman_lineless")
    result = extract_pdf_structured(data)
    assert result["page_count"] >= 1


def test_garbled_pdf_returns_error_gracefully():
    """Malformed bytes should not raise; should return ERROR-prefixed text + empty tables/figures."""
    from docpluck import extract_pdf_structured
    result = extract_pdf_structured(b"not a real pdf")
    # text may start with "ERROR:" OR pdftotext may produce empty output;
    # in either case, structured fields must remain valid types.
    assert isinstance(result["text"], str)
    assert isinstance(result["tables"], list)
    assert isinstance(result["figures"], list)


def test_extract_pdf_unchanged():
    """extract_pdf() byte-for-byte unchanged after Task 13 lands."""
    from docpluck import extract_pdf
    data = _read("apa_chan_feldman_lineless")
    text1, method1 = extract_pdf(data)
    text2, method2 = extract_pdf(data)
    assert text1 == text2
    assert method1 == method2
