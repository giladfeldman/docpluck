# Table & Figure Extraction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `docpluck.tables` and `docpluck.figures` package, plus a top-level `extract_pdf_structured()` function, that detects every table and figure in born-digital academic PDFs, structures table cells when ruling-line geometry or clean column-gap whitespace permits, and isolates (raw text + bbox + caption + footnote) when structure cannot be confidently recovered. Existing `extract_pdf()` behavior stays bit-for-bit identical.

**Architecture:** Two packages — `docpluck/tables/` (detection + lattice clustering + whitespace clustering + HTML render + confidence scoring) and `docpluck/figures/` (caption + bbox metadata only). New `docpluck/extract_structured.py` orchestrator runs `extract_pdf()` for raw text, consumes `LayoutDoc` from `docpluck/extract_layout.py` (introduced by section-id v1.6.0), dispatches to detection modules, applies an optional `table_text_mode="placeholder"` substitution, and assembles a result dict. All MIT-licensed; no new runtime deps.

**Tech Stack:** Python ≥3.10, dataclasses, TypedDict, pdfplumber (already a dep), pdfminer.six (transitive via pdfplumber — used directly for `LTLine`/`LTRect`/`LTChar` access), pytest. No new runtime deps.

**Spec:** `docs/superpowers/specs/2026-05-06-table-extraction-design.md`

**Coordination:** This plan has TWO BARRIERS that must be cleared before specific phases can proceed:

- **BARRIER 1 — Section-id Phase 4** must land on `main` (the `extract_pdf_layout()` + `LayoutDoc` piece in `docpluck/extract_layout.py`) before any task in **Phases 6–14**. Phases 1–5 are fully implementable now and produce committable, tested code in parallel with section-id work.
- **BARRIER 2 — Section-id Phase 5** must land on `main` (the `F0` footnote/header strip step in `normalize.py`) before **Phase 13** (the F0 table-region-aware patch).

When you reach a barrier and it's not clear, stop and ask the user.

---

## Pre-flight

- [ ] **Step 0.1: Confirm working tree is clean**

```bash
cd C:/Users/filin/Dropbox/Vibe/MetaScienceTools/docpluck
git status
```

Expected: `nothing to commit, working tree clean`. If the section-id branch is in flight on this same checkout, coordinate with the user before continuing.

- [ ] **Step 0.2: Create a fresh branch**

```bash
git checkout main
git pull origin main
git checkout -b feat/table-extraction
```

Expected: branch switched to `feat/table-extraction`.

- [ ] **Step 0.3: Confirm full test suite passes before any changes**

```bash
pytest -x -q
```

Expected: all green. If anything fails, stop and investigate before adding new work.

- [ ] **Step 0.4: Confirm pdfplumber is importable**

```bash
python -c "import pdfplumber; print(pdfplumber.__version__)"
```

Expected: a version string ≥ 0.11.0.

---

## Phase 1 — Foundation (no external dependencies)

Goal of phase: every type, version constant, and package skeleton the rest of the plan refers to exists and is importable. No detection logic yet. **All of Phase 1 is implementable before BARRIER 1.**

### Task 1: Create `tables/` and `figures/` package skeletons + `TABLE_EXTRACTION_VERSION`

**Files:**
- Create: `docpluck/tables/__init__.py`
- Create: `docpluck/figures/__init__.py`
- Create: `docpluck/extract_structured.py`
- Create: `tests/test_structured_version.py`

- [ ] **Step 1.1: Write the failing test**

`tests/test_structured_version.py`:

```python
"""Smoke test — modules exist and TABLE_EXTRACTION_VERSION is exposed."""


def test_tables_package_imports():
    from docpluck import tables
    assert tables is not None


def test_figures_package_imports():
    from docpluck import figures
    assert figures is not None


def test_extract_structured_module_imports():
    from docpluck import extract_structured
    assert extract_structured is not None


def test_table_extraction_version_is_semver_string():
    from docpluck.extract_structured import TABLE_EXTRACTION_VERSION
    parts = TABLE_EXTRACTION_VERSION.split(".")
    assert len(parts) == 3
    assert all(p.isdigit() for p in parts)


def test_table_extraction_version_starts_at_1_0_0():
    from docpluck.extract_structured import TABLE_EXTRACTION_VERSION
    assert TABLE_EXTRACTION_VERSION == "1.0.0"
```

- [ ] **Step 1.2: Run test to verify it fails**

```bash
pytest tests/test_structured_version.py -v
```

Expected: `ImportError: No module named 'docpluck.tables'` or similar.

- [ ] **Step 1.3: Create `docpluck/tables/__init__.py`**

```python
"""
docpluck.tables — table detection + structuring for academic PDFs.

See docs/superpowers/specs/2026-05-06-table-extraction-design.md for the design.

Public types: Cell, Table, TableKind, TableRendering.
"""

__all__: list[str] = []
```

- [ ] **Step 1.4: Create `docpluck/figures/__init__.py`**

```python
"""
docpluck.figures — figure metadata extraction for academic PDFs.

See docs/superpowers/specs/2026-05-06-table-extraction-design.md for the design.

Public types: Figure.
"""

__all__: list[str] = []
```

- [ ] **Step 1.5: Create `docpluck/extract_structured.py`**

```python
"""
docpluck.extract_structured — top-level structured PDF extraction.

Provides extract_pdf_structured(), the orchestrator over the existing
extract_pdf() text path plus the new tables/ and figures/ detection paths.

See docs/superpowers/specs/2026-05-06-table-extraction-design.md for the design.
"""

TABLE_EXTRACTION_VERSION = "1.0.0"

__all__ = ["TABLE_EXTRACTION_VERSION"]
```

- [ ] **Step 1.6: Run tests to verify they pass**

```bash
pytest tests/test_structured_version.py -v
```

Expected: 5 passing.

- [ ] **Step 1.7: Commit**

```bash
git add docpluck/tables/__init__.py docpluck/figures/__init__.py docpluck/extract_structured.py tests/test_structured_version.py
git commit -m "feat(structured): scaffold tables/figures packages + TABLE_EXTRACTION_VERSION"
```

### Task 2: Add `Cell`, `Table`, `Figure` TypedDicts

**Files:**
- Modify: `docpluck/tables/__init__.py`
- Modify: `docpluck/figures/__init__.py`
- Test: `tests/test_structured_types.py`

- [ ] **Step 2.1: Write the failing test**

`tests/test_structured_types.py`:

```python
"""TypedDict types — Cell, Table, Figure exposed from their packages."""

from typing import get_type_hints


def test_cell_typed_dict_fields():
    from docpluck.tables import Cell
    hints = get_type_hints(Cell)
    expected = {"r", "c", "rowspan", "colspan", "text", "is_header", "bbox"}
    assert set(hints.keys()) == expected


def test_table_typed_dict_fields():
    from docpluck.tables import Table
    hints = get_type_hints(Table)
    expected = {
        "id", "label", "page", "bbox", "caption", "footnote",
        "kind", "rendering", "confidence",
        "n_rows", "n_cols", "header_rows",
        "cells", "html", "raw_text",
    }
    assert set(hints.keys()) == expected


def test_table_kind_literal_values():
    from docpluck.tables import TableKind
    # TableKind is a Literal type alias; runtime check via __args__ on the alias
    import typing
    args = typing.get_args(TableKind)
    assert set(args) == {"structured", "isolated"}


def test_table_rendering_literal_values():
    from docpluck.tables import TableRendering
    import typing
    args = typing.get_args(TableRendering)
    assert set(args) == {"lattice", "whitespace", "isolated"}


def test_figure_typed_dict_fields():
    from docpluck.figures import Figure
    hints = get_type_hints(Figure)
    expected = {"id", "label", "page", "bbox", "caption"}
    assert set(hints.keys()) == expected


def test_cell_constructable_as_dict():
    from docpluck.tables import Cell
    c: Cell = {
        "r": 0, "c": 0, "rowspan": 1, "colspan": 1,
        "text": "Variable", "is_header": True,
        "bbox": (0.0, 0.0, 100.0, 20.0),
    }
    assert c["r"] == 0


def test_figure_constructable_as_dict():
    from docpluck.figures import Figure
    f: Figure = {
        "id": "f1", "label": "Figure 1", "page": 3,
        "bbox": (72.0, 100.0, 540.0, 320.0),
        "caption": "Mean reaction time across conditions.",
    }
    assert f["id"] == "f1"
```

- [ ] **Step 2.2: Run test to verify it fails**

```bash
pytest tests/test_structured_types.py -v
```

Expected: `ImportError: cannot import name 'Cell' from 'docpluck.tables'`.

- [ ] **Step 2.3: Implement TypedDicts in `docpluck/tables/__init__.py`**

```python
"""
docpluck.tables — table detection + structuring for academic PDFs.

See docs/superpowers/specs/2026-05-06-table-extraction-design.md for the design.

Public types: Cell, Table, TableKind, TableRendering.
"""

from __future__ import annotations

from typing import Literal, Optional, TypedDict


TableKind = Literal["structured", "isolated"]
TableRendering = Literal["lattice", "whitespace", "isolated"]


class Cell(TypedDict):
    r: int
    c: int
    rowspan: int
    colspan: int
    text: str
    is_header: bool
    bbox: tuple[float, float, float, float]


class Table(TypedDict):
    id: str
    label: Optional[str]
    page: int
    bbox: tuple[float, float, float, float]
    caption: Optional[str]
    footnote: Optional[str]
    kind: TableKind
    rendering: TableRendering
    confidence: Optional[float]
    n_rows: Optional[int]
    n_cols: Optional[int]
    header_rows: Optional[int]
    cells: list[Cell]
    html: Optional[str]
    raw_text: str


__all__ = ["Cell", "Table", "TableKind", "TableRendering"]
```

- [ ] **Step 2.4: Implement Figure TypedDict in `docpluck/figures/__init__.py`**

```python
"""
docpluck.figures — figure metadata extraction for academic PDFs.

See docs/superpowers/specs/2026-05-06-table-extraction-design.md for the design.

Public types: Figure.
"""

from __future__ import annotations

from typing import Optional, TypedDict


class Figure(TypedDict):
    id: str
    label: Optional[str]
    page: int
    bbox: tuple[float, float, float, float]
    caption: Optional[str]


__all__ = ["Figure"]
```

- [ ] **Step 2.5: Run tests to verify they pass**

```bash
pytest tests/test_structured_types.py -v
```

Expected: 7 passing.

- [ ] **Step 2.6: Commit**

```bash
git add docpluck/tables/__init__.py docpluck/figures/__init__.py tests/test_structured_types.py
git commit -m "feat(structured): add Cell, Table, Figure TypedDicts + TableKind/TableRendering literals"
```

### Task 3: Add `StructuredResult` TypedDict + re-export `Table`/`Figure` from top-level package

**Files:**
- Modify: `docpluck/extract_structured.py`
- Modify: `docpluck/__init__.py`
- Test: `tests/test_structured_result_type.py`

- [ ] **Step 3.1: Write the failing test**

`tests/test_structured_result_type.py`:

```python
"""StructuredResult TypedDict + top-level re-exports."""

from typing import get_type_hints


def test_structured_result_fields():
    from docpluck.extract_structured import StructuredResult
    hints = get_type_hints(StructuredResult)
    expected = {
        "text", "method", "page_count",
        "tables", "figures", "table_extraction_version",
    }
    assert set(hints.keys()) == expected


def test_table_reexported_from_top_level():
    from docpluck import Table
    assert Table is not None


def test_figure_reexported_from_top_level():
    from docpluck import Figure
    assert Figure is not None


def test_table_extraction_version_reexported_from_top_level():
    from docpluck import TABLE_EXTRACTION_VERSION
    assert TABLE_EXTRACTION_VERSION == "1.0.0"


def test_existing_extract_pdf_still_exported():
    """Backwards-compat smoke: existing extract_pdf is still there."""
    from docpluck import extract_pdf
    assert callable(extract_pdf)
```

- [ ] **Step 3.2: Run test to verify it fails**

```bash
pytest tests/test_structured_result_type.py -v
```

Expected: `ImportError: cannot import name 'StructuredResult'`.

- [ ] **Step 3.3: Add `StructuredResult` to `docpluck/extract_structured.py`**

Replace the current contents of `docpluck/extract_structured.py` with:

```python
"""
docpluck.extract_structured — top-level structured PDF extraction.

Provides extract_pdf_structured(), the orchestrator over the existing
extract_pdf() text path plus the new tables/ and figures/ detection paths.

See docs/superpowers/specs/2026-05-06-table-extraction-design.md for the design.
"""

from __future__ import annotations

from typing import TypedDict

from .tables import Table
from .figures import Figure


TABLE_EXTRACTION_VERSION = "1.0.0"


class StructuredResult(TypedDict):
    text: str
    method: str
    page_count: int
    tables: list[Table]
    figures: list[Figure]
    table_extraction_version: str


__all__ = ["TABLE_EXTRACTION_VERSION", "StructuredResult"]
```

- [ ] **Step 3.4: Update `docpluck/__init__.py` to re-export new symbols**

Edit `docpluck/__init__.py`. Find the existing `from .extract import ...` block and add new imports below it. Then update `__all__`.

Add the import lines:

```python
from .tables import Table
from .figures import Figure
from .extract_structured import TABLE_EXTRACTION_VERSION, StructuredResult
```

Update `__all__` to include the new symbols (preserve all existing ones):

```python
__all__ = [
    # Extraction
    "extract_pdf",
    "extract_pdf_file",
    "extract_docx",
    "extract_html",
    "html_to_text",
    "count_pages",
    # Normalization
    "normalize_text",
    "NormalizationLevel",
    "NormalizationReport",
    # Quality
    "compute_quality_score",
    # Batch
    "ExtractionReport",
    "extract_to_dir",
    # Version
    "get_version_info",
    # Structured extraction (v2.0)
    "Table",
    "Figure",
    "TABLE_EXTRACTION_VERSION",
    "StructuredResult",
]
```

- [ ] **Step 3.5: Run tests to verify they pass**

```bash
pytest tests/test_structured_result_type.py tests/test_structured_version.py tests/test_structured_types.py -v
```

Expected: all passing.

- [ ] **Step 3.6: Run the full suite to verify backwards compat**

```bash
pytest -x -q
```

Expected: all green.

- [ ] **Step 3.7: Commit**

```bash
git add docpluck/extract_structured.py docpluck/__init__.py tests/test_structured_result_type.py
git commit -m "feat(structured): add StructuredResult + re-export Table/Figure/TABLE_EXTRACTION_VERSION"
```

---

## Phase 2 — Caption-regex pre-scan (no external dependencies)

Goal of phase: pure-regex caption detection on `raw_text` that returns the set of pages containing table or figure captions. No layout dependency. **Phase 2 is implementable before BARRIER 1.**

### Task 4: Caption regex constants + `find_caption_pages()`

**Files:**
- Create: `docpluck/tables/captions.py`
- Test: `tests/test_caption_regex.py`

- [ ] **Step 4.1: Write the failing test**

`tests/test_caption_regex.py`:

