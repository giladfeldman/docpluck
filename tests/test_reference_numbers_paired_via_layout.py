"""Reference numbers set in a column of their own are paired with the entry
they are printed beside, never with the Nth text line.

10.1098/rsos.240120 pp20-24 (rasterised 2026-10-27): each page sets the
numbers 1-119 in a left column. pdftotext streams them as a block of bare
``N.`` lines apart from the entries, and the entries' wrapped lines start with
capitals ("Ecol. Prog. Ser. 583", "Ocean Turtle Newsletter 31"), so pairing
number N with the Nth capitalised line renumbered the list from entry 4 on
("4. Ecol. Prog. Ser."), merged 19-24 and left 25-83 as runs of bare numbers.
The layout says which line each number sits on.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from docpluck.normalize import _pair_reference_numbers_via_layout


def _w(text, x0, top):
    return {"text": text, "x0": x0, "x1": x0 + 6.0 * len(text), "top": top}


def _layout():
    words = [
        _w("1.", 55, 100), _w("Haywood", 75, 100), _w("JC,", 125, 100),
        _w("us", 75, 112), _w("understand", 95, 112),
        _w("2.", 55, 124), _w("Pearson", 75, 124), _w("R,", 125, 124),
        _w("Ecol.", 75, 136), _w("Prog.", 110, 136),
        _w("3.", 55, 148), _w("Carr", 75, 148), _w("AF,", 110, 148),
        _w("article", 75, 160),
        _w("1.", 75, 172),
        _w("4.", 55, 184), _w("Carr", 75, 184), _w("A.", 110, 184),
    ]
    return SimpleNamespace(pages=(SimpleNamespace(words=tuple(words)),))


TEXT = ("References\n1.\n2.\n3.\n4.\n\n"
        "Haywood JC, Fuller WJ. 2019 Global review\n"
        "us understand ecology. Mar. Ecol.\n"
        "Pearson R, Limpus C. 2017 Realignment. Mar.\n"
        "Ecol. Prog. Ser. 583, 259-271.\n"
        "Carr AF, Carr MH. 1978 The ecology. Bull. AMNH 162, article\n"
        "1.\n"
        "Carr A. 1956 The windward road.\n")


def test_numbers_attach_to_the_lines_they_sit_beside():
    out, n = _pair_reference_numbers_via_layout(TEXT, _layout())
    assert n == 4
    lines = [ln for ln in out.split("\n") if ln.strip()]
    assert "1. Haywood JC, Fuller WJ. 2019 Global review" in lines
    assert "2. Pearson R, Limpus C. 2017 Realignment. Mar." in lines
    assert "Ecol. Prog. Ser. 583, 259-271." in lines          # a wrapped line, unnumbered
    assert "3. Carr AF, Carr MH. 1978 The ecology. Bull. AMNH 162, article" in lines
    assert "1." in lines                                       # entry 3's wrapped "article 1." stays
    assert "4. Carr A. 1956 The windward road." in lines


def test_no_layout_or_no_number_column_is_a_noop():
    assert _pair_reference_numbers_via_layout(TEXT, None) == (TEXT, 0)
    plain = "References\nSmith J. 2001 A title.\nJones K. 2002 Another.\n"
    assert _pair_reference_numbers_via_layout(plain, _layout()) == (plain, 0)


def test_real_rsos_reference_list_is_numbered_by_the_page():
    from docpluck.testing.corpus import custody_path
    from docpluck.render import render_pdf_to_markdown
    p = custody_path("fulltext", "10.1098__rsos.240120.pdf")
    if not p.is_file():
        pytest.skip("10.1098/rsos.240120 not held")
    md = render_pdf_to_markdown(p.read_bytes())
    md = md[0] if isinstance(md, tuple) else md
    refs = md[md.index("## References"):]
    lines = refs.split("\n")
    assert any(ln.startswith("4. Seminoff JA, Phillott AD. 2020") for ln in lines)
    assert any(ln.startswith("25. Trubek AB. 2001") for ln in lines)
    assert any(ln.startswith("57. Avens L, Goshe") for ln in lines)
    assert any(ln.startswith("119. Guiry EJ, Szpak") for ln in lines)
    assert any(ln.startswith("99. de Kock W et al. 2023") for ln in lines)
    assert not any(ln.startswith("4. Ecol. Prog. Ser.") for ln in lines)
    # No line is a run of bare numbers any more.
    import re
    assert not any(re.fullmatch(r"(?:\d{1,3}\.\s*){3,}", ln.strip()) for ln in lines)


def test_next_numbered_entry_with_lowercase_author_is_not_merged():
    from docpluck.normalize import NormalizationLevel, normalize_text
    text = ("Body text of the article ends here.\n\nReferences\n"
            "1. Smith AB. 2001 A first title. J. Biol. 1, 1-2.\n"
            "2. Jones CD. 2002 A second title that wraps onto\n"
            "a second line. J. Biol. 2, 3-4.\n"
            "3. de Kock W et al. 2023 A third title. Proc. Natl Acad. Sci. 120, 5.\n"
            "4. Brown EF. 2004 A fourth title. J. Biol. 4, 7-8.\n")
    out, _ = normalize_text(text, NormalizationLevel.academic)
    lines = out.split("\n")
    assert "3. de Kock W et al. 2023 A third title. Proc. Natl Acad. Sci. 120, 5." in lines, lines
    assert any(ln.startswith("2. Jones CD. 2002 A second title that wraps onto a second line.") for ln in lines)
