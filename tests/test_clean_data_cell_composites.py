"""``_cell_is_clean_data`` rejected common APA COMPOSITE value cells (2026-08-04).

The clean-data-cell test is what proves a whitespace grid is a real DATA table rather
than absorbed prose: ``_whitespace_grid_is_clean`` requires at least
``_MIN_CLEAN_DATA_ROWS`` rows carrying such a cell. The pattern was anchored
``^ … $`` around a SINGLE numeric token, so it accepted ``2.84``, ``.67``, ``-0.78``,
``[0.59, 0.73]``, ``(170)``, ``<.001`` and ``45%`` — but rejected every multi-token APA
composite:

    2.84 [1.89]          mean [SD]                 <- maier Tables 5 and 7
    2.84 (1.89)          mean (SD)
    3.47 [1.23] (170)    mean [SD] (n)             <- maier Table 7, gold-exact
    2.84 ± 1.89          mean ± SD
    0.42***              estimate with sig markers

A descriptives table built from those cells therefore scored ``clean_data_rows = 0`` and
was discarded as "not a data table" — the grid thrown away and the table rendered as a
caption-only stub. maier Table 5 is exactly this: its region resolves, its data is
present, and it still yields 0 cells.

Fix: judge a cell by NUMERIC DOMINANCE rather than by matching one token shape. A data
cell is one whose content is essentially all numbers, separators and stat punctuation
(brackets, parens, comparison ops, ±, significance stars) with no substantive word. That
generalises to composites this project has not seen yet, instead of chasing each new
shape with another alternation.

The prose side must not move: a cell with real words is still not a data cell, which is
what keeps absorbed body text out of the grid (cog_emo Table 3's 27x4 all-prose grid).
"""

from __future__ import annotations

import pytest

from docpluck.tables.whitespace import _cell_is_clean_data


def _is_clean(text: str) -> bool:
    return _cell_is_clean_data(text)


# Shapes that already worked — these must NOT regress.
@pytest.mark.parametrize(
    "cell",
    [
        "2.84",
        ".67",
        "-0.78",
        "−0.78",          # U+2212 minus
        "[0.59, 0.73]",
        "(170)",
        "<.001",
        "≥ 5",
        "45%",
        "1004",
    ],
)
def test_single_token_data_cells_still_accepted(cell: str):
    assert _is_clean(cell) is True, f"regressed on {cell!r}"


# The gap: multi-token APA composites.
@pytest.mark.parametrize(
    "cell",
    [
        "2.84 [1.89]",           # mean [SD] — maier T5
        "2.84 (1.89)",           # mean (SD)
        "3.47 [1.23] (170)",     # mean [SD] (n) — maier T7, gold-exact
        "2.84 ± 1.89",           # mean ± SD
        "0.42***",               # estimate with significance markers
        "-0.73***",              # signed estimate with markers
        "2.60 [1.94] (502)",     # maier T5 total row
        "0.67 [0.59, 0.73]",     # estimate followed by its CI
    ],
)
def test_apa_composite_data_cells_accepted(cell: str):
    assert _is_clean(cell) is True, f"composite still rejected: {cell!r}"


# The guard that must hold: prose is still not data.
@pytest.mark.parametrize(
    "cell",
    [
        "Explicit learning intervention",
        "we ran 3 studies with 264 people",
        "Participants (n = 264) were asked to rate",
        "Note. Statistics are presented as mean [SD].",
        "Table 8. Statistical tests",
        "High (Extension) empathy",
        "Geographic origin",
    ],
)
def test_prose_cells_still_rejected(cell: str):
    assert _is_clean(cell) is False, f"prose wrongly accepted as data: {cell!r}"


def test_empty_and_whitespace_are_not_data():
    assert _is_clean("") is False
    assert _is_clean("   ") is False
