"""Splice spike (phase 0).

Throwaway prototype that wraps existing docpluck extraction and produces
a single .md per input PDF with pdfplumber tables spliced into pdftotext
text. Used to answer: is the splice algorithm viable?

This module is NOT production code. It will be deleted (or its surviving
helpers moved into proper modules) once phase 1 ships.
"""
from __future__ import annotations

import re
from typing import Optional, Sequence


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


_TOKEN_RE = re.compile(r"[A-Za-z]{3,}|\d+(?:\.\d+)?")


def _tokens(s: str) -> set[str]:
    """Identifying tokens of a string: words ≥3 chars and numeric literals."""
    return set(_TOKEN_RE.findall(s))


def find_table_region_in_text(
    page_text: str,
    table_rows: Sequence[Sequence[Optional[str]]],
) -> Optional[tuple[int, int]]:
    """Locate the contiguous line range in ``page_text`` that the given table occupies.

    Algorithm: build the union of "identifying tokens" across all cells of the
    table. For each line, compute hit count = number of identifying tokens
    present. Scan all contiguous windows whose summed hit count is the highest;
    take the smallest such window with at least 60% of the table's tokens
    represented. Return ``(start_line, end_line_exclusive)`` or ``None`` if no
    window meets the threshold.

    This is a coarse, approximate algorithm by design — phase 0's whole point
    is to learn how often it actually works on real PDFs.
    """
    table_tokens: set[str] = set()
    for row in table_rows:
        for cell in row:
            if cell is None:
                continue
            table_tokens |= _tokens(cell)
    if not table_tokens:
        return None

    lines = page_text.split("\n")
    if not lines:
        return None

    per_line_hits = [len(_tokens(line) & table_tokens) for line in lines]

    # Search every contiguous window. n is small (one page worth of lines), so
    # O(n^2) is fine.
    best: Optional[tuple[int, int, int]] = None  # (-hits, length, start)
    for start in range(len(lines)):
        running_hits = 0
        running_token_set: set[str] = set()
        for end in range(start, len(lines)):
            running_hits += per_line_hits[end]
            running_token_set |= _tokens(lines[end]) & table_tokens
            coverage = len(running_token_set) / len(table_tokens)
            if coverage < 0.6:
                continue
            length = end - start + 1
            # Prefer higher hits, then shorter window.
            candidate = (-running_hits, length, start)
            if best is None or candidate < best:
                best = (-running_hits, length, start)

    if best is None:
        return None
    _, length, start = best
    return (start, start + length)
