"""A row that prints only a row label, directly above a data row, opens a block
of the body; it is not another header line.

10.1001/jamanetworkopen.2023.16111 Table 2 prints "Outcome and time | Score,
mean (SD)", then "Anxiety" and "Continued smoking" each alone in the label
column, then "Baseline 4.31 (3.67)". Once the caption line left the grid, the
header took three rows, so "Continued smoking" became a header line while its
twin "Stopped smoking" further down stayed a body row, and the first block's
records lost their block label.
"""
from __future__ import annotations

from docpluck.tables.cell_cleaning import _header_row_count

_GRID = [
    ["Outcome and time", "Score, mean (SD)"],
    ["Anxietya", ""],
    ["Continued smoking", ""],
    ["Baseline", "4.31 (3.67)"],
    ["Follow-up", "2.29 (3.43)"],
    ["Stopped smoking", ""],
    ["Baseline", "3.81 (3.43)"],
    ["Follow-up", "1.51 (2.79)"],
]


def test_label_only_row_over_a_data_row_ends_the_header():
    assert _header_row_count(_GRID, 2) == 2


def test_a_label_only_line_over_another_header_line_still_joins():
    grid = [
        ["Outcome", "Score, mean (SD)"],
        ["Anxiety", ""],
        ["Wave", "Mean"],
        ["Baseline", "4.31"],
    ]
    assert _header_row_count(grid, 2) == 3
