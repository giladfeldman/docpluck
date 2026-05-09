"""Splice spike (phase 0).

Throwaway prototype that wraps existing docpluck extraction and produces
a single .md per input PDF with pdfplumber tables spliced into pdftotext
text. Used to answer: is the splice algorithm viable?

This module is NOT production code. It will be deleted (or its surviving
helpers moved into proper modules) once phase 1 ships.
"""
from __future__ import annotations

from typing import Sequence


def pdfplumber_table_to_markdown(rows: Sequence[Sequence[str | None]]) -> str:
    """Render a pdfplumber-style table (list of rows of cells) as a GFM pipe table.

    - Cells that are None render as empty strings.
    - Embedded newlines in a cell collapse to a single space (pipe-table syntax
      cannot represent in-cell newlines).
    - Pipe characters in cells are escaped as ``\\|``.
    - Returns the empty string for tables with fewer than 2 rows (no data).
    """
    if len(rows) < 2:
        return ""

    def _cell(value: str | None) -> str:
        if value is None:
            return ""
        return value.replace("\n", " ").replace("|", "\\|").strip()

    header = [_cell(c) for c in rows[0]]
    body = [[_cell(c) for c in row] for row in rows[1:]]

    n_cols = len(header)
    lines: list[str] = []
    lines.append("| " + " | ".join(header) + " |")
    lines.append("| " + " | ".join(["---"] * n_cols) + " |")
    for row in body:
        # pad / truncate to header width so pipe-table is rectangular
        normalized = list(row) + [""] * max(0, n_cols - len(row))
        normalized = normalized[:n_cols]
        lines.append("| " + " | ".join(normalized) + " |")

    return "\n".join(lines) + "\n"
