"""Regression test for W0j: '2'-for-U+2212 minus in body PROSE (v2.4.109).

An independent Sonnet canary AI-verify (2026-07-03) found efendic_2022_affect
FAIL — the A1/A2 table-cell glyph fixes (v2.4.102/103) had left the BODY-PROSE
and italic-table-CAPTION channels corrupt. Two prose shapes carry a '2'-for-minus
glyph with NO bracket CI, so W0b/W0d (bracket-pairing recoveries) could not reach
them:

  A · contrast-coding note:  "direction: 20.5 = low, + 0.5 = high"  (should be -0.5)
  B · change M-statistic:    "Mchange = 20.14"  (should be -0.14)

Fix (v2.4.109): `recover_prose_two_for_minus` recovers A when the "+ X.X = <word>"
±contrast twin is on the same line, and B when the M carries a difference-type
subscript (change/diff/posterior/…). Wired into channel 1 (normalize_text) AND
channel 3 (render post-process). Both signatures are line-local and tight — a
genuine "mean age of M = 20.14" is NEVER flipped (bare M, no difference subscript).
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("DOCPLUCK_DISABLE_CAMELOT", "1")

from docpluck.render import render_pdf_to_markdown

TEST_PDFS = Path(__file__).resolve().parents[1].parent / "PDFextractor" / "test-pdfs"


def test_efendic_prose_coding_note_and_mchange_recovered():
    """The coding-note contrast codes and Mchange statistics render with a minus,
    not a corrupted leading '2'."""
    pdf = TEST_PDFS / "apa" / "efendic_2022_affect.pdf"
    if not pdf.exists():
        pytest.skip(f"fixture missing: {pdf}")
    md = render_pdf_to_markdown(pdf.read_bytes())
    # Coding note: contrast codes recovered.
    assert "direction: -0.5 = low, + 0.5 = high" in md
    assert "attribute: -0.5 = benefit, + 0.5 = risk" in md
    # Mchange difference statistics recovered.
    assert "Mchange = -0.14" in md
    assert "Mchange = -1.01" in md
    assert "Mchange = -0.62" in md
    # No residual corrupt forms.
    assert "direction: 20.5 = low" not in md
    assert "Mchange = 20.14" not in md
    assert "Mchange = 21.01" not in md
    assert "Mchange = 20.62" not in md


def test_prose_minus_idempotent_on_efendic():
    """Running the recovery twice equals running it once (no double-flip)."""
    from docpluck.normalize import recover_prose_two_for_minus

    pdf = TEST_PDFS / "apa" / "efendic_2022_affect.pdf"
    if not pdf.exists():
        pytest.skip(f"fixture missing: {pdf}")
    md = render_pdf_to_markdown(pdf.read_bytes())
    assert recover_prose_two_for_minus(md) == md  # already recovered → no change


def test_coding_note_contrast_twin_required():
    """Signature A fires only when the '+ X.X = <word>' contrast twin is present."""
    from docpluck.normalize import recover_prose_two_for_minus

    # With the +twin → recover.
    with_twin = "coded as follows: 20.5 = low, + 0.5 = high"
    assert recover_prose_two_for_minus(with_twin) == "coded as follows: -0.5 = low, + 0.5 = high"
    # Without the +twin → leave alone (a bare "20.5 = X" could be genuine).
    no_twin = "the cutoff was 20.5 = threshold for inclusion"
    assert recover_prose_two_for_minus(no_twin) == no_twin


def test_mstat_bare_mean_never_flipped():
    """Signature B must NOT flip a bare mean (age ~20) — only difference stats."""
    from docpluck.normalize import recover_prose_two_for_minus

    # Genuine mean age — bare M, NO difference subscript → untouched.
    assert (
        recover_prose_two_for_minus("mean age of M = 20.14 years")
        == "mean age of M = 20.14 years"
    )
    # A genuine positive mean 2.84 → untouched.
    assert recover_prose_two_for_minus("M = 2.84, SD = 0.51") == "M = 2.84, SD = 0.51"
    # A difference statistic → recovered.
    assert recover_prose_two_for_minus("Mdiff = 20.33") == "Mdiff = -0.33"
    assert recover_prose_two_for_minus("Mposterior = 21.05") == "Mposterior = -1.05"


def test_prose_minus_leaves_percentages_and_ordinals():
    """Percentages, ordinary condition coding, and counts are never touched."""
    from docpluck.normalize import recover_prose_two_for_minus

    for s in (
        "The sample included 20.5% women and 79.5% men.",
        "We coded condition as 1 = control, 2 = treatment.",
        "Table 2 summarizes the 20 items across 2 studies.",
        "reached 20.5 million by 2020",
    ):
        assert recover_prose_two_for_minus(s) == s
