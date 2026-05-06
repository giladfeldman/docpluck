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
        from .annotators.pdf import _annotate_layout
        from .core import partition_into_sections, append_footnotes_section
        from ..extract_layout import extract_pdf_layout
        from ..normalize import normalize_text, NormalizationLevel

        layout = extract_pdf_layout(file_bytes)
        # Run normalize at academic level WITH layout — this strips
        # footnotes/headers/footers and appends a footnote appendix.
        normalized, report = normalize_text(
            layout.raw_text, NormalizationLevel.academic, layout=layout
        )
        # Re-extract layout-aware hints from raw layout (annotator works on
        # the layout itself, not on the post-strip text).
        _, hints = _annotate_layout(layout)
        # Adjust hint offsets: hints reference offsets in the RAW text;
        # F0 produced a different normalized string. Drop hints that don't
        # appear verbatim in `normalized` and rebuild offsets via .find().
        adjusted: list = []
        cursor = 0
        for h in hints:
            idx = normalized.find(h.text, cursor)
            if idx < 0:
                continue
            cursor = idx + len(h.text)
            adjusted.append(type(h)(
                text=h.text, char_start=idx, char_end=idx + len(h.text),
                page=h.page, is_heading_candidate=h.is_heading_candidate,
                heading_strength=h.heading_strength,
                heading_source=h.heading_source,
            ))
        sections = partition_into_sections(
            normalized, adjusted, source_format="pdf",
            page_offsets=report.page_offsets,
        )
        sections = append_footnotes_section(
            sections, normalized, report.footnote_spans
        )
        return SectionedDocument(
            sections=tuple(sections),
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
