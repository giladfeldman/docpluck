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
