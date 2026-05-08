# Phase 0: Splice Spike — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Determine, by hands-on prototype, whether pdfplumber-derived tables can be reliably spliced into pdftotext's linear text at the correct reading-order position on real academic PDFs — the gating empirical question for the unified-extraction architecture.

**Architecture:** A throwaway Python module under `docs/superpowers/plans/spot-checks/splice-spike/` that wraps the existing `extract_pdf` and `extract_pdf_layout` functions, locates each pdfplumber-detected table inside the pdftotext line stream via content fingerprinting, replaces those lines with a markdown pipe-table, and emits one `.md` per input PDF for eyeball review. Production code is untouched.

**Tech Stack:** Python 3.11+, existing `docpluck` library, pytest for synthetic-input unit tests.

**Spec:** [`docs/superpowers/specs/2026-05-08-unified-extraction-design.md`](../specs/2026-05-08-unified-extraction-design.md), §6 "Engineering risk: table splicing" and §7 phase 0.

**Phase 0 deliverable:** A written report at `docs/superpowers/plans/spot-checks/splice-spike/report.md` that ANSWERS the question "is the splice algorithm viable?" — with one of three recommendations: (a) ship phase 1 as designed, (b) modify the splice algorithm in specific ways, or (c) fall back to "tables-at-end-of-section" rendering. Subsequent phases' plans get written based on this report.

**This plan does NOT cover:** phases 1–4 from the spec. They get separate plans after phase 0 reports.

---

## File Structure

| Path | Purpose |
|---|---|
| `docs/superpowers/plans/spot-checks/splice-spike/splice_spike.py` | The prototype module — helpers + CLI. |
| `docs/superpowers/plans/spot-checks/splice-spike/test_splice_spike.py` | Unit tests on synthetic inputs (no PDF dependency). |
| `docs/superpowers/plans/spot-checks/splice-spike/papers.md` | The 5 chosen PDFs and the rationale. |
| `docs/superpowers/plans/spot-checks/splice-spike/outputs/<paper>.md` | One spliced-markdown output per chosen PDF. |
| `docs/superpowers/plans/spot-checks/splice-spike/report.md` | Final phase-0 report and recommendation. |

All five files live under one directory so the entire spike can be reviewed together and deleted as a unit if the algorithm doesn't survive.

---

## Task 1: Choose 5 candidate PDFs and document the choice

**Files:**
- Create: `docs/superpowers/plans/spot-checks/splice-spike/papers.md`

**Goal:** Pick five PDFs that span the layout variations the splice algorithm must handle. Lock the list in writing so subsequent tasks have a concrete target.

- [ ] **Step 1: List candidates and pick 5**

The candidates available in `../PDFextractor/test-pdfs/apa/` cover several APA-style layouts. The five chosen for the spike must cover the following five conditions, one PDF each:

1. **Clean single-column APA with at least one stats table.** Recommended: `efendic_2022_affect.pdf` (already used as a benchmark in handoffs).
2. **Two-column journal layout with at least one inline table.** Recommended: `chen_2021_jesp.pdf` (JESP 2-col, called out in the handoff).
3. **Paper with two or more tables on the same page.** Recommended: `chandrashekar_2023_mp.pdf` if it has multi-table pages, otherwise pick another from the APA folder by inspection.
4. **Paper with a table that spans or sits at a page boundary.** Recommended: `ip_feldman_2025_pspb.pdf` if it has one; otherwise inspect the folder to find one.
5. **Paper with at least one structurally-complex table** (merged cells, multi-row header, or rotated). Recommended: pick by inspection — open candidates in a PDF viewer and find one. If none in the APA folder qualify, document that and note what we couldn't test.

Do NOT pick five clean single-column papers. The whole point is to exercise the algorithm on layouts where pdftotext linearization is most likely to mangle table regions.

- [ ] **Step 2: Write `papers.md`**

Create `docs/superpowers/plans/spot-checks/splice-spike/papers.md` with this content (replace `<chosen N>` and `<rationale>` with actual filenames and one-sentence rationales):

