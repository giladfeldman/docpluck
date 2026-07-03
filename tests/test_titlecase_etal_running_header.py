"""Regression test for the Title-Case surname running-header strip (v2.4.114).

The independent Sonnet canary audit found efendic_2022_affect leaking its Sage
running header "Efendić et al." at 5 page breaks (the line arrives as
"\fEfendić et al."). The existing P0r pattern only stripped an ALL-CAPS
"SMITH et al." running header; a Title-Case surname was excluded because
"Smith et al." can be an inline citation.

Fix (v2.4.114): a P0r pattern that strips a Title-Case (mixed-case, accented)
surname + "et al." ONLY when it is the COMPLETE line with nothing after
"et al." — an inline citation always carries a "(YEAR)" or continues the
sentence, never a bare "Surname et al." alone on its own line.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("DOCPLUCK_DISABLE_CAMELOT", "1")

from docpluck.normalize import normalize_text, NormalizationLevel
from docpluck.render import render_pdf_to_markdown

TEST_PDFS = Path(__file__).resolve().parents[1].parent / "PDFextractor" / "test-pdfs"


def _normed(text: str) -> str:
    out, _ = normalize_text(text, NormalizationLevel.academic)
    return out


@pytest.mark.parametrize("hdr", [
    "\fEfendić et al.",
    "Efendić et al.",
    "Smith et al.",
    "van der Wal et al.",
    "\fGarcía Márquez et al.",
    "Chandrashekar et al",
])
def test_standalone_titlecase_etal_stripped(hdr):
    # A standalone running-header line is removed.
    text = f"Body paragraph one ends here.\n\n{hdr}\n\nBody paragraph two begins here."
    out = _normed(text)
    assert hdr.strip() not in out.split("\n")
    assert "Body paragraph one ends here." in out
    assert "Body paragraph two begins here." in out


@pytest.mark.parametrize("line", [
    "as shown by Efendić et al., 2022, this holds across conditions.",
    "Efendić et al. (2022) found that risks and benefits are related.",
    "consistent with Smith et al. (2020) and later work.",
    "We replicate Efendić et al. and extend it to a new domain.",
    "This finding (Efendić et al., 2021) is robust.",
    "In their seminal work, Finucane et al. (2000) proposed the affect heuristic.",
])
def test_inline_citation_preserved(line):
    # An inline citation (year / parens / continuing sentence) is NEVER stripped.
    text = f"Prior text.\n\n{line}\n\nMore text."
    out = _normed(text)
    assert line in out


def test_efendic_running_header_stripped_real_pdf():
    pdf = TEST_PDFS / "apa" / "efendic_2022_affect.pdf"
    if not pdf.exists():
        pytest.skip(f"fixture missing: {pdf}")
    md = render_pdf_to_markdown(pdf.read_bytes())
    import re
    # No standalone "Efendić et al." running-header line survives.
    assert not re.search(r"(?m)^\f?Efendić et al\.\s*$", md)
