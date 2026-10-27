"""W0u: a digit-range hyphen that pdftotext's dehyphenation removed is restored.

10.1111/jasp.12453 prints the reference page ranges ``(pp. 101-`` / ``125)``
(p24, Allen 1993) and ``pp. 1-`` / ``36)`` (p29, Sheeran 2002) across a line
end (rasterized 2026-10-27). pdftotext's default mode joins a line ending in a
hyphen to the next line and drops the hyphen, even between digits, so the text
channel says ``pp. 101125`` and ``pp. 136``: a wrong number with nothing to
show it. pdfplumber's words keep ``101-``.

The gate mirrors W0t: restore ``AB`` -> ``A-B`` only when the layout holds a
line-end fragment ``A-`` and a word opening with the digits ``B``, never holds
``AB`` as a digit run, and holds one fragment per restored site.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from docpluck.normalize import recover_numeric_range_hyphens_via_layout


def _layout(*words):
    page = SimpleNamespace(words=tuple({"text": w} for w in words))
    return SimpleNamespace(pages=(page,))


def test_glued_page_range_is_restored():
    text = "meta-analysis (pp. 101125). Dubuque, IA"
    lay = _layout("meta-analysis", "(pp.", "101-", "125).", "Dubuque,", "IA")
    n = [0]
    assert recover_numeric_range_hyphens_via_layout(text, lay, n) == (
        "meta-analysis (pp. 101-125). Dubuque, IA"
    )
    assert n[0] == 1


def test_one_digit_start_of_range_is_restored():
    text = "(Vol. 12, pp. 136). Chichester"
    lay = _layout("(Vol.", "12,", "pp.", "1-", "36).", "Chichester")
    assert recover_numeric_range_hyphens_via_layout(text, lay, None) == (
        "(Vol. 12, pp. 1-36). Chichester"
    )


def test_a_number_the_page_prints_glued_is_never_touched():
    text = "N = 101125 and pp. 101125"
    lay = _layout("N", "=", "101125", "pp.", "101-", "125")
    assert recover_numeric_range_hyphens_via_layout(text, lay, None) == text


def test_no_line_end_fragment_no_rewrite():
    text = "a sample of 101125 people"
    lay = _layout("a", "sample", "of", "101125", "people")
    assert recover_numeric_range_hyphens_via_layout(text, lay, None) == text


def test_more_glued_sites_than_fragments_is_refused():
    text = "pp. 101125 and again 101125"
    lay = _layout("pp.", "101-", "125")
    assert recover_numeric_range_hyphens_via_layout(text, lay, None) == text


def test_inside_a_doi_or_url_is_never_touched():
    text = "https://doi.org/10.1111/101125"
    lay = _layout("https://doi.org/10.1111/101-", "125")
    assert recover_numeric_range_hyphens_via_layout(text, lay, None) == text


def test_no_layout_is_a_no_op():
    assert recover_numeric_range_hyphens_via_layout("pp. 101125", None, None) == "pp. 101125"


def test_jasp_12453_reference_ranges_survive_the_render():
    from docpluck.render import render_pdf_to_markdown
    from docpluck.testing.corpus import custody_path

    p = custody_path("fulltext", "10.1111__jasp.12453.pdf")
    md = render_pdf_to_markdown(p.read_bytes())
    assert "pp. 101-125" in md
    assert "pp. 1-36" in md
    assert "101125" not in md
