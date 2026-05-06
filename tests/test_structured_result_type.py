"""StructuredResult TypedDict + top-level re-exports."""

from typing import get_type_hints


def test_structured_result_fields():
    from docpluck.extract_structured import StructuredResult
    hints = get_type_hints(StructuredResult)
    expected = {
        "text", "method", "page_count",
        "tables", "figures", "table_extraction_version",
    }
    assert set(hints.keys()) == expected


def test_table_reexported_from_top_level():
    from docpluck import Table
    assert Table is not None


def test_figure_reexported_from_top_level():
    from docpluck import Figure
    assert Figure is not None


def test_table_extraction_version_reexported_from_top_level():
    from docpluck import TABLE_EXTRACTION_VERSION
    assert TABLE_EXTRACTION_VERSION == "1.0.0"


def test_existing_extract_pdf_still_exported():
    """Backwards-compat smoke: existing extract_pdf is still there."""
    from docpluck import extract_pdf
    assert callable(extract_pdf)