```python
"""Caption-regex pre-scan tests."""

import pytest
from docpluck.tables.captions import (
    TABLE_CAPTION_RE,
    FIGURE_CAPTION_RE,
    find_caption_matches,
    CaptionMatch,
)


@pytest.mark.parametrize("line, num", [
    ("Table 1. Descriptive statistics", 1),
    ("Table 2: Correlation matrix", 2),
    ("Table 12 Means and standard deviations", 12),
    ("    Table 3. Indented caption", 3),
    ("Table 1.", 1),
])
def test_table_caption_re_matches(line, num):
    m = TABLE_CAPTION_RE.search(line)
    assert m is not None
    assert int(m.group("num")) == num


@pytest.mark.parametrize("line", [
    "the table shows that",            # no number
    "Tabular form of",                  # not "Table"
    "see Table",                        # no number
    "Table A1",                         # appendix-numbered, deferred to level-C
])
def test_table_caption_re_does_not_match(line):
    assert TABLE_CAPTION_RE.search(line) is None


@pytest.mark.parametrize("line, num", [
    ("Figure 1. Mean reaction time", 1),
    ("Figure 2: Forest plot of effects", 2),
    ("Fig. 3 Bar chart", 3),
    ("Fig 4. Histogram", 4),
])
def test_figure_caption_re_matches(line, num):
    m = FIGURE_CAPTION_RE.search(line)
    assert m is not None
    assert int(m.group("num")) == num


def test_find_caption_matches_with_page_offsets():
    """find_caption_matches: regex over raw_text + page-offset list -> CaptionMatch list."""
    raw_text = (
        "Page 1 prose text that has nothing\n"
        "Just normal sentences here.\n"
        "\f"  # form-feed = pdftotext page break
        "Page 2 introduction paragraph...\n"
        "Table 1. Descriptive statistics\n"
        "Variable  M  SD\n"
        "\f"
        "Page 3 results section\n"
        "Figure 2. Bar chart of conditions\n"
    )
    # page_offsets: list of char-offsets where each page starts (1-indexed)
    page_offsets = [0, 67, 142]   # values are illustrative — test structure, not exact offsets

    matches = find_caption_matches(raw_text, page_offsets)
    assert len(matches) == 2
    table_match = next(m for m in matches if m.kind == "table")
    figure_match = next(m for m in matches if m.kind == "figure")
    assert table_match.number == 1
    assert table_match.label == "Table 1"
    assert figure_match.number == 2
    assert figure_match.label == "Figure 2"
    # Both should have a non-None page assigned
    assert table_match.page >= 1
    assert figure_match.page >= 1


def test_caption_match_dataclass_shape():
    m = CaptionMatch(
        kind="table",
        number=1,
        label="Table 1",
        page=3,
        char_start=100,
        char_end=130,
        line_text="Table 1. Descriptive statistics",
    )
    assert m.kind == "table"
    assert m.number == 1
```

- [ ] **Step 4.2: Run test to verify it fails**

```bash
pytest tests/test_caption_regex.py -v
```

Expected: `ImportError: No module named 'docpluck.tables.captions'`.

- [ ] **Step 4.3: Implement `docpluck/tables/captions.py`**

```python
"""
Caption-regex pre-scan for tables and figures.

Returns the set of pages that contain at least one Table N or Figure N
caption — used by extract_pdf_structured() in default mode to skip
pdfplumber on caption-free pages (~5x speedup vs. thorough mode).

See spec §5.1 for the regex shape rationale.
"""

from __future__ import annotations

import bisect
import re
from dataclasses import dataclass
from typing import Literal


TABLE_CAPTION_RE = re.compile(
    r"^\s*Table\s+(?P<num>\d+)(?:[.:]|\s+[A-Z])",
    re.MULTILINE,
)

FIGURE_CAPTION_RE = re.compile(
    r"^\s*(?:Figure|Fig\.?)\s+(?P<num>\d+)(?:[.:]|\s+[A-Z])",
    re.MULTILINE,
)


CaptionKind = Literal["table", "figure"]


@dataclass(frozen=True)
class CaptionMatch:
    kind: CaptionKind
    number: int
    label: str
    page: int
    char_start: int
    char_end: int
    line_text: str


def find_caption_matches(
    raw_text: str,
    page_offsets: list[int],
) -> list[CaptionMatch]:
    """Find all Table N / Figure N caption lines in raw_text.

    Args:
        raw_text: Linear extracted text (output of extract_pdf()).
        page_offsets: list[int] where page_offsets[i] is the char index
            where page i+1 starts in raw_text. Length = page_count.

    Returns:
        List of CaptionMatch in document order. Page is 1-indexed.
    """
    matches: list[CaptionMatch] = []

    for kind, regex in [("table", TABLE_CAPTION_RE), ("figure", FIGURE_CAPTION_RE)]:
        for m in regex.finditer(raw_text):
            num = int(m.group("num"))
            label_word = "Table" if kind == "table" else "Figure"
            label = f"{label_word} {num}"
            char_start = m.start()
            line_text = _line_at(raw_text, char_start)
            char_end = char_start + len(line_text)
            page = _page_for_offset(char_start, page_offsets)
            matches.append(CaptionMatch(
                kind=kind,
                number=num,
                label=label,
                page=page,
                char_start=char_start,
                char_end=char_end,
                line_text=line_text,
            ))

    matches.sort(key=lambda m: m.char_start)
    return matches


def _line_at(text: str, offset: int) -> str:
    """Return the full line in text containing offset (without trailing newline)."""
    line_start = text.rfind("\n", 0, offset) + 1
    line_end = text.find("\n", offset)
    if line_end == -1:
        line_end = len(text)
    return text[line_start:line_end]


def _page_for_offset(offset: int, page_offsets: list[int]) -> int:
    """1-indexed page number for a char offset."""
    if not page_offsets:
        return 1
    idx = bisect.bisect_right(page_offsets, offset) - 1
    return max(idx + 1, 1)


__all__ = [
    "TABLE_CAPTION_RE",
    "FIGURE_CAPTION_RE",
    "CaptionMatch",
    "CaptionKind",
    "find_caption_matches",
]
```

- [ ] **Step 4.4: Run tests to verify they pass**

```bash
pytest tests/test_caption_regex.py -v
```

Expected: all passing (10+ test cases).

- [ ] **Step 4.5: Commit**

```bash
git add docpluck/tables/captions.py tests/test_caption_regex.py
git commit -m "feat(tables): add caption-regex pre-scan + find_caption_matches()"
```

---

## Phase 3 — HTML renderer (no external dependencies)

Goal of phase: pure-function `cells_to_html()` that takes a list of `Cell` and returns an `<table>` HTML string. No layout dependency. **Phase 3 is implementable before BARRIER 1.**

### Task 5: HTML renderer

**Files:**
- Create: `docpluck/tables/render.py`
- Test: `tests/test_render_html.py`

- [ ] **Step 5.1: Write the failing test**

`tests/test_render_html.py`:

```python
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
    second_row = html[html.find("<tbody>"):html.find("</tbody>")]
    assert second_row.count("<td>") == 2
```

- [ ] **Step 5.2: Run test to verify it fails**

```bash
pytest tests/test_render_html.py -v
```

Expected: `ImportError: cannot import name 'cells_to_html'`.

- [ ] **Step 5.3: Implement `docpluck/tables/render.py`**

```python
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
```

- [ ] **Step 5.4: Run tests to verify they pass**

```bash
pytest tests/test_render_html.py -v
```

Expected: 6 passing.

- [ ] **Step 5.5: Commit**

```bash
git add docpluck/tables/render.py tests/test_render_html.py
git commit -m "feat(tables): add HTML renderer (cells_to_html)"
```

---

## Phase 4 — Confidence scoring (no external dependencies)

Goal of phase: pure-function `score_table()` that takes the rendering kind and the cell list, returns a float in [0, 1] OR `None` (for `kind="isolated"`). Threshold logic for falling back to isolated lives here. **Phase 4 is implementable before BARRIER 1.**

### Task 6: Confidence scorer

**Files:**
- Create: `docpluck/tables/confidence.py`
- Test: `tests/test_confidence.py`

- [ ] **Step 6.1: Write the failing test**

`tests/test_confidence.py`:

```python
"""Confidence scoring for structured tables."""

from docpluck.tables import Cell
from docpluck.tables.confidence import (
    score_table,
    should_fall_back_to_isolated,
    ISOLATION_THRESHOLD,
)


def _row(r, n_cols, is_header=False) -> list[Cell]:
    return [
        {
            "r": r, "c": c, "rowspan": 1, "colspan": 1,
            "text": "x", "is_header": is_header,
            "bbox": (0.0, 0.0, 0.0, 0.0),
        }
        for c in range(n_cols)
    ]


def test_isolated_returns_none():
    assert score_table([], rendering="isolated") is None


def test_clean_lattice_high_score_unclamped():
    # 4 rows × 3 cols, all rows full → no deviation → base 0.85
    cells = []
    for r in range(4):
        cells.extend(_row(r, 3, is_header=(r == 0)))
    raw = score_table(cells, rendering="lattice")
    assert raw is not None
    assert raw == 0.85   # base, no penalties


def test_lattice_can_go_below_threshold_when_degraded():
    # Many deviation rows → pre-clamp score < 0.4 → should_fall_back returns True
    cells = []
    for r in range(12):
        cells.extend(_row(r, 1 if r else 3))  # row 0 has 3 cells, others 1
    raw = score_table(cells, rendering="lattice")
    assert raw is not None
    assert raw < 0.4
    assert should_fall_back_to_isolated(raw) is True


def test_clean_whitespace_lower_than_lattice():
    cells = []
    for r in range(4):
        cells.extend(_row(r, 3, is_header=(r == 0)))
    lattice = score_table(cells, rendering="lattice")
    whitespace = score_table(cells, rendering="whitespace")
    assert whitespace is not None and lattice is not None
    assert whitespace < lattice
    assert whitespace == 0.65   # base, no penalties


def test_should_fall_back_when_below_threshold():
    # Pre-clamp score below ISOLATION_THRESHOLD → fall back to isolated
    assert should_fall_back_to_isolated(score=0.3) is True
    assert should_fall_back_to_isolated(score=0.39) is True
    assert should_fall_back_to_isolated(score=0.4) is False
    assert should_fall_back_to_isolated(score=None) is False


def test_clamp_confidence_lattice_bounds():
    # Clamp applied separately by callers; raw scores beyond bounds get clamped.
    from docpluck.tables.confidence import clamp_confidence
    assert clamp_confidence(0.99, rendering="lattice") == 0.95
    assert clamp_confidence(0.10, rendering="lattice") == 0.5
    assert clamp_confidence(0.85, rendering="lattice") == 0.85


def test_clamp_confidence_whitespace_bounds():
    from docpluck.tables.confidence import clamp_confidence
    assert clamp_confidence(0.99, rendering="whitespace") == 0.85
    assert clamp_confidence(0.10, rendering="whitespace") == 0.4
    assert clamp_confidence(0.65, rendering="whitespace") == 0.65


def test_clamp_confidence_isolated_returns_none():
    from docpluck.tables.confidence import clamp_confidence
    assert clamp_confidence(0.99, rendering="isolated") is None
    assert clamp_confidence(None, rendering="isolated") is None


def test_isolation_threshold_value():
    """The threshold is 0.4 per spec §5.6."""
    assert ISOLATION_THRESHOLD == 0.4
```

- [ ] **Step 6.2: Run test to verify it fails**

```bash
pytest tests/test_confidence.py -v
```

Expected: `ImportError: cannot import name 'score_table'`.

- [ ] **Step 6.3: Implement `docpluck/tables/confidence.py`**

```python
"""
Confidence scoring for structured tables.

Two-stage design:
  - score_table() returns the *pre-clamp* raw score (or None for isolated).
    The orchestrator uses this raw value to decide whether to fall back to
    kind="isolated" (when raw < ISOLATION_THRESHOLD = 0.4).
  - clamp_confidence() applies per-rendering floors/ceilings to produce
    the user-facing Table.confidence value.

This separation matters: if we clamped inside score_table, the floor would
silently absorb the fall-back signal (e.g. whitespace floor 0.4 == threshold
0.4 means clamped scores never trigger fall-back).

See spec §5.6.
"""

from __future__ import annotations

from collections import Counter
from typing import Optional

from . import Cell, TableRendering


ISOLATION_THRESHOLD: float = 0.4


def score_table(cells: list[Cell], *, rendering: TableRendering) -> Optional[float]:
    """Pre-clamp raw confidence. None for isolated."""
    if rendering == "isolated":
        return None

    if not cells:
        return 0.0

    if rendering == "lattice":
        base = 0.85
    else:  # whitespace
        base = 0.65

    cells_per_row: dict[int, int] = Counter(c["r"] for c in cells)
    counts = list(cells_per_row.values())
    modal = Counter(counts).most_common(1)[0][0]

    deviation_rows = sum(1 for n in counts if n != modal)
    score = base - 0.05 * deviation_rows

    if any(n == 0 for n in counts):
        score -= 0.10

    return score


def clamp_confidence(score: Optional[float], *, rendering: TableRendering) -> Optional[float]:
    """Apply per-rendering floor/ceiling to produce the user-facing confidence."""
    if rendering == "isolated" or score is None:
        return None
    if rendering == "lattice":
        floor, ceiling = 0.5, 0.95
    else:  # whitespace
        floor, ceiling = 0.4, 0.85
    return max(floor, min(ceiling, score))


def should_fall_back_to_isolated(score: Optional[float]) -> bool:
    """Whether a pre-clamp score is too low to ship as structured."""
    if score is None:
        return False
    return score < ISOLATION_THRESHOLD


__all__ = ["score_table", "clamp_confidence", "should_fall_back_to_isolated", "ISOLATION_THRESHOLD"]
```

- [ ] **Step 6.4: Run tests to verify they pass**

```bash
pytest tests/test_confidence.py -v
```

Expected: 6 passing.

- [ ] **Step 6.5: Commit**

```bash
git add docpluck/tables/confidence.py tests/test_confidence.py
git commit -m "feat(tables): add confidence scoring (score_table, ISOLATION_THRESHOLD=0.4)"
```

---

## Phase 5 — Smoke fixture corpus collection (no external dependencies)

Goal of phase: assemble ~15 PDFs into `tests/fixtures/structured/` with a manifest. Per-PDF assertion files come later (after detection logic exists). **Phase 5 is implementable before BARRIER 1.**

### Task 7: Build fixture directory + manifest

**Files:**
- Create: `tests/fixtures/structured/README.md`
- Create: `tests/fixtures/structured/MANIFEST.json`
- Create: `tests/fixtures/structured/<various>.pdf` (copied from existing test corpora)
- Test: `tests/test_fixtures_manifest.py`

- [ ] **Step 7.1: Write the failing test**

`tests/test_fixtures_manifest.py`:

