"""Real-corpus integration tests."""

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
    """Every ESCIcheck replication report yields at least 3 sections.

    REPOINTED 2026-09-25. This read ``$DOCPLUCK_ESCICHECK_PDFS`` -- a folder in a
    sibling project -- took the first five files a directory listing returned,
    and SKIPPED when the variable was unset or the folder absent. The folder was
    retired into the article custodian on 2026-08-28, so from then on the test
    never ran, and no run shows how long before that the variable was set at all.

    The set is now the ``escicheck/`` group of the committed corpus manifest:
    the ESCIcheck regression papers that are published articles held by DOI (22;
    ``apa/korbmacher_2022_kruger.pdf`` was one too and stays under ``apa/``).
    ``corpus_pdfs`` raises when any of them does not resolve, so a missing paper
    FAILS, and the denominator cannot shrink without a diff.
    """
    from docpluck import extract_sections
    from docpluck.testing import corpus_names, corpus_pdfs

    names = corpus_names("escicheck")
    pdfs = corpus_pdfs("escicheck")  # raises if any of them does not resolve
    assert len(pdfs) >= 20, f"escicheck group holds only {len(pdfs)} papers"
    thin = []
    for name, pdf in zip(names, pdfs):
        doc = extract_sections(pdf.read_bytes())
        if len(doc.sections) < 3:
            thin.append(f"{name}: only {len(doc.sections)} sections")
    assert not thin, (
        f"{len(thin)}/{len(pdfs)} papers under 3 sections:\n" + "\n".join(thin)
    )
