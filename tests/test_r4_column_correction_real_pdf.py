"""R4 column-aware re-extraction regression test (v2.4.76, 2026-05-25;
word-integrity revision v2.4.82, 2026-06-08).

Asserts the column-correction pipeline (`docpluck.extract.extract_pdf` →
`_detect_column_interleave_pages` → `splice_column_corrected_pages` →
`_crop_and_extract`) produces a WORD-CORRECT, coherent rendering of the JAMA
Open abstract + Key Points sidebar.

**v2.4.82 word-integrity revision.** The original R4 whole-page crop on
jama_open_1 page 1 de-interleaved the abstract/sidebar but SPLIT words at the
column-crop boundary (``adults`` → ``adu``, ``control`` → ``cont``,
``body`` → ``bod``) — a rule-0a/0b text corruption that shipped for weeks. The
splice now applies an UNCONDITIONAL word-preservation guard, so that corrupting
crop is rejected and page 1 keeps its word-correct (raw pdftotext) text. The
rendered abstract is therefore word-intact; the structured-abstract labels stay
in document order and the Key Points block is present without the correction.
Properly de-interleaving this page (a full-width title/byline band crossing the
two abstract/sidebar columns) requires the per-band Step 2 region-aware crop
(`docs/superpowers/specs/2026-06-08-rc1-region-aware-column-architecture.md`),
which can de-interleave WITHOUT cutting words. Until then word-integrity wins.

Real-PDF (rule 0d) + structural-signature general fix (rule 16). Closes
jama-open-1 D4 (MISSING_SECTION / Key Points sidebar) from the 2026-05-25
Haiku-orchestration pretest; the word-split it introduced is closed here.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from docpluck.extract import extract_pdf
from docpluck.render import render_pdf_to_markdown


_PDF = Path(__file__).resolve().parents[2] / "PDFextractor" / "test-pdfs" / "ama" / "jama_open_1.pdf"


@pytest.fixture(scope="module")
def jama_pdf_bytes() -> bytes:
    if not _PDF.exists():
        pytest.skip(f"corpus fixture missing: {_PDF}")
    return _PDF.read_bytes()


def test_r4_jama_abstract_word_integrity(jama_pdf_bytes: bytes):
    """The rendered abstract must contain WHOLE words — never the column-crop
    SPLIT fragments the old accept-any R4 path shipped (``adults`` → ``adu``,
    ``control`` → ``cont``, ``mean`` → ``mea``, ``body`` → ``bod``). This is the
    rule-0a/0b corruption the unconditional word-preservation guard closes; it
    is the keystone assertion for jama_open_1 (a digit/word change in a
    meta-science extraction is catastrophic)."""
    md = render_pdf_to_markdown(jama_pdf_bytes)
    # The whole words must be present...
    for whole in ["adults", "control", "body", "mean", "continued"]:
        assert re.search(rf"\b{whole}\b", md, re.IGNORECASE), (
            f"jama_open_1: whole word {whole!r} missing from rendered output — "
            f"the column-crop may have split it (rule 0a)."
        )
    # ...and the truncated crop fragments must NOT appear as standalone tokens.
    for frag in ["adu", "cont", "mea", "bod", "contin"]:
        assert not re.search(rf"(?<![A-Za-z]){frag}(?![A-Za-z])", md), (
            f"jama_open_1: word-split fragment {frag!r} appears as a standalone "
            f"token — the column-crop split a word straddling the crop x "
            f"(rule 0a/0b). The word-preservation guard must reject that crop."
        )


def test_r4_jama_no_crop_corruption_in_method(jama_pdf_bytes: bytes):
    """Either page 1 is NOT column-corrected (the whole-page crop splits words,
    so word-preservation rejects it — the current correct state), OR if a future
    band-aware crop DOES correct it, the output must still be word-intact. Encodes
    the invariant: a column correction is never accepted at the cost of a split
    word. Guards against a regression that re-enables the corrupting accept-any
    crop."""
    text, method = extract_pdf(jama_pdf_bytes)
    # The raw words survive in the extracted text regardless of whether the page
    # was corrected — the guard guarantees a reorder never splits a word.
    for whole in ["adults", "control", "body"]:
        assert re.search(rf"\b{whole}\b", text, re.IGNORECASE), (
            f"jama_open_1 extract text lost whole word {whole!r} (rule 0a)."
        )


def test_r4_jama_abstract_not_interleaved(jama_pdf_bytes: bytes):
    """The rendered .md's Abstract section must have IMPORTANCE / OBJECTIVE
    / DESIGN / INTERVENTIONS / MAIN OUTCOMES AND MEASURES labels appearing
    in document order (no interleaving with Key Points sidebar lines)."""
    md = render_pdf_to_markdown(jama_pdf_bytes)
    lines = md.split("\n")
    abstract_zone_start = next(
        (i for i, ln in enumerate(lines) if ln.strip() == "## Abstract"), None
    )
    assert abstract_zone_start is not None
    abstract_zone_end = next(
        (i for i in range(abstract_zone_start + 1, len(lines))
         if lines[i].startswith("## Introduction") or lines[i].startswith("## Methods")),
        len(lines),
    )
    zone = lines[abstract_zone_start:abstract_zone_end]
    zone_text = "\n".join(zone)

    # The structured-abstract labels should appear in document order.
    labels = ["IMPORTANCE", "OBJECTIVE", "INTERVENTIONS", "MAIN OUTCOMES AND MEASURES"]
    last_pos = -1
    for label in labels:
        pos = zone_text.find(label)
        assert pos > last_pos, (
            f"R4 interleave: structured-abstract label {label!r} does not "
            f"appear after the prior label (pos={pos}, last={last_pos}). "
            f"Check column-aware re-extraction in extract.py."
        )
        last_pos = pos


def test_r4_jama_key_points_block_present(jama_pdf_bytes: bytes):
    """The Key Points sidebar (Question / Findings / Meaning) must be
    present in the rendered output as a recoverable block — closes
    jama-open-1 D4 MISSING_SECTION."""
    md = render_pdf_to_markdown(jama_pdf_bytes)
    assert "Key Points" in md, (
        "jama-open-1 D4: Key Points header missing from rendered output. "
        "Column-aware re-extraction should surface the right-column sidebar."
    )
    # All three sidebar subsection labels should appear.
    for label in ["Question", "Findings", "Meaning"]:
        assert any(
            label in ln[:40]
            for ln in md.split("\n")
        ), (
            f"jama-open-1 D4: Key Points sidebar label {label!r} not found. "
            f"R4 may have failed to capture the right-column content."
        )