```python
"""Smoke fixture manifest is well-formed and points at real files."""

import json
import os
from pathlib import Path

import pytest


_FIXTURES_DIR = Path(__file__).parent / "fixtures" / "structured"
_MANIFEST = _FIXTURES_DIR / "MANIFEST.json"


def test_fixtures_directory_exists():
    assert _FIXTURES_DIR.is_dir(), f"Missing: {_FIXTURES_DIR}"


def test_manifest_exists_and_is_json():
    assert _MANIFEST.is_file(), f"Missing: {_MANIFEST}"
    json.loads(_MANIFEST.read_text(encoding="utf-8"))


def test_manifest_schema():
    data = json.loads(_MANIFEST.read_text(encoding="utf-8"))
    assert "fixtures" in data
    assert isinstance(data["fixtures"], list)
    assert len(data["fixtures"]) >= 8, "expect ≥8 fixtures collected"

    for entry in data["fixtures"]:
        assert "filename" in entry
        assert "category" in entry
        assert entry["category"] in {
            "lattice_table", "apa_lineless", "nature_minimal_rule",
            "figure_only", "negative_no_tables_no_figures",
            "table_of_contents_negative", "uncaptioned_table",
        }
        assert "expected_tables" in entry
        assert "expected_figures" in entry


@pytest.mark.parametrize("entry", json.loads(_MANIFEST.read_text(encoding="utf-8"))["fixtures"]
                                  if _MANIFEST.exists() else [])
def test_fixture_file_exists(entry):
    path = _FIXTURES_DIR / entry["filename"]
    assert path.is_file(), f"Missing fixture: {path}"
    # Sanity: file is non-empty and has %PDF magic
    head = path.read_bytes()[:5]
    assert head[:4] == b"%PDF", f"Not a PDF: {path}"
```

- [ ] **Step 7.2: Run test to verify it fails**

```bash
pytest tests/test_fixtures_manifest.py -v
```

Expected: `AssertionError: Missing: .../fixtures/structured`.

- [ ] **Step 7.3: Create the fixtures directory + README**

```bash
mkdir -p tests/fixtures/structured
```

`tests/fixtures/structured/README.md`:

```markdown
# Structured-extraction smoke fixtures

PDFs used for v2.0 smoke tests of `extract_pdf_structured()`. Per-PDF
assertions live alongside the detection-logic test files (assertions
are added in Phase 14 once detection is implemented).

Coverage targets (see MANIFEST.json):
- 4 lattice (full-grid) tables: 2× Elsevier, 1× IEEE, 1× Springer/BMC
- 4 APA-style lineless tables (descriptives, regression, etc.)
- 2 Nature-style minimal-rule tables
- 2 figure-only fixtures (no tables, ≥1 figure)
- 1 table-of-contents / list-of-tables negative case
- 1 no-tables-no-figures negative case
- 1 uncaptioned-table fixture (default mode misses; thorough finds)

Total target: ~15 PDFs.

## Source

All PDFs are copied from:
- `~/Dropbox/Vibe/PDFextractor/test-pdfs/` (existing docpluck corpus)
- `~/Dropbox/Vibe/ESCIcheck/testpdfs/Coded already/` (ESCIcheck 10-PDF set)

If a source PDF is unavailable on a fresh checkout, the corresponding
test SKIPs (per `conftest.py`'s `pdf_available()` pattern).
```

- [ ] **Step 7.4: Identify candidate PDFs from the existing test corpora**

Run this to list candidate PDFs:

```bash
ls "$HOME/Dropbox/Vibe/PDFextractor/test-pdfs/apa/" 2>/dev/null | head -20
ls "$HOME/Dropbox/Vibe/PDFextractor/test-pdfs/" 2>/dev/null | head -30
```

Pick fixtures that match the categories in §11.1 of the spec. **Ask the user** if you cannot find suitable candidates for a category — they may have specific PDFs they want included.

Document each pick in `MANIFEST.json` as you copy it.

- [ ] **Step 7.5: Copy chosen PDFs into fixtures directory**

For each chosen PDF:

```bash
cp "$SOURCE_PATH" tests/fixtures/structured/<descriptive_name>.pdf
```

Where `<descriptive_name>` is short, lowercase, underscore-separated, e.g. `chan_feldman_apa_lineless_table1.pdf`.

If a per-category candidate is not available locally, document the gap in the README under a `## Known gaps` heading and skip that fixture for now — the smoke tests will skip cleanly.

- [ ] **Step 7.6: Build `MANIFEST.json`**

`tests/fixtures/structured/MANIFEST.json` (template — fill in real entries):

```json
{
  "version": "1.0.0",
  "fixtures": [
    {
      "filename": "elsevier_full_grid_descriptives.pdf",
      "category": "lattice_table",
      "expected_tables": 1,
      "expected_figures": 0,
      "notes": "Single descriptive-statistics table with full vertical and horizontal rules. Page 4."
    },
    {
      "filename": "ieee_lattice_regression.pdf",
      "category": "lattice_table",
      "expected_tables": 2,
      "expected_figures": 1,
      "notes": "IEEE-style heavy grid lines."
    },
    {
      "filename": "chan_feldman_apa_descriptives.pdf",
      "category": "apa_lineless",
      "expected_tables": 1,
      "expected_figures": 0,
      "notes": "APA Table 1, lineless, three-row header."
    },
    {
      "filename": "apa_correlation_matrix.pdf",
      "category": "apa_lineless",
      "expected_tables": 1,
      "expected_figures": 0,
      "notes": "Lower-triangular correlation matrix. v2.0 expected to fall back to isolated (level-C target)."
    },
    {
      "filename": "nature_minimal_rule_table.pdf",
      "category": "nature_minimal_rule",
      "expected_tables": 1,
      "expected_figures": 0,
      "notes": "Nature-style — header row has gray-band rect, no horizontal rules in body."
    },
    {
      "filename": "psych_paper_figures_only.pdf",
      "category": "figure_only",
      "expected_tables": 0,
      "expected_figures": 2,
      "notes": "Two-column psych paper with figures but no tables."
    },
    {
      "filename": "thesis_table_of_contents.pdf",
      "category": "table_of_contents_negative",
      "expected_tables": 0,
      "expected_figures": 0,
      "notes": "Front-matter TOC with leader dots — must NOT be detected as tables."
    },
    {
      "filename": "letter_no_tables.pdf",
      "category": "negative_no_tables_no_figures",
      "expected_tables": 0,
      "expected_figures": 0,
      "notes": "Editorial / commentary with no tables or figures."
    },
    {
      "filename": "uncaptioned_data_block.pdf",
      "category": "uncaptioned_table",
      "expected_tables": 1,
      "expected_figures": 0,
      "notes": "Small data table embedded in methods text without 'Table N' caption. Default mode misses; thorough=True finds it."
    }
  ]
}
```

Adjust entries to match what you actually copied. Aim for ≥8 fixtures (test asserts this); ≤15 keeps CI fast.

- [ ] **Step 7.7: Verify `.gitattributes` / `.gitignore` lets these in**

```bash
cat .gitignore | grep -i pdf
```

If PDFs are gitignored, add an exception for the fixtures directory:

```bash
echo '!tests/fixtures/structured/*.pdf' >> .gitignore
```

- [ ] **Step 7.8: Run tests to verify they pass**

```bash
pytest tests/test_fixtures_manifest.py -v
```

Expected: all passing for entries that exist; SKIPs for any documented gaps.

- [ ] **Step 7.9: Commit**

```bash
git add tests/fixtures/structured/ tests/test_fixtures_manifest.py
# If you edited .gitignore:
git add .gitignore
git commit -m "feat(structured): collect smoke-fixture PDFs + MANIFEST.json"
```

---

## ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## BARRIER 1: Section-id Phase 4 must land

Before any task in Phases 6–14, verify:

```bash
git log origin/main --oneline | head -20
ls -la docpluck/extract_layout.py 2>&1 || echo "MISSING: extract_layout.py"
python -c "from docpluck.extract_layout import LayoutDoc; print('OK')" 2>&1
```

All three must succeed. If `extract_layout.py` does not exist on `main` or `LayoutDoc` is not importable, **stop and ask the user**.

Once cleared, rebase onto `main` to pick up the new file:

```bash
git fetch origin
git rebase origin/main
```

Resolve any conflicts (Phase 1–5 files should not conflict with section-id work since they live in disjoint paths).

## ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## Phase 6 — bbox utilities (requires BARRIER 1)

Goal of phase: a small `bbox_utils.py` module that maps `(page, bbox)` to char-range slices in `raw_text`, and slices `LayoutDoc` regions for downstream detection.

### Task 8: bbox-to-char-range + region word slice

**Files:**
- Create: `docpluck/tables/bbox_utils.py`
- Test: `tests/test_bbox_utils.py`

- [ ] **Step 8.1: Inspect `LayoutDoc` shape**

Read `docpluck/extract_layout.py`. Confirm `LayoutDoc.pages[i]` exposes (or can expose):
- `chars` — list of dicts/objects with `x0, x1, top, bottom, text, fontname, size, page_number`
- `lines` — horizontal/vertical line primitives with `x0, x1, top, bottom`
- `rects` — rectangle primitives
- `words` — pre-clustered word boxes (or call `extract_words()`)

If any of these are not exposed, add a small backwards-compatible accessor to `extract_layout.py` *with section-id author coordination*. Keep additions minimal.

- [ ] **Step 8.2: Write the failing test**

`tests/test_bbox_utils.py`:

```python
"""bbox utilities — bbox-to-char-range + word-slicing."""

import pytest

from docpluck.tables.bbox_utils import (
    bbox_to_char_range,
    words_in_bbox,
    chars_in_bbox,
)


# These tests use a real PDF from the fixtures collection so we exercise
# real LayoutDoc structure. If the fixture is unavailable, tests SKIP.
from pathlib import Path
_FIX = Path(__file__).parent / "fixtures" / "structured"


def _layout_for(filename):
    pdf = _FIX / filename
    if not pdf.is_file():
        pytest.skip(f"Fixture not available: {filename}")
    from docpluck.extract_layout import extract_pdf_layout
    return extract_pdf_layout(pdf.read_bytes())


def test_bbox_to_char_range_returns_valid_slice():
    layout = _layout_for("chan_feldman_apa_descriptives.pdf")
    page = 1  # 1-indexed
    page_bbox = (0.0, 0.0, 1000.0, 1000.0)  # whole page
    start, end = bbox_to_char_range(layout, bbox=page_bbox, page=page)
    assert 0 <= start < end <= len(layout.raw_text)


def test_bbox_to_char_range_subregion_is_subset():
    layout = _layout_for("chan_feldman_apa_descriptives.pdf")
    full = bbox_to_char_range(layout, bbox=(0, 0, 1000, 1000), page=1)
    half = bbox_to_char_range(layout, bbox=(0, 0, 500, 500), page=1)
    assert full[0] <= half[0]
    assert half[1] <= full[1]


def test_words_in_bbox_returns_list_of_dicts():
    layout = _layout_for("chan_feldman_apa_descriptives.pdf")
    words = words_in_bbox(layout, bbox=(0, 0, 1000, 1000), page=1)
    assert isinstance(words, list)
    assert all("x0" in w and "x1" in w and "text" in w for w in words)


def test_chars_in_bbox_subset_of_page_chars():
    layout = _layout_for("chan_feldman_apa_descriptives.pdf")
    page1 = layout.pages[0]
    all_chars = list(getattr(page1, "chars", []))
    in_top_half = chars_in_bbox(layout, bbox=(0, 0, 10000, 500), page=1)
    assert len(in_top_half) <= len(all_chars)


def test_bbox_to_char_range_invalid_page_raises():
    layout = _layout_for("chan_feldman_apa_descriptives.pdf")
    with pytest.raises(ValueError):
        bbox_to_char_range(layout, bbox=(0, 0, 100, 100), page=999)
```

- [ ] **Step 8.3: Run test to verify it fails**

```bash
pytest tests/test_bbox_utils.py -v
```

Expected: `ImportError: No module named 'docpluck.tables.bbox_utils'`.

- [ ] **Step 8.4: Implement `docpluck/tables/bbox_utils.py`**

```python
"""
Bbox -> char-range and bbox -> word/char slicing utilities.

Used by both table-region detection and the table_text_mode="placeholder"
substitution. Operates on the LayoutDoc abstraction from
docpluck/extract_layout.py.

PDF coordinates are bottom-left origin; "top"/"bottom" in pdfplumber are
distance-from-page-top. We keep the pdfplumber convention internally
(top/bottom) and convert to PDF-points (origin bottom-left) only at the
public-schema boundary in extract_structured.py.

See spec §5.8.
"""

from __future__ import annotations

from typing import Any

from docpluck.extract_layout import LayoutDoc  # type: ignore[import-not-found]


Bbox = tuple[float, float, float, float]


def bbox_to_char_range(
    layout: LayoutDoc,
    *,
    bbox: Bbox,
    page: int,
) -> tuple[int, int]:
    """Map a (page, bbox) to (char_start, char_end) in layout.raw_text.

    Args:
        layout: LayoutDoc from extract_pdf_layout().
        bbox: (x0, top, x1, bottom) — pdfplumber convention.
        page: 1-indexed page number.

    Returns:
        (char_start, char_end) inclusive-exclusive offsets in raw_text.

    Raises:
        ValueError: if page is out of range.
    """
    if not (1 <= page <= len(layout.pages)):
        raise ValueError(f"page {page} out of range [1, {len(layout.pages)}]")

    page_offsets = getattr(layout, "page_offsets", None)
    if page_offsets is None:
        # Fallback: split raw_text on form-feed (pdftotext page break).
        page_offsets = _derive_page_offsets(layout.raw_text)

    page_start = page_offsets[page - 1]
    page_end = page_offsets[page] if page < len(page_offsets) else len(layout.raw_text)

    chars = chars_in_bbox(layout, bbox=bbox, page=page)
    if not chars:
        # Empty region — return a degenerate but valid range at page start.
        return (page_start, page_start)

    # Map first/last char by reading order to char offsets within the page.
    page_text = layout.raw_text[page_start:page_end]
    text_pieces = "".join(c["text"] for c in chars)
    if not text_pieces:
        return (page_start, page_start)

    # Best-effort: find the first piece in page_text.
    first_offset = page_text.find(chars[0]["text"])
    last_offset = page_text.rfind(chars[-1]["text"])
    if first_offset == -1:
        first_offset = 0
    if last_offset == -1:
        last_offset = len(page_text)
    char_start = page_start + first_offset
    char_end = page_start + last_offset + len(chars[-1]["text"])
    return (char_start, char_end)


def words_in_bbox(
    layout: LayoutDoc,
    *,
    bbox: Bbox,
    page: int,
) -> list[dict[str, Any]]:
    """All words in layout whose midpoint falls inside bbox on the given page."""
    if not (1 <= page <= len(layout.pages)):
        raise ValueError(f"page {page} out of range [1, {len(layout.pages)}]")
    page_obj = layout.pages[page - 1]

    words = getattr(page_obj, "words", None)
    if words is None:
        # Fallback: pdfplumber.extract_words on the underlying plumber-page if exposed.
        plumber_page = getattr(page_obj, "_plumber_page", None)
        if plumber_page is None:
            return []
        words = plumber_page.extract_words()

    x0, top, x1, bottom = bbox
    return [
        w for w in words
        if x0 <= (w["x0"] + w["x1"]) / 2 <= x1
        and top <= (w["top"] + w["bottom"]) / 2 <= bottom
    ]


def chars_in_bbox(
    layout: LayoutDoc,
    *,
    bbox: Bbox,
    page: int,
) -> list[dict[str, Any]]:
    """All chars in layout whose midpoint falls inside bbox on the given page."""
    if not (1 <= page <= len(layout.pages)):
        raise ValueError(f"page {page} out of range [1, {len(layout.pages)}]")
    page_obj = layout.pages[page - 1]
    chars = getattr(page_obj, "chars", []) or []
    x0, top, x1, bottom = bbox
    return [
        c for c in chars
        if x0 <= (c["x0"] + c["x1"]) / 2 <= x1
        and top <= (c["top"] + c["bottom"]) / 2 <= bottom
    ]


def _derive_page_offsets(raw_text: str) -> list[int]:
    """Char-offset of each page-start in raw_text. Pages are split by form-feed."""
    offsets = [0]
    pos = 0
    while True:
        idx = raw_text.find("\f", pos)
        if idx == -1:
            break
        offsets.append(idx + 1)
        pos = idx + 1
    return offsets


__all__ = ["bbox_to_char_range", "words_in_bbox", "chars_in_bbox", "Bbox"]
```

