"""Smoke test — modules exist and TABLE_EXTRACTION_VERSION is exposed."""


def test_tables_package_imports():
    from docpluck import tables
    assert tables is not None


def test_figures_package_imports():
    from docpluck import figures
    assert figures is not None


def test_extract_structured_module_imports():
    from docpluck import extract_structured
    assert extract_structured is not None


def test_table_extraction_version_is_semver_string():
    from docpluck.extract_structured import TABLE_EXTRACTION_VERSION
    parts = TABLE_EXTRACTION_VERSION.split(".")
    assert len(parts) == 3
    assert all(p.isdigit() for p in parts)


def test_table_extraction_version_v2_after_pdfplumber_removal():
    """v2.x.x marks the post-pdfplumber, Camelot-based pipeline (LESSONS L-006)."""
    from docpluck.extract_structured import TABLE_EXTRACTION_VERSION
    major = TABLE_EXTRACTION_VERSION.split(".")[0]
    assert int(major) >= 2
