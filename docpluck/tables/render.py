"""HTML rendering of structured table cells.

v2.3.0: ``cells_to_html`` now runs the full cell-cleaning pipeline from
``docpluck.tables.cell_cleaning`` (ported from the 2026-05 splice spike).
The pipeline merges multi-line cell continuations, strips leader dots,
splits column-mashed cells, drops leaked running headers, detects
multi-row headers (capped at 3), folds 2-row super-headers, attaches
significance markers as ``<sup>``, and renders only-col-0 rows as
``<tr><td colspan="N"><strong>...</strong></td></tr>`` group separators.

The cleaning pipeline ignores the ``is_header`` flag on each Cell and
uses heuristics (cell length, numeric ratio) to detect headers. This is
intentional: Camelot's per-cell header flag is unreliable; the heuristics
match a wider range of real-world academic tables.

When the cleaning pipeline collapses a small table to fewer than 2 rows
(e.g. a 2-row table where the second row is a continuation that folds
into the first), we fall back to a minimal raw renderer rather than
returning the empty string. This preserves the contract that structured
tables (``kind == "structured"``) always have non-empty HTML containing
``<table>``.
"""

from __future__ import annotations

import html as _html

from . import Cell
from .cell_cleaning import cells_grid_to_html


def cells_to_html(cells: list[Cell]) -> str:
    """Render a list of Cell to a single <table>...</table> HTML string.

    Empty input → empty string (no table to render).
    Single-row input → empty string (degenerate; not a real table).
    Multi-row input: run the cleaning pipeline; if it collapses the
    table to <2 rows, fall back to a minimal raw renderer so structured
    tables always have valid HTML.
    """
    if not cells:
        return ""

    n_rows = max(c["r"] for c in cells) + 1
    n_cols = max(c["c"] for c in cells) + 1

    # Degenerate single-row input: nothing meaningful to render. Returning
    # "" here keeps the contract that one-row "tables" produce no output
    # (matches both the v2.3.0 cleaning pipeline behavior and the legacy
    # ``test_single_cell_returns_empty_string`` invariant).
    if n_rows < 2:
        return ""

    grid: list[list[str]] = [[""] * n_cols for _ in range(n_rows)]
    for c in cells:
        grid[c["r"]][c["c"]] = c["text"] or ""

    cleaned = cells_grid_to_html(grid)
    if cleaned:
        return cleaned

    # Fallback: cleaning collapsed the table to <2 rows during processing
    # (e.g. row 2 was a continuation that merged into row 1). The input
    # had ≥2 rows so a structured-table caller still needs valid HTML;
    # emit a raw renderer pass. See
    # ``tests/test_smoke_fixtures.py::test_table_html_renders_when_structured``.
    return _raw_cells_to_html(grid, cells)


def _raw_cells_to_html(grid: list[list[str]], cells: list[Cell]) -> str:
    """Minimal HTML renderer used as a fallback when cleaning collapses.

    Uses the same is_header signal as the pre-v2.3.0 renderer so the
    output is recognizable. Pure formatting; no cleaning heuristics.
    """
    n_rows = len(grid)
    if n_rows == 0:
        return ""

    has_header = any(c["is_header"] for c in cells)
    header_row_index = (
        min(c["r"] for c in cells if c["is_header"]) if has_header else None
    )

    parts: list[str] = ["<table>"]
    if has_header and 0 <= header_row_index < n_rows:
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


def _render_row(row: list[str], *, cell_tag: str) -> str:
    pieces: list[str] = ["<tr>"]
    for text in row:
        escaped = _html.escape(text or "", quote=False)
        pieces.append(f"<{cell_tag}>{escaped}</{cell_tag}>")
    pieces.append("</tr>")
    return "".join(pieces)


__all__ = ["cells_to_html"]
