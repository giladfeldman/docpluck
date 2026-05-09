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


def splice_tables_into_text(
    pdftotext_text: str,
    tables: list[dict],
) -> str:
    """Splice each table's markdown rendering into the page it belongs to.

    ``pdftotext_text`` uses ``\\f`` (form feed, ASCII 12) as the page
    separator — this is pdftotext's default behavior.

    Each entry in ``tables`` is a dict with at least:
      - ``page``: 0-based index of the page (matches ``pdftotext_text.split('\\f')``)
      - ``rows``: pdfplumber-style list-of-lists of cells

    For each table, we find its line range on its page using
    ``find_table_region_in_text``. If found, we replace those lines with the
    markdown-rendered table. If not, we prepend the markdown table at the top
    of the page with a visible diagnostic note so reviewers can spot the
    failure mode.
    """
    pages = pdftotext_text.split("\f")

    # Group tables by page so we can splice all of a page's tables before
    # moving on (table region indices shift as we splice; per-page reverse
    # ordering keeps indices stable).
    by_page: dict[int, list[dict]] = {}
    for t in tables:
        by_page.setdefault(t["page"], []).append(t)

    new_pages: list[str] = []
    for page_idx, page_text in enumerate(pages):
        page_tables = by_page.get(page_idx, [])
        if not page_tables:
            new_pages.append(page_text)
            continue

        # Locate each table's region first, then splice in reverse line order
        # so earlier indices stay valid.
        located: list[tuple[Optional[tuple[int, int]], dict]] = []
        for t in page_tables:
            region = find_table_region_in_text(page_text, t["rows"])
            located.append((region, t))

        lines = page_text.split("\n")

        # Splice located tables in reverse-start order.
        located_with_region = [
            (region, t) for (region, t) in located if region is not None
        ]
        located_with_region.sort(key=lambda x: x[0][0], reverse=True)
        for region, t in located_with_region:
            start, end = region
            md = pdfplumber_table_to_markdown(t["rows"]).rstrip("\n")
            lines[start:end] = [md]

        # Prepend unlocated tables (with diagnostic note) at the top of page.
        unlocated = [t for (region, t) in located if region is None]
        if unlocated:
            preface: list[str] = []
            for t in unlocated:
                md = pdfplumber_table_to_markdown(t["rows"]).rstrip("\n")
                note = (
                    "[splice-spike: table location not found on this page; "
                    "inserted at top]"
                )
                preface.append(note)
                preface.append(md)
                preface.append("")
            lines = preface + lines

        new_pages.append("\n".join(lines))

    return "\n".join(new_pages)


def _load_tables_for_spike(pdf_path: str) -> tuple[str, list[dict]]:
    """Load text and tables from a PDF using docpluck's structured extractor.

    Actual schema (discovered 2026-05-09):
      - ``extract_pdf_structured(bytes)`` returns a TypedDict with ``text`` (str,
        pages joined by \\f) and ``tables`` (list[Table]).
      - ``Table`` is a TypedDict with ``page`` (int, **1-indexed**), ``cells``
        (list[Cell] — **empty** for isolated/whitespace tables, which is the norm
        for APA psychology papers), ``raw_text`` (str, unstructured table text).
      - pdfplumber ``extract_tables()`` also returns 0 tables for these papers
        (no ruled lines), so ``cells`` will always be empty here.
      - We convert ``raw_text`` → pseudo-rows (one line = one single-cell row)
        so the token-based location algorithm has something to work with.
    """
    from docpluck.extract_structured import extract_pdf_structured  # local import: no cost when running tests

    with open(pdf_path, "rb") as f:
        pdf_bytes = f.read()

    result = extract_pdf_structured(pdf_bytes)
    text: str = result["text"]

    out: list[dict] = []
    for t in result.get("tables", []):
        page_1indexed: int = t["page"]  # docpluck Table.page is 1-indexed
        page_0indexed = page_1indexed - 1

        cells = t.get("cells") or []
        if cells:
            # Lattice table: reconstruct rows from (r, c, text) cell dicts.
            n_rows = max(c["r"] for c in cells) + 1
            n_cols = max(c["c"] for c in cells) + 1
            grid: list[list[str]] = [[""] * n_cols for _ in range(n_rows)]
            for c in cells:
                grid[c["r"]][c["c"]] = c["text"]
            rows = grid
        else:
            # Isolated/whitespace table: use raw_text lines as single-cell rows.
            raw = t.get("raw_text") or ""
            rows = [[line] for line in raw.splitlines() if line.strip()]

        out.append({"page": page_0indexed, "rows": rows})

    return text, out


def _run_cli(pdf_path: str) -> str:
    text, tables = _load_tables_for_spike(pdf_path)
    return splice_tables_into_text(text, tables)


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print("usage: python splice_spike.py <pdf-path>", file=sys.stderr)
        sys.exit(2)
    output = _run_cli(sys.argv[1])
    # Re-open stdout in UTF-8 mode for Windows compatibility (Windows default
    # is often cp1252 which cannot encode many Unicode chars in PDF text).
    sys.stdout = open(sys.stdout.fileno(), mode="w", encoding="utf-8", closefd=False)
    sys.stdout.write(output)