```markdown
# Splice Spike — Chosen Papers

Five PDFs from `PDFextractor/test-pdfs/apa/`, picked to span the layout
variations the splice algorithm must handle.

| # | Filename | Layout condition | Why this paper |
|---|---|---|---|
| 1 | <chosen 1>.pdf | clean single-column APA | <rationale> |
| 2 | <chosen 2>.pdf | two-column journal | <rationale> |
| 3 | <chosen 3>.pdf | multi-table page | <rationale> |
| 4 | <chosen 4>.pdf | table at page boundary | <rationale> |
| 5 | <chosen 5>.pdf | structurally-complex table | <rationale> |

If condition 5 was not satisfied by any APA folder paper, this is noted
and the spike's coverage of that condition is acknowledged as untested.
```

- [ ] **Step 3: Commit**

```bash
git add docs/superpowers/plans/spot-checks/splice-spike/papers.md
git commit -m "spike(splice): choose 5 candidate PDFs covering layout conditions"
```

---

## Task 2: Implement `pdfplumber_table_to_markdown` (TDD)

**Files:**
- Create: `docs/superpowers/plans/spot-checks/splice-spike/splice_spike.py`
- Create: `docs/superpowers/plans/spot-checks/splice-spike/test_splice_spike.py`

**Goal:** Convert a pdfplumber-style table (a list of rows, each row a list of cell strings, possibly with `None` for empty cells) into a GitHub-flavored markdown pipe-table string. This is pure logic, fully testable on synthetic input.

- [ ] **Step 1: Write the failing test**

Create `docs/superpowers/plans/spot-checks/splice-spike/test_splice_spike.py`:

```python
"""Unit tests for the splice spike. Synthetic inputs only — no PDF I/O."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))

from splice_spike import pdfplumber_table_to_markdown


def test_simple_2x3_table_becomes_pipe_table():
    table = [
        ["Variable", "M", "SD"],
        ["Age", "24.3", "3.1"],
        ["IQ", "100.5", "15.2"],
    ]
    result = pdfplumber_table_to_markdown(table)
    expected = (
        "| Variable | M | SD |\n"
        "| --- | --- | --- |\n"
        "| Age | 24.3 | 3.1 |\n"
        "| IQ | 100.5 | 15.2 |\n"
    )
    assert result == expected


def test_none_cells_render_as_empty_string():
    table = [
        ["A", "B"],
        ["1", None],
        [None, "2"],
    ]
    result = pdfplumber_table_to_markdown(table)
    expected = (
        "| A | B |\n"
        "| --- | --- |\n"
        "| 1 |  |\n"
        "|  | 2 |\n"
    )
    assert result == expected


def test_pipe_in_cell_is_escaped():
    table = [
        ["expression"],
        ["a | b"],
    ]
    result = pdfplumber_table_to_markdown(table)
    expected = (
        "| expression |\n"
        "| --- |\n"
        "| a \\| b |\n"
    )
    assert result == expected


def test_multiline_cell_collapses_to_single_line():
    """pdfplumber sometimes returns cells with embedded newlines.
    Pipe-table syntax cannot represent newlines inside a cell, so they
    must collapse to a space."""
    table = [
        ["heading"],
        ["line one\nline two"],
    ]
    result = pdfplumber_table_to_markdown(table)
    expected = (
        "| heading |\n"
        "| --- |\n"
        "| line one line two |\n"
    )
    assert result == expected


def test_empty_table_returns_empty_string():
    assert pdfplumber_table_to_markdown([]) == ""


def test_single_row_returns_empty_string():
    """A table with only a header and no data rows is degenerate; emit nothing
    so the spike doesn't insert phantom tables."""
    assert pdfplumber_table_to_markdown([["header only"]]) == ""
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest docs/superpowers/plans/spot-checks/splice-spike/test_splice_spike.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'splice_spike'`.

- [ ] **Step 3: Write minimal implementation**

Create `docs/superpowers/plans/spot-checks/splice-spike/splice_spike.py`:

```python
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
```

- [ ] **Step 4: Run tests, verify they all pass**

```bash
pytest docs/superpowers/plans/spot-checks/splice-spike/test_splice_spike.py -v
```

Expected: 6 PASS.

- [ ] **Step 5: Commit**

