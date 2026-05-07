"""
docpluck.extract_structured — top-level structured PDF extraction.

Provides extract_pdf_structured(), the orchestrator over the existing
extract_pdf() text path plus the new tables/ and figures/ detection paths.

See docs/superpowers/specs/2026-05-06-table-extraction-design.md for the design.
"""

from __future__ import annotations

from typing import Literal, TypedDict

from .extract import extract_pdf, count_pages
from .figures import Figure
from .figures.detect import find_figures
from .tables import Cell, Table
from .tables.bbox_utils import bbox_to_char_range
from .tables.captions import CaptionMatch
from .tables.cluster import lattice_cells
from .tables.confidence import (
    clamp_confidence,
    score_table,
    should_fall_back_to_isolated,
)
from .tables.detect import CandidateRegion, find_table_regions
from .tables.render import cells_to_html
from .tables.whitespace import whitespace_cells


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
    page_count = count_pages(pdf_bytes)

    if raw_text.startswith("ERROR:"):
        return {
            "text": raw_text,
            "method": base_method,
            "page_count": page_count,
            "tables": [],
            "figures": [],
            "table_extraction_version": TABLE_EXTRACTION_VERSION,
        }

    method_pieces = [base_method]
    tables: list[Table] = []
    figures: list[Figure] = []
    layout = None

    try:
        from .extract_layout import extract_pdf_layout
        layout = extract_pdf_layout(pdf_bytes)
    except Exception:
        method_pieces.append("pdfplumber_tables_failed")
        return {
            "text": raw_text,
            "method": "+".join(method_pieces),
            "page_count": page_count,
            "tables": [],
            "figures": [],
            "table_extraction_version": TABLE_EXTRACTION_VERSION,
        }

    try:
        regions = find_table_regions(layout, thorough=thorough)
        tables = [_build_table(layout, region, idx) for idx, region in enumerate(regions, start=1)]
        figures = find_figures(layout)
        method_pieces.append("pdfplumber_tables")
        if thorough:
            method_pieces.append("thorough")
    except Exception:
        method_pieces.append("pdfplumber_tables_failed")
        tables = []
        figures = []

    text_out = (
        _apply_placeholder(raw_text, layout, tables, figures)
        if table_text_mode == "placeholder"
        else raw_text
    )

    return {
        "text": text_out,
        "method": "+".join(method_pieces),
        "page_count": page_count,
        "tables": tables,
        "figures": figures,
        "table_extraction_version": TABLE_EXTRACTION_VERSION,
    }


# --- helpers ---


def _build_table(layout, region: CandidateRegion, idx: int) -> Table:
    raw_slice = _bbox_raw_text(layout, region)

    cells: list[Cell] = []
    rendering: str = "isolated"

    if region.geometry_signal == "lattice":
        try:
            cells = lattice_cells(layout, region=region)
        except Exception:
            cells = []
        rendering = "lattice" if cells else "isolated"
    elif region.geometry_signal == "whitespace":
        try:
            cells = whitespace_cells(layout, region=region)
        except Exception:
            cells = []
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
            "n_rows": None,
            "n_cols": None,
            "header_rows": None,
            "cells": [],
            "html": None,
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


def _apply_placeholder(raw_text: str, layout, tables: list[Table], figures: list[Figure]) -> str:
    """Replace each table/figure region with [Label: caption] markers in raw_text."""
    items: list[tuple[int, int, str]] = []
    for t in tables:
        try:
            start, end = bbox_to_char_range(layout, bbox=t["bbox"], page=t["page"])
        except Exception:
            continue
        items.append((start, end, _marker(t.get("label"), t.get("caption"))))
    for f in figures:
        try:
            start, end = bbox_to_char_range(layout, bbox=f["bbox"], page=f["page"])
        except Exception:
            continue
        items.append((start, end, _marker(f.get("label"), f.get("caption"))))

    items.sort(key=lambda triplet: triplet[0], reverse=True)
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
    "TableTextMode",
    "extract_pdf_structured",
]
