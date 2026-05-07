"""
HTML rendering of structured table cells.

Deterministic transform: list[Cell] -> <table> HTML string. No styling, no
class attributes, no inline style. Cell text is HTML-escaped. v2.0 always
emits rowspan=1/colspan=1 (omitted because they're the default); level-C
will populate higher rowspans/colspans.

See spec §5.5.
"""

from __future__ import annotations

import html as _html

from . import Cell


def cells_to_html(cells: list[Cell]) -> str:
    """Render a list of Cell to a single <table>...</table> HTML string."""
    if not cells:
        return "<table></table>"

    n_rows = max(c["r"] for c in cells) + 1
    n_cols = max(c["c"] for c in cells) + 1

    grid: list[list[Cell | None]] = [[None] * n_cols for _ in range(n_rows)]
    for c in cells:
        grid[c["r"]][c["c"]] = c

    has_header = any(c["is_header"] for c in cells)
    header_row_index = (
        min(c["r"] for c in cells if c["is_header"]) if has_header else None
    )

    parts: list[str] = ["<table>"]

    if has_header:
        parts.append("<thead>")
        parts.append(_render_row(grid[header_row_index], cell_tag="th"))
        parts.append("</thead>")

    parts.append("<tbody>")
    for r in range(n_rows):
        if r == header_row_index:
            continue
        parts.append(_render_row(grid[r], cell_tag="td"))
    parts.append("</tbody>")

    parts.append("</table>")
    return "".join(parts)


def _render_row(row: list[Cell | None], *, cell_tag: str) -> str:
    pieces: list[str] = ["<tr>"]
    for cell in row:
        if cell is None:
            pieces.append(f"<{cell_tag}></{cell_tag}>")
        else:
            text = _html.escape(cell["text"], quote=False)
            pieces.append(f"<{cell_tag}>{text}</{cell_tag}>")
    pieces.append("</tr>")
    return "".join(pieces)


__all__ = ["cells_to_html"]
