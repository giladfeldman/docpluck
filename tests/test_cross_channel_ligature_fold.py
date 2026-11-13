"""Every comparison between the table channel and the text channel folds ligatures (d-58ce8d class).

pdftotext keeps U+FB01/U+FB00 ("ﬁ", "ﬀ") where Camelot's pdfminer and pdfplumber spell
the letters out, so an equality test between the two channels failed on every
ligature word. A sweep on 2026-11-13 found the same unfolded comparison at six
more sites besides the running-text check; one test per site. Each failed on v2.4.159.
"""
from __future__ import annotations

from docpluck.extract_structured import (
    _caption_overlap_tokens,
    _grid_covers_little_of_printed_table,
    _rows_survive_in,
)
from docpluck.normalize import _key as f0_key
from docpluck.tables.caption_rows import _caption_rows_at_top, _closes_the_caption
from docpluck.tables.flatten import _alnum_key

FI, FF = "ﬁ", "ﬀ"


def test_partial_grid_guard_counts_ligature_words():
    words_text = [f"{FI}xed", f"{FI}rst", f"e{FF}ect", f"de{FI}ned", f"o{FF}set", f"{FI}eld"]
    words_grid = ["fixed", "first", "effect", "defined", "offset", "field"]
    body = "\n".join(" ".join(words_text) for _ in range(8))
    grid = {"cells": [{"r": i, "c": 0, "text": " ".join(words_grid)} for i in range(8)]}
    assert not _grid_covers_little_of_printed_table(grid, body)


def test_caption_tokens_match_across_ligature():
    assert "significant" in _caption_overlap_tokens(f"Signi{FI}cant e{FF}ects of condition")
    assert "effects" in _caption_overlap_tokens(f"Signi{FI}cant e{FF}ects of condition")


def test_note_rows_survive_across_ligature():
    assert _rows_survive_in(["Note. Coefficients are", "fixed effects."],
                            f"Note. Coe{FF}icients are {FI}xed e{FF}ects.")


def test_caption_row_key_folds_ligature():
    assert _alnum_key(f"De{FI}nition") == "definition"


def test_caption_tail_closes_caption_across_ligature():
    assert _closes_the_caption([["Outcomes by definition."]], f"Table 3. Outcomes by de{FI}nition.")


def test_caption_rows_at_top_strips_ligature_caption():
    rows = [["Table 3"], ["Effects of the first manipulation on the outcome measures"], ["Measure", "M", "SD"]]
    cap = f"E{FF}ects of the {FI}rst manipulation on the outcome measures"
    assert _caption_rows_at_top(rows, "Table 3", cap) == 2


def test_f0_key_matches_layout_spelling():
    assert f0_key(f"Journal of E{FF}ective Signi{FI}cance") == f0_key("Journal of Effective Significance")
