"""
docpluck.sections — section identification for academic papers.

See docs/superpowers/specs/2026-05-06-section-identification-design.md.

Public API: extract_sections, SectionedDocument, Section, SectionLabel,
Confidence, DetectedVia, SECTIONING_VERSION.
"""

from .taxonomy import SectionLabel, Confidence, DetectedVia
from .types import Section, SectionedDocument

SECTIONING_VERSION = "1.0.0"

__all__ = [
    "SECTIONING_VERSION",
    "Section",
    "SectionedDocument",
    "SectionLabel",
    "Confidence",
    "DetectedVia",
]
