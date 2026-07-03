"""Regression test for Sage / APA back-matter heading promotion (v2.4.105).

The cycle-1 canary AI-verify (2026-07-03) found ip_feldman_2025_pspb rendering
three back-matter headings as plain body text — "Authorship Declaration",
"Declaration of Conflicting Interests", and "ORCID iDs" — while their siblings
("Acknowledgments", "Author Contributions", "Funding") rendered as `##`. The
distinguishing structural feature: the demoted headings immediately precede
their paragraph with no blank line (Sage PSPB back-matter typography), so only
canonical-heading recognition (not the line-isolated fallback, which needs the
heading on its own line) can promote them — and these three variants were
missing from the taxonomy.

Fix (v2.4.105): add the Sage / APA wordings to `docpluck/sections/taxonomy.py`
("declaration of conflicting interests" → conflict_of_interest, "authorship
declaration" → author_contributions, "orcid ids" → author_note). Only the plural
"orcid ids" heading form is canonical — a bare/singular/inline "ORCID:" is not,
to avoid false-matching a line-leading identifier.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("DOCPLUCK_DISABLE_CAMELOT", "1")

from docpluck.render import render_pdf_to_markdown

TEST_PDFS = Path(__file__).resolve().parents[1].parent / "PDFextractor" / "test-pdfs"


def test_ip_feldman_backmatter_headings_promoted():
    """The three previously-demoted back-matter headings must render as `##`,
    not as plain body text."""
    pdf = TEST_PDFS / "apa" / "ip_feldman_2025_pspb.pdf"
    if not pdf.exists():
        pytest.skip(f"fixture missing: {pdf}")
    md = render_pdf_to_markdown(pdf.read_bytes())
    for heading in (
        "Authorship Declaration",
        "Declaration of Conflicting Interests",
        "ORCID iDs",
    ):
        assert f"## {heading}" in md, f"{heading!r} not promoted to a heading"
        # And it must NOT appear as a bare body line (the demoted form).
        assert f"\n{heading}\n" not in md, f"{heading!r} still rendered as body text"


def test_ip_feldman_inline_orcid_not_promoted():
    """An inline "(ORCID: 0000-…)" mention inside the Acknowledgments paragraph
    must stay body text — only the standalone "ORCID iDs" heading is promoted."""
    pdf = TEST_PDFS / "apa" / "ip_feldman_2025_pspb.pdf"
    if not pdf.exists():
        pytest.skip(f"fixture missing: {pdf}")
    md = render_pdf_to_markdown(pdf.read_bytes())
    # The inline identifier line must not have become a heading.
    assert "## ORCID: 0000" not in md
    assert "(ORCID: 0000-0002-1305-0547)" in md  # preserved inline in Acknowledgments
