"""The upright whitespace grid keeps the word spaces the page prints.

10.1001/jamanetworkopen.2023.39337 draws no space glyphs, and pdfplumber's
``extract_words()`` (a fixed 3pt x-tolerance) runs a line's words together, so
the whitespace grid delivered ``Table1.BaselineCharacteristicsoftheStudy...`` and
``Non-HispanicWhite`` (Table 1, p6). On that line consecutive glyphs sit either
<= 0.01 font sizes apart (inside a word) or 0.18 apart (a word space). The
rotated path already splits at ``whitespace.WORD_GAP_RATIO`` of the font size;
the upright cell text now does the same.
"""
from __future__ import annotations

import re

import pytest

from docpluck.testing.corpus import custody_path


@pytest.fixture(scope="module")
def jama_tables_camelot_off():
    import os

    from docpluck.extract_structured import extract_pdf_structured

    prior = os.environ.get("DOCPLUCK_DISABLE_CAMELOT")
    os.environ["DOCPLUCK_DISABLE_CAMELOT"] = "1"
    try:
        p = custody_path("fulltext", "10.1001__jamanetworkopen.2023.39337.pdf")
        return extract_pdf_structured(p.read_bytes())["tables"]
    finally:
        if prior is None:
            os.environ.pop("DOCPLUCK_DISABLE_CAMELOT", None)
        else:
            os.environ["DOCPLUCK_DISABLE_CAMELOT"] = prior


def test_table1_words_are_not_glued(jama_tables_camelot_off):
    t1 = next(t for t in jama_tables_camelot_off if t.get("label") == "Table 1")
    assert t1.get("cell_geometry") == "whitespace_native"
    text = " | ".join(c["text"] for c in t1["cells"])
    assert "Baseline Characteristics of the Study" in text
    assert "Non-Hispanic White" in text
    assert not re.search(r"BaselineCharacteristics|Non-HispanicWhite|oftheStudy", text)


def test_no_character_is_lost_or_added(jama_tables_camelot_off):
    # Only spaces may change: the non-space characters of every cell are the same
    # multiset the glued version carried (pinned on two known cells).
    t1 = next(t for t in jama_tables_camelot_off if t.get("label") == "Table 1")
    squeezed = {re.sub(r"\s+", "", c["text"]) for c in t1["cells"]}
    assert "Table1.BaselineCharacteristicsoftheStudyParticipantsa" in squeezed


def test_spacing_does_not_change_which_grids_are_kept():
    """The gates judge the squeezed text; spacing is applied after them. Judged
    on the spaced text, 10.5465/amle.2017.0488 lost six whitespace grids
    (Tables 2, 3, 8, 9, 11, 12) with Camelot off."""
    import os

    from docpluck.extract_structured import extract_pdf_structured

    prior = os.environ.get("DOCPLUCK_DISABLE_CAMELOT")
    os.environ["DOCPLUCK_DISABLE_CAMELOT"] = "1"
    try:
        p = custody_path("fulltext", "10.5465__amle.2017.0488.pdf")
        tables = extract_pdf_structured(p.read_bytes())["tables"]
    finally:
        if prior is None:
            os.environ.pop("DOCPLUCK_DISABLE_CAMELOT", None)
        else:
            os.environ["DOCPLUCK_DISABLE_CAMELOT"] = prior
    by = {t.get("label"): t for t in tables}
    for label in ("Table 2", "Table 3"):
        t = by[label]
        assert t.get("cells"), label
        assert t.get("cell_geometry") == "whitespace_native", label
