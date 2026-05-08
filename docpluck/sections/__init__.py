"""
docpluck.sections — section identification for academic papers.

See docs/superpowers/specs/2026-05-06-section-identification-design.md.

Public API: extract_sections, SectionedDocument, Section, SectionLabel,
Confidence, DetectedVia, SECTIONING_VERSION.
"""

from typing import Literal

from .taxonomy import SectionLabel, Confidence, DetectedVia
from .types import Section, SectionedDocument

SECTIONING_VERSION = "1.1.0"


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

    Supports text path, HTML bytes, DOCX bytes, and PDF bytes (layout-aware
    via pdfplumber).
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

    if fmt == "pdf":
        # Architecture note: the section pipeline reads the TEXT channel
        # (pdftotext via extract_pdf), not the LAYOUT channel
        # (pdfplumber via extract_pdf_layout).  See LESSONS.md L-001 and
        # docs/DESIGN.md §13.  All heading regexes, taxonomy variants,
        # watermark patterns, and unit tests are calibrated to pdftotext's
        # output format.  DO NOT replace `extract_pdf` here — pdfplumber's
        # text wraps differently and breaks ~60+ corpus papers in one
        # commit (verified 2026-05-09).  Real-world-paper artifacts must
        # be fixed in the layer that owns them: normalize.py W0 patterns
        # for watermarks/headers, sections/annotators/text.py for heading
        # detection, sections/core.py for synthesis, sections/taxonomy.py
        # for canonical variants and numbering prefixes.
        from ..extract import extract_pdf
        from ..normalize import normalize_text, NormalizationLevel
        from .annotators.text import annotate_text
        from .core import partition_into_sections

        raw_text, _method = extract_pdf(file_bytes)
        normalized, report = normalize_text(raw_text, NormalizationLevel.academic)
        hints = annotate_text(normalized)
        sections = partition_into_sections(
            normalized, hints, source_format="pdf",
            page_offsets=report.page_offsets,
        )
        return SectionedDocument(
            sections=sections,
            normalized_text=normalized,
            sectioning_version=SECTIONING_VERSION,
            source_format="pdf",
        )

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

    if fmt == "docx":
        from .annotators.docx import annotate_docx
        from .core import partition_into_sections
        reconstructed_text, hints = annotate_docx(file_bytes)
        sections = partition_into_sections(
            reconstructed_text, hints, source_format="docx"
        )
        return SectionedDocument(
            sections=sections,
            normalized_text=reconstructed_text,
            sectioning_version=SECTIONING_VERSION,
            source_format="docx",
        )

    raise NotImplementedError(
        f"Byte input for format '{fmt}' not yet supported."
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
