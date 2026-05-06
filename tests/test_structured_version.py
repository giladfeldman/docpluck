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


def test_table_extraction_version_starts_at_1_0_0():
    from docpluck.extract_structured import TABLE_EXTRACTION_VERSION
    assert TABLE_EXTRACTION_VERSION == "1.0.0"
