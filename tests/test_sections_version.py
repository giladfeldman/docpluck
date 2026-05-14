"""Smoke test — module exists and exposes SECTIONING_VERSION."""


def test_sections_module_imports():
    from docpluck import sections
    assert sections is not None


def test_sectioning_version_is_semver_string():
    from docpluck.sections import SECTIONING_VERSION
    parts = SECTIONING_VERSION.split(".")
    assert len(parts) == 3
    assert all(p.isdigit() for p in parts)


def test_sectioning_version_is_v12x():
    """v1.2.x family: additive `conclusion` canonical label (separate from
    discussion); plus expanded methods/results/funding variants and
    Pattern E abstract/intro synthesis. Bumped from 1.1.0 in 2026-05-09.
    v1.2.1 (2026-05-14): Pass 1a/1b function-word reject for body-prose
    openers like "Results from our study…".
    """
    from docpluck.sections import SECTIONING_VERSION
    assert SECTIONING_VERSION.startswith("1.2.")
