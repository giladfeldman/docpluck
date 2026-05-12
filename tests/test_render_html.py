"""HTML rendering of cells -> <table>.

v2.3.0: cells_to_html now runs the full cell_cleaning pipeline. Heavy
behavioral coverage lives in test_tables_cell_cleaning.py; this file
just verifies the list[Cell] → grid → HTML adapter behaves correctly.
"""

from docpluck.tables import Cell
from docpluck.tables.render import cells_to_html


def _cell(r, c, text, is_header=False) -> Cell:
    return {
        "r": r, "c": c, "rowspan": 1, "colspan": 1,
        "text": text, "is_header": is_header,
        "bbox": (0.0, 0.0, 0.0, 0.0),
    }


def test_empty_cells_returns_empty_string():
    """v2.3.0: empty input returns empty string (was '<table></table>')."""
    assert cells_to_html([]) == ""


def test_simple_2x3_renders_thead_and_tbody():
    """A 2x3 grid runs through the cleaning pipeline; the heuristic
    promotes the first row to <thead>."""
    cells = [
        _cell(0, 0, "Variable"), _cell(0, 1, "M"), _cell(0, 2, "SD"),
        _cell(1, 0, "Age"), _cell(1, 1, "24.3"), _cell(1, 2, "3.1"),
        _cell(2, 0, "IQ"), _cell(2, 1, "100.5"), _cell(2, 2, "15.2"),
    ]
    html = cells_to_html(cells)
    assert "<thead>" in html
    assert "<tbody>" in html
    assert "<th>Variable</th>" in html
    assert "<td>Age</td>" in html
    assert "<td>24.3</td>" in html


def test_with_header_row_flag_does_not_matter():
    """v2.3.0: the Cell is_header flag is ignored; heuristics drive
    header detection. A short-label row above numeric data still goes
    to <thead>."""
    cells = [
        _cell(0, 0, "Name", is_header=True),
        _cell(0, 1, "Score", is_header=True),
        _cell(1, 0, "Alice"),
        _cell(1, 1, "42"),
    ]
    html = cells_to_html(cells)
    assert "<thead>" in html
    assert "<tbody>" in html
    assert "<th>Name</th>" in html
    assert "<th>Score</th>" in html
    assert "<td>Alice</td>" in html
    assert "<td>42</td>" in html


def test_html_escapes_special_chars():
    cells = [
        _cell(0, 0, "expression"),
        _cell(1, 0, "p < .05 & d > 0"),
    ]
    html = cells_to_html(cells)
    assert "&lt;" in html
    assert "&gt;" in html
    assert "&amp;" in html


def test_handles_missing_cells_in_grid():
    """Cells missing from the grid render as empty <td>/<th>."""
    cells = [
        _cell(0, 0, "Variable"), _cell(0, 1, "Mean"),
        _cell(1, 0, "Age"),
    ]
    html = cells_to_html(cells)
    # Second row should still have 2 td slots — the missing (1,1) becomes "".
    assert "<td>Age</td>" in html
    assert "<td></td>" in html


def test_single_cell_returns_empty_string():
    """v2.3.0: single-row grid is too small to render meaningfully."""
    cells = [_cell(0, 0, "hello")]
    assert cells_to_html(cells) == ""
