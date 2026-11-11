"""A table footnote LETTER the layout proves raised is marked, not glued on.

10.1177/01461672251327169 p3 Table 1 header "Estimation error" carries a raised
footnote "a" (5.85 pt against the 9 pt word); p4 Table 2 hypotheses end
"well-being." + raised "a" and "subjective happiness." + raised "b". On 2.4.158
the cells read "Estimation errora" and "well-being.a" (canary re-audit
2026-10-31). They now use W0p's caret notation: "error^a", "well-being.^a".
"""
from __future__ import annotations

import pytest

from docpluck.testing.corpus import custody_path


@pytest.fixture(scope="module")
def ip_tables():
    from docpluck.extract_structured import extract_pdf_structured

    p = custody_path("fulltext", "10.1177__01461672251327169.pdf")
    return {t.get("label"): t for t in extract_pdf_structured(p.read_bytes())["tables"]}


def _cells(t) -> list[str]:
    return [c["text"] for c in t.get("cells") or []]


def test_table_1_header_letter_is_marked(ip_tables):
    cells = _cells(ip_tables["Table 1"])
    assert any(c.endswith("error^a") for c in cells), cells[:12]
    assert not any("errora" in c for c in cells)


def test_table_2_hypothesis_letters_are_marked(ip_tables):
    text = " ".join(_cells(ip_tables["Table 2"]))
    assert "well-being.^a" in text and "well-being.a" not in text
    assert "happiness.^b" in text and "happiness.b" not in text


def _glyphs(word: str, top: float, size: float = 9.0) -> list[dict]:
    return [{"text": ch, "size": size, "top": top, "upright": True} for ch in word]


def _layout(*runs):
    class _Page:
        pass

    class _Doc:
        pass

    page = _Page()
    page.chars = [g for run in runs for g in run]
    doc = _Doc()
    doc.pages = [page]
    return doc


def test_raised_letter_is_marked_in_cells():
    from docpluck.tables.cell_cleaning import _mark_raised_letter_markers

    layout = _layout(_glyphs(" error", 100.0), _glyphs("a", 99.0, 5.85), _glyphs(" x", 100.0))
    cells = [{"text": "Estimation errora"}]
    _mark_raised_letter_markers(cells, layout)
    assert cells[0]["text"] == "Estimation error^a"


def test_a_token_also_printed_as_an_ordinary_word_is_left_alone():
    from docpluck.tables.cell_cleaning import _mark_raised_letter_markers

    # "Item" + raised "s" once, and "Items" printed as a plain word elsewhere:
    # a cell's text cannot say which one it is.
    layout = _layout(
        _glyphs(" Item", 100.0), _glyphs("s", 99.0, 5.85),
        _glyphs(" Items ", 200.0),
    )
    cells = [{"text": "Items"}]
    _mark_raised_letter_markers(cells, layout)
    assert cells[0]["text"] == "Items"


def test_more_cell_copies_than_raised_sites_are_left_alone():
    from docpluck.tables.cell_cleaning import _mark_raised_letter_markers

    layout = _layout(_glyphs(" error", 100.0), _glyphs("a", 99.0, 5.85), _glyphs(" x", 100.0))
    cells = [{"text": "errora"}, {"text": "errora"}]
    _mark_raised_letter_markers(cells, layout)
    assert [c["text"] for c in cells] == ["errora", "errora"]


def test_pdf_without_space_glyphs_marks_every_letter():
    """10.1001/jamanetworkopen.2023.47449 p7 Table 3 emits no space glyphs, so
    words are bounded by x-gaps; before that, "Current age" + "NA" + raised "d"
    read as one word, the cell count (4) exceeded the layout count (3), and all
    four "NAd" cells stayed unmarked."""
    from docpluck.extract_structured import extract_pdf_structured
    from docpluck.testing.corpus import custody_path

    b = custody_path("fulltext", "10.1001__jamanetworkopen.2023.47449.pdf").read_bytes()
    t3 = next(t for t in extract_pdf_structured(b)["tables"] if t.get("label") == "Table 3")
    texts = [c.get("text") or "" for c in t3["cells"]]
    assert texts.count("NA^d") == 4 and "NA^c" in texts, texts
    assert any(x.endswith("No.^e") for x in texts) and any(x.endswith("baseline^f") for x in texts)
    assert "NAd" not in texts
