"""Real-corpus integration tests. Skipped when test PDFs aren't present."""

import os

import pytest

from .conftest import requires_pdftotext, pdf_path

pytest.importorskip("pdfplumber")


@requires_pdftotext
def test_li_feldman_rsos():
    path = pdf_path("docpluck", "Li&Feldman-2025-RSOS-...-print.pdf")
    if not path or not os.path.exists(path):
        pytest.skip("Li&Feldman RSOS PDF not available")
    from docpluck import extract_sections
    with open(path, "rb") as f:
        doc = extract_sections(f.read())
    # Universal coverage holds.
    total = sum(s.char_end - s.char_start for s in doc.sections)
    assert total >= len(doc.normalized_text) - 8  # allow sentinel tolerance
    # References section is present and substantive.
    refs = doc.references
    assert refs is not None
    assert len(refs.text) > 1000
    # Abstract is present.
    assert doc.abstract is not None


@requires_pdftotext
def test_escicheck_pdfs_smoke():
    base = os.environ.get("DOCPLUCK_ESCICHECK_PDFS")
    if not base or not os.path.isdir(base):
        pytest.skip("ESCIcheck PDFs not available")
    from docpluck import extract_sections
    files = sorted(p for p in os.listdir(base) if p.lower().endswith(".pdf"))[:5]
    if not files:
        pytest.skip("No PDFs found in ESCIcheck dir")
    for fn in files:
        with open(os.path.join(base, fn), "rb") as f:
            doc = extract_sections(f.read())
        # Smoke: every PDF should produce ≥3 sections.
        assert len(doc.sections) >= 3, f"{fn}: only {len(doc.sections)} sections"
