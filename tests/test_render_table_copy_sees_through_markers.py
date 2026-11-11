"""A table cell carrying a ^a footnote marker still matches its text copy.

2.4.159 marks raised footnote letters in cells ("Estimation error^a"); the text
channel still reads "Estimation errora". The render removes the body copy of a
table by comparing the two, so without folding the caret the copies of
10.1177/01461672251327169 Tables 1 and 2 came back into the Introduction
(canary audit 2026-11-11, two findings). Both comparison paths are covered:
the caption-led run test (`_grid_tokens`) and the block test (`_copy_norm`).
"""
from __future__ import annotations

from docpluck.render import _copy_norm, _grid_tokens


def test_grid_tokens_fold_the_marker():
    assert _grid_tokens("Estimation error^a 5.47**")[:2] == _grid_tokens("Estimation errora 5.47**")[:2]
    assert _grid_tokens("well-being.^a")[1] == _grid_tokens("well-being.a")[1]


def test_copy_norm_folds_the_marker():
    assert _copy_norm("People underestimate the intensity of experiences.^c") == \
        _copy_norm("People underestimate the intensity of experiences.c")
    assert _copy_norm("mean (SD)^e,f") == _copy_norm("mean (SD)e,f")
