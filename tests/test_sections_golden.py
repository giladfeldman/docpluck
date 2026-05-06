"""Regression test: sectioner output snapshot.

CI fails when SECTIONING_VERSION is unchanged but output drifts.
On a SECTIONING_VERSION bump, regenerate snapshots:

    DOCPLUCK_REGEN_GOLDEN=1 pytest tests/test_sections_golden.py
"""

import json
import os
import pathlib

import pytest

pytest.importorskip("reportlab")
pytest.importorskip("pdfplumber")

from docpluck import extract_sections, SECTIONING_VERSION
from tests.fixtures.sections import builders


GOLDEN_DIR = pathlib.Path(__file__).parent / "golden" / "sections"


def _serialize(doc) -> dict:
    return {
        "sectioning_version": doc.sectioning_version,
        "source_format": doc.source_format,
        "sections": [
            {
                "label": s.label,
                "canonical_label": s.canonical_label.value,
                "char_start": s.char_start,
                "char_end": s.char_end,
                "pages": list(s.pages),
                "confidence": s.confidence.value,
                "detected_via": s.detected_via.value,
                "heading_text": s.heading_text,
            }
            for s in doc.sections
        ],
    }


def _check_snapshot(name: str, doc) -> None:
    path = GOLDEN_DIR / f"{name}.json"
    serialized = _serialize(doc)
    if os.environ.get("DOCPLUCK_REGEN_GOLDEN"):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(serialized, indent=2))
        return
    if not path.exists():
        pytest.skip(f"No golden file for {name}; set DOCPLUCK_REGEN_GOLDEN=1 to create.")
    expected = json.loads(path.read_text())
    assert serialized["sectioning_version"] == SECTIONING_VERSION
    assert serialized == expected, (
        f"{name}: output drifted but SECTIONING_VERSION unchanged. "
        "Either fix the regression, or bump SECTIONING_VERSION and regenerate "
        "with DOCPLUCK_REGEN_GOLDEN=1."
    )


def test_golden_apa_single_study_pdf():
    doc = extract_sections(builders.build_apa_single_study_pdf())
    _check_snapshot("apa_single_study_pdf", doc)


def test_golden_apa_multi_study_pdf():
    doc = extract_sections(builders.build_apa_multi_study_pdf())
    _check_snapshot("apa_multi_study_pdf", doc)


def test_golden_html_real_headings():
    pytest.importorskip("bs4")
    doc = extract_sections(builders.build_html_with_real_headings())
    _check_snapshot("html_real_headings", doc)
