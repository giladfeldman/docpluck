"""
Tests for PDF extraction.

These tests require:
1. pdftotext binary (poppler-utils)
2. The corpus papers, held by article-finder and resolved by DOI

Missing pdftotext is still a skip -- it is a tool this machine may not have. A
missing PAPER is a FAILURE: it used to skip, so an absent corpus reported these
extraction tests as passing without extracting anything.
"""

import shutil
import pytest
from docpluck import extract_pdf, count_pages

from docpluck.testing import require_corpus_pdf

# Skip all extraction tests if pdftotext is not on PATH
requires_pdftotext = pytest.mark.skipif(
    shutil.which("pdftotext") is None,
    reason="pdftotext not installed (apt-get install poppler-utils)"
)

@requires_pdftotext
class TestExtractPdf:
    def _read(self, *parts: str) -> bytes:
        return require_corpus_pdf("/".join(parts)).read_bytes()

    def test_apa_2col_psychology(self):
        """APA 2-column psychology paper — primary use case."""
        content = self._read("apa", "chan_feldman_2025_cogemo.pdf")
        text, method = extract_pdf(content)
        assert not text.startswith("ERROR:")
        assert method == "pdftotext_default"
        assert len(text) > 10_000
        assert "significant" in text.lower() or "p <" in text or "p=" in text

    def test_apa_extracts_pvalues(self):
        """APA paper should yield extractable p-values after normalization."""
        content = self._read("apa", "chan_feldman_2025_cogemo.pdf")
        text, _ = extract_pdf(content)
        # Should contain statistical patterns
        import re
        pvalues = re.findall(r'[pP]\s*[<=>]\s*\.?\d', text)
        assert len(pvalues) >= 10, f"Expected ≥10 p-values, found {len(pvalues)}"

    @pytest.mark.xfail(
        strict=True,
        reason=(
            "THE PREMISE IS FALSE FOR THIS PAPER, measured 2026-09-17. "
            "`nature/nathumbeh_2.pdf` extracts as `pdftotext_default` with ZERO "
            "U+FFFD, so the pdfplumber SMP-recovery path cannot fire and the "
            "assertion below can never pass. NOT caused by the corpus repoint: the "
            "bytes the test reads are IDENTICAL before and after (sha b2ab88120b88), "
            "and extract_pdf returns the same method from either copy -- checked "
            "both ways rather than assumed, because the first diagnosis offered for "
            "this failure was a secondary-manifestation swap that did not happen. "
            "OWED: find a corpus paper that genuinely carries SMP fonts and repoint "
            "this at it, or retire the assertion. strict=True so this turns RED the "
            "moment recovery does fire, instead of quietly passing."
        ),
    )
    def test_nature_smp_recovery(self):
        """Nature-style paper with SMP fonts triggers pdfplumber recovery."""
        content = self._read("nature", "nathumbeh_2.pdf")
        text, method = extract_pdf(content)
        assert not text.startswith("ERROR:")
        assert "pdfplumber" in method, f"SMP recovery not triggered: {method}"
        assert text.count("\ufffd") == 0, "Garbled characters remain after SMP recovery"

    def test_vancouver_medical(self):
        """Vancouver/BMC medical paper."""
        content = self._read("vancouver", "bmc_med_1.pdf")
        text, method = extract_pdf(content)
        assert not text.startswith("ERROR:")
        assert len(text) > 5_000

    def test_ieee_engineering(self):
        """IEEE engineering paper."""
        content = self._read("ieee", "ieee_access_2.pdf")
        text, method = extract_pdf(content)
        assert not text.startswith("ERROR:")
        assert len(text) > 5_000

    def test_zero_garbled_chars(self):
        """All test PDFs should have zero garbled chars after extraction."""
        content = self._read("apa", "chan_feldman_2025_cogemo.pdf")
        text, _ = extract_pdf(content)
        assert text.count("\ufffd") == 0

    def test_extract_returns_tuple(self):
        """Return type is always (str, str)."""
        content = self._read("apa", "chan_feldman_2025_cogemo.pdf")
        result = extract_pdf(content)
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], str)
        assert isinstance(result[1], str)


class TestCountPages:
    def test_count_with_real_pdf(self):
        """count_pages works without pdftotext."""
        path = str(require_corpus_pdf("apa/chan_feldman_2025_cogemo.pdf"))
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
