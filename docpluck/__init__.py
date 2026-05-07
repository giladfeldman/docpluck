"""
docpluck — PDF, DOCX, and HTML text extraction and normalization for academic papers
====================================================================================

A Python library for extracting and normalizing text from academic documents.
Built from cross-project lessons across 8,000+ PDFs from psychology, medicine,
economics, physics, and biology.

Supports:
- **PDF** via pdftotext (default mode, with pdfplumber SMP fallback)
- **DOCX** via mammoth (DOCX → HTML → text, preserves soft breaks)
- **HTML** via beautifulsoup4 + lxml (custom block/inline-aware tree-walk)

Quick start::

    from docpluck import extract_pdf, extract_docx, extract_html
    from docpluck import normalize_text, NormalizationLevel, compute_quality_score

    # PDF
    with open("paper.pdf", "rb") as f:
        text, method = extract_pdf(f.read())

    # DOCX (requires: pip install docpluck[docx])
    with open("paper.docx", "rb") as f:
        text, method = extract_docx(f.read())

    # HTML (requires: pip install docpluck[html])
    with open("paper.html", "rb") as f:
        text, method = extract_html(f.read())

    # Normalization and quality scoring work on text from any source
    normalized, report = normalize_text(text, NormalizationLevel.academic)
    quality = compute_quality_score(normalized)

    print(f"Method: {method}")
    print(f"Quality: {quality['score']}/100 ({quality['confidence']})")
    print(f"Steps applied: {report.steps_applied}")

Installation::

    pip install docpluck             # PDF only (pdfplumber)
    pip install docpluck[docx]       # + mammoth
    pip install docpluck[html]       # + beautifulsoup4 + lxml
    pip install docpluck[all]        # everything

    # extract_pdf() also requires poppler-utils:
    #   Linux/WSL: apt-get install poppler-utils
    #   macOS:     brew install poppler
    #   Windows:   https://github.com/oschwartz10612/poppler-windows/releases

See Also:
    - docs/README.md — Full usage guide and API reference
    - docs/DESIGN.md — Implementation decisions and rationale
    - docs/BENCHMARKS.md — Benchmark results across all supported formats
    - docs/NORMALIZATION.md — All 15 pipeline steps documented
"""

from .extract import extract_pdf, extract_pdf_file, count_pages
from .extract_docx import extract_docx
from .extract_html import extract_html, html_to_text
from .normalize import normalize_text, NormalizationLevel, NormalizationReport
from .quality import compute_quality_score
from .batch import ExtractionReport, extract_to_dir
from .version import get_version_info
from .sections import (
    extract_sections, SectionedDocument, Section,
    SectionLabel, Confidence, DetectedVia, SECTIONING_VERSION,
)
from .tables import Cell, Table
from .figures import Figure
from .extract_structured import TABLE_EXTRACTION_VERSION, StructuredResult, extract_pdf_structured

__version__ = "2.0.0"
__author__ = "Gilad Feldman"
__license__ = "MIT"

__all__ = [
    # Extraction
    "extract_pdf",
    "extract_pdf_file",
    "extract_docx",
    "extract_html",
    "html_to_text",
    "count_pages",
    # Normalization
    "normalize_text",
    "NormalizationLevel",
    "NormalizationReport",
    # Quality
    "compute_quality_score",
    # Batch
    "ExtractionReport",
    "extract_to_dir",
    # Version
    "get_version_info",
    # Sections
    "extract_sections",
    "SectionedDocument",
    "Section",
    "SectionLabel",
    "Confidence",
    "DetectedVia",
    "SECTIONING_VERSION",
    # Structured extraction (v2.0)
    "Cell",
    "Table",
    "Figure",
    "TABLE_EXTRACTION_VERSION",
    "StructuredResult",
    "extract_pdf_structured",
]
