"""
docpluck — PDF text extraction and normalization for academic papers
=====================================================================

A Python library for extracting and normalizing text from academic PDFs.
Built from cross-project lessons across 8,000+ PDFs from psychology, medicine,
economics, physics, and biology.

Quick start::

    from docpluck import extract_pdf, normalize_text, NormalizationLevel, compute_quality_score

    with open("paper.pdf", "rb") as f:
        text, method = extract_pdf(f.read())

    normalized, report = normalize_text(text, NormalizationLevel.academic)
    quality = compute_quality_score(normalized)

    print(f"Method: {method}")
    print(f"Quality: {quality['score']}/100 ({quality['confidence']})")
    print(f"Steps applied: {report.steps_applied}")

Installation::

    pip install docpluck

    # Requires poppler-utils for extract_pdf():
    #   Linux/WSL: apt-get install poppler-utils
    #   macOS:     brew install poppler
    #   Windows:   https://github.com/oschwartz10612/poppler-windows/releases

See Also:
    - docs/README.md — Full usage guide and API reference
    - docs/DESIGN.md — Implementation decisions and rationale
    - docs/BENCHMARKS.md — Phase 0 benchmark results (50 PDFs, 8 citation styles)
    - docs/NORMALIZATION.md — All 15 pipeline steps documented
"""

from .extract import extract_pdf, count_pages
from .normalize import normalize_text, NormalizationLevel, NormalizationReport
from .quality import compute_quality_score

__version__ = "1.1.0"
__author__ = "Gilad Feldman"
__license__ = "MIT"

__all__ = [
    # Extraction
    "extract_pdf",
    "count_pages",
    # Normalization
    "normalize_text",
    "NormalizationLevel",
    "NormalizationReport",
    # Quality
    "compute_quality_score",
]
