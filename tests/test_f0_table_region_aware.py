"""F0 footnote-strip must skip lines inside table-region bboxes."""

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


def test_normalize_text_accepts_table_regions_kwarg():
    """normalize_text() must accept the new table_regions kwarg without error."""
    from docpluck.normalize import normalize_text, NormalizationLevel
    from docpluck.extract_layout import extract_pdf_layout

    data = _read("apa_chan_feldman_lineless")
    layout = extract_pdf_layout(data)
    text, report = normalize_text(
        layout.raw_text,
        NormalizationLevel.academic,
        layout=layout,
        table_regions=[],
    )
    assert isinstance(text, str)


def test_normalize_text_table_regions_default_none_unchanged():
    """When table_regions is not provided, output equals output without it (backwards-compat)."""
    from docpluck.normalize import normalize_text, NormalizationLevel
    from docpluck.extract_layout import extract_pdf_layout

    data = _read("apa_chan_feldman_lineless")
    layout = extract_pdf_layout(data)
    a, _ = normalize_text(layout.raw_text, NormalizationLevel.academic, layout=layout)
    b, _ = normalize_text(layout.raw_text, NormalizationLevel.academic, layout=layout, table_regions=None)
    assert a == b


def test_table_regions_preserves_text_inside_regions():
    """When a region covers nearly the whole page, F0 should NOT strip lines in that region."""
    from docpluck.normalize import normalize_text, NormalizationLevel
    from docpluck.extract_layout import extract_pdf_layout

    data = _read("apa_chan_feldman_lineless")
    layout = extract_pdf_layout(data)
    if not layout.pages:
        pytest.skip("empty layout")

    huge_regions = [
        {"page": p.page_index + 1, "bbox": (0.0, 0.0, p.width + 100, p.height + 100)}
        for p in layout.pages
    ]
    no_regions, _ = normalize_text(
        layout.raw_text, NormalizationLevel.academic, layout=layout, table_regions=None,
    )
    with_regions, _ = normalize_text(
        layout.raw_text, NormalizationLevel.academic, layout=layout, table_regions=huge_regions,
    )
    # If F0 was stripping any text as a footnote on this fixture, with_regions should
    # retain at least as many chars as no_regions.
    assert len(with_regions) >= len(no_regions) - 5  # tiny tolerance for whitespace edges


def test_extract_pdf_structured_yields_table_footnotes_when_present():
    """Sanity: extract_pdf_structured may surface table.footnote on real APA PDFs.
    Not a strict requirement (footnote detection is heuristic), but verifies the API works."""
    from docpluck import extract_pdf_structured
    data = _read("apa_chan_feldman_lineless")
    result = extract_pdf_structured(data)
    # Just confirm the fields exist and aren't malformed.
    for t in result["tables"]:
        assert "footnote" in t
        if t["footnote"] is not None:
            assert isinstance(t["footnote"], str)
