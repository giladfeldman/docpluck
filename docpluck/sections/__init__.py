"""
docpluck.sections — section identification for academic papers.

See docs/superpowers/specs/2026-05-06-section-identification-design.md.

Public API: extract_sections, SectionedDocument, Section, SectionLabel,
Confidence, DetectedVia, SECTIONING_VERSION.
"""

from typing import Literal

from .taxonomy import SectionLabel, Confidence, DetectedVia
from .types import Section, SectionedDocument

SECTIONING_VERSION = "1.0.0"


def _detect_format(file_bytes: bytes) -> str:
    if file_bytes[:5] == b"%PDF-":
        return "pdf"
    if file_bytes[:2] == b"PK":  # ZIP-based, likely DOCX
        return "docx"
    head = file_bytes[:64].lower()
    if b"<!doctype html" in head or b"<html" in head:
        return "html"
    raise ValueError("Could not detect source format from bytes; pass source_format=")


def extract_sections(
    file_bytes: bytes | None = None,
    *,
    text: str | None = None,
    source_format: Literal["pdf", "docx", "html"] | None = None,
) -> SectionedDocument:
    """Public entry point. Either pass `file_bytes` (with optional
    source_format hint) or pre-extracted `text` + required `source_format`.

    Phase 2 supports the text path and HTML bytes. Phases 3-4 add markup-aware
    DOCX and layout-aware PDF paths.
    """
    if text is not None:
        if source_format is None:
            raise ValueError(
                "extract_sections(text=...) requires source_format= "
                "('pdf', 'docx', or 'html')"
            )
        from .core import extract_sections_from_text
        return extract_sections_from_text(text, source_format=source_format)

    if file_bytes is None:
        raise ValueError("extract_sections requires file_bytes= or text=")

    fmt = source_format or _detect_format(file_bytes)

    if fmt == "html":
        from .annotators.html import annotate_html
        from .core import partition_into_sections
        reconstructed_text, hints = annotate_html(file_bytes)
        sections = partition_into_sections(
            reconstructed_text, hints, source_format="html"
        )
        return SectionedDocument(
            sections=sections,
            normalized_text=reconstructed_text,
            sectioning_version=SECTIONING_VERSION,
            source_format="html",
        )

    raise NotImplementedError(
        f"Byte input for format '{fmt}' not yet supported. "
        "PDF/DOCX byte input lands in Phases 3-4."
    )


__all__ = [
    "SECTIONING_VERSION",
    "Section",
    "SectionedDocument",
    "SectionLabel",
    "Confidence",
    "DetectedVia",
    "extract_sections",
]
