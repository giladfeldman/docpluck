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

from docpluck.tables import Cell, Table
from docpluck.tables.render import cells_to_html

if TYPE_CHECKING:
    pass


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
            tables_obj = camelot.read_pdf(tmp_path, pages="all", flavor="stream")
        except Exception:
            return []

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

            cells: list[Cell] = []
            raw_row_texts: list[str] = []
            for r in range(n_rows):
                row_cells: list[str] = []
                for c in range(n_cols):
                    text = str(df.iloc[r, c]).replace("\n", " ").strip()
                    row_cells.append(text)
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
