"""Real-corpus integration tests."""

import os

import pytest

from .conftest import requires_pdftotext

pytest.importorskip("pdfplumber")


# RETIRED 2026-09-17: `test_li_feldman_rsos` is gone, and this note is its record.
#
# It named `Li&Feldman-2025-RSOS-...-print.pdf` -- a filename carrying a LITERAL
# `...` where the rest of the title had been elided. No such file exists and none
# can, so the test could never resolve and never ran; it skipped, which reads as
# "the corpus is incomplete" rather than "this check has never executed once".
#
# It is retired rather than repointed because repointing a regression test at the
# nearest similar file is a decision, not a typo fix, and would silently change
# what the test measures. Searched the custodian for the real paper: six Li/Feldman
# RSOS registered reports are held (10.1098/rsos.240687, .250441, .250508, .250908
# among them) and nothing identifies WHICH one this was.
#
# Nothing measurable is lost. Its three assertions -- universal section coverage, a
# substantive references section, a present abstract -- are exercised by the
# corpus-backed section tests over all 101 papers, which do run.
#
# TO RESTORE: identify the paper by DOI, confirm it is in custody, and write the
# test against `require_corpus_pdf("<subdir>/<name>.pdf")` so a miss FAILS.


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
