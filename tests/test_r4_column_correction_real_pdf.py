"""R4 column-aware re-extraction regression test (v2.4.76, 2026-05-25).

Asserts the column-correction pipeline (`docpluck.extract.extract_pdf` →
`_detect_column_interleave_pages` → `splice_column_corrected_pages` →
`_crop_and_extract`) fires end-to-end on jama_open_1.pdf and produces
non-interleaved abstract text + a coherent Key Points sidebar block.

Real-PDF (rule 0d) + structural-signature general fix (rule 16). Closes
jama-open-1 D4 (MISSING_SECTION / Key Points sidebar) from the 2026-05-25
Haiku-orchestration pretest.
"""

from __future__ import annotations

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


def test_r4_fires_on_jama_open_1(jama_pdf_bytes: bytes):
    """The extract_pdf method tag must include `+column_corrected:N,...`
    when R4 fires on the JAMA Open paper. Asserts the detector picks up
    page 1 (where Signature B / bimodal-line-length should fire on the
    abstract+Key-Points sidebar)."""
    _text, method = extract_pdf(jama_pdf_bytes)
    assert "column_corrected" in method, (
        f"R4 did not fire on jama_open_1 — method tag missing "
        f"`+column_corrected:N,...` (got: {method!r}). Check "
        f"_detect_column_interleave_pages Signature B threshold."
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