```bash
git add docs/superpowers/plans/spot-checks/splice-spike/splice_spike.py docs/superpowers/plans/spot-checks/splice-spike/test_splice_spike.py
git commit -m "spike(splice): pdfplumber_table_to_markdown helper + tests"
```

---

## Task 3: Implement `find_table_region_in_text` (TDD)

**Files:**
- Modify: `docs/superpowers/plans/spot-checks/splice-spike/splice_spike.py`
- Modify: `docs/superpowers/plans/spot-checks/splice-spike/test_splice_spike.py`

**Goal:** Given (a) the pdftotext text of a single page, and (b) the cell content of a pdfplumber-detected table, locate the contiguous range of lines on that page that the table occupies. This is the splice-spike's core question. The fingerprinting algorithm: for each line of pdftotext, check what fraction of the table's tokens (numbers, multi-char words) appear in that line. The contiguous run of lines with the highest density is the table region. Returns `(start_line_idx, end_line_idx_exclusive)` or `None` if confidence is too low.

- [ ] **Step 1: Write the failing tests**

Add to `test_splice_spike.py`:

```python
from splice_spike import find_table_region_in_text


def test_finds_table_in_clear_page():
    page_text = (
        "This is the introduction paragraph that talks about the study.\n"
        "We measured several variables in our sample of 142 participants.\n"
        "\n"
        "Variable      M     SD    n\n"
        "Age          24.3   3.1   142\n"
        "IQ          100.5  15.2   142\n"
        "\n"
        "The table above shows our descriptives. Discussion follows."
    )
    table = [
        ["Variable", "M", "SD", "n"],
        ["Age", "24.3", "3.1", "142"],
        ["IQ", "100.5", "15.2", "142"],
    ]
    region = find_table_region_in_text(page_text, table)
    assert region is not None
    start, end = region
    lines = page_text.split("\n")
    region_text = "\n".join(lines[start:end])
    assert "Variable" in region_text
    assert "Age" in region_text
    assert "IQ" in region_text
    assert "introduction paragraph" not in region_text
    assert "Discussion follows" not in region_text


def test_returns_none_when_table_content_not_in_page():
    page_text = "No tables here. Just prose about cats."
    table = [
        ["Variable", "M"],
        ["Age", "24.3"],
    ]
    assert find_table_region_in_text(page_text, table) is None


def test_picks_correct_table_when_two_present():
    """Two tables on the same page; the function should return the region
    matching the table cells passed in, not the other table's region."""
    page_text = (
        "First table follows.\n"
        "Country  Population\n"
        "France   67000000\n"
        "Germany  83000000\n"
        "Then prose.\n"
        "Variable  M    SD\n"
        "Age       24   3\n"
        "IQ        100  15\n"
        "End."
    )
    second_table = [
        ["Variable", "M", "SD"],
        ["Age", "24", "3"],
        ["IQ", "100", "15"],
    ]
    region = find_table_region_in_text(page_text, second_table)
    assert region is not None
    start, end = region
    lines = page_text.split("\n")
    region_text = "\n".join(lines[start:end])
    assert "Variable" in region_text
    assert "France" not in region_text
    assert "Germany" not in region_text


def test_handles_pdftotext_column_interleaving_gracefully():
    """When pdftotext interleaves a 2-column page, table cells may be split
    across non-contiguous lines. The function should either return a region
    that covers the densest cluster (best-effort) or None (acknowledging
    failure). Either is acceptable; what's NOT acceptable is silently
    returning a region of unrelated prose."""
    page_text = (
        "Left column intro paragraph.\n"
        "Right column intro paragraph.\n"
        "Variable    M     SD     and right-column body line one\n"
        "Age         24.3  3.1    right-column body line two\n"
        "Discussion of left-column results.\n"
    )
    table = [
        ["Variable", "M", "SD"],
        ["Age", "24.3", "3.1"],
    ]
    region = find_table_region_in_text(page_text, table)
    if region is not None:
        start, end = region
        lines = page_text.split("\n")
        region_text = "\n".join(lines[start:end])
        # The region must contain at least the data row's identifying tokens
        assert "Age" in region_text
        assert "24.3" in region_text
```