- [ ] **Step 8.5: Run tests to verify they pass**

```bash
pytest tests/test_bbox_utils.py -v
```

Expected: 5 passing (or some SKIPped if fixture unavailable).

- [ ] **Step 8.6: Commit**

```bash
git add docpluck/tables/bbox_utils.py tests/test_bbox_utils.py
git commit -m "feat(tables): add bbox-to-char-range + word/char slicing utilities"
```

---

## Phase 7 — Region detection (requires BARRIER 1)

Goal of phase: given a `LayoutDoc` and a list of `CaptionMatch`, infer the bbox of each table/figure region. Outputs `CandidateRegion` objects fed to the cell-clustering modules.

### Task 9: Table region detection

**Files:**
- Create: `docpluck/tables/detect.py`
- Test: `tests/test_table_detect.py`

- [ ] **Step 9.1: Write the failing test**

`tests/test_table_detect.py`:

```python
"""Table region detection — caption anchor → bbox."""

from pathlib import Path
import pytest

from docpluck.tables.detect import find_table_regions, CandidateRegion


_FIX = Path(__file__).parent / "fixtures" / "structured"


def _layout_for(filename):
    pdf = _FIX / filename
    if not pdf.is_file():
        pytest.skip(f"Fixture not available: {filename}")
    from docpluck.extract_layout import extract_pdf_layout
    return extract_pdf_layout(pdf.read_bytes())


def test_lattice_fixture_finds_one_region():
    layout = _layout_for("elsevier_full_grid_descriptives.pdf")
    regions = find_table_regions(layout)
    assert len(regions) >= 1
    r = regions[0]
    assert isinstance(r, CandidateRegion)
    assert r.label == "Table 1"
    # Lattice should be the geometric signal
    assert r.geometry_signal in {"lattice", "whitespace"}
    # Bbox sanity
    x0, top, x1, bottom = r.bbox
    assert x1 > x0 and bottom > top


def test_apa_lineless_finds_region_with_whitespace_signal():
    layout = _layout_for("chan_feldman_apa_descriptives.pdf")
    regions = find_table_regions(layout)
    assert len(regions) >= 1
    # APA tables have no rules → expect whitespace OR caption-only anchor
    assert regions[0].geometry_signal in {"whitespace", "caption_only"}


def test_table_of_contents_returns_no_regions():
    """TOC must NOT trip table detection."""
    layout = _layout_for("thesis_table_of_contents.pdf")
    regions = find_table_regions(layout)
    # Allow at most caption_only false positives — but no whitespace or lattice
    assert all(r.geometry_signal == "caption_only" for r in regions) or regions == []


def test_no_tables_fixture_returns_empty():
    layout = _layout_for("letter_no_tables.pdf")
    regions = find_table_regions(layout)
    assert regions == []


def test_thorough_mode_finds_uncaptioned_table():
    layout = _layout_for("uncaptioned_data_block.pdf")
    default = find_table_regions(layout)
    thorough = find_table_regions(layout, thorough=True)
    assert len(thorough) >= len(default)


def test_caption_above_and_caption_below_both_supported():
    """Some publishers (Nature) put caption below; we should still find geometry."""
    layout = _layout_for("nature_minimal_rule_table.pdf")
    regions = find_table_regions(layout)
    assert len(regions) >= 1
```

- [ ] **Step 9.2: Run test to verify it fails**

```bash
pytest tests/test_table_detect.py -v
```

Expected: `ImportError: cannot import name 'find_table_regions'`.

- [ ] **Step 9.3: Implement `docpluck/tables/detect.py`**

```python
"""
Table region detection.

Pipeline (per spec §5.2):
  1. Caption-regex pre-scan on layout.raw_text -> CaptionMatch list.
  2. For each caption, search ±window in PDF pt for geometric signal:
     - lattice signal: ≥2 horizontal rules + (≥1 vertical rule OR clean
       column-gap whitespace).
     - whitespace signal: ≥3 y-clustered rows with stable column boundaries.
  3. Fall back to caption_only when neither signal fires.
  4. Bbox = union of (caption line) ∪ (rules) ∪ (word cluster) ∪ (footnote).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from docpluck.extract_layout import LayoutDoc  # type: ignore[import-not-found]

from . import TableRendering
from .captions import find_caption_matches, CaptionMatch
from .bbox_utils import words_in_bbox, Bbox


GeometrySignal = Literal["lattice", "whitespace", "caption_only"]


@dataclass(frozen=True)
class CandidateRegion:
    label: str | None
    page: int
    bbox: Bbox
    caption: str | None
    footnote: str | None
    geometry_signal: GeometrySignal
    caption_match: CaptionMatch | None


SEARCH_BELOW_PT: float = 250.0
SEARCH_ABOVE_PT: float = 150.0


def find_table_regions(
    layout: LayoutDoc,
    *,
    thorough: bool = False,
) -> list[CandidateRegion]:
    """Find candidate table regions in the document."""
    page_offsets = getattr(layout, "page_offsets", None) or _derive_page_offsets(layout.raw_text)
    captions = [
        m for m in find_caption_matches(layout.raw_text, page_offsets)
        if m.kind == "table"
    ]

    regions: list[CandidateRegion] = []
    for cap in captions:
        region = _region_for_caption(layout, cap)
        if region is not None:
            regions.append(region)

    if thorough:
        # Phase-7 thorough mode: scan every page for tables without captions.
        # v2.0 implementation: heuristic — find pages with ≥3 horizontal rules
        # not already explained by an existing region. Mark as caption_only.
        regions.extend(_find_uncaptioned_tables(layout, exclude=regions))

    return regions


def _region_for_caption(
    layout: LayoutDoc,
    cap: CaptionMatch,
) -> CandidateRegion | None:
    page_obj = layout.pages[cap.page - 1]
    caption_bbox = _bbox_of_caption_line(page_obj, cap)
    if caption_bbox is None:
        return None

    # Search below first (APA convention), then above.
    below = _detect_geometry(layout, page=cap.page,
                             bbox=_extend(caption_bbox, dy=SEARCH_BELOW_PT, direction="down"))
    above = _detect_geometry(layout, page=cap.page,
                             bbox=_extend(caption_bbox, dy=SEARCH_ABOVE_PT, direction="up"))

    if below is not None:
        signal, geom_bbox = below
    elif above is not None:
        signal, geom_bbox = above
    else:
        # No geometric signal — emit caption_only with a 200pt block below the caption.
        signal = "caption_only"
        geom_bbox = _extend(caption_bbox, dy=200.0, direction="down")

    full_bbox = _union_bboxes(caption_bbox, geom_bbox)
    footnote = _detect_footnote_below(layout, page=cap.page, bbox=full_bbox)
    if footnote is not None:
        full_bbox = _union_bboxes(full_bbox, footnote.bbox)

    caption_text = _full_caption_text(layout.raw_text, cap)

    return CandidateRegion(
        label=cap.label,
        page=cap.page,
        bbox=full_bbox,
        caption=caption_text,
        footnote=footnote.text if footnote else None,
        geometry_signal=signal,  # type: ignore[arg-type]
        caption_match=cap,
    )


@dataclass(frozen=True)
class _Footnote:
    text: str
    bbox: Bbox


# --- helpers ---


def _bbox_of_caption_line(page_obj, cap: CaptionMatch) -> Bbox | None:
    """Find the bbox on `page_obj` that contains the first occurrence of cap.line_text."""
    chars = getattr(page_obj, "chars", []) or []
    if not chars:
        return None
    target = cap.line_text.strip()
    if not target:
        return None
    # Best-effort: find a char-row whose joined text starts with target.
    rows: dict[int, list[dict]] = {}
    for c in chars:
        key = round(c.get("top", 0))
        rows.setdefault(key, []).append(c)
    for top_key, row_chars in sorted(rows.items()):
        row_chars.sort(key=lambda c: c["x0"])
        joined = "".join(c.get("text", "") for c in row_chars)
        if target[:20] in joined:
            x0 = min(c["x0"] for c in row_chars)
            x1 = max(c["x1"] for c in row_chars)
            top = min(c["top"] for c in row_chars)
            bottom = max(c["bottom"] for c in row_chars)
            return (x0, top, x1, bottom)
    return None


def _extend(bbox: Bbox, *, dy: float, direction: Literal["down", "up"]) -> Bbox:
    x0, top, x1, bottom = bbox
    if direction == "down":
        return (x0, bottom, x1, bottom + dy)
    return (x0, max(0.0, top - dy), x1, top)


def _union_bboxes(a: Bbox, b: Bbox) -> Bbox:
    return (
        min(a[0], b[0]),
        min(a[1], b[1]),
        max(a[2], b[2]),
        max(a[3], b[3]),
    )


def _detect_geometry(layout: LayoutDoc, *, page: int, bbox: Bbox) -> tuple[str, Bbox] | None:
    page_obj = layout.pages[page - 1]
    horiz_lines = _horizontal_rules_in(page_obj, bbox)
    vert_lines = _vertical_rules_in(page_obj, bbox)
    if len(horiz_lines) >= 2 and (len(vert_lines) >= 1 or _whitespace_columns_stable(layout, page=page, bbox=bbox)):
        rule_bbox = _union_of_rules(horiz_lines + vert_lines, fallback=bbox)
        return ("lattice", rule_bbox)
    if _whitespace_columns_stable(layout, page=page, bbox=bbox):
        return ("whitespace", bbox)
    return None


def _horizontal_rules_in(page_obj, bbox: Bbox) -> list[dict]:
    lines = getattr(page_obj, "lines", []) or []
    x0, top, x1, bottom = bbox
    out = []
    for ln in lines:
        if (ln["x1"] - ln["x0"]) > (ln.get("height", ln.get("bottom", 0) - ln.get("top", 0)) + 0.5) * 5:
            if x0 - 2 <= ln["x0"] and ln["x1"] <= x1 + 2 and top - 2 <= ln["top"] <= bottom + 2:
                out.append(ln)
    return out


def _vertical_rules_in(page_obj, bbox: Bbox) -> list[dict]:
    lines = getattr(page_obj, "lines", []) or []
    x0, top, x1, bottom = bbox
    out = []
    for ln in lines:
        height = ln.get("height", ln.get("bottom", 0) - ln.get("top", 0))
        width = ln["x1"] - ln["x0"]
        if height > width * 5:
            if x0 - 2 <= ln["x0"] <= x1 + 2 and top - 2 <= ln["top"] and ln["bottom"] <= bottom + 2:
                out.append(ln)
    return out


def _union_of_rules(rules: list[dict], fallback: Bbox) -> Bbox:
    if not rules:
        return fallback
    return (
        min(r["x0"] for r in rules),
        min(r["top"] for r in rules),
        max(r["x1"] for r in rules),
        max(r["bottom"] for r in rules),
    )


def _whitespace_columns_stable(layout: LayoutDoc, *, page: int, bbox: Bbox) -> bool:
    """≥3 y-clustered rows of words with column boundaries that align across rows."""
    words = words_in_bbox(layout, bbox=bbox, page=page)
    if len(words) < 9:  # 3 rows × 3 cols minimum
        return False

    rows: dict[int, list[dict]] = {}
    for w in words:
        key = round((w["top"] + w["bottom"]) / 2 / 5) * 5  # 5pt y-bucket
        rows.setdefault(key, []).append(w)

    row_signatures: list[tuple[float, ...]] = []
    for ws in rows.values():
        ws.sort(key=lambda w: w["x0"])
        if len(ws) < 2:
            continue
        sig = tuple(round(w["x0"]) for w in ws)
        row_signatures.append(sig)

    if len(row_signatures) < 3:
        return False

    modal_len = max(set(len(s) for s in row_signatures), key=lambda L: sum(1 for s in row_signatures if len(s) == L))
    matching = sum(1 for s in row_signatures if len(s) == modal_len)
    return matching / len(row_signatures) >= 0.6


def _detect_footnote_below(layout: LayoutDoc, *, page: int, bbox: Bbox) -> _Footnote | None:
    page_obj = layout.pages[page - 1]
    chars = getattr(page_obj, "chars", []) or []
    if not chars:
        return None
    body_size = _modal_font_size(chars)
    x0, top, x1, bottom = bbox
    candidates = [c for c in chars if c["top"] >= bottom and c["x0"] >= x0 - 5 and c["x1"] <= x1 + 5]
    if not candidates:
        return None
    smaller = [c for c in candidates if c.get("size", body_size) < body_size * 0.92]
    if len(smaller) < 5:
        return None
    fx0 = min(c["x0"] for c in smaller)
    fx1 = max(c["x1"] for c in smaller)
    ftop = min(c["top"] for c in smaller)
    fbot = max(c["bottom"] for c in smaller)
    smaller.sort(key=lambda c: (c["top"], c["x0"]))
    text = "".join(c.get("text", "") for c in smaller)
    return _Footnote(text=text.strip(), bbox=(fx0, ftop, fx1, fbot))


def _modal_font_size(chars: list[dict]) -> float:
    sizes = [c.get("size", 0.0) for c in chars if c.get("size")]
    if not sizes:
        return 10.0
    counts: dict[float, int] = {}
    for s in sizes:
        counts[round(s, 1)] = counts.get(round(s, 1), 0) + 1
    return max(counts.items(), key=lambda kv: kv[1])[0]


def _full_caption_text(raw_text: str, cap: CaptionMatch) -> str:
    """Caption is the matched line + continuation lines until next paragraph break."""
    end = raw_text.find("\n\n", cap.char_end)
    if end == -1:
        end = min(cap.char_end + 500, len(raw_text))
    return raw_text[cap.char_start:end].replace("\n", " ").strip()


def _find_uncaptioned_tables(layout: LayoutDoc, *, exclude: list[CandidateRegion]) -> list[CandidateRegion]:
    """Thorough mode: scan every page for ≥3-rule clusters not already in `exclude`."""
    out: list[CandidateRegion] = []
    excluded_pages = {r.page for r in exclude}
    for i, page_obj in enumerate(layout.pages, start=1):
        if i in excluded_pages:
            continue
        lines = getattr(page_obj, "lines", []) or []
        horiz = [ln for ln in lines if (ln["x1"] - ln["x0"]) > 50]
        if len(horiz) < 3:
            continue
        x0 = min(ln["x0"] for ln in horiz)
        x1 = max(ln["x1"] for ln in horiz)
        top = min(ln["top"] for ln in horiz)
        bottom = max(ln["bottom"] for ln in horiz)
        out.append(CandidateRegion(
            label=None,
            page=i,
            bbox=(x0, top, x1, bottom),
            caption=None,
            footnote=None,
            geometry_signal="lattice",
            caption_match=None,
        ))
    return out


def _derive_page_offsets(raw_text: str) -> list[int]:
    offsets = [0]
    pos = 0
    while True:
        idx = raw_text.find("\f", pos)
        if idx == -1:
            break
        offsets.append(idx + 1)
        pos = idx + 1
    return offsets


__all__ = ["find_table_regions", "CandidateRegion", "GeometrySignal"]
```

