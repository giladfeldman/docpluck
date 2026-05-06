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
