"""
Test configuration for docpluck library tests.

PDF-dependent tests are skipped gracefully when pdftotext is not installed
or when test PDFs are not available (library tests should run anywhere).
"""

import os
import shutil
import pytest

# Ensure subprocess calls that invoke the docpluck CLI inherit UTF-8 stdio.
# This is needed on Windows where the default console encoding is cp1252 and
# U+2212 (MINUS SIGN) — which appears in normalized statistical text — is not
# representable.  Setting PYTHONUTF8 here propagates to any subprocess launched
# by subprocess.run() in tests without an explicit env= argument.
os.environ.setdefault("PYTHONUTF8", "1")


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
# docpluck's sibling repos under the same parent (e.g. MetaScienceTools/).
# Derived from this file so paths are robust to where the tree is checked out.
_SIBLINGS = os.path.dirname(os.path.dirname(_HERE))  # parent of the docpluck repo
_VIBE = os.path.join(os.path.expanduser("~"), "Dropbox", "Vibe")

PDF_PATHS = {
    # docpluck's test corpus = sibling PDFextractor repo's test-pdfs/.
    "docpluck": os.path.join(_SIBLINGS, "PDFextractor", "test-pdfs"),
    # Other-project corpora — if not under `_SIBLINGS`, dependent tests skip
    # gracefully (pdf_available returns False). Update to repo-relative once
    # the locations of these sibling repos are confirmed.
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
