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


def test_extract_pdf_layout_top_level_importable():
    """v2.4.83: extract_pdf_layout is the public LAYOUT channel entry point
    (CLAUDE.md architecture table) and the required input to F0's
    running-header/footnote strip. It must be importable from top-level
    docpluck — symmetric with extract_pdf — so consumers can run the
    layout-aware normalize path (and read report.footnote_texts) without
    reaching into the docpluck.extract_layout submodule."""
    from docpluck import extract_pdf_layout
    assert callable(extract_pdf_layout)
    import docpluck
    assert "extract_pdf_layout" in docpluck.__all__