- [ ] **Step 2: Run tests, verify they fail**

```bash
pytest docs/superpowers/plans/spot-checks/splice-spike/test_splice_spike.py -v
```

Expected: 4 NEW failures (`find_table_region_in_text` undefined). Existing 6 still pass.

- [ ] **Step 3: Write the implementation**

Append to `splice_spike.py`:

```python
import re
from typing import Optional


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
```

- [ ] **Step 4: Run tests, verify all pass**

```bash
pytest docs/superpowers/plans/spot-checks/splice-spike/test_splice_spike.py -v
```

Expected: 10 PASS (6 from Task 2 + 4 new).

- [ ] **Step 5: Commit**

```bash
git add docs/superpowers/plans/spot-checks/splice-spike/splice_spike.py docs/superpowers/plans/spot-checks/splice-spike/test_splice_spike.py
git commit -m "spike(splice): find_table_region_in_text via token fingerprinting"
```

---

## Task 4: Implement `splice_tables_into_text` orchestrator (TDD)

**Files:**
- Modify: `docs/superpowers/plans/spot-checks/splice-spike/splice_spike.py`
- Modify: `docs/superpowers/plans/spot-checks/splice-spike/test_splice_spike.py`

**Goal:** Given the full pdftotext text (with `\f` form-feed page separators) and a list of pdfplumber-detected tables (each with a `page` index and `rows`), produce the markdown by replacing each table's identified line range with its rendered pipe-table.

- [ ] **Step 1: Write the failing test**

Add to `test_splice_spike.py`:

```python
from splice_spike import splice_tables_into_text


def test_replaces_table_region_with_markdown_table():
    pdftotext_text = (
        "Page 1 prose introduction.\n"
        "We measured the following variables.\n"
        "Variable      M     SD\n"
        "Age          24.3   3.1\n"
        "IQ          100.5  15.2\n"
        "Discussion follows the table."
    )
    tables = [
        {
            "page": 0,  # only page in this synthetic input
            "rows": [
                ["Variable", "M", "SD"],
                ["Age", "24.3", "3.1"],
                ["IQ", "100.5", "15.2"],
            ],
        }
    ]
    result = splice_tables_into_text(pdftotext_text, tables)

    # Original prose preserved
    assert "Page 1 prose introduction." in result
    assert "Discussion follows the table." in result
    # Original garbled table rows replaced
    assert "Variable      M     SD" not in result
    # Markdown table inserted
    assert "| Variable | M | SD |" in result
    assert "| --- | --- | --- |" in result
    assert "| Age | 24.3 | 3.1 |" in result


def test_handles_multiple_pages_via_form_feed():
    page1 = (
        "Page 1 prose.\n"
        "Variable A    Value\n"
        "thing         42\n"
        "more page 1 prose."
    )
    page2 = (
        "Page 2 prose, different tokens.\n"
        "Country  Population\n"
        "France   67000000\n"
        "page 2 ending."
    )
    pdftotext_text = page1 + "\f" + page2
    tables = [
        {"page": 0, "rows": [["Variable A", "Value"], ["thing", "42"]]},
        {"page": 1, "rows": [["Country", "Population"], ["France", "67000000"]]},
    ]
    result = splice_tables_into_text(pdftotext_text, tables)
    assert "| Variable A | Value |" in result
    assert "| Country | Population |" in result
    assert "| thing | 42 |" in result
    assert "| France | 67000000 |" in result
    # Prose between pages still present
    assert "Page 1 prose." in result
    assert "Page 2 prose, different tokens." in result


def test_table_with_unfindable_region_falls_back_to_page_top():
    """If find_table_region_in_text returns None, the orchestrator inserts the
    markdown table at the top of that page with a note. Tested by giving a
    table whose tokens do not appear on the page."""
    pdftotext_text = "Page with prose only and no table content."
    tables = [
        {
            "page": 0,
            "rows": [
                ["alpha", "beta"],
                ["gamma", "delta"],
            ],
        }
    ]
    result = splice_tables_into_text(pdftotext_text, tables)
    assert "| alpha | beta |" in result
    # Note must accompany unlocated tables so the eyeball reviewer can spot them.
    assert "[splice-spike: table location not found" in result
```

