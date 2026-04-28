"""
Request 9 (Scimeto, 2026-04-27): Reference-list normalization regression tests.

Asserts on the Li&Feldman 2025 RSOS PDF that triggered the original bug report.
The PDF is gated through ``conftest.pdf_available`` — tests skip cleanly when
the corpus is not present (so the suite still runs anywhere).

Acceptance criteria from REQUEST_09_REFERENCE_LIST_NORMALIZATION.md:
  1. Royal Society "Downloaded from..." watermark absent from normalized output.
  2. RSOS running-footer artifact absent.
  3. Bibliography splits into 45 numbered chunks, consecutive 1..45.
  4. Ref 17 silent corruption (`psychological 41 science`) is repaired.
  5. Ref 38 DOI line break (`10.\n1007/...`) is rejoined.
"""

from __future__ import annotations

import os
import re

import pytest

from docpluck.extract import extract_pdf_file
from docpluck.normalize import normalize_text, NormalizationLevel
from .conftest import requires_pdftotext

PDF = os.path.join(
    os.path.expanduser("~"),
    "Dropbox", "Vibe", "MetaScienceTools", "ESCIcheckapp", "testpdfs",
    "Li&Feldman-2025-RSOS-PCIRR-Revisiting-mental-accounting-Thaler1999-RRR-print.pdf",
)


def _pdf_available() -> bool:
    return os.path.isfile(PDF)


requires_fixture = pytest.mark.skipif(
    not _pdf_available(),
    reason=f"Li&Feldman fixture PDF not present at {PDF}",
)


@pytest.fixture(scope="module")
def normalized_text() -> str:
    raw, _ = extract_pdf_file(PDF)
    text, _ = normalize_text(raw, NormalizationLevel.academic)
    return text


@requires_pdftotext
@requires_fixture
class TestRequest09:
    def test_watermark_url_stripped(self, normalized_text: str):
        assert "Downloaded from https://royalsocietypublishing" not in normalized_text

    def test_running_footer_artifact_stripped(self, normalized_text: str):
        assert "royalsocietypublishing.org/journal/rsos" not in normalized_text

    def test_bibliography_splits_into_45_consecutive(self, normalized_text: str):
        # Locate main bibliography (first "References" header followed by "1. Thaler")
        m = re.search(r"^References\s*\n1\.\s+Thaler", normalized_text, re.MULTILINE)
        assert m is not None, "main bibliography not located"
        biblio = normalized_text[m.start():m.start() + 10000]
        end = re.search(
            r"\n(Acknowledg|Funding|Supplementary|Appendix|Notes|Conflict|Author)",
            biblio[20:],
        )
        biblio = biblio[: 20 + end.start()] if end else biblio

        nums: list[int] = []
        for chunk in re.split(r"(?<=\s)(?=\d{1,3}\.\s+[A-Z])", biblio):
            nm = re.match(r"^(\d{1,3})\.", chunk.strip())
            if nm:
                nums.append(int(nm.group(1)))
        assert nums == list(range(1, 46)), f"expected refs 1..45, got {nums}"

    def test_ref_17_pgnum_artifact_repaired(self, normalized_text: str):
        # Should be "psychological science", not "psychological 41 science"
        m = re.search(r"17\.\s+Nosek[^\n]*", normalized_text)
        assert m is not None, "ref 17 not located"
        assert " 41 science" not in m.group()
        assert "psychological science" in m.group()

    def test_ref_38_doi_rejoined(self, normalized_text: str):
        m = re.search(r"38\.\s+Merkle[^\n]{0,400}", normalized_text)
        assert m is not None, "ref 38 not located"
        # DOI must be on one line, not split as "10.\n1007"
        assert "doi:10.1007/s10683-020-09663-x" in m.group()
