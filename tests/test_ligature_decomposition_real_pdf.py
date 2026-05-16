"""Regression test for Latin typographic ligature decomposition
(cycle 12, v2.4.44).

pdftotext preserves presentation-form ligature glyphs (ﬁ ﬂ ﬀ ﬃ ﬄ ﬅ ﬆ,
U+FB00-FB06) verbatim, so words render as "conﬁdent" / "inﬂuence" —
broken for search, word matching, and downstream NLP. A corpus scan
found the glyphs in 35 rendered papers (korbmacher 82×, jdm_.2023.16 34×).

Fix (v2.4.44): `normalize.py::decompose_ligatures` maps the U+FB00-FB06
block to ASCII via an explicit table (`ﬁ→fi`, `ﬂ→fl`, …, `ﬅ/ﬆ→st`). An
explicit table is used rather than a scoped NFKC pass because NFKC of
U+FB05 yields "ſt" with a non-ASCII LONG S. It is the SINGLE shared helper
for all three text channels: the body channel's S3 step calls it, and so
do `cell_cleaning._html_escape` (table cells) and the `render_pdf_to_markdown`
post-process (figure/table captions, unstructured-table fences, raw_text) —
the latter two channels bypass `normalize_text` entirely, which is why a
body-only fix left raw ligature glyphs in tables and captions.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

os.environ.setdefault("DOCPLUCK_DISABLE_CAMELOT", "1")

from docpluck.extract import extract_pdf
from docpluck.normalize import NormalizationLevel, decompose_ligatures, normalize_text
from docpluck.render import render_pdf_to_markdown

TEST_PDFS = Path(__file__).resolve().parents[1].parent / "PDFextractor" / "test-pdfs"

_LIGATURE_RE = re.compile("[ﬀ-ﬆ]")


# ── Unit tests on decompose_ligatures ───────────────────────────────────

def test_decomposes_fi_ligature():
    assert decompose_ligatures("conﬁdent") == "confident"


def test_decomposes_fl_ligature():
    assert decompose_ligatures("inﬂuence") == "influence"


def test_decomposes_ffi_and_ffl():
    assert decompose_ligatures("eﬃcient") == "efficient"
    assert decompose_ligatures("baﬄing") == "baffling"


def test_decomposes_ff_and_st():
    assert decompose_ligatures("eﬀort") == "effort"
    assert decompose_ligatures("ﬆop") == "stop"


def test_decomposes_long_s_t_ligature_to_ascii():
    # U+FB05 (long-s + t). NFKC would map it to "ſt" with a non-ASCII LONG S;
    # the explicit table maps it to plain ASCII "st".
    out = decompose_ligatures("ﬅop")
    assert out == "stop"
    assert out.isascii()


def test_superscript_untouched():
    # Full NFKC would turn ² into 2; the scoped decomposition must not.
    assert decompose_ligatures("R² = .34") == "R² = .34"


def test_plain_text_untouched():
    assert decompose_ligatures("ordinary academic prose") == "ordinary academic prose"


# ── Body-channel regression: S3 must remain the ligature step ───────────

def test_s3_step_tracks_ligature_expansion():
    """The body channel's S3 step must SEE and expand ligatures itself.

    Cycle 12's first attempt called decompose_ligatures early in
    normalize_text — it consumed every ligature before S3 ran, so S3
    tracked `ligatures_expanded = 0` and starved its own report. S3 must
    remain the body channel's ligature step (it now calls the shared helper).
    """
    _, report = normalize_text("signiﬁcant eﬀect −0.73", NormalizationLevel.standard)
    assert "S3_ligature_expansion" in report.steps_applied
    assert report.changes_made.get("ligatures_expanded", 0) > 0


def test_s3_tracks_ligatures_on_real_pdf():
    """Real-PDF version of the S3-tracking regression."""
    pdf = TEST_PDFS / "apa" / "korbmacher_2022_kruger.pdf"
    if not pdf.exists():
        pytest.skip(f"fixture missing: {pdf}")
    raw, _method = extract_pdf(pdf.read_bytes())
    if not _LIGATURE_RE.search(raw):
        pytest.skip("fixture's raw extraction carries no ligature glyphs")
    _, report = normalize_text(raw, NormalizationLevel.standard)
    assert report.changes_made.get("ligatures_expanded", 0) > 0


# ── Real-PDF regression test (all channels) ─────────────────────────────

def test_jdm_m_2022_2_no_ligature_glyphs():
    pdf = TEST_PDFS / "apa" / "jdm_m.2022.2.pdf"
    if not pdf.exists():
        pytest.skip(f"fixture missing: {pdf}")
    md = render_pdf_to_markdown(pdf.read_bytes())
    leftover = _LIGATURE_RE.findall(md)
    assert not leftover, f"ligature glyphs remain: {leftover[:10]}"
    # Words that carried a ligature now read as plain ASCII.
    assert "confident" in md.lower()


def test_korbmacher_no_ligature_glyphs():
    pdf = TEST_PDFS / "apa" / "korbmacher_2022_kruger.pdf"
    if not pdf.exists():
        pytest.skip(f"fixture missing: {pdf}")
    md = render_pdf_to_markdown(pdf.read_bytes())
    leftover = _LIGATURE_RE.findall(md)
    assert not leftover, f"ligature glyphs remain: {leftover[:10]}"