- [ ] **Step 2: Run tests, verify failures**

```bash
pytest docs/superpowers/plans/spot-checks/splice-spike/test_splice_spike.py -v
```

Expected: 3 NEW failures (`splice_tables_into_text` undefined). Existing 10 still pass.

- [ ] **Step 3: Write the implementation**

Append to `splice_spike.py`:

```python
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
```

- [ ] **Step 4: Run tests, verify all pass**

```bash
pytest docs/superpowers/plans/spot-checks/splice-spike/test_splice_spike.py -v
```

Expected: 13 PASS.

- [ ] **Step 5: Commit**

```bash
git add docs/superpowers/plans/spot-checks/splice-spike/splice_spike.py docs/superpowers/plans/spot-checks/splice-spike/test_splice_spike.py
git commit -m "spike(splice): splice_tables_into_text orchestrator + tests"
```

---

## Task 5: Wire into a CLI driver that processes one PDF

**Files:**
- Modify: `docs/superpowers/plans/spot-checks/splice-spike/splice_spike.py`

**Goal:** Add a `__main__` block so the script can be run as `python splice_spike.py <pdf-path>` and prints the spliced markdown to stdout. Uses the real `extract_pdf` / `extract_pdf_layout` to fetch text and tables.

- [ ] **Step 1: Inspect what `extract_pdf_layout` returns for tables**

Run this once at the terminal to confirm the layout-channel output shape so the CLI driver passes the right structure to `splice_tables_into_text`:

```bash
python -c "
from docpluck import extract_pdf_layout
import json
layout = extract_pdf_layout('../PDFextractor/test-pdfs/apa/efendic_2022_affect.pdf')
print('keys:', list(layout.keys())[:10])
if 'tables' in layout:
    t0 = layout['tables'][0] if layout['tables'] else None
    print('first table keys:', list(t0.keys()) if t0 else 'no tables')
    print('first table sample:', json.dumps(t0, default=str)[:500])
"
```

If the table object's structure differs from what's assumed below, adjust the `_load_tables_for_spike` function accordingly in step 2 before running the CLI.

- [ ] **Step 2: Add the CLI block to `splice_spike.py`**

Append to `splice_spike.py`:

```python
def _load_tables_for_spike(pdf_path: str) -> list[dict]:
    """Adapt docpluck's layout-channel table objects to the splice spike's shape.

    Adjust this function if the actual ``extract_pdf_layout`` schema differs
    from what's assumed (cell rows under ``rows``, page index under ``page``
    or ``page_number``). The whole point of the spike is to discover these
    discrepancies — fix them here, not in production code.
    """
    from docpluck import extract_pdf_layout  # local import: no cost when running tests

    layout = extract_pdf_layout(pdf_path)
    out: list[dict] = []
    for t in layout.get("tables", []):
        # pdfplumber tables typically have a `rows` (or similar) key with cells.
        # If the schema uses a different key, update here.
        rows = t.get("rows") or t.get("cells") or []
        page = t.get("page", t.get("page_number", 0))
        if isinstance(page, int) and page >= 1:
            page = page - 1  # normalize to 0-based for splice_tables_into_text
        out.append({"page": page, "rows": rows})
    return out


def _run_cli(pdf_path: str) -> str:
    from docpluck import extract_pdf
    text = extract_pdf(pdf_path)
    tables = _load_tables_for_spike(pdf_path)
    return splice_tables_into_text(text, tables)


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print("usage: python splice_spike.py <pdf-path>", file=sys.stderr)
        sys.exit(2)
    sys.stdout.write(_run_cli(sys.argv[1]))
```

- [ ] **Step 3: Smoke-test the CLI on one of the chosen PDFs**

```bash
python docs/superpowers/plans/spot-checks/splice-spike/splice_spike.py "../PDFextractor/test-pdfs/apa/efendic_2022_affect.pdf" | head -100
```

Expected: the first 100 lines of the spliced markdown print to stdout. If the script errors with `KeyError` or similar, the table schema assumption is wrong — fix `_load_tables_for_spike` and rerun.

- [ ] **Step 4: Verify the existing unit tests still pass (no regressions)**

