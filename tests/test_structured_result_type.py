"""StructuredResult TypedDict + top-level re-exports."""

from typing import get_type_hints


def test_structured_result_fields():
    from docpluck.extract_structured import StructuredResult
    hints = get_type_hints(StructuredResult)
    expected = {
        "text", "method", "page_count",
        "tables", "figures", "table_extraction_version",
        # v2.4.133: which fallback paths fired for THIS document. The library
        # had 31 `record_fallback(...)` call sites and NO production reader —
        # every silent substitution, dropped table and refused repair was
        # recorded and then told to nobody, which is the project's fourth check
        # ("every value computed is read back") failed across a whole subsystem.
        # This field is what makes them reachable.
        "fallbacks",
        # …and this one makes them ATTRIBUTABLE. `record_fallback` accepted a
        # `detail` (the font, the exception type, the shape) and then dropped it
        # on the floor, so a consumer told "symbol-font corruption detected"
        # could not tell which font — an R8 false positive and a real corruption
        # arrived identical. Kept separate from `fallbacks` so that stays a flat
        # `dict[str, int]` a consumer can threshold on.
        "fallback_details",
    }
    assert set(hints.keys()) == expected


def test_every_declared_field_is_actually_populated():
    """A declared field the code never fills is a promise to every consumer that
    the library does not keep (the project's fourth check). Asserted against a
    real return value, not the annotation."""
    from docpluck.extract_structured import StructuredResult, extract_pdf_structured

    result = extract_pdf_structured(b"not a pdf at all")
    assert set(result.keys()) == set(get_type_hints(StructuredResult).keys())


def test_table_reexported_from_top_level():
    from docpluck import Table
    assert Table is not None


def test_figure_reexported_from_top_level():
    from docpluck import Figure
    assert Figure is not None


def test_table_extraction_version_reexported_from_top_level():
    from docpluck import TABLE_EXTRACTION_VERSION
    # v2+ marks the post-pdfplumber Camelot-based pipeline (LESSONS L-006).
    major = TABLE_EXTRACTION_VERSION.split(".")[0]
    assert int(major) >= 2


def test_existing_extract_pdf_still_exported():
    """Backwards-compat smoke: existing extract_pdf is still there."""
    from docpluck import extract_pdf
    assert callable(extract_pdf)