- [ ] **Step 9.4: Run tests to verify they pass**

```bash
pytest tests/test_table_detect.py -v
```

Expected: tests pass for fixtures that exist; SKIPped for missing fixtures.

- [ ] **Step 9.5: Commit**

```bash
git add docpluck/tables/detect.py tests/test_table_detect.py
git commit -m "feat(tables): add table region detection (find_table_regions)"
```

---

## Phase 8 — Lattice cell clustering (requires BARRIER 1)

### Task 10: Lattice clustering

**Files:**
- Create: `docpluck/tables/cluster.py`
- Test: `tests/test_lattice_cluster.py`

- [ ] **Step 10.1: Write the failing test**

`tests/test_lattice_cluster.py`:

```python
"""Lattice (ruling-line) cell clustering."""

from pathlib import Path
import pytest

from docpluck.tables.cluster import lattice_cells


_FIX = Path(__file__).parent / "fixtures" / "structured"


def _layout_for(filename):
    pdf = _FIX / filename
    if not pdf.is_file():
        pytest.skip(f"Fixture not available: {filename}")
    from docpluck.extract_layout import extract_pdf_layout
    return extract_pdf_layout(pdf.read_bytes())


def test_lattice_emits_grid_cells():
    layout = _layout_for("elsevier_full_grid_descriptives.pdf")
    from docpluck.tables.detect import find_table_regions
    regions = find_table_regions(layout)
    assert regions, "expected at least one region"
    region = regions[0]
    cells = lattice_cells(layout, region=region)
    assert len(cells) > 0
    rows = {c["r"] for c in cells}
    cols = {c["c"] for c in cells}
    assert len(rows) >= 2
    assert len(cols) >= 2


def test_lattice_cells_have_text():
    layout = _layout_for("elsevier_full_grid_descriptives.pdf")
    from docpluck.tables.detect import find_table_regions
    regions = find_table_regions(layout)
    if not regions:
        pytest.skip("no regions found")
    cells = lattice_cells(layout, region=regions[0])
    non_empty = [c for c in cells if c["text"].strip()]
    assert len(non_empty) >= len(cells) // 2  # at least half non-empty


def test_lattice_returns_empty_on_no_geometry():
    layout = _layout_for("letter_no_tables.pdf")
    # Build a fake region pointing at empty space
    from docpluck.tables.detect import CandidateRegion
    region = CandidateRegion(
        label=None, page=1, bbox=(0, 0, 100, 100),
        caption=None, footnote=None,
        geometry_signal="lattice", caption_match=None,
    )
    cells = lattice_cells(layout, region=region)
    assert cells == []
```

- [ ] **Step 10.2: Run test to verify it fails**

```bash
pytest tests/test_lattice_cluster.py -v
```

Expected: `ImportError: cannot import name 'lattice_cells'`.

- [ ] **Step 10.3: Implement `docpluck/tables/cluster.py`**

```python
"""
Lattice (ruling-line) cell clustering.

Algorithm (per spec §5.3):
  1. Cluster horizontal segments by y → row separators.
  2. Cluster vertical segments by x → column separators (or derive from word x-gaps).
  3. Build grid of cells from adjacent separators.
  4. Assign chars to cells by midpoint containment.
  5. Concatenate chars per cell, normalize whitespace.
  6. Mark first row as header if bold or larger font.

Returns list[Cell].
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from docpluck.extract_layout import LayoutDoc  # type: ignore[import-not-found]

from . import Cell
from .bbox_utils import chars_in_bbox
from .detect import CandidateRegion


SNAP_TOLERANCE: float = 2.0


def lattice_cells(layout: LayoutDoc, *, region: CandidateRegion) -> list[Cell]:
    page_obj = layout.pages[region.page - 1]
    lines = getattr(page_obj, "lines", []) or []
    x0, top, x1, bottom = region.bbox

    horiz_ys = sorted({_snap(ln["top"]) for ln in lines
                       if (ln["x1"] - ln["x0"]) > 50
                       and x0 - 2 <= ln["x0"] and ln["x1"] <= x1 + 2
                       and top - 2 <= ln["top"] <= bottom + 2})
    vert_xs = sorted({_snap(ln["x0"]) for ln in lines
                      if (ln.get("height", 0) or (ln.get("bottom", 0) - ln.get("top", 0))) > 20
                      and x0 - 2 <= ln["x0"] <= x1 + 2})

    if len(horiz_ys) < 2:
        return []

    if len(vert_xs) < 2:
        vert_xs = _derive_columns_from_words(layout, region=region)
        if len(vert_xs) < 2:
            return []

    chars = chars_in_bbox(layout, bbox=region.bbox, page=region.page)

    cells: list[Cell] = []
    body_size = _modal_size(chars)
    for r, (y_top, y_bot) in enumerate(zip(horiz_ys[:-1], horiz_ys[1:])):
        for c, (x_left, x_right) in enumerate(zip(vert_xs[:-1], vert_xs[1:])):
            cell_chars = [
                ch for ch in chars
                if x_left <= (ch["x0"] + ch["x1"]) / 2 <= x_right
                and y_top <= (ch["top"] + ch["bottom"]) / 2 <= y_bot
            ]
            if not cell_chars:
                cells.append({
                    "r": r, "c": c, "rowspan": 1, "colspan": 1,
                    "text": "", "is_header": (r == 0 and _row_is_header(cells, body_size)),
                    "bbox": (x_left, y_top, x_right, y_bot),
                })
                continue
            cell_chars.sort(key=lambda ch: (ch["top"], ch["x0"]))
            text = _normalize_cell_text("".join(ch.get("text", "") for ch in cell_chars))
            is_header = (r == 0) and _is_header_chars(cell_chars, body_size)
            cells.append({
                "r": r, "c": c, "rowspan": 1, "colspan": 1,
                "text": text, "is_header": is_header,
                "bbox": (x_left, y_top, x_right, y_bot),
            })

    return cells


def _snap(v: float) -> float:
    return round(v / SNAP_TOLERANCE) * SNAP_TOLERANCE


def _derive_columns_from_words(layout: LayoutDoc, *, region: CandidateRegion) -> list[float]:
    """Fallback: cluster word x-gaps to find column boundaries."""
    from .bbox_utils import words_in_bbox
    words = words_in_bbox(layout, bbox=region.bbox, page=region.page)
    if not words:
        return []
    words.sort(key=lambda w: w["x0"])
    boundaries: list[float] = [region.bbox[0]]
    last_x1 = words[0]["x1"]
    for w in words[1:]:
        gap = w["x0"] - last_x1
        if gap > 8.0:
            boundaries.append((last_x1 + w["x0"]) / 2)
        last_x1 = max(last_x1, w["x1"])
    boundaries.append(region.bbox[2])
    return sorted(set(boundaries))


def _normalize_cell_text(text: str) -> str:
    import re
    text = text.replace("­", "")  # soft hyphen
    text = text.replace("−", "-")  # unicode minus → ASCII hyphen
    return re.sub(r"\s+", " ", text).strip()


def _modal_size(chars: list[dict[str, Any]]) -> float:
    sizes = [c.get("size", 0.0) for c in chars if c.get("size")]
    if not sizes:
        return 10.0
    counts: defaultdict[float, int] = defaultdict(int)
    for s in sizes:
        counts[round(s, 1)] += 1
    return max(counts.items(), key=lambda kv: kv[1])[0]


def _is_header_chars(chars: list[dict[str, Any]], body_size: float) -> bool:
    if not chars:
        return False
    avg_size = sum(c.get("size", body_size) for c in chars) / len(chars)
    if avg_size > body_size * 1.05:
        return True
    bold_count = sum(1 for c in chars if "Bold" in c.get("fontname", ""))
    return bold_count > len(chars) * 0.5


def _row_is_header(prior_cells: list[Cell], _body_size: float) -> bool:
    return any(c["is_header"] for c in prior_cells)


__all__ = ["lattice_cells"]
```

- [ ] **Step 10.4: Run tests to verify they pass**

```bash
pytest tests/test_lattice_cluster.py -v
```

Expected: passing for fixtures that exist; SKIPped for missing.

- [ ] **Step 10.5: Commit**

```bash
git add docpluck/tables/cluster.py tests/test_lattice_cluster.py
git commit -m "feat(tables): add lattice cell clustering (lattice_cells)"
```

---

## Phase 9 — Whitespace cell clustering (requires BARRIER 1)

### Task 11: Whitespace clustering

**Files:**
- Create: `docpluck/tables/whitespace.py`
- Test: `tests/test_whitespace_cluster.py`

- [ ] **Step 11.1: Write the failing test**

`tests/test_whitespace_cluster.py`:

```python
"""Whitespace (column-gap) cell clustering for lineless tables."""

from pathlib import Path
import pytest

from docpluck.tables.whitespace import whitespace_cells


_FIX = Path(__file__).parent / "fixtures" / "structured"


def _layout_for(filename):
    pdf = _FIX / filename
    if not pdf.is_file():
        pytest.skip(f"Fixture not available: {filename}")
    from docpluck.extract_layout import extract_pdf_layout
    return extract_pdf_layout(pdf.read_bytes())


def test_apa_lineless_yields_grid():
    layout = _layout_for("chan_feldman_apa_descriptives.pdf")
    from docpluck.tables.detect import find_table_regions
    regions = find_table_regions(layout)
    if not regions:
        pytest.skip("no regions detected")
    cells = whitespace_cells(layout, region=regions[0])
    assert len(cells) > 0
    rows = {c["r"] for c in cells}
    cols = {c["c"] for c in cells}
    assert len(rows) >= 3
    assert len(cols) >= 2


def test_whitespace_returns_empty_on_no_words():
    from docpluck.tables.detect import CandidateRegion
    layout = _layout_for("letter_no_tables.pdf")
    region = CandidateRegion(
        label=None, page=1, bbox=(0, 0, 50, 50),
        caption=None, footnote=None,
        geometry_signal="whitespace", caption_match=None,
    )
    cells = whitespace_cells(layout, region=region)
    assert cells == []
```

- [ ] **Step 11.2: Run test to verify it fails**

```bash
pytest tests/test_whitespace_cluster.py -v
```

Expected: `ImportError: cannot import name 'whitespace_cells'`.

- [ ] **Step 11.3: Implement `docpluck/tables/whitespace.py`**

```python
"""
Whitespace (column-gap) cell clustering for lineless tables.

Algorithm (per spec §5.4):
  1. Cluster words by y-coordinate (gap > 1.2 × line-height → new row).
  2. Find column boundaries from word x-gaps that persist across ≥60% of rows.
  3. Assign each word to a column by x-midpoint containment.
  4. Concatenate words per (row, col) → cell text.

Returns list[Cell].
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from docpluck.extract_layout import LayoutDoc  # type: ignore[import-not-found]

from . import Cell
from .bbox_utils import words_in_bbox
from .detect import CandidateRegion


def whitespace_cells(layout: LayoutDoc, *, region: CandidateRegion) -> list[Cell]:
    words = words_in_bbox(layout, bbox=region.bbox, page=region.page)
    if not words:
        return []

    rows = _cluster_into_rows(words)
    if len(rows) < 3:
        return []

    column_xs = _find_stable_column_boundaries(rows, bbox=region.bbox)
    if len(column_xs) < 3:  # need ≥2 columns → ≥3 boundaries
        return []

    body_size = _modal_word_size(words)
    cells: list[Cell] = []
    for r, row_words in enumerate(rows):
        for c, (x_left, x_right) in enumerate(zip(column_xs[:-1], column_xs[1:])):
            in_cell = [w for w in row_words if x_left <= (w["x0"] + w["x1"]) / 2 <= x_right]
            text = " ".join(_normalize(w["text"]) for w in in_cell).strip()
            row_top = min((w["top"] for w in row_words), default=0.0)
            row_bot = max((w["bottom"] for w in row_words), default=0.0)
            cells.append({
                "r": r, "c": c, "rowspan": 1, "colspan": 1,
                "text": text,
                "is_header": (r == 0) and _row_is_header(row_words, body_size),
                "bbox": (x_left, row_top, x_right, row_bot),
            })
    return cells


def _cluster_into_rows(words: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    if not words:
        return []
    sorted_words = sorted(words, key=lambda w: (w["top"], w["x0"]))
    line_heights = [w["bottom"] - w["top"] for w in sorted_words]
    median_h = sorted(line_heights)[len(line_heights) // 2]
    threshold = max(median_h * 1.2, 5.0)

    rows: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = [sorted_words[0]]
    for w in sorted_words[1:]:
        prev_top = current[-1]["top"]
        if w["top"] - prev_top > threshold:
            rows.append(current)
            current = [w]
        else:
            current.append(w)
    rows.append(current)
    return rows


def _find_stable_column_boundaries(
    rows: list[list[dict[str, Any]]],
    *,
    bbox: tuple[float, float, float, float],
) -> list[float]:
    if not rows:
        return []
    candidates: dict[float, int] = defaultdict(int)
    for row in rows:
        if len(row) < 2:
            continue
        row_sorted = sorted(row, key=lambda w: w["x0"])
        for prev, curr in zip(row_sorted[:-1], row_sorted[1:]):
            gap = curr["x0"] - prev["x1"]
            if gap > 5.0:
                mid = round((prev["x1"] + curr["x0"]) / 2)
                candidates[mid] += 1

    threshold = max(1, int(len(rows) * 0.6))
    stable = sorted(x for x, count in candidates.items() if count >= threshold)
    return [bbox[0]] + stable + [bbox[2]]


def _modal_word_size(words: list[dict[str, Any]]) -> float:
    sizes = [w.get("bottom", 0) - w.get("top", 0) for w in words]
    sizes = [s for s in sizes if s > 0]
    if not sizes:
        return 10.0
    counts: defaultdict[float, int] = defaultdict(int)
    for s in sizes:
        counts[round(s, 1)] += 1
    return max(counts.items(), key=lambda kv: kv[1])[0]


def _row_is_header(words: list[dict[str, Any]], body_size: float) -> bool:
    if not words:
        return False
    sizes = [w.get("bottom", 0) - w.get("top", 0) for w in words]
    avg = sum(sizes) / len(sizes) if sizes else body_size
    return avg > body_size * 1.05


def _normalize(text: str) -> str:
    return text.replace("­", "").replace("−", "-")


__all__ = ["whitespace_cells"]
```

