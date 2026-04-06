"""
Test configuration for docpluck library tests.

PDF-dependent tests are skipped gracefully when pdftotext is not installed
or when test PDFs are not available (library tests should run anywhere).
"""

import os
import shutil
import pytest


def pdftotext_available():
    """Check if pdftotext binary is on PATH."""
    return shutil.which("pdftotext") is not None


# Skip marker for tests that require pdftotext
requires_pdftotext = pytest.mark.skipif(
    not pdftotext_available(),
    reason="pdftotext not installed (apt-get install poppler-utils)"
)

# Test PDF directories — optional, tests skip if not present
_HERE = os.path.dirname(__file__)
_VIBE = os.path.join(os.path.expanduser("~"), "Dropbox", "Vibe")

PDF_PATHS = {
    "docpluck": os.path.join(_VIBE, "PDFextractor", "test-pdfs"),
    "escicheck": os.path.join(_VIBE, "ESCIcheck", "testpdfs", "Coded already"),
    "metaesci": os.path.join(_VIBE, "MetaESCI", "data", "pdfs"),
    "metamiscitations": os.path.join(_VIBE, "MetaMisCitations", "data", "pretest_a", "pdfs"),
}


def pdf_path(corpus: str, *parts: str) -> str:
    """Return path to a test PDF, or empty string if not available."""
    base = PDF_PATHS.get(corpus, "")
    if not base:
        return ""
    return os.path.join(base, *parts)


def pdf_available(corpus: str, *parts: str) -> bool:
    """Check if a test PDF exists."""
    path = pdf_path(corpus, *parts)
    return bool(path) and os.path.isfile(path)
