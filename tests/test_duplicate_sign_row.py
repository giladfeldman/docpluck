"""A row of lone sign glyphs that copies the signs of the row above is our
reader's duplicate, not page content (Release B page check, 2026-11-16).

10.1093/sf/soaf022 Table 3 (p12) prints "−73.57" over "(40.24)", one minus
glyph per number in the file. The grid carried a third row of lone "-" between
them, and the continuation merge glued it onto the SE: "-(40.24)".
"""
from __future__ import annotations

from docpluck.tables.cell_cleaning import _drop_duplicate_sign_rows, cells_grid_to_html
from docpluck.tables.flatten import flatten_table

GRID = [["Variables", "Panel B", "Panel C", "Panel D"],
        ["Cutpoint 1", "-73.57", "-84.97", "-93.98"],
        ["", "-", "-", "-"],
        ["", "(40.24)", "(33.32)", "(30.39)"],
        ["Cutpoint 2", "-71.11", "-81.79", "-91.84"]]


def test_the_copied_sign_row_is_dropped():
    assert _drop_duplicate_sign_rows([list(r) for r in GRID]) == [
        GRID[0], GRID[1], GRID[3], GRID[4]]


def test_a_lone_sign_under_an_unsigned_cell_stays():
    grid = [["a", "1.0"], ["", "-"]]
    assert _drop_duplicate_sign_rows([list(r) for r in grid]) == grid


def test_no_negative_standard_error_reaches_html_or_records():
    html = cells_grid_to_html([list(r) for r in GRID])
    assert "-(40.24)" not in html and "(40.24)" in html
    cells = [{"r": r, "c": c, "rowspan": 1, "colspan": 1, "text": t, "is_header": r == 0,
              "bbox": (0.0, 0.0, 0.0, 0.0)}
             for r, row in enumerate(GRID) for c, t in enumerate(row) if t]
    recs = flatten_table({"id": "t3", "label": "Table 3", "page": 12, "cells": cells,
                          "caption": "Table 3. Odds ratios", "footnote": None,
                          "kind": "structured"})
    assert not any("-(40.24)" in c for x in recs for c in x["raw_cells"])
