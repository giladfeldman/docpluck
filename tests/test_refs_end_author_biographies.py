"""An "Author Biographies" block ends the reference list.

SAGE journals (SPPS, PSPB) print author biographies straight after the last
reference. The academic-level reference join (R3) merges every line inside the
detected bibliography span into its entry, and the span ran to the next
``_REFS_END`` heading or to the end of the document. "Author Biographies" was
not one of those headings, so the heading and the first biography were glued
onto the last reference:

    ... https://doi.org/10.1111/ jcom.12071 Author Biographies Emir Efendić is ...

It surfaced in 2.4.155 because the column reorder put the heading where it is
printed, right after the references (10.1177/19485506211056761, p12).
"""

from __future__ import annotations

import pytest

from docpluck.normalize import NormalizationLevel, normalize_text
from docpluck.testing import require_corpus_pdf

_REFS = (
    "References\n"
    "Alpha, A., & Beta, B. (2001). A first title. Journal of Things, 1(2), 3-4.\n"
    "Gamma, C. (2002). A second title that wraps onto\n"
    "a second line. Journal of Things, 5(6), 7-8.\n"
    "Delta, D., & Eps, E. (2003). A third title. Journal of Things, 9(1), 10-11.\n"
    "Zeta, Z. (2004). The last title. Journal of Things, 12(3), 13-14.\n"
    "https://doi.org/10.1111/\n"
    "jcom.12071\n"
    "\n"
)


@pytest.mark.parametrize(
    "heading",
    ["Author Biographies", "Author Biography", "Authors' Biographies", "About the Authors"],
)
def test_biography_heading_stays_out_of_the_last_reference(heading):
    text = _REFS + heading + "\nFirst Author is a postdoctoral scholar at a university.\n"
    out, _ = normalize_text(text, NormalizationLevel.academic)
    lines = [ln.strip() for ln in out.splitlines()]
    assert heading in lines, out
    last_ref = next(ln for ln in lines if ln.startswith("Zeta, Z."))
    assert heading not in last_ref and "postdoctoral" not in last_ref, last_ref


def test_wrapped_reference_is_still_joined():
    # control: the join R3 exists for still happens inside the span
    out, _ = normalize_text(_REFS + "Author Biographies\nX is a scholar.\n", NormalizationLevel.academic)
    assert "A second title that wraps onto a second line." in out, out


def test_efendic_biographies_heading_survives_the_reference_join():
    from docpluck.extract import extract_pdf

    pdf = require_corpus_pdf("apa/efendic_2022_affect.pdf")
    text, _method = extract_pdf(pdf.read_bytes())
    out, _ = normalize_text(text, NormalizationLevel.academic)
    i = out.find("jcom.12071")
    assert i >= 0
    tail = out[i : i + 200]
    assert "Author Biographies" in tail, tail
    assert "jcom.12071 Author Biographies" not in tail, tail
