"""bbox utilities — bbox-to-char-range + word/char slicing."""

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


def test_layout_doc_pages_expose_geometric_primitives():
    """PageLayout must expose lines/rects/curves/chars/words on every page."""
    layout = _layout("apa_chan_feldman_lineless")
    assert len(layout.pages) >= 1
    p = layout.pages[0]
    assert hasattr(p, "lines")
    assert hasattr(p, "rects")
    assert hasattr(p, "curves")
    assert hasattr(p, "chars")
    assert hasattr(p, "words")
    # chars should be present on a real PDF page
    assert len(p.chars) > 0
    # words should be present (pdfplumber extract_words always finds something on text-bearing pages)
    assert len(p.words) > 0


def test_bbox_to_char_range_returns_valid_slice():
    layout = _layout("apa_chan_feldman_lineless")
    from docpluck.tables.bbox_utils import bbox_to_char_range
    page_bbox = (0.0, 0.0, 1000.0, 1000.0)  # whole page
    start, end = bbox_to_char_range(layout, bbox=page_bbox, page=1)
    assert 0 <= start <= end <= len(layout.raw_text)


def test_bbox_to_char_range_subregion_inside_full_range():
    layout = _layout("apa_chan_feldman_lineless")
    from docpluck.tables.bbox_utils import bbox_to_char_range
    full_start, full_end = bbox_to_char_range(layout, bbox=(0, 0, 10000, 10000), page=1)
    # Subregion in upper-left should produce a range within the full page range.
    sub_start, sub_end = bbox_to_char_range(layout, bbox=(0, 0, 200, 200), page=1)
    assert full_start <= sub_start
    assert sub_end <= full_end


def test_words_in_bbox_returns_list_of_dicts_with_required_keys():
    layout = _layout("apa_chan_feldman_lineless")
    from docpluck.tables.bbox_utils import words_in_bbox
    words = words_in_bbox(layout, bbox=(0, 0, 10000, 10000), page=1)
    assert isinstance(words, list)
    assert len(words) > 0
    for w in words:
        assert "x0" in w
        assert "x1" in w
        assert "text" in w


def test_chars_in_bbox_subset_of_page_chars():
    layout = _layout("apa_chan_feldman_lineless")
    from docpluck.tables.bbox_utils import chars_in_bbox
    page = layout.pages[0]
    all_chars_count = len(page.chars)
    in_top_band = chars_in_bbox(layout, bbox=(0, 0, 10000, 200), page=1)
    assert isinstance(in_top_band, list)
    assert len(in_top_band) <= all_chars_count


def test_bbox_to_char_range_invalid_page_raises():
    layout = _layout("apa_chan_feldman_lineless")
    from docpluck.tables.bbox_utils import bbox_to_char_range
    with pytest.raises(ValueError):
        bbox_to_char_range(layout, bbox=(0, 0, 100, 100), page=999)


def test_words_in_bbox_invalid_page_raises():
    layout = _layout("apa_chan_feldman_lineless")
    from docpluck.tables.bbox_utils import words_in_bbox
    with pytest.raises(ValueError):
        words_in_bbox(layout, bbox=(0, 0, 100, 100), page=999)


def test_chars_in_bbox_invalid_page_raises():
    layout = _layout("apa_chan_feldman_lineless")
    from docpluck.tables.bbox_utils import chars_in_bbox
    with pytest.raises(ValueError):
        chars_in_bbox(layout, bbox=(0, 0, 100, 100), page=999)
