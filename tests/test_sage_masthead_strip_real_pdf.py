"""Regression test for the Sage volume/issue + ©-glyph masthead markers (v2.4.113).

The independent Sonnet canary audit found efendic_2022_affect leaking its Sage
masthead between the H1 title and `## Abstract`:
  Social Psychological and / Personality Science / 2022, Vol. 13(7) 1173-1184 /
  Ó The Author(s) 2021 / <author byline>
`_strip_frontmatter_masthead_block` fires only with >=2 hard markers, but three
Sage-specific shapes were missing from `_looks_like_masthead_hard_marker`:
  - the journal volume/issue/page line "2022, Vol. 13(7) 1173-1184" (the bare
    NN-NN page-range pattern didn't match the "<year>, Vol. <v>(<i>)" prefix);
  - the copyright line "Ó The Author(s) 2021" — © glyph-corrupted to "Ó";
  - the author byline with a "*" corresponding-author mark + trailing comma.

Fix (v2.4.113): add `_MASTHEAD_VOL_ISSUE_RE`, broaden `_MASTHEAD_COPYRIGHT_RE` to
the ©-glyph-corruption forms, and relax `_MASTHEAD_AUTHOR_SUPERSCRIPT_RE`. Only
two of these need to match for the strip to fire, so the whole Sage masthead zone
(including the byline) is removed.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("DOCPLUCK_DISABLE_CAMELOT", "1")

from docpluck.render import _looks_like_masthead_hard_marker, render_pdf_to_markdown

TEST_PDFS = Path(__file__).resolve().parents[1].parent / "PDFextractor" / "test-pdfs"


def test_sage_masthead_markers_detected():
    assert _looks_like_masthead_hard_marker("2022, Vol. 13(7) 1173-1184")
    assert _looks_like_masthead_hard_marker("2021, Vol. 12(5) 800-812")
    assert _looks_like_masthead_hard_marker("Ó The Author(s) 2021")
    assert _looks_like_masthead_hard_marker("© The Author(s) 2023")


def test_non_masthead_lines_not_marked():
    # Body prose / headings that superficially contain digits must NOT be markers.
    for s in (
        "We ran three studies in 2021 and 2022 with 1184 participants.",
        "The effect held across studies 1 to 3.",
        "Table 3. Regression coefficients for the 2022 sample.",
        "participants rated items on a 1-7 scale",
        "Results",
        "This finding replicates Smith (2021).",
    ):
        assert not _looks_like_masthead_hard_marker(s), f"false marker: {s!r}"


def test_efendic_masthead_stripped():
    """efendic renders H1 immediately followed by `## Abstract` — no Sage
    masthead furniture in between."""
    pdf = TEST_PDFS / "apa" / "efendic_2022_affect.pdf"
    if not pdf.exists():
        pytest.skip(f"fixture missing: {pdf}")
    md = render_pdf_to_markdown(pdf.read_bytes())
    # The masthead lines must be gone from the H1→Abstract zone.
    assert "Social Psychological and\nPersonality Science" not in md
    assert "2022, Vol. 13(7) 1173-1184" not in md
    assert "Ó The Author(s) 2021" not in md
    # H1 and Abstract both still present.
    assert "# Risky Therefore Not Beneficial" in md
    assert "## Abstract" in md