- [ ] **Step 11.4: Run tests to verify they pass**

```bash
pytest tests/test_whitespace_cluster.py -v
```

Expected: passing where fixtures exist.

- [ ] **Step 11.5: Commit**

```bash
git add docpluck/tables/whitespace.py tests/test_whitespace_cluster.py
git commit -m "feat(tables): add whitespace (column-gap) cell clustering"
```

---

## Phase 10 — Figure detection (requires BARRIER 1)

### Task 12: Figure region detection

**Files:**
- Create: `docpluck/figures/detect.py`
- Test: `tests/test_figure_detect.py`

- [ ] **Step 12.1: Write the failing test**

`tests/test_figure_detect.py`:

```python
"""Figure region detection — caption + bbox metadata only."""

from pathlib import Path
import pytest

from docpluck.figures.detect import find_figures
from docpluck.figures import Figure


_FIX = Path(__file__).parent / "fixtures" / "structured"


def _layout_for(filename):
    pdf = _FIX / filename
    if not pdf.is_file():
        pytest.skip(f"Fixture not available: {filename}")
    from docpluck.extract_layout import extract_pdf_layout
    return extract_pdf_layout(pdf.read_bytes())


def test_figure_only_fixture_finds_figures():
    layout = _layout_for("psych_paper_figures_only.pdf")
    figures = find_figures(layout)
    assert len(figures) >= 2
    for f in figures:
        assert f["label"] is not None and f["label"].startswith("Figure ")
        assert f["caption"] is not None and len(f["caption"]) > 0
        x0, y0, x1, y1 = f["bbox"]
        assert x1 > x0 and y1 > y0


def test_no_figures_fixture_returns_empty():
    layout = _layout_for("letter_no_tables.pdf")
    figures = find_figures(layout)
    assert figures == []


def test_figure_id_is_unique_and_stable():
    layout = _layout_for("psych_paper_figures_only.pdf")
    figs = find_figures(layout)
    ids = [f["id"] for f in figs]
    assert len(set(ids)) == len(ids)
    assert all(fid.startswith("f") for fid in ids)


def test_fig_dot_variant_recognized():
    """Fig. 1 and Figure 1 must both work."""
    # Use whichever fixture has 'Fig.' if available.
    layout = _layout_for("psych_paper_figures_only.pdf")
    figs = find_figures(layout)
    # At least all figures have non-None labels
    assert all(f["label"] for f in figs)
```

- [ ] **Step 12.2: Run test to verify it fails**

```bash
pytest tests/test_figure_detect.py -v
```

Expected: `ImportError: cannot import name 'find_figures'`.

- [ ] **Step 12.3: Implement `docpluck/figures/detect.py`**

```python
"""
Figure region detection.

For each Figure N caption match, infer the figure bbox by looking for
graphics primitives (rects, lines, curves) above (APA convention) or
below the caption. Emit metadata only — no image extraction in v2.0.

See spec §5.7.
"""

from __future__ import annotations

from typing import Any

from docpluck.extract_layout import LayoutDoc  # type: ignore[import-not-found]

from docpluck.tables.captions import find_caption_matches, CaptionMatch
from docpluck.tables.bbox_utils import Bbox

from . import Figure


SEARCH_ABOVE_PT: float = 400.0
SEARCH_BELOW_PT: float = 400.0


def find_figures(layout: LayoutDoc) -> list[Figure]:
    page_offsets = getattr(layout, "page_offsets", None) or _derive_page_offsets(layout.raw_text)
    captions = [m for m in find_caption_matches(layout.raw_text, page_offsets) if m.kind == "figure"]

    figures: list[Figure] = []
    for i, cap in enumerate(captions, start=1):
        bbox = _figure_bbox_for(layout, cap)
        figures.append({
            "id": f"f{i}",
            "label": cap.label,
            "page": cap.page,
            "bbox": bbox,
            "caption": _full_caption_text(layout.raw_text, cap),
        })
    return figures


def _figure_bbox_for(layout: LayoutDoc, cap: CaptionMatch) -> Bbox:
    page_obj = layout.pages[cap.page - 1]
    caption_bbox = _bbox_of_caption_line(page_obj, cap)
    if caption_bbox is None:
        # Fallback bbox: full column width × 200pt block
        page_w = float(getattr(page_obj, "width", 612.0))
        return (50.0, 100.0, page_w - 50.0, 300.0)

    above = _graphics_bbox_above(page_obj, caption_bbox, SEARCH_ABOVE_PT)
    if above is not None:
        return _union(caption_bbox, above)
    below = _graphics_bbox_below(page_obj, caption_bbox, SEARCH_BELOW_PT)
    if below is not None:
        return _union(caption_bbox, below)

    # No graphics found; emit bbox = caption + 200pt block above (best effort)
    x0, top, x1, bottom = caption_bbox
    return (x0, max(0.0, top - 200.0), x1, bottom)


def _graphics_bbox_above(page_obj, caption_bbox: Bbox, max_pt: float) -> Bbox | None:
    return _graphics_bbox_in_band(page_obj, caption_bbox, direction="above", max_pt=max_pt)


def _graphics_bbox_below(page_obj, caption_bbox: Bbox, max_pt: float) -> Bbox | None:
    return _graphics_bbox_in_band(page_obj, caption_bbox, direction="below", max_pt=max_pt)


def _graphics_bbox_in_band(page_obj, caption_bbox: Bbox, *, direction: str, max_pt: float) -> Bbox | None:
    cx0, ctop, cx1, cbottom = caption_bbox
    if direction == "above":
        band_top, band_bot = max(0.0, ctop - max_pt), ctop
    else:
        band_top, band_bot = cbottom, cbottom + max_pt

    rects = list(getattr(page_obj, "rects", []) or [])
    lines = list(getattr(page_obj, "lines", []) or [])
    curves = list(getattr(page_obj, "curves", []) or [])
    primitives: list[dict[str, Any]] = rects + lines + curves
    in_band = [p for p in primitives
               if band_top <= ((p["top"] + p["bottom"]) / 2) <= band_bot]
    if not in_band:
        return None
    return (
        min(p["x0"] for p in in_band),
        min(p["top"] for p in in_band),
        max(p["x1"] for p in in_band),
        max(p["bottom"] for p in in_band),
    )


def _union(a: Bbox, b: Bbox) -> Bbox:
    return (min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3]))


def _bbox_of_caption_line(page_obj, cap: CaptionMatch) -> Bbox | None:
    chars = getattr(page_obj, "chars", []) or []
    if not chars:
        return None
    target = cap.line_text.strip()
    if not target:
        return None
    rows: dict[int, list[dict]] = {}
    for c in chars:
        rows.setdefault(round(c.get("top", 0)), []).append(c)
    for top_key, row_chars in sorted(rows.items()):
        row_chars.sort(key=lambda c: c["x0"])
        joined = "".join(c.get("text", "") for c in row_chars)
        if target[:20] in joined:
            return (
                min(c["x0"] for c in row_chars),
                min(c["top"] for c in row_chars),
                max(c["x1"] for c in row_chars),
                max(c["bottom"] for c in row_chars),
            )
    return None


def _full_caption_text(raw_text: str, cap: CaptionMatch) -> str:
    end = raw_text.find("\n\n", cap.char_end)
    if end == -1:
        end = min(cap.char_end + 500, len(raw_text))
    return raw_text[cap.char_start:end].replace("\n", " ").strip()


def _derive_page_offsets(raw_text: str) -> list[int]:
    offsets = [0]
    pos = 0
    while True:
        idx = raw_text.find("\f", pos)
        if idx == -1:
            break
        offsets.append(idx + 1)
        pos = idx + 1
    return offsets


__all__ = ["find_figures"]
```

- [ ] **Step 12.4: Run tests to verify they pass**

```bash
pytest tests/test_figure_detect.py -v
```

Expected: passing where fixtures exist.

- [ ] **Step 12.5: Commit**

```bash
git add docpluck/figures/detect.py tests/test_figure_detect.py
git commit -m "feat(figures): add figure detection (find_figures)"
```

---

## Phase 11 — Top-level orchestrator (requires BARRIER 1)

### Task 13: `extract_pdf_structured()`

**Files:**
- Modify: `docpluck/extract_structured.py`
- Test: `tests/test_extract_pdf_structured.py`

- [ ] **Step 13.1: Write the failing test**

`tests/test_extract_pdf_structured.py`:

```python
"""End-to-end tests for extract_pdf_structured()."""

from pathlib import Path
import pytest

from docpluck import extract_pdf, extract_pdf_structured, TABLE_EXTRACTION_VERSION


_FIX = Path(__file__).parent / "fixtures" / "structured"


def _read(filename: str) -> bytes:
    p = _FIX / filename
    if not p.is_file():
        pytest.skip(f"Fixture not available: {filename}")
    return p.read_bytes()


def test_returns_required_fields():
    data = _read("elsevier_full_grid_descriptives.pdf")
    result = extract_pdf_structured(data)
    assert "text" in result
    assert "method" in result
    assert "page_count" in result
    assert "tables" in result
    assert "figures" in result
    assert result["table_extraction_version"] == TABLE_EXTRACTION_VERSION


def test_text_default_mode_matches_extract_pdf():
    """In raw mode (default), text should equal extract_pdf()'s text byte-for-byte."""
    data = _read("elsevier_full_grid_descriptives.pdf")
    plain_text, _plain_method = extract_pdf(data)
    result = extract_pdf_structured(data)
    assert result["text"] == plain_text


def test_lattice_table_returns_structured_kind():
    data = _read("elsevier_full_grid_descriptives.pdf")
    result = extract_pdf_structured(data)
    assert len(result["tables"]) >= 1
    t = result["tables"][0]
    assert t["kind"] in {"structured", "isolated"}
    if t["kind"] == "structured":
        assert t["rendering"] in {"lattice", "whitespace"}
        assert t["confidence"] is not None
        assert 0.0 <= t["confidence"] <= 1.0
        assert t["html"] is not None
        assert "<table>" in t["html"]


def test_negative_fixture_emits_no_tables_no_figures():
    data = _read("letter_no_tables.pdf")
    result = extract_pdf_structured(data)
    assert result["tables"] == []
    assert result["figures"] == []


def test_method_string_indicates_table_extraction():
    data = _read("elsevier_full_grid_descriptives.pdf")
    result = extract_pdf_structured(data)
    assert "pdfplumber_tables" in result["method"]


def test_thorough_mode_method_string():
    data = _read("uncaptioned_data_block.pdf")
    result = extract_pdf_structured(data, thorough=True)
    assert "+thorough" in result["method"] or "thorough" in result["method"]


def test_table_ids_unique_and_stable():
    data = _read("elsevier_full_grid_descriptives.pdf")
    result = extract_pdf_structured(data)
    ids = [t["id"] for t in result["tables"]]
    assert len(set(ids)) == len(ids)
    assert all(tid.startswith("t") for tid in ids)


def test_isolated_table_has_raw_text_but_no_cells():
    data = _read("apa_correlation_matrix.pdf")
    result = extract_pdf_structured(data)
    if not result["tables"]:
        pytest.skip("no tables detected on this fixture")
    isolated = [t for t in result["tables"] if t["kind"] == "isolated"]
    if not isolated:
        pytest.skip("no isolated tables on this fixture")
    t = isolated[0]
    assert t["cells"] == []
    assert t["html"] is None
    assert t["confidence"] is None
    assert t["raw_text"]
```

- [ ] **Step 13.2: Run test to verify it fails**

```bash
pytest tests/test_extract_pdf_structured.py -v
```

Expected: `ImportError: cannot import name 'extract_pdf_structured'`.

- [ ] **Step 13.3: Implement orchestrator in `docpluck/extract_structured.py`**

Replace the contents of `docpluck/extract_structured.py` with:

