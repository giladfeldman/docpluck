"""Camelot-based table cell extraction.

Per [LESSONS.md L-006](../../LESSONS.md#l-006), Camelot ``flavor="stream"`` is the
chosen library for extracting cell-structured content from APA-style
whitespace-aligned tables. This module wraps Camelot and converts results
into docpluck's :class:`Table` TypedDict shape so callers can mix Camelot
output with the rest of the table pipeline.

License: Camelot is MIT (atlanhq/camelot). Stream flavor does NOT require
Ghostscript (only lattice does). Camelot is an OPTIONAL dependency: if the
library is not installed, this module's functions return ``[]`` and callers
silently fall back to the existing pdfplumber path.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

import re

from docpluck.tables import Cell, Table
from docpluck.tables.render import cells_to_html


# Patterns used to detect rows that look like running headers / page footers.
# These are rows where the joined cell content matches one of:
#   - Journal name + Vol./No./year ("Personality and Social Psychology Bulletin 00(0)")
#   - "Journal of X, Vol. N, No. M, ..." style
#   - Single small integer (page number)
#   - Author-list short header ("Ip and Feldman", "Korbmacher et al.")
_RUNNING_HEADER_PATTERNS = [
    re.compile(r"\b(?:[A-Z][\w&'-]*\s+){1,8}\d+\s*\([^)]*\)\s*$"),     # "...Journal Name 00(0)"
    re.compile(r"\bVol\.?\s*\d+\b", re.IGNORECASE),                    # contains "Vol. N"
    re.compile(r"\bNo\.\s*\d+\b", re.IGNORECASE),                      # contains "No. N"
    re.compile(r"^\s*\d{1,4}\s*$"),                                    # page number only
    re.compile(r"^\s*[A-Z][\w'-]+(?:\s+(?:and|&|et\s+al\.?))\s+[A-Z][\w'-]+\s*$"),  # "Ip and Feldman"
    re.compile(r"^\s*[A-Z][\w'-]+\s+et\s+al\.?\s*$"),                  # "Korbmacher et al."
    re.compile(r"\bJournal\s+of\s+\w+", re.IGNORECASE),                # "...Journal of X..."
    re.compile(r"\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}\b"),
    re.compile(r"https?://", re.IGNORECASE),                           # DOI/URL footer
    re.compile(r"^\s*\d+\s*\([^)]*\)\s*\d{4}\s*$"),                    # "13(7) 2022"
    re.compile(r"\bPersonality\s+and\s+Social\s+Psychology\b", re.IGNORECASE),
    re.compile(r"\bJudgment\s+and\s+Decision\b", re.IGNORECASE),
    re.compile(r"\bSocial\s+Psychological\s+and\s+Personality\s+Science\b", re.IGNORECASE),
    re.compile(r"\bMeta-?Psychology\b", re.IGNORECASE),
    re.compile(r"\bJournal\s+of\s+Economic\s+Psychology\b", re.IGNORECASE),
]

_CAPTION_ROW_PATTERN = re.compile(
    r"^\s*(?:Table|Fig\.?|Figure)\s+\d+(?:\.\d+)?\s*[.:]",
    re.IGNORECASE,
)


def _row_joined(row: list[str]) -> str:
    return " ".join(c for c in row if c).strip()


def _looks_like_running_header(row: list[str]) -> bool:
    joined = _row_joined(row)
    if not joined or len(joined) > 120:
        return False
    # If only one column has content, more likely a running header
    nonempty = [c for c in row if c]
    if len(nonempty) > 2:
        return False
    for pat in _RUNNING_HEADER_PATTERNS:
        if pat.search(joined):
            return True
    return False


def _strip_running_header_rows(rows: list[list[str]]) -> list[list[str]]:
    """Drop rows at the top or bottom that look like page running headers/footers."""
    out = list(rows)
    while out and _looks_like_running_header(out[0]):
        out.pop(0)
    while out and _looks_like_running_header(out[-1]):
        out.pop()
    return out


def _drop_caption_first_row(rows: list[list[str]]) -> list[list[str]]:
    """Drop "Table N. Caption text" rows from among the first 3 rows.

    Camelot sometimes includes the caption line as a table row. The caller has
    already extracted the caption from the surrounding text, so this row is
    duplicate noise. Scan the first 3 rows to catch cases where the running
    header occupies row 0 and the caption is at row 1 or 2.
    """
    out: list[list[str]] = []
    seen_caption = False
    for i, row in enumerate(rows):
        if i < 3 and not seen_caption and _CAPTION_ROW_PATTERN.search(_row_joined(row)):
            seen_caption = True
            continue
        out.append(row)
    return out


# A "purely numeric" cell: starts with a number-like token (-?digits, optional
# decimal, optional %, optional ± SD, etc.). Citations like "p. 3" or
# "(Finucane et al., 2000, p. 3)" should NOT match — they're prose with a
# number embedded, not data cells.
_PURE_NUMERIC_RE = re.compile(
    r"^\s*-?\d+(?:\.\d+)?\s*[%*]?\s*$"      # 0.45, -0.15, 95%, 5*
    r"|^\s*\(?\d+(?:\.\d+)?\)?\s*\(.*\)\s*$"  # 5 (3.2), (5)
    r"|^\s*[-+−–]?\.\d+\s*[*]*\s*$"           # .45, -.45, .45***
    r"|^\s*[χβtFpr]\s*[=<>]?\s*\d"            # χ²=, β=, t=, F=, p=, r=
)


def _is_data_cell(cell: str) -> bool:
    """A "data cell" is either:
      - purely numeric (a stat value: 0.45, 95%, χ²=12.3, etc.), or
      - a short categorical label (≤25 chars, ≤4 words) that doesn't end with
        a sentence terminator.
    Long prose with embedded citations like "(Finucane et al., 2000, p. 3)"
    should NOT count as a data cell.
    """
    if not cell:
        return False
    s = cell.strip()
    if len(s) > 60:
        return False
    if _PURE_NUMERIC_RE.match(s):
        return True
    # Short categorical labels: ≤25 chars, ≤4 words, no terminal period.
    # The end-period check rejects body-prose endings like "...as we found.".
    if len(s) <= 25 and s.split() and len(s.split()) <= 4 and not s.endswith((".", "!", "?")):
        return True
    return False


def _is_table_like(rows: list[list[str]]) -> bool:
    """Heuristic: ≥40% of non-empty rows have at least one numeric/short cell.

    Rejects "tables" that are entirely 2-column journal body prose.
    """
    nonempty = [r for r in rows if any(c for c in r)]
    if len(nonempty) < 2:
        return False
    data_like = sum(
        1 for r in nonempty
        if any(_is_data_cell(c) for c in r if c)
    )
    return (data_like / len(nonempty)) >= 0.4


def _row_looks_like_prose(row: list[str]) -> bool:
    """A row is "prose-like" if it has no data cells AND ≥1 cell of long text
    that ends with sentence punctuation OR is clearly a continuation."""
    if not any(c for c in row):
        return False
    if any(_is_data_cell(c) for c in row if c):
        return False
    longs = [c for c in row if c and len(c) > 30]
    if not longs:
        return False
    # At least one long cell — looks prose-y.
    return True


def _trim_prose_tail(rows: list[list[str]]) -> list[list[str]]:
    """Trim trailing prose rows from a Camelot table.

    Camelot sometimes bundles a real small table at the top of a 2-column page
    with 50+ rows of body prose below it. We keep the data rows at the top,
    trim where the prose run begins.

    Rule: walk from the end backwards. Drop while the row is empty or prose-like.
    Then walk from the start forward; stop at the first run of ≥3 consecutive
    prose-like rows and trim there.
    """
    if not rows:
        return rows
    # Drop trailing empty/prose rows.
    while rows and (not any(c for c in rows[-1]) or _row_looks_like_prose(rows[-1])):
        rows = rows[:-1]
    if not rows:
        return rows
    # Forward scan: find first run of ≥3 consecutive prose rows.
    n = len(rows)
    i = 0
    while i < n:
        # Skip non-prose rows
        if not _row_looks_like_prose(rows[i]):
            i += 1
            continue
        # Found a prose row — count run length
        j = i
        while j < n and _row_looks_like_prose(rows[j]):
            j += 1
        run_len = j - i
        if run_len >= 3:
            # Trim everything from i onward
            return rows[:i]
        i = j
    return rows

if TYPE_CHECKING:
    pass


def _pick_best_per_page(stream_tables: list, lattice_tables: list) -> list:
    """Given Camelot's stream and lattice outputs, pick the better extraction
    per (page, bbox-region).

    Heuristic: for each page, lattice usually wins when it returns ≥1 high-
    accuracy table on that page (lattice means the PDF has visible ruled
    lines, which is a strong tabularity signal). Otherwise stream wins.
    """
    by_page: dict[int, list] = {}
    for ct in stream_tables:
        page = getattr(ct, "page", 1)
        by_page.setdefault(page, []).append(("stream", ct))
    pages_with_lattice: dict[int, list] = {}
    for ct in lattice_tables:
        page = getattr(ct, "page", 1)
        try:
            acc = float(getattr(ct, "accuracy", 0))
        except (ValueError, TypeError):
            acc = 0.0
        if acc >= 80.0:
            pages_with_lattice.setdefault(page, []).append(("lattice", ct))

    out: list = []
    for page in sorted(set(list(by_page.keys()) + list(pages_with_lattice.keys()))):
        if page in pages_with_lattice:
            for _, ct in pages_with_lattice[page]:
                out.append(ct)
        else:
            for _, ct in by_page.get(page, []):
                out.append(ct)
    return out


def extract_tables_camelot(
    pdf_bytes: bytes,
    *,
    accuracy_threshold: float = 50.0,
) -> list[Table]:
    """Run Camelot stream on each page; return tables as docpluck Table dicts.

    Returns ``[]`` if camelot is not installed or fails to run. Tables below
    ``accuracy_threshold`` (Camelot's self-reported accuracy 0–100) are filtered
    out. Tables with fewer than 2 rows or 2 columns are filtered out.

    The returned dicts have ``label=None`` and ``caption=None`` because Camelot
    does not extract these. Callers (typically ``extract_structured``) should
    merge these with docpluck-detected tables to recover label/caption.
    """
    try:
        import camelot
    except ImportError:
        return []

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(pdf_bytes)
        tmp_path = tmp.name

    try:
        try:
            # `strip_text="\n"` collapses cell-internal newlines so multi-line
            # cells render as single lines (per Camelot best practice).
            # Run BOTH stream and lattice; pick the better one per (page, region).
            stream_tables = list(
                camelot.read_pdf(tmp_path, pages="all", flavor="stream", strip_text="\n")
            )
        except Exception:
            stream_tables = []
        try:
            lattice_tables = list(
                camelot.read_pdf(
                    tmp_path,
                    pages="all",
                    flavor="lattice",
                    strip_text="\n",
                    line_scale=40,
                    process_background=True,
                )
            )
        except Exception:
            lattice_tables = []
        tables_obj = _pick_best_per_page(stream_tables, lattice_tables)

        out: list[Table] = []
        for idx, ct in enumerate(tables_obj):
            try:
                accuracy = float(ct.accuracy)
            except (AttributeError, ValueError, TypeError):
                accuracy = 0.0
            if accuracy < accuracy_threshold:
                continue
            df = ct.df
            try:
                n_rows = len(df)
                n_cols = len(df.columns)
            except Exception:
                continue
            if n_rows < 2 or n_cols < 2:
                continue

            # Build the row matrix first; trim noisy rows; then emit cells.
            row_matrix: list[list[str]] = []
            for r in range(n_rows):
                row_cells: list[str] = [
                    str(df.iloc[r, c]).replace("\n", " ").strip()
                    for c in range(n_cols)
                ]
                row_matrix.append(row_cells)

            row_matrix = _strip_running_header_rows(row_matrix)
            row_matrix = _drop_caption_first_row(row_matrix)
            # Trim trailing prose rows (Camelot sometimes bundles a small real
            # table at the top of a 2-column page with body prose below).
            row_matrix = _trim_prose_tail(row_matrix)
            if not _is_table_like(row_matrix):
                # Even after trimming, the remaining content doesn't look like
                # a real table. Skip.
                continue

            n_rows = len(row_matrix)
            n_cols = max((len(r) for r in row_matrix), default=0)

            cells: list[Cell] = []
            raw_row_texts: list[str] = []
            for r, row_cells in enumerate(row_matrix):
                for c, text in enumerate(row_cells):
                    if not text:
                        continue
                    cells.append(
                        {
                            "r": r,
                            "c": c,
                            "rowspan": 1,
                            "colspan": 1,
                            "text": text,
                            "is_header": (r == 0),
                            "bbox": (0.0, 0.0, 0.0, 0.0),
                        }
                    )
                row_text = " ".join(s for s in row_cells if s).strip()
                if row_text:
                    raw_row_texts.append(row_text)

            try:
                page = int(ct.page)
            except (AttributeError, ValueError, TypeError):
                page = 1
            try:
                cam_bbox = tuple(ct._bbox)
            except (AttributeError, TypeError):
                cam_bbox = (0.0, 0.0, 0.0, 0.0)

            try:
                html = cells_to_html(cells)
            except Exception:
                html = None

            out.append(
                {
                    "id": f"camelot_t{idx}",
                    "label": None,
                    "page": page,
                    "bbox": cam_bbox,
                    "caption": None,
                    "footnote": None,
                    "kind": "structured",
                    "rendering": "whitespace",
                    "confidence": accuracy / 100.0,
                    "n_rows": n_rows,
                    "n_cols": n_cols,
                    "header_rows": 1,
                    "cells": cells,
                    "html": html,
                    "raw_text": "\n".join(raw_row_texts),
                }
            )
        return out
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def _bboxes_overlap(a: tuple[float, ...], b: tuple[float, ...]) -> bool:
    """Liberal bbox overlap check: intersection area > 0 in any consistent space."""
    if not a or not b or len(a) < 4 or len(b) < 4:
        return False
    if a == (0.0, 0.0, 0.0, 0.0) or b == (0.0, 0.0, 0.0, 0.0):
        return False
    a0, a1, a2, a3 = a[0], a[1], a[2], a[3]
    b0, b1, b2, b3 = b[0], b[1], b[2], b[3]
    return (
        max(a0, b0) < min(a2, b2)
        and max(a1, b1) < min(a3, b3)
    )


def merge_camelot_with_docpluck(
    docpluck_tables: list[Table],
    camelot_tables: list[Table],
) -> list[Table]:
    """Merge Camelot-extracted tables with docpluck-detected tables.

    Strategy:
      1. For each docpluck table, if it has empty ``cells`` (whitespace/isolated
         table that pdfplumber couldn't structure), look for a Camelot table on
         the same page. Replace the empty cells with Camelot's. Preserve
         docpluck's ``label``, ``caption``, ``footnote`` (Camelot doesn't have these).
      2. For Camelot tables on pages where docpluck found nothing covering them,
         add them as new tables (synthesizing a sequential label like "Table N"
         that doesn't collide with docpluck-supplied labels).
      3. Return the merged list, sorted by ``(page, label)``.
    """
    used_camelot: set[int] = set()
    out: list[Table] = []

    # Pass 1: enrich docpluck tables with camelot cells where they exist
    for dt in docpluck_tables:
        if dt.get("cells"):
            out.append(dt)
            continue
        # Find a camelot table on the same page (prefer bbox overlap)
        same_page_idx = [
            i for i, ct in enumerate(camelot_tables)
            if i not in used_camelot and ct.get("page") == dt.get("page")
        ]
        match: int | None = None
        for i in same_page_idx:
            if _bboxes_overlap(camelot_tables[i].get("bbox", ()), dt.get("bbox", ())):
                match = i
                break
        if match is None and same_page_idx:
            # Fallback: same-page largest camelot table
            match = max(same_page_idx, key=lambda i: len(camelot_tables[i].get("cells", [])))
        if match is not None:
            ct = camelot_tables[match]
            used_camelot.add(match)
            enriched = dict(dt)
            enriched["cells"] = ct["cells"]
            enriched["n_rows"] = ct["n_rows"]
            enriched["n_cols"] = ct["n_cols"]
            enriched["header_rows"] = ct.get("header_rows", 1)
            enriched["rendering"] = "whitespace"
            enriched["kind"] = "structured"
            enriched["confidence"] = ct.get("confidence", enriched.get("confidence"))
            enriched["html"] = ct.get("html")
            # Keep docpluck's label/caption/footnote/raw_text/bbox
            out.append(enriched)
        else:
            out.append(dt)

    # Pass 2: add unused camelot tables (pages docpluck missed entirely)
    docpluck_label_count = sum(1 for t in out if t.get("label"))
    camelot_synthesized_idx = 0
    for i, ct in enumerate(camelot_tables):
        if i in used_camelot:
            continue
        synthesized = dict(ct)
        if not synthesized.get("label"):
            camelot_synthesized_idx += 1
            synthesized["label"] = f"Table {docpluck_label_count + camelot_synthesized_idx}"
        out.append(synthesized)

    # Sort by (page, label) for stable ordering
    out.sort(
        key=lambda t: (
            t.get("page") or 0,
            t.get("label") or "",
        )
    )
    return out


__all__ = ["extract_tables_camelot", "merge_camelot_with_docpluck"]
