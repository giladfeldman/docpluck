"""v2.0 top-level export regression test.

CHANGELOG v2.0.0 documents `Cell, Table, Figure, StructuredResult` and
`TABLE_EXTRACTION_VERSION` as re-exported from top-level `docpluck`. Cell
was originally missed; this test guards against that drift recurring.
"""


def test_v2_structured_types_top_level_importable():
    """All v2.0 structured-extraction names documented in CHANGELOG must be
    importable from the top-level `docpluck` package."""
    from docpluck import Cell, Table, Figure, StructuredResult, TABLE_EXTRACTION_VERSION
    assert Cell.__name__ == "Cell"
    assert Table.__name__ == "Table"
    assert Figure.__name__ == "Figure"
    assert StructuredResult.__name__ == "StructuredResult"
    assert isinstance(TABLE_EXTRACTION_VERSION, str)


def test_v2_structured_types_in_all():
    """Importable AND in __all__ — protects against `from docpluck import *` users."""
    import docpluck
    expected = {"Cell", "Table", "Figure", "StructuredResult",
                "TABLE_EXTRACTION_VERSION", "extract_pdf_structured"}
    missing = expected - set(docpluck.__all__)
    assert not missing, f"v2.0 names missing from __all__: {missing}"