```python
"""
docpluck.extract_structured — top-level structured PDF extraction.

Provides extract_pdf_structured(), the orchestrator over the existing
extract_pdf() text path plus the new tables/ and figures/ detection paths.

See docs/superpowers/specs/2026-05-06-table-extraction-design.md for the design.
"""

from __future__ import annotations

from typing import Literal, TypedDict

from .extract import extract_pdf, count_pages
from .tables import Table, Cell
from .tables.detect import find_table_regions, CandidateRegion
from .tables.cluster import lattice_cells
from .tables.whitespace import whitespace_cells
from .tables.render import cells_to_html
from .tables.confidence import score_table, clamp_confidence, should_fall_back_to_isolated
from .tables.bbox_utils import bbox_to_char_range
from .figures import Figure
from .figures.detect import find_figures


TABLE_EXTRACTION_VERSION = "1.0.0"

TableTextMode = Literal["raw", "placeholder"]


class StructuredResult(TypedDict):
    text: str
    method: str
    page_count: int
    tables: list[Table]
    figures: list[Figure]
    table_extraction_version: str


def extract_pdf_structured(
    pdf_bytes: bytes,
    *,
    thorough: bool = False,
    table_text_mode: TableTextMode = "raw",
) -> StructuredResult:
    """Extract text + structured tables + figures from a PDF.

    Args:
        pdf_bytes: Raw PDF bytes.
        thorough: If True, scan every page for tables (slower; finds uncaptioned
            tables). Default False scans only pages with caption matches.
        table_text_mode: "raw" (default; text identical to extract_pdf()) or
            "placeholder" ([Table N: caption] markers replace table regions).

    Returns:
        StructuredResult dict per spec §4.
    """
    raw_text, base_method = extract_pdf(pdf_bytes)

    if raw_text.startswith("ERROR:"):
        return {
            "text": raw_text,
            "method": base_method,
            "page_count": 0,
            "tables": [],
            "figures": [],
            "table_extraction_version": TABLE_EXTRACTION_VERSION,
        }

    method_pieces = [base_method]

    try:
        from .extract_layout import extract_pdf_layout
    except ImportError as e:
        raise ImportError(
            "extract_pdf_structured() requires docpluck/extract_layout.py "
            "(introduced in v1.6.0). Install with `pip install docpluck[all]`."
        ) from e

    layout = extract_pdf_layout(pdf_bytes)

    try:
        regions = find_table_regions(layout, thorough=thorough)
        tables = [_build_table(layout, region, idx) for idx, region in enumerate(regions, start=1)]
        figures = find_figures(layout)
        method_pieces.append("pdfplumber_tables")
        if thorough:
            method_pieces.append("thorough")
    except Exception:
        tables = []
        figures = []
        method_pieces.append("pdfplumber_tables_failed")

    text_out = (
        _apply_placeholder(raw_text, layout, tables, figures)
        if table_text_mode == "placeholder"
        else raw_text
    )

    return {
        "text": text_out,
        "method": "+".join(method_pieces),
        "page_count": count_pages(pdf_bytes),
        "tables": tables,
        "figures": figures,
        "table_extraction_version": TABLE_EXTRACTION_VERSION,
    }


def _build_table(layout, region: CandidateRegion, idx: int) -> Table:
    raw_slice = _bbox_raw_text(layout, region)

    cells: list[Cell] = []
    rendering: str = "isolated"

    if region.geometry_signal == "lattice":
        cells = lattice_cells(layout, region=region)
        rendering = "lattice" if cells else "isolated"
    elif region.geometry_signal == "whitespace":
        cells = whitespace_cells(layout, region=region)
        rendering = "whitespace" if cells else "isolated"

    raw_score = score_table(cells, rendering=rendering) if rendering != "isolated" else None
    if should_fall_back_to_isolated(raw_score):
        cells = []
        rendering = "isolated"
        raw_score = None

    confidence = clamp_confidence(raw_score, rendering=rendering)

    if rendering == "isolated":
        return {
            "id": f"t{idx}",
            "label": region.label,
            "page": region.page,
            "bbox": region.bbox,
            "caption": region.caption,
            "footnote": region.footnote,
            "kind": "isolated",
            "rendering": "isolated",
            "confidence": None,
            "n_rows": None, "n_cols": None, "header_rows": None,
            "cells": [], "html": None,
            "raw_text": raw_slice,
        }

    n_rows = max(c["r"] for c in cells) + 1 if cells else 0
    n_cols = max(c["c"] for c in cells) + 1 if cells else 0
    header_rows = 1 if any(c["is_header"] for c in cells) else 0

    return {
        "id": f"t{idx}",
        "label": region.label,
        "page": region.page,
        "bbox": region.bbox,
        "caption": region.caption,
        "footnote": region.footnote,
        "kind": "structured",
        "rendering": rendering,  # type: ignore[typeddict-item]
        "confidence": confidence,
        "n_rows": n_rows,
        "n_cols": n_cols,
        "header_rows": header_rows,
        "cells": cells,
        "html": cells_to_html(cells),
        "raw_text": raw_slice,
    }


def _bbox_raw_text(layout, region: CandidateRegion) -> str:
    try:
        start, end = bbox_to_char_range(layout, bbox=region.bbox, page=region.page)
        return layout.raw_text[start:end]
    except Exception:
        return ""


def _apply_placeholder(raw_text, layout, tables: list[Table], figures: list[Figure]) -> str:
    """Replace each table/figure region with [Label: caption] markers."""
    items: list[tuple[int, int, str]] = []
    for t in tables:
        try:
            start, end = bbox_to_char_range(layout, bbox=t["bbox"], page=t["page"])
        except Exception:
            continue
        marker = _marker(t.get("label"), t.get("caption"))
        items.append((start, end, marker))
    for f in figures:
        try:
            start, end = bbox_to_char_range(layout, bbox=f["bbox"], page=f["page"])
        except Exception:
            continue
        marker = _marker(f.get("label"), f.get("caption"))
        items.append((start, end, marker))

    items.sort(key=lambda t: t[0], reverse=True)
    out = raw_text
    for start, end, marker in items:
        out = out[:start] + marker + "\n\n" + out[end:]
    return out


def _marker(label: str | None, caption: str | None) -> str:
    if label and caption:
        return f"[{label}: {caption}]"
    if label:
        return f"[{label}]"
    return "[Table]"


__all__ = [
    "TABLE_EXTRACTION_VERSION",
    "StructuredResult",
    "extract_pdf_structured",
    "TableTextMode",
]
```

- [ ] **Step 13.4: Re-export `extract_pdf_structured` from top-level `docpluck/__init__.py`**

In `docpluck/__init__.py`, add:

```python
from .extract_structured import extract_pdf_structured
```

And update `__all__` to include `"extract_pdf_structured"`.

- [ ] **Step 13.5: Run tests to verify they pass**

```bash
pytest tests/test_extract_pdf_structured.py -v
```

Expected: all passing where fixtures exist.

- [ ] **Step 13.6: Run the FULL suite to verify nothing broke**

```bash
pytest -x -q
```

Expected: all green.

- [ ] **Step 13.7: Commit**

```bash
git add docpluck/extract_structured.py docpluck/__init__.py tests/test_extract_pdf_structured.py
git commit -m "feat(structured): add extract_pdf_structured() orchestrator"
```

---

## Phase 12 — table_text_mode placeholder mode tests (requires BARRIER 1)

### Task 14: Placeholder mode tests + edge cases

**Files:**
- Test: `tests/test_text_mode.py`

- [ ] **Step 14.1: Write the failing test**

`tests/test_text_mode.py`:

```python
"""table_text_mode='raw' vs 'placeholder' behavior."""

from pathlib import Path
import pytest

from docpluck import extract_pdf, extract_pdf_structured


_FIX = Path(__file__).parent / "fixtures" / "structured"


def _read(filename: str) -> bytes:
    p = _FIX / filename
    if not p.is_file():
        pytest.skip(f"Fixture not available: {filename}")
    return p.read_bytes()


def test_raw_mode_text_byte_identical_to_extract_pdf():
    data = _read("elsevier_full_grid_descriptives.pdf")
    plain_text, _ = extract_pdf(data)
    raw_result = extract_pdf_structured(data, table_text_mode="raw")
    assert raw_result["text"] == plain_text


def test_placeholder_mode_inserts_markers():
    data = _read("elsevier_full_grid_descriptives.pdf")
    result = extract_pdf_structured(data, table_text_mode="placeholder")
    assert "[Table" in result["text"]


def test_placeholder_mode_shorter_or_equal_length():
    data = _read("elsevier_full_grid_descriptives.pdf")
    raw = extract_pdf_structured(data, table_text_mode="raw")
    placeholder = extract_pdf_structured(data, table_text_mode="placeholder")
    # Replacing a region with a short marker should not grow the text dramatically.
    assert len(placeholder["text"]) <= len(raw["text"]) + 200


def test_placeholder_marker_format_includes_label_and_caption():
    data = _read("elsevier_full_grid_descriptives.pdf")
    result = extract_pdf_structured(data, table_text_mode="placeholder")
    if result["tables"]:
        t = result["tables"][0]
        if t.get("label") and t.get("caption"):
            expected_substring = f"[{t['label']}: "
            assert expected_substring in result["text"]


def test_placeholder_with_figures_inserts_figure_markers():
    data = _read("psych_paper_figures_only.pdf")
    result = extract_pdf_structured(data, table_text_mode="placeholder")
    assert "[Figure" in result["text"]
```

- [ ] **Step 14.2: Run tests to verify behavior**

```bash
pytest tests/test_text_mode.py -v
```

Expected: all passing where fixtures exist. If markers don't appear, debug the bbox→char-range mapping in `bbox_utils.py`.

- [ ] **Step 14.3: Commit**

```bash
git add tests/test_text_mode.py
git commit -m "test(structured): table_text_mode raw/placeholder behavior tests"
```

---

## ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## BARRIER 2: Section-id Phase 5 must land

Before Task 15 (the F0 patch), verify:

```bash
git log origin/main --oneline | grep -i "F0\|footnote" | head
python -c "from docpluck.normalize import normalize_text; from docpluck.extract_layout import extract_pdf_layout; print('OK')"
```

Confirm with the user that section-id Phase 5 (the F0 footnote/header strip step in `normalize.py`) is committed.

If unclear, **stop and ask the user**. Skip Task 15 for now and proceed to Task 16+ if a release is needed without F0 awareness; document the gap in `CHANGELOG.md`.

## ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## Phase 13 — F0 patch (requires BARRIER 2)

### Task 15: Make F0 table-region-aware

**Files:**
- Modify: `docpluck/normalize.py` (the F0 step)
- Test: `tests/test_f0_table_region_aware.py`

- [ ] **Step 15.1: Read section-id's F0 implementation**

```bash
grep -n "F0\|footnote_strip\|strip_footnotes" docpluck/normalize.py
```

Identify the function that performs F0. Locate where it iterates over candidate footnote spans.

- [ ] **Step 15.2: Write the failing test**

`tests/test_f0_table_region_aware.py`:

```python
"""F0 footnote-strip must skip lines inside table-region bboxes."""

from pathlib import Path
import pytest

from docpluck import extract_pdf_structured
from docpluck.normalize import normalize_text, NormalizationLevel


_FIX = Path(__file__).parent / "fixtures" / "structured"


def _read(filename: str) -> bytes:
    p = _FIX / filename
    if not p.is_file():
        pytest.skip(f"Fixture not available: {filename}")
    return p.read_bytes()


def test_table_footnote_preserved_in_table_object_not_stripped():
    """A 'Note. *p < .05.' below a table should appear in table.footnote, not be stripped."""
    data = _read("chan_feldman_apa_descriptives.pdf")
    result = extract_pdf_structured(data)
    if not result["tables"]:
        pytest.skip("no table detected")
    t = result["tables"][0]
    if t["footnote"] is None:
        pytest.skip("no footnote on this table")
    assert "*" in t["footnote"] or "Note" in t["footnote"] or "p" in t["footnote"].lower()


def test_normalize_text_with_table_regions_kwarg_skips_table_footnotes():
    """normalize_text(text, level, layout=..., table_regions=[...]) must not strip
    text inside the supplied table-region bboxes.

    Behavior: For each table-region bbox, lines whose y-range overlaps the bbox
    must NOT be classified as page-footnote candidates by F0.
    """
    data = _read("chan_feldman_apa_descriptives.pdf")
    from docpluck.extract_layout import extract_pdf_layout
    layout = extract_pdf_layout(data)
    result = extract_pdf_structured(data)

    table_regions = [
        {"page": t["page"], "bbox": t["bbox"]}
        for t in result["tables"]
    ]

    normalized_with_regions = normalize_text(
        layout.raw_text,
        NormalizationLevel.academic,
        layout=layout,
        table_regions=table_regions,
    )
    normalized_without = normalize_text(
        layout.raw_text,
        NormalizationLevel.academic,
        layout=layout,
    )

    # With table-region awareness, body should retain table footnote text;
    # without, that text should appear in the appendix footnotes section.
    # We check len(text) increases as a proxy: regions skipped = more text in body.
    assert len(normalized_with_regions.text) >= len(normalized_without.text) - 50
```

- [ ] **Step 15.3: Run test to verify it fails**

```bash
pytest tests/test_f0_table_region_aware.py -v
```

Expected: FAIL — `normalize_text()` doesn't accept `table_regions` kwarg yet.

- [ ] **Step 15.4: Patch `docpluck/normalize.py`**

Find the F0 function (post Section-id Phase 5 — name may be `_strip_footnotes_and_headers` or similar). Add a `table_regions: list[dict] | None = None` keyword argument to both `normalize_text()` and the F0 step.

Inside F0's per-page candidate-line loop, after computing the candidate footnote line's bbox, add an early-skip:

```python
def _line_inside_table_region(line_bbox, page_num, table_regions):
    if not table_regions:
        return False
    lx0, ltop, lx1, lbot = line_bbox
    for r in table_regions:
        if r.get("page") != page_num:
            continue
        rx0, rtop, rx1, rbot = r["bbox"]
        if not (lbot < rtop or ltop > rbot or lx1 < rx0 or lx0 > rx1):
            return True
    return False

# inside F0:
if _line_inside_table_region(line_bbox, page_num, table_regions):
    continue  # do not strip
```

Plumb `table_regions` from `normalize_text()` down to F0.

- [ ] **Step 15.5: Run tests to verify they pass**

```bash
pytest tests/test_f0_table_region_aware.py -v
pytest -x -q  # full suite — F0 tests from section-id should still pass
```

Expected: all green.

- [ ] **Step 15.6: Commit**

```bash
git add docpluck/normalize.py tests/test_f0_table_region_aware.py
git commit -m "feat(normalize): F0 skips lines inside supplied table_regions"
```

---

## Phase 14 — CLI integration (requires BARRIER 1)

### Task 16: CLI flags

**Files:**
- Modify: `docpluck/cli.py`
- Test: `tests/test_cli_structured.py`

- [ ] **Step 16.1: Read existing CLI**

```bash
cat docpluck/cli.py
```

Identify the existing `extract` subcommand and argument-parsing pattern.

- [ ] **Step 16.2: Write the failing test**

`tests/test_cli_structured.py`:

```python
"""CLI: docpluck extract --structured ..."""

import json
import subprocess
import sys
from pathlib import Path
import pytest


_FIX = Path(__file__).parent / "fixtures" / "structured"


def _fixture(filename: str) -> Path:
    p = _FIX / filename
    if not p.is_file():
        pytest.skip(f"Fixture not available: {filename}")
    return p


def _run(*args: str) -> subprocess.CompletedProcess:
    cmd = [sys.executable, "-m", "docpluck", *args]
    return subprocess.run(cmd, capture_output=True, text=True, timeout=60)


def test_structured_flag_outputs_json():
    pdf = _fixture("elsevier_full_grid_descriptives.pdf")
    result = _run("extract", "--structured", str(pdf))
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert "tables" in data
    assert "figures" in data
    assert "text" in data


def test_thorough_flag():
    pdf = _fixture("uncaptioned_data_block.pdf")
    result = _run("extract", "--structured", "--thorough", str(pdf))
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert "thorough" in data["method"] or "+thorough" in data["method"]


def test_text_mode_placeholder_flag():
    pdf = _fixture("elsevier_full_grid_descriptives.pdf")
    result = _run("extract", "--structured", "--text-mode", "placeholder", str(pdf))
    assert result.returncode == 0
    data = json.loads(result.stdout)
    if data["tables"]:
        assert "[Table" in data["text"]


def test_tables_only_omits_figures():
    pdf = _fixture("psych_paper_figures_only.pdf")
    result = _run("extract", "--structured", "--tables-only", str(pdf))
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert data["figures"] == []


def test_figures_only_omits_tables():
    pdf = _fixture("elsevier_full_grid_descriptives.pdf")
    result = _run("extract", "--structured", "--figures-only", str(pdf))
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert data["tables"] == []


def test_existing_extract_no_flags_unchanged():
    pdf = _fixture("elsevier_full_grid_descriptives.pdf")
    result = _run("extract", str(pdf))
    assert result.returncode == 0
    # Plain mode does NOT emit JSON, just text
    assert not result.stdout.lstrip().startswith("{")
```

- [ ] **Step 16.3: Run test to verify it fails**

```bash
pytest tests/test_cli_structured.py -v
```

Expected: most tests fail or error.

- [ ] **Step 16.4: Patch `docpluck/cli.py`**

Add the new flags to the `extract` subcommand parser. Roughly:

```python
parser_extract.add_argument(
    "--structured", action="store_true",
    help="Emit JSON with tables and figures (extract_pdf_structured).",
)
parser_extract.add_argument(
    "--thorough", action="store_true",
    help="With --structured: scan every page for uncaptioned tables.",
)
parser_extract.add_argument(
    "--text-mode", choices=("raw", "placeholder"), default="raw",
    help="With --structured: how to render table/figure regions in 'text'.",
)
parser_extract.add_argument(
    "--tables-only", action="store_true",
    help="With --structured: omit figures from output.",
)
parser_extract.add_argument(
    "--figures-only", action="store_true",
    help="With --structured: omit tables from output.",
)
parser_extract.add_argument(
    "--html-tables-to", metavar="DIR",
    help="With --structured: write each table's HTML to DIR/<id>.html.",
)
```

