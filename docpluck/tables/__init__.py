"""
docpluck.tables — table detection + structuring for academic PDFs.

See an internal design doc for the design.

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
    # Composite capture-quality score in [0, 1], Camelot's own formula
    # `(accuracy/100) * (1 - whitespace/100)` applied to the grid docpluck
    # ships. `None` on paths that have no capture-quality signal at all (the
    # whitespace fallback and the isolated path).
    confidence: Optional[float]
    # The COMPONENTS of `confidence`, so a consumer can reconstruct any
    # threshold and can see which half moved. Before v2.4.133 `confidence` was
    # `accuracy/100` alone, so an 80%-empty capture scored 0.95; shipping only
    # the composite would repeat that mistake in a new place.
    accuracy: Optional[float]        # Camelot's 0-100 structural accuracy
    whitespace: Optional[float]      # 0-100, share of empty slots WE emit
    # Which Camelot parser won this page ("stream" / "lattice"), or None when
    # the table did not come from Camelot. `rendering` cannot carry this: it is
    # hardcoded per capture path, so a lattice capture was indistinguishable
    # from a stream one — an unlabelled engine substitution.
    camelot_flavor: Optional[str]
    n_rows: Optional[int]
    n_cols: Optional[int]
    header_rows: Optional[int]
    cells: list[Cell]
    html: Optional[str]
    raw_text: str


__all__ = ["Cell", "Table", "TableKind", "TableRendering"]
