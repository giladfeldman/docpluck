"""Regression test for G16 — Page-header leak inside equation regions.

The TRIAGE_2026-05-14_phase_5d_gold_audit (Tier S2 / G16) observed that
ieee_access_2.pdf rendered equation ``(2)`` as ``Page 4 (2)`` — the
``Page 4`` running-header line from pdftotext was fused with the
equation number directly below it.

Investigation at v2.4.31 (cycle 15e):
  - pdftotext output still contains ``L et al.\n\nPage 4\n\nAuthor Manuscript\n\ndI\n= βSI ...``
  - The rendered .md emits ``(2)`` cleanly with no ``Page 4`` prefix.
  - Verified across 6 IEEE papers: 0 ``Page N`` leaks near equation numbers.

The leak was incidentally closed by some combination of v2.4.29's
preserve_math_glyphs + NFC composition + section-partitioning shifts
between v2.4.27 and v2.4.31. This regression test locks the absence
in place so a future normalize / section change can't silently
re-introduce it.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest


os.environ.setdefault("DOCPLUCK_DISABLE_CAMELOT", "1")


TEST_PDFS = Path(__file__).resolve().parents[1].parent / "PDFextractor" / "test-pdfs"


# Captures the exact failure mode from G16: ``Page <N>`` immediately
# (allowing surrounding blank lines) preceding or following an equation
# number ``(<N>)`` on its own line. Also catches the inline variant
# ``Page <N> (<N>)`` in case a future change collapses the vertical
# layout.
_PAGE_NEAR_EQNUM_RE = re.compile(
    r"^Page \d+\s*\n+\s*\(\d+\)|"  # Page N \n (N)
    r"\(\d+\)\s*\n+\s*Page \d+|"   # (N) \n Page N
    r"Page \d+\s+\(\d+\)",         # Page N (N) inline
    re.MULTILINE,
)


@pytest.mark.skipif(
    not (TEST_PDFS / "ieee" / "ieee_access_2.pdf").exists(),
    reason="ieee_access_2.pdf fixture not present",
)
def test_ieee_access_2_no_page_header_near_equation_numbers():
    """G16 regression — ieee_access_2.pdf had ``Page 4`` fused with eq ``(2)``."""
    from docpluck.render import render_pdf_to_markdown

    pdf = TEST_PDFS / "ieee" / "ieee_access_2.pdf"
    md = render_pdf_to_markdown(pdf.read_bytes())
    hits = _PAGE_NEAR_EQNUM_RE.findall(md)
    assert not hits, (
        f"G16 regression: found Page-header leak near equation numbers in "
        f"ieee_access_2.pdf rendered output: {hits}"
    )


@pytest.mark.parametrize(
    "pdf_stem",
    [
        "ieee_access_2",
        "ieee_access_3",
        "ieee_access_4",
        "ieee_access_5",
        "ieee_access_6",
    ],
)
def test_ieee_engineering_corpus_no_page_header_near_equation_numbers(pdf_stem):
    """Corpus-level G16 invariant across the IEEE engineering papers."""
    pdf = TEST_PDFS / "ieee" / f"{pdf_stem}.pdf"
    if not pdf.exists():
        pytest.skip(f"{pdf_stem}.pdf fixture not present")
    from docpluck.render import render_pdf_to_markdown
    md = render_pdf_to_markdown(pdf.read_bytes())
    hits = _PAGE_NEAR_EQNUM_RE.findall(md)
    assert not hits, (
        f"G16 regression on {pdf_stem}: found Page-header near equation "
        f"numbers: {hits[:3]}"
    )