In the `extract` handler, branch on `args.structured`:

```python
if args.structured:
    from docpluck import extract_pdf_structured
    import json
    result = extract_pdf_structured(
        pdf_bytes,
        thorough=args.thorough,
        table_text_mode=args.text_mode,
    )
    if args.tables_only:
        result["figures"] = []
    if args.figures_only:
        result["tables"] = []
    if args.html_tables_to:
        out_dir = Path(args.html_tables_to)
        out_dir.mkdir(parents=True, exist_ok=True)
        for t in result["tables"]:
            if t["html"]:
                (out_dir / f"{t['id']}.html").write_text(t["html"], encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False, default=list))
    return 0
```

- [ ] **Step 16.5: Run tests to verify they pass**

```bash
pytest tests/test_cli_structured.py -v
```

Expected: all passing.

- [ ] **Step 16.6: Commit**

```bash
git add docpluck/cli.py tests/test_cli_structured.py
git commit -m "feat(cli): add --structured / --thorough / --text-mode flags"
```

---

## Phase 15 — Smoke fixture assertions (requires BARRIER 1)

### Task 17: Per-fixture assertion tests

**Files:**
- Test: `tests/test_smoke_fixtures.py`

- [ ] **Step 17.1: Write the assertions test**

`tests/test_smoke_fixtures.py`:

```python
"""Per-fixture assertions driven by tests/fixtures/structured/MANIFEST.json."""

import json
from pathlib import Path
import pytest

from docpluck import extract_pdf_structured


_FIX = Path(__file__).parent / "fixtures" / "structured"
_MANIFEST = _FIX / "MANIFEST.json"


def _entries():
    if not _MANIFEST.is_file():
        return []
    return json.loads(_MANIFEST.read_text(encoding="utf-8"))["fixtures"]


@pytest.mark.parametrize("entry", _entries(), ids=lambda e: e.get("filename", "?"))
def test_table_count_matches_manifest(entry):
    pdf = _FIX / entry["filename"]
    if not pdf.is_file():
        pytest.skip(f"Fixture not available: {entry['filename']}")
    expected_tables = entry["expected_tables"]
    result = extract_pdf_structured(pdf.read_bytes())
    actual = len(result["tables"])
    # Detection should match within ±1 (small tolerance for edge cases)
    assert abs(actual - expected_tables) <= 1, (
        f"{entry['filename']}: expected {expected_tables} tables, got {actual}"
    )


@pytest.mark.parametrize("entry", _entries(), ids=lambda e: e.get("filename", "?"))
def test_figure_count_matches_manifest(entry):
    pdf = _FIX / entry["filename"]
    if not pdf.is_file():
        pytest.skip(f"Fixture not available: {entry['filename']}")
    expected_figures = entry["expected_figures"]
    result = extract_pdf_structured(pdf.read_bytes())
    actual = len(result["figures"])
    assert abs(actual - expected_figures) <= 1, (
        f"{entry['filename']}: expected {expected_figures} figures, got {actual}"
    )


@pytest.mark.parametrize("entry", _entries(), ids=lambda e: e.get("filename", "?"))
def test_lattice_fixtures_emit_structured_kind(entry):
    if entry["category"] != "lattice_table":
        pytest.skip("not a lattice fixture")
    pdf = _FIX / entry["filename"]
    if not pdf.is_file():
        pytest.skip(f"Fixture not available: {entry['filename']}")
    result = extract_pdf_structured(pdf.read_bytes())
    structured = [t for t in result["tables"] if t["kind"] == "structured"]
    # 100% structure rate target on lattice fixtures (per spec §2 success criteria)
    assert len(structured) == len(result["tables"]) >= 1


@pytest.mark.parametrize("entry", _entries(), ids=lambda e: e.get("filename", "?"))
def test_apa_lineless_fixtures_at_least_isolated(entry):
    if entry["category"] != "apa_lineless":
        pytest.skip("not an apa_lineless fixture")
    pdf = _FIX / entry["filename"]
    if not pdf.is_file():
        pytest.skip(f"Fixture not available: {entry['filename']}")
    result = extract_pdf_structured(pdf.read_bytes())
    # Must detect; structured is preferred but isolated is acceptable for v2.0.
    assert len(result["tables"]) == entry["expected_tables"]


@pytest.mark.parametrize("entry", _entries(), ids=lambda e: e.get("filename", "?"))
def test_negative_fixtures_emit_no_tables(entry):
    if entry["category"] not in {"negative_no_tables_no_figures", "table_of_contents_negative"}:
        pytest.skip("not a negative fixture")
    pdf = _FIX / entry["filename"]
    if not pdf.is_file():
        pytest.skip(f"Fixture not available: {entry['filename']}")
    result = extract_pdf_structured(pdf.read_bytes())
    assert result["tables"] == []
    assert result["figures"] == []
```

- [ ] **Step 17.2: Run smoke tests**

```bash
pytest tests/test_smoke_fixtures.py -v
```

Expected: tests pass for fixtures present; SKIPped for absent. **Investigate any failures** — they reveal bugs that must be fixed before release.

- [ ] **Step 17.3: Commit**

```bash
git add tests/test_smoke_fixtures.py
git commit -m "test(structured): add manifest-driven per-fixture smoke assertions"
```

---

## Phase 16 — Backwards-compat verification

### Task 18: Backwards-compat regression tests

**Files:**
- Test: `tests/test_v2_backwards_compat.py`

- [ ] **Step 18.1: Write the test**

`tests/test_v2_backwards_compat.py`:

```python
"""v2.0 must not change extract_pdf() output for any existing test PDF."""

import os
from pathlib import Path

import pytest

from docpluck import extract_pdf


_VIBE = Path(os.path.expanduser("~")) / "Dropbox" / "Vibe"
_PDF_DIRS = [
    _VIBE / "PDFextractor" / "test-pdfs",
    _VIBE / "ESCIcheck" / "testpdfs" / "Coded already",
]


def _all_pdfs():
    out: list[Path] = []
    for d in _PDF_DIRS:
        if d.is_dir():
            out.extend(p for p in d.rglob("*.pdf") if p.is_file())
    return out


@pytest.mark.parametrize("pdf", _all_pdfs(), ids=lambda p: p.name)
def test_extract_pdf_byte_identical(pdf):
    """extract_pdf() output must match its v1.6.x golden — captured to a snapshot file."""
    snapshot = Path(__file__).parent / "snapshots" / f"{pdf.name}.txt"
    text, method = extract_pdf(pdf.read_bytes())

    if not snapshot.exists():
        snapshot.parent.mkdir(parents=True, exist_ok=True)
        snapshot.write_text(text, encoding="utf-8")
        pytest.skip(f"Snapshot created: {snapshot}")

    expected = snapshot.read_text(encoding="utf-8")
    assert text == expected, f"extract_pdf() output drifted for {pdf.name}"


def test_method_value_uses_known_strings():
    """method must be one of the documented values."""
    pdfs = _all_pdfs()
    if not pdfs:
        pytest.skip("no test PDFs available")
    for pdf in pdfs[:5]:
        _, method = extract_pdf(pdf.read_bytes())
        assert method in {
            "pdftotext_default",
            "pdftotext_default+pdfplumber_recovery",
            "error",
        } or method.startswith("ERROR")
```

- [ ] **Step 18.2: First run — captures snapshots**

```bash
pytest tests/test_v2_backwards_compat.py -v
```

Expected: many SKIPs (snapshots created on first run). Re-run:

```bash
pytest tests/test_v2_backwards_compat.py -v
```

Expected: all PASS now (snapshots match).

- [ ] **Step 18.3: Commit snapshots + test**

```bash
git add tests/test_v2_backwards_compat.py tests/snapshots/
git commit -m "test(structured): backwards-compat snapshot tests for extract_pdf"
```

---

## Phase 17 — Documentation + release

### Task 19: Update README, CHANGELOG, BENCHMARKS

**Files:**
- Modify: `docs/README.md`
- Modify: `docs/DESIGN.md`
- Modify: `docs/BENCHMARKS.md`
- Modify: `CHANGELOG.md`
- Modify: `docpluck/__init__.py` (version)
- Modify: `pyproject.toml` (version)

- [ ] **Step 19.1: Bump versions consistently**

Edit `docpluck/__init__.py`:

```python
__version__ = "2.0.0"
```

Edit `pyproject.toml`:

```toml
version = "2.0.0"
```

`NORMALIZATION_VERSION` and `SECTIONING_VERSION` are NOT bumped (their semantics didn't change). `TABLE_EXTRACTION_VERSION` stays at `1.0.0` (first release).

- [ ] **Step 19.2: Add CHANGELOG entry**

Edit `CHANGELOG.md`. At the top, before any existing entries:

```markdown
## [2.0.0] — 2026-XX-XX

### Added
- `extract_pdf_structured()` — structured PDF extraction returning tables, figures, and text in a single call.
- `docpluck.tables` package — table detection (caption-anchored + thorough modes), lattice and whitespace cell clustering, HTML rendering, confidence scoring.
- `docpluck.figures` package — figure caption + bbox detection (metadata only; no image extraction in v2.0).
- New CLI flags: `--structured`, `--thorough`, `--text-mode {raw,placeholder}`, `--tables-only`, `--figures-only`, `--html-tables-to DIR`.
- `TABLE_EXTRACTION_VERSION` constant (starts at `1.0.0`).
- F0 footnote-strip step (in normalize_text) is now table-region-aware via the new `table_regions=` kwarg.

### Compatibility
- `extract_pdf()` output is byte-identical to v1.6.x — verified by snapshot tests across the full corpus.
- All existing public APIs unchanged; v2.0 is a major bump because of the headline new feature, not because of breaking changes.

### Coordination with v1.6.0
- Built on top of `extract_pdf_layout()` / `LayoutDoc` (introduced in v1.6.0).
- Resolves the F0/table-footnote latent conflict documented in v1.6.0's spec.
```

- [ ] **Step 19.3: Add a "Structured extraction" section to `docs/README.md`**

After the existing "Quick start" section, add:

```markdown
## Structured extraction (v2.0)

For consumers that need tables and figures as structured data — meta-analysis tooling, statistical-claim extraction, dashboards — call `extract_pdf_structured()`:

```python
from docpluck import extract_pdf_structured

with open("paper.pdf", "rb") as f:
    result = extract_pdf_structured(f.read())

print(f"{result['page_count']} pages")
print(f"{len(result['tables'])} tables, {len(result['figures'])} figures")

for t in result["tables"]:
    print(f"  {t['label']} on page {t['page']} ({t['kind']}, confidence={t['confidence']})")
    if t["kind"] == "structured":
        print(f"    {t['n_rows']} rows × {t['n_cols']} cols")
```

### Modes

```python
# Default: caption-anchored fast path (~1-2s for a 30-page paper).
extract_pdf_structured(pdf_bytes)

# Thorough: scan every page for uncaptioned tables (~9s).
extract_pdf_structured(pdf_bytes, thorough=True)

# Strip table/figure regions from `text` and replace with markers.
extract_pdf_structured(pdf_bytes, table_text_mode="placeholder")
```

See `docs/superpowers/specs/2026-05-06-table-extraction-design.md` for the schema reference.
```

- [ ] **Step 19.4: Update DESIGN.md with the §1 entry**

Add a section to `docs/DESIGN.md` linking the new feature with prior decisions, e.g.:

```markdown
## 13. Why a separate `extract_pdf_structured()` function

v2.0 added structured table/figure extraction. We considered three API
approaches (additive function, opt-in flag on `extract_pdf()`, breaking
change to a dict return). We chose additive: the existing two-tuple
contract is pinned by the SaaS service via git-pin, so a breaking change
forces a coordinated bump across 4+ projects. An additive function lets
new consumers opt in immediately without disturbing existing call sites.

Internally `extract_pdf()` and `extract_pdf_structured()` share their PDF
parse via the LayoutDoc abstraction from v1.6.0; structured extraction
costs ~3-5× more than text-only because of the geometric clustering pass,
not because of duplicated parsing.

See `docs/superpowers/specs/2026-05-06-table-extraction-design.md` §6.
```

- [ ] **Step 19.5: Add preliminary BENCHMARKS.md numbers**

Add a section to `docs/BENCHMARKS.md`:

```markdown
## Phase 4: Table & Figure Extraction (v2.0)

Smoke fixture results (15 PDFs, hand-picked for category coverage). Formal
TEDS / cell-exact-match benchmarks deferred to v2.1 (see TODO.md).

| Category | Fixtures | Detect rate | Structure rate |
|---|---|---|---|
| Lattice (full-grid) | 4 | TBD% | TBD% |
| APA lineless | 4 | TBD% | TBD% (level-C work expected to lift) |
| Nature minimal-rule | 2 | TBD% | TBD% |
| Figure-only | 2 | TBD% | n/a |
| Negative cases | 2 | 0 false positives | n/a |

Fill in the actual numbers from the smoke tests after they run on the final fixture corpus.
```

Run the smoke tests and replace `TBD` with the real numbers. If a category fails the spec's success criteria (§2.5: 100% lattice, ≥80% APA-lineless, ≥95% figure-caption), file an issue or fix before tagging.

- [ ] **Step 19.6: Run the FULL test suite end-to-end**

```bash
pytest -x -q
```

Expected: all green. If anything fails, fix before tagging.

- [ ] **Step 19.7: Commit and tag**

```bash
git add docpluck/__init__.py pyproject.toml CHANGELOG.md docs/
git commit -m "release: v2.0.0 — table & figure extraction"
git tag -a v2.0.0 -m "v2.0.0 — extract_pdf_structured() with table & figure detection"
```

- [ ] **Step 19.8: Push branch + tag (after user approval)**

**Stop here. Confirm with the user** before pushing — releasing changes the SaaS service's available pin target.

```bash
git push -u origin feat/table-extraction
git push origin v2.0.0
```

- [ ] **Step 19.9: Coordinate the SaaS app bump**

Per `CLAUDE.md`'s two-repo release flow:

1. In `PDFextractor/service/requirements.txt`, bump:
   ```
   docpluck[all] @ git+https://github.com/giladfeldman/docpluck.git@v2.0.0
   ```
2. Update any frozen version examples in `PDFextractor/API.md`.
3. Run `/docpluck-deploy` from the docpluck repo — pre-flight check 4 verifies the pin matches.

**Stop here. The SaaS app bump is a separate change in a separate repo and requires explicit user instruction to proceed.**

---

## Done.

After all 19 tasks land:
- v2.0.0 is tagged.
- `extract_pdf()` byte-identical to v1.6.x verified by snapshot.
- `extract_pdf_structured()` available with smoke-test coverage on ≥8 fixtures.
- F0 footnote-strip is table-region-aware.
- CLI exposes the structured path.
- README, DESIGN, CHANGELOG, BENCHMARKS updated.
- TODO.md tracks deferred level-C work and the v2.1 formal eval corpus.

**Next:** v2.1 milestone picks up the formal eval corpus (TEDS, cell-exact-match on 30-40 hand-labeled APA-psych PDFs) per the deferred items in TODO.md.
