"""Smoke test — module exists and exposes SECTIONING_VERSION."""


def test_sections_module_imports():
    from docpluck import sections
    assert sections is not None


def test_sectioning_version_is_semver_string():
    from docpluck.sections import SECTIONING_VERSION
    parts = SECTIONING_VERSION.split(".")
    assert len(parts) == 3
    assert all(p.isdigit() for p in parts)


def test_sectioning_version_is_v161():
    """v1.6.1 architectural pivot: canonical text path + disabled truncation."""
    from docpluck.sections import SECTIONING_VERSION
    assert SECTIONING_VERSION == "1.6.1"
