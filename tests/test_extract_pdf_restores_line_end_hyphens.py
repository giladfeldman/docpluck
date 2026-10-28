"""extract_pdf restores a real hyphen pdftotext dropped at a line end.

pdftotext's default mode joins a line ending in ``-`` to the next line and drops
the hyphen, even when it is a real one: 10.1080/02699931.2024.2434156 prints
``Self-`` / ``Compassion`` and ``self-`` / ``esteem`` in two reference titles
(p22-24) and the text said ``SelfCompassion`` and ``selfesteem``;
10.1177/01461672251327169 p10 prints the heading ``Well-`` / ``Being`` and the
text said ``WellBeing``; 10.1111/jasp.12453 prints ``pp. 101-`` / ``125``.

W0t / W0u repaired these from the pdfplumber layout, but only on the paths that
compute one (render, sections, batch). A caller of ``extract_pdf`` followed by a
plain ``normalize_text(text)`` -- the hosted text endpoint among them -- got
neither. ``extract_pdf`` now reads the page's own words from ``pdftotext -bbox``
(one more pdftotext pass over the same file; the words keep the line-end
fragment ``Self-``) and runs the same two document-level gates on its text.
"""
from __future__ import annotations

import pytest

from docpluck.extract import extract_pdf


def _pdf(name: str) -> bytes:
    from docpluck.testing.corpus import custody_path

    return custody_path("fulltext", name).read_bytes()


def test_bbox_html_is_read_into_per_page_words():
    from docpluck.extract import _bbox_word_layout

    html = (
        '<doc>\n<page width="612" height="792">\n'
        '<word xMin="1" yMin="1" xMax="2" yMax="2">Self-</word>\n'
        '<word xMin="1" yMin="3" xMax="2" yMax="4">Compassion&amp;co</word>\n'
        '</page>\n<page width="612" height="792">\n'
        '<word xMin="1" yMin="1" xMax="2" yMax="2">101-</word>\n'
        "</page>\n</doc>\n"
    )
    lay = _bbox_word_layout(html)
    assert [[w["text"] for w in p.words] for p in lay.pages] == [
        ["Self-", "Compassion&co"],
        ["101-"],
    ]


def test_compound_hyphens_at_line_ends_survive_extract_pdf():
    text, _ = extract_pdf(_pdf("10.1080__02699931.2024.2434156.pdf"))
    assert "Self-Compassion and forgiveness" in text
    assert "SelfCompassion" not in text
    assert "selfesteem" not in text


def test_heading_compound_survives_extract_pdf():
    text, _ = extract_pdf(_pdf("10.1177__01461672251327169.pdf"))
    assert "WellBeing" not in text
    assert "Associations with Well-Being (Replication)" in text


def test_page_range_hyphen_survives_extract_pdf():
    text, _ = extract_pdf(_pdf("10.1111__jasp.12453.pdf"))
    assert "pp. 101-125" in text
    assert "101125" not in text


def test_opt_out_returns_pdftotexts_join():
    text, _ = extract_pdf(
        _pdf("10.1080__02699931.2024.2434156.pdf"), restore_line_end_hyphens=False
    )
    assert "SelfCompassion" in text


def test_extract_pdf_restores_a_doi_hyphen_at_a_line_end():
    # 10.1001/jamanetworkopen.2023.39337 p11 ref 5 prints "10.3233/NHA-" / "170036";
    # plain-text callers (no layout) must get the printed DOI, not the glued one.
    from docpluck import extract_pdf
    from docpluck.testing.corpus import custody_path

    p = custody_path("fulltext", "10.1001__jamanetworkopen.2023.39337.pdf")
    text, _ = extract_pdf(p.read_bytes())
    assert "10.3233/NHA-170036" in text
    assert "10.3233/NHA170036" not in text
