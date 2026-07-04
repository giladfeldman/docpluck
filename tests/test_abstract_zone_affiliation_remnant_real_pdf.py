"""Regression test for the abstract-zone affiliation-remnant strip (v2.4.115).

chandrashekar_2023_mp rendered "Department of Philosophy, Lake Forest College" +
"*Joint first authors" right after the "## Abstract" heading, before the abstract
body. The masthead strip stops AT "## Abstract" (so it caught the other two
affiliations, which precede the heading), and the >=3-line body-affiliation strip
could not reach a single surviving affiliation line — the section partitioner had
inserted "## Abstract" mid-affiliation-block, orphaning the last one.

Fix (v2.4.115): `_strip_abstract_zone_affiliation_remnant` removes an affiliation
line (+ companion note) that is the FIRST non-blank content after "## Abstract".
A real Abstract opens with PROSE, so an affiliation LINE in that slot is
unambiguously a boundary-split front-matter remnant. An abstract that merely
MENTIONS a university mid-sentence is prose (not an affiliation line) and is kept.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("DOCPLUCK_DISABLE_CAMELOT", "1")

from docpluck.render import (
    _strip_abstract_zone_affiliation_remnant,
    render_pdf_to_markdown,
)

TEST_PDFS = Path(__file__).resolve().parents[1].parent / "PDFextractor" / "test-pdfs"


def test_chandrashekar_affiliation_not_in_abstract():
    pdf = TEST_PDFS / "apa" / "chandrashekar_2023_mp.pdf"
    if not pdf.exists():
        pytest.skip(f"fixture missing: {pdf}")
    md = render_pdf_to_markdown(pdf.read_bytes())
    lines = md.split("\n")
    ai = next((i for i, ln in enumerate(lines) if ln.strip() == "## Abstract"), None)
    assert ai is not None, "## Abstract heading missing"
    zone = "\n".join(lines[ai:ai + 6])
    # The affiliation + joint-authors companion must NOT be in the abstract zone.
    assert "Department of Philosophy, Lake Forest College" not in zone
    assert "*Joint first authors" not in zone
    # The abstract body prose is intact and is the first content after the heading.
    assert "People tend to stick with a default option" in md


def test_remnant_stripped_unit():
    text = (
        "## Abstract\n\n"
        "Department of Philosophy, Lake Forest College\n"
        "*Joint first authors\n"
        "People tend to stick with a default option instead of switching.\n\n"
        "## Keywords\n"
    )
    out = _strip_abstract_zone_affiliation_remnant(text)
    assert "Lake Forest College" not in out
    assert "Joint first authors" not in out
    assert "People tend to stick" in out
    assert "## Abstract" in out


def test_real_abstract_untouched():
    # Prose immediately after ## Abstract → nothing stripped.
    text = (
        "## Abstract\n\n"
        "We conducted three studies examining the effect of framing on choice.\n\n"
        "## Keywords\n"
    )
    assert _strip_abstract_zone_affiliation_remnant(text) == text


def test_abstract_that_mentions_a_university_untouched():
    # A university MENTION inside abstract prose is not an affiliation line.
    text = (
        "## Abstract\n\n"
        "Data were collected at the University of Hong Kong and analysed centrally.\n\n"
        "## Keywords\n"
    )
    out = _strip_abstract_zone_affiliation_remnant(text)
    assert out == text
    assert "Data were collected at the University of Hong Kong" in out
