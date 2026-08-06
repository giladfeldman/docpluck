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
    confidence: Optional[float]
    n_rows: Optional[int]
    n_cols: Optional[int]
    header_rows: Optional[int]
    cells: list[Cell]
    html: Optional[str]
    raw_text: str


__all__ = ["Cell", "Table", "TableKind", "TableRendering"]
