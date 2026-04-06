"""
Tests for PDF extraction.

These tests require:
1. pdftotext binary (poppler-utils)
2. Test PDFs in expected locations (Dropbox/Vibe/PDFextractor/test-pdfs/)

All tests skip gracefully when requirements are not available.
"""

import os
import shutil
import pytest
from docpluck import extract_pdf, count_pages

# Skip all extraction tests if pdftotext is not on PATH
requires_pdftotext = pytest.mark.skipif(
    shutil.which("pdftotext") is None,
    reason="pdftotext not installed (apt-get install poppler-utils)"
)

_VIBE = os.path.join(os.path.expanduser("~"), "Dropbox", "Vibe")
_PDF_DIR = os.path.join(_VIBE, "PDFextractor", "test-pdfs")


def pdf_path(*parts: str) -> str:
    return os.path.join(_PDF_DIR, *parts)


def pdf_available(*parts: str) -> bool:
    return os.path.isfile(pdf_path(*parts))


@requires_pdftotext
class TestExtractPdf:
    def _read(self, corpus: str, *parts: str) -> bytes:
        path = pdf_path(corpus, *parts)
        if not path or not pdf_available(corpus, *parts):
            pytest.skip(f"Test PDF not available: {corpus}/{'/'.join(parts)}")
        with open(path, "rb") as f:
            return f.read()

    def test_apa_2col_psychology(self):
        """APA 2-column psychology paper — primary use case."""
        content = self._read("docpluck", "apa", "chan_feldman_2025_cogemo.pdf")
        text, method = extract_pdf(content)
        assert not text.startswith("ERROR:")
        assert method == "pdftotext_default"
        assert len(text) > 10_000
        assert "significant" in text.lower() or "p <" in text or "p=" in text

    def test_apa_extracts_pvalues(self):
        """APA paper should yield extractable p-values after normalization."""
        content = self._read("docpluck", "apa", "chan_feldman_2025_cogemo.pdf")
        text, _ = extract_pdf(content)
        # Should contain statistical patterns
        import re
        pvalues = re.findall(r'[pP]\s*[<=>]\s*\.?\d', text)
        assert len(pvalues) >= 10, f"Expected ≥10 p-values, found {len(pvalues)}"

    def test_nature_smp_recovery(self):
        """Nature-style paper with SMP fonts triggers pdfplumber recovery."""
        content = self._read("docpluck", "nature", "nathumbeh_2.pdf")
        text, method = extract_pdf(content)
        assert not text.startswith("ERROR:")
        assert "pdfplumber" in method, f"SMP recovery not triggered: {method}"
        assert text.count("\ufffd") == 0, "Garbled characters remain after SMP recovery"

    def test_vancouver_medical(self):
        """Vancouver/BMC medical paper."""
        content = self._read("docpluck", "vancouver", "bmc_med_1.pdf")
        text, method = extract_pdf(content)
        assert not text.startswith("ERROR:")
        assert len(text) > 5_000

    def test_ieee_engineering(self):
        """IEEE engineering paper."""
        content = self._read("docpluck", "ieee", "ieee_access_2.pdf")
        text, method = extract_pdf(content)
        assert not text.startswith("ERROR:")
        assert len(text) > 5_000

    def test_zero_garbled_chars(self):
        """All test PDFs should have zero garbled chars after extraction."""
        content = self._read("docpluck", "apa", "chan_feldman_2025_cogemo.pdf")
        text, _ = extract_pdf(content)
        assert text.count("\ufffd") == 0

    def test_extract_returns_tuple(self):
        """Return type is always (str, str)."""
        content = self._read("docpluck", "apa", "chan_feldman_2025_cogemo.pdf")
        result = extract_pdf(content)
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], str)
        assert isinstance(result[1], str)


class TestCountPages:
    def test_count_with_real_pdf(self):
        """count_pages works without pdftotext."""
        path = pdf_path("docpluck", "apa", "chan_feldman_2025_cogemo.pdf")
        if not pdf_available("docpluck", "apa", "chan_feldman_2025_cogemo.pdf"):
            pytest.skip("Test PDF not available")
        with open(path, "rb") as f:
            content = f.read()
        pages = count_pages(content)
        assert pages >= 1

    def test_count_returns_int(self):
        """count_pages always returns an integer."""
        fake_pdf = b"%PDF-1.4\n/Type /Page\n/Type /Page\n"
        result = count_pages(fake_pdf)
        assert isinstance(result, int)
        assert result >= 1

    def test_count_empty_bytes(self):
        """count_pages handles empty/invalid input gracefully."""
        result = count_pages(b"")
        assert result == 0 or result == 1  # Either is acceptable
