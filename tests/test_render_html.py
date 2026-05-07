"""HTML rendering of cells -> <table>."""

from docpluck.tables import Cell
from docpluck.tables.render import cells_to_html


def _cell(r, c, text, is_header=False) -> Cell:
    return {
        "r": r, "c": c, "rowspan": 1, "colspan": 1,
        "text": text, "is_header": is_header,
        "bbox": (0.0, 0.0, 0.0, 0.0),
    }


def test_empty_cells_returns_empty_table():
    assert cells_to_html([]) == "<table></table>"


def test_simple_2x2_no_header():
    cells = [
        _cell(0, 0, "a"), _cell(0, 1, "b"),
        _cell(1, 0, "c"), _cell(1, 1, "d"),
    ]
    html = cells_to_html(cells)
    assert html == (
        "<table>"
        "<tbody>"
        "<tr><td>a</td><td>b</td></tr>"
        "<tr><td>c</td><td>d</td></tr>"
        "</tbody>"
        "</table>"
    )


def test_with_header_row():
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
    cells = [_cell(0, 0, "p < .05 & d > 0")]
    html = cells_to_html(cells)
    assert "&lt;" in html
    assert "&gt;" in html
    assert "&amp;" in html
    assert "<" not in html.replace("<table>", "").replace("<tbody>", "").replace("<tr>", "").replace("<td>", "").replace("</td>", "").replace("</tr>", "").replace("</tbody>", "").replace("</table>", "")


def test_empty_cells_render_as_empty_td():
    cells = [
        _cell(0, 0, "x"), _cell(0, 1, ""),
        _cell(1, 0, ""), _cell(1, 1, "y"),
    ]
    html = cells_to_html(cells)
    assert "<td></td>" in html
    assert "<td>x</td>" in html
    assert "<td>y</td>" in html


def test_handles_missing_cells_in_grid():
    # Row 1 has cell (1,0) but no (1,1) — render empty <td> in the gap.
    cells = [
        _cell(0, 0, "a"), _cell(0, 1, "b"),
        _cell(1, 0, "c"),
    ]
    html = cells_to_html(cells)
    assert html.count("<tr>") == 2
    # Second row should still have 2 td slots
    tbody = html[html.find("<tbody>"):html.find("</tbody>")]
    assert tbody.count("<td>") == 4  # 2 cells in first row + 2 cells in second row
    # Verify second row has empty cell
    assert "<td>c</td><td></td></tr>" in html
