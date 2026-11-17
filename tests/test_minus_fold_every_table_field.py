"""U+2212 is folded to '-' in EVERY text field a table or figure hands a
consumer (hard rule: always normalize U+2212).

The first version of `_fold_unicode_minus` (2026-11-16) folded cells, html and
raw_text only; the Release B consult (Sonnet + Haiku) found caption, footnote
and header_text_below_caption outside it, and figures were never folded.
"""
from __future__ import annotations

from docpluck.extract_structured import _fold_unicode_minus

M = "−"


def test_every_string_field_of_a_table_is_folded():
    t = {
        "label": "Table 8",
        "caption": f"Correlations (r = {M}.28)",
        "footnote": f"Note. {M}0.42 to 0.30.",
        "header_text_below_caption": f"r {M}.11",
        "html": f"<td>{M}.43</td>",
        "raw_text": f"{M}.05",
        "cells": [{"r": 0, "c": 0, "text": f"{M}.11"}],
        "n_rows": 1,
    }
    _fold_unicode_minus(t)
    for key, val in t.items():
        if isinstance(val, str):
            assert M not in val, key
    assert t["cells"][0]["text"] == "-.11"
    assert t["caption"] == "Correlations (r = -.28)"
    assert t["n_rows"] == 1


def test_a_figure_caption_is_folded():
    f = {"label": "Figure 2", "caption": f"Effect of {M}2 SD", "page": 3}
    _fold_unicode_minus(f)
    assert f["caption"] == "Effect of -2 SD"
