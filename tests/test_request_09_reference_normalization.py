"""
Request 9 (Scimeto, 2026-04-27): Reference-list normalization regression tests.

Asserts on the Li&Feldman 2025 RSOS PDF that triggered the original bug report.
The PDF is gated through ``conftest.pdf_available`` — tests skip cleanly when
the corpus is not present (so the suite still runs anywhere).

Acceptance criteria from REQUEST_09_REFERENCE_LIST_NORMALIZATION.md:
  1. Royal Society "Downloaded from..." watermark absent from normalized output.
  2. RSOS running-footer artifact DEDUPLICATED to one copy (see the test; the
     original criterion said "absent", and criterion 2 was amended 2026-08-29).
  3. Bibliography splits into 45 numbered chunks, consecutive 1..45.
  4. Ref 17 silent corruption (`psychological 41 science`) is repaired.
  5. Ref 38 DOI line break (`10.\n1007/...`) is rejoined.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from docpluck.extract import extract_pdf_file
from docpluck.normalize import normalize_text, NormalizationLevel
from .conftest import requires_pdftotext

# CUSTODY: article-finder's repository is the SOLE custodian of papers
# (CLAUDE.md, user directive 2026-08-07) — "reference articles by DOI, never
# by a local path. A path is a copy waiting to happen."
#
# This resolved to `MetaScienceTools/ESCIcheckapp/testpdfs/` until 2026-08-29.
# That project-local copy is gone, so `requires_fixture` matched and ALL FIVE
# tests here SKIPPED SILENTLY — a coverage hole wearing a green tick, and the
# reason the obsolete contract below outlived the release that invalidated it.
DOI = "10.1098/rsos.250979"
PDF = str(
    Path(os.environ.get("VIBE_ROOT") or Path.home() / "Vibe")
    / "ArticleRepository"
    / "fulltext"
    / (DOI.replace("/", "__") + ".pdf")
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

    def test_running_footer_artifact_deduplicated_leaving_exactly_one_copy(
        self, normalized_text: str
    ):
        """The RSOS running footer is DEDUPLICATED, never deleted outright.

        ⚠️ THIS TEST USED TO ASSERT ``needle not in normalized_text`` — TOTAL
        removal — and that contract is the exact shape that shipped an article
        with no title. **DO NOT "FIX" A FAILURE HERE BY RESTORING TOTAL
        DELETION.**

        On `10.1001/jamanetworkopen.2023.39337` the title *"Effect of
        Time-Restricted Eating on Weight Loss in Adults With Type 2 Diabetes"*
        is ALSO the running head, so it occurs 13 times: twelve headers and the
        page-1 title block. Under the old contract the strip took all thirteen
        and the paper was delivered with no title, with nothing in
        `changes_made` naming the line. CLAUDE.md rule 0g: a deleting step
        "must refuse all-or-nothing per run", and "deduplication is legitimate
        only when a copy demonstrably survives, otherwise it is a deletion
        wearing a dedup's name".

        Measured on this paper, 2026-08-29 under normalization 1.9.62: the
        footer line occurs on 40 of 73 pages, once per page, so it takes the
        `once_per_page` arm; 40 copies in, exactly 1 out.

        Contract rewritten 2026-08-29. Sibling of
        `tests/test_normalization.py::TestS9_HeaderFooter` and
        `tests/test_repeated_line_strip_is_observable.py`, which pin the same
        promise on synthetic input; this is the real-paper case.
        """
        needle = "royalsocietypublishing.org/journal/rsos"
        hits = [ln for ln in normalized_text.split("\n") if needle in ln]
        assert len(hits) == 1, (
            f"exactly one copy of the running footer must survive — 0 is the "
            f"all-or-nothing deletion rule 0g forbids, {len(hits)} means the "
            f"dedup did not fire"
        )

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
