"""Body lines that are text, not furniture, stay in the text.

Rasterised 2026-10-27:

* 10.1098/rsos.240120 p15 and p18 print body lines that wrap to open with
  "electronic supplementary material, ...". A case-insensitive pattern for the
  capitalised PMC footer "ELECTRONIC SUPPLEMENTARY MATERIAL" deleted them.
* 10.1037/a0012616 p1 prints "Correspondence concerning this article should be
  addressed to Richard / A. Bryant, School of Psychology, ...". P1 deleted the
  first line and stranded the address; it is now kept whole as a note.
"""
from __future__ import annotations

import pytest


def _render(key):
    from docpluck.testing.corpus import custody_path
    from docpluck.render import render_pdf_to_markdown
    p = custody_path("fulltext", key + ".pdf")
    if not p.is_file():
        pytest.skip(f"{key} not held")
    md = render_pdf_to_markdown(p.read_bytes())
    return md[0] if isinstance(md, tuple) else md


def test_body_line_opening_with_lowercase_esm_reference_is_kept():
    # 10.1098/rsos.240120 p15: a wrapped body line that opens "electronic
    # supplementary material, table S6), ..." was deleted as the PMC
    # "ELECTRONIC SUPPLEMENTARY MATERIAL" footer (case-insensitive match).
    from docpluck.normalize import _strip_page_footer_lines
    text = ("and archaeological bone samples show a wide range of variation;\n"
            "electronic supplementary material, table S6), but rather, our data show\n"
            "to which individuals specialized.\n")
    assert "table S6), but rather" in _strip_page_footer_lines(text)
    assert "ELECTRONIC SUPPLEMENTARY MATERIAL" not in _strip_page_footer_lines(
        "Body.\nELECTRONIC SUPPLEMENTARY MATERIAL\nMore.\n")


def test_real_correspondence_note_and_esm_lines_kept():
    md = _render("10.1037__a0012616")
    assert "Correspondence concerning this article should be addressed to Richard" in md
    md = _render("10.1098__rsos.240120")
    assert "table S6), but rather, our data show" in md
    assert "text 6, for more details). Statistical comparisons" in md