```bash
pytest docs/superpowers/plans/spot-checks/splice-spike/test_splice_spike.py -v
```

Expected: 13 PASS.

- [ ] **Step 5: Commit**

```bash
git add docs/superpowers/plans/spot-checks/splice-spike/splice_spike.py
git commit -m "spike(splice): CLI driver wiring real extract_pdf + extract_pdf_layout"
```

---

## Task 6: Generate spliced output for each of the 5 chosen PDFs

**Files:**
- Create: `docs/superpowers/plans/spot-checks/splice-spike/outputs/<paper>.md` × 5

**Goal:** Run the CLI on each of the five chosen PDFs and save the spliced-markdown output for review. These five files ARE the data the phase-0 report draws conclusions from.

- [ ] **Step 1: Make the outputs directory**

```bash
mkdir docs/superpowers/plans/spot-checks/splice-spike/outputs
```

- [ ] **Step 2: Generate one output per chosen PDF**

For each filename in `papers.md`, run:

```bash
python docs/superpowers/plans/spot-checks/splice-spike/splice_spike.py "../PDFextractor/test-pdfs/apa/<paper>.pdf" > "docs/superpowers/plans/spot-checks/splice-spike/outputs/<paper>.md"
```

There are five such commands (one per paper from Task 1). If any errors, capture stderr in a separate `.err` file alongside the `.md` so the failure mode is preserved for the report.

- [ ] **Step 3: Verify all five outputs exist and are non-empty**

```bash
ls -lah docs/superpowers/plans/spot-checks/splice-spike/outputs/
```

Expected: 5 `.md` files, each non-zero size.

- [ ] **Step 4: Commit the outputs**

```bash
git add docs/superpowers/plans/spot-checks/splice-spike/outputs/
git commit -m "spike(splice): generated outputs for 5 candidate PDFs"
```

---

## Task 7: Manual eyeball review and write the phase-0 report

**Files:**
- Create: `docs/superpowers/plans/spot-checks/splice-spike/report.md`

**Goal:** Open each of the 5 output `.md` files alongside the source PDF (in any markdown viewer + PDF viewer) and assess: did the splice land at the right place? Are cells lost or duplicated? Are pages where the algorithm fails entirely? The report ANSWERS phase 0's gating question.

- [ ] **Step 1: Review each output against its PDF**

For each of the 5 papers, open both the source PDF and `outputs/<paper>.md`. Note for each table found in the PDF:

- Is there a corresponding markdown table in the output? (Yes / No)
- Is the markdown table at the correct reading-order position relative to surrounding prose? (Yes / Approximately / No)
- Are all cells present, with the right values? (Yes / Some missing / Garbled)
- If there is a `[splice-spike: table location not found …]` note, why did the algorithm fail? (Page-boundary table / structurally complex table / two-column-page interleaving / other)

Tally the assessments. The unit of measurement is "tables correctly spliced" out of "total tables in the 5 PDFs."

- [ ] **Step 2: Write the report**

Create `docs/superpowers/plans/spot-checks/splice-spike/report.md` with this exact structure (replace the bracketed parts with actual data from the review):

```markdown
# Splice Spike — Phase 0 Report

**Date:** [YYYY-MM-DD when review was done]
**Spec:** docs/superpowers/specs/2026-05-08-unified-extraction-design.md

## Summary

[One paragraph: of N tables across 5 PDFs, M were correctly spliced (P%).
Algorithm succeeded on these layout conditions: [list]. Algorithm failed on
these layout conditions: [list].]

## Per-paper findings

### 1. [paper filename]
- Layout: [single-column / two-column / multi-table / etc.]
- Tables in PDF: [N]
- Tables correctly spliced: [M]
- Notes: [free text — what worked, what didn't]

### 2. [paper filename]
…

(same structure for papers 3, 4, 5)

## Failure modes observed

[Itemized list. Each item: a brief description of the failure pattern + which
papers exhibit it + a guess at the cause.]

## Recommendation

Pick ONE:

**(a) Ship phase 1 as designed.** The splice algorithm is reliable enough on
the spike corpus that the spec's phase-1 plan can proceed without algorithmic
changes. Failure modes are bounded and the diagnostic-note fallback is
acceptable.

**(b) Modify the splice algorithm.** Specific changes recommended: [list].
The spec stays intact; only the splice-locator implementation needs the
listed adjustments before phase 1.

**(c) Fall back to "tables-at-end-of-section" rendering.** Splicing in-line
is too unreliable on real-world PDFs. Phase 1 should render tables in a
``## Tables`` appendix at the end of the document (or end of section)
instead of inline. The spec needs an amendment in §3 and §6.

[State the chosen recommendation in 1–2 sentences with the justification
from the data above.]

## What this report does NOT say

- Performance numbers. Phase 0 did not measure speed.
- Behavior on non-APA layouts (Nature, JAMA, AMA). Phase 0 corpus was APA only.
- Behavior on tables with extracted figures or images.
- Whether the markdown profile (sections, footnotes, figures) is correct —
  phase 0 only addresses the splice algorithm.
```

- [ ] **Step 3: Commit the report**

```bash
git add docs/superpowers/plans/spot-checks/splice-spike/report.md
git commit -m "spike(splice): phase-0 report and recommendation"
```

---

## Task 8: Decide next step

**Files:**
- None (this task is a decision, not a code change).

**Goal:** Based on the report's recommendation, choose the next action and announce it clearly so phase 1's plan can be written with the right starting assumptions.

- [ ] **Step 1: Read the recommendation in `report.md`**

- [ ] **Step 2: Pick the next action**

- If recommendation is **(a) Ship phase 1 as designed:** announce "Phase 0 succeeded; proceed to write phase 1 implementation plan." Open a new brainstorming/writing-plans session targeting `docs/superpowers/specs/2026-05-08-unified-extraction-design.md` phase 1.

- If recommendation is **(b) Modify the splice algorithm:** announce "Phase 0 succeeded with caveats; the spec stays but the splice algorithm needs the changes listed in the report. Next step: amend `splice_spike.py` to incorporate those changes, regenerate outputs, and update the report. Then proceed to phase 1 plan."

- If recommendation is **(c) Fall back to tables-at-end-of-section:** announce "Phase 0 surfaced a blocker; the spec needs amendment. Next step: revise `docs/superpowers/specs/2026-05-08-unified-extraction-design.md` §3 (table conventions) and §6 (engineering risk) to reflect tables-at-end rendering, then write phase 1's plan against the amended spec."

In all three cases, the spike artifact (`splice-spike/` directory) STAYS in the repo as the durable record of why the chosen direction was picked. It's deleted only after phase 1 ships and we know which (if any) spike helpers survived.

---

## Self-Review (writer's checklist; run before handing the plan off)

Run this checklist on the plan before it's executed.

- [ ] **Spec coverage:** every requirement in spec §6–§7 phase 0 maps to a task above?
  - "5-PDF prototype script" → Tasks 2–5 (helpers + CLI), Task 6 (run on 5 PDFs).
  - "Eyeball-diff" → Task 7.
  - "Splices look correct on ≥4 of 5 papers" → Task 7's per-paper findings.
  - "If <4 of 5 succeed: revisit design before phase 1" → Task 8 branches.

- [ ] **Placeholder scan:** no "TBD"/"TODO"/"add appropriate handling" in any task body. The five paper filenames in Task 1 are *recommendations* with explicit instructions to substitute concrete filenames before committing — that is intentional, not a placeholder.

- [ ] **Type consistency:** function names match across tasks?
  - `pdfplumber_table_to_markdown` defined Task 2, used Task 4 ✓
  - `find_table_region_in_text` defined Task 3, used Task 4 ✓
  - `splice_tables_into_text` defined Task 4, used Task 5 ✓
  - `_load_tables_for_spike`, `_run_cli` defined Task 5, used Task 6 (via CLI) ✓

- [ ] **Schema risk on `extract_pdf_layout`:** Task 5 step 1 explicitly inspects the real schema before assuming it. The fallback advice ("adjust `_load_tables_for_spike` accordingly") is correct: this is the ONE place where assumptions might be wrong, and the spike is the right place to discover that.

If any of these check items fail when read in sequence: fix inline before handoff.
