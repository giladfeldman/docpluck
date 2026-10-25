"""RC-1 Step 1 — general two-column interleave correction (v2.4.82), real-PDF.

Background
==========
pdftotext serialises two-column academic pages by interleaving the columns when
the layout carries no geometric signal it can latch onto. ``extract_columns``
(O5 / v2.4.80) can re-extract a page left-column-then-right under a full-height
GUTTER-STRIP midline detector + a word-multiset preservation guard, but until
v2.4.82 that machinery was wired ONLY for the narrow O5 reference-inversion
case. The GENERAL-interleave pages flagged by
``normalize._detect_column_interleave_pages`` reached ``splice_column_corrected_pages``
WITHOUT ``allow_gutter_fallback`` and WITHOUT the word-preservation guard, so
they fell to the histogram detector + bilateral table gate and stayed
interleaved on narrow-gutter (Collabra / JESP / Elsevier) and table-bearing
pages — the dominant defect on two-column APA papers (TRIAGE 2026-06-08).

The fix (general, keyed on a STRUCTURAL SIGNATURE — a clean full-height central
gutter + a word-preserving reorder, never paper identity): when
``DOCPLUCK_COLUMN_CORRECT_GENERAL=1`` the general-interleave flagged pages join
the inversion pages under BOTH safeties. It shipped dark (default OFF) and was
turned ON by default in v2.4.155, behind the prose gate (see
``test_column_prose_gate.py``); ``=0`` turns the general path off again.

These tests assert the two invariants that make the flag safe to flip:
  1. Flag OFF: no general column-correction, deterministic output.
  2. Flag ON: corrects strictly MORE pages, and every corrected page is a PURE
     REORDER — the document's substantial-word multiset is unchanged (rules
     0a/0b: no text dropped, none invented).

Real-PDF (rule 0d) + structural-signature general fix (rule 16).
"""

from __future__ import annotations


import pytest

from docpluck.extract import extract_pdf
from docpluck.extract_columns import _word_multiset

from docpluck.testing import require_corpus_pdf


# Two-column corpus papers whose general-interleave pages have a clean gutter
# (so the flag corrects them). chandrashekar_2023_mp was the second until
# v2.4.155: its flagged pages carry tables and figures the region plan does not
# read safely, so the general path now leaves them as they were.
_STEMS = ["chan_feldman_2025_cogemo", "ip_feldman_2025_pspb"]

_FLAG = "DOCPLUCK_COLUMN_CORRECT_GENERAL"


def _corrected_pages(method: str) -> set[int]:
    """Parse the ``+column_corrected:a,b,c`` tag out of an extract_pdf method."""
    if "+column_corrected:" not in method:
        return set()
    tag = method.split("+column_corrected:")[1].split("+")[0]
    return {int(x) for x in tag.split(",") if x.strip().isdigit()}


@pytest.mark.parametrize("stem", _STEMS)
def test_flag_off_is_legacy_byte_identical(stem: str, monkeypatch):
    """With the flag set to 0, the general path must NOT fire and extraction
    must be deterministic (the opt-out restores the legacy output). The flag
    is ON by default since v2.4.155."""
    pdf = require_corpus_pdf(f"apa/{stem}.pdf")
    monkeypatch.setenv(_FLAG, "0")
    b = pdf.read_bytes()
    text_a, method_a = extract_pdf(b)
    text_b, _ = extract_pdf(b)
    assert text_a == text_b, f"{stem}: flag-off extraction is non-deterministic"
    # These papers carry no O5 reference-inversion, so flag-off corrects nothing.
    assert _corrected_pages(method_a) == set(), (
        f"{stem}: general column-correction fired with the flag OFF "
        f"(method={method_a!r}) — the opt-out must be byte-identical legacy."
    )


@pytest.mark.parametrize("stem", _STEMS)
def test_flag_on_corrects_more_pages_preserving_words(stem: str, monkeypatch):
    """With the flag ON, the general path corrects strictly more pages than the
    legacy path, and the correction is a PURE REORDER — the substantial-word
    multiset of the whole document is identical to the flag-off extraction
    (rules 0a/0b: no text-loss, no hallucination)."""
    pdf = require_corpus_pdf(f"apa/{stem}.pdf")
    b = pdf.read_bytes()

    monkeypatch.setenv(_FLAG, "0")
    text_off, method_off = extract_pdf(b)

    monkeypatch.setenv(_FLAG, "1")
    text_on, method_on = extract_pdf(b)

    off_pages = _corrected_pages(method_off)
    on_pages = _corrected_pages(method_on)
    assert on_pages > off_pages, (
        f"{stem}: flag ON did not correct more pages than OFF "
        f"(off={sorted(off_pages)}, on={sorted(on_pages)}) — the general "
        f"column-correction never fired."
    )
    assert text_on != text_off, f"{stem}: flag ON did not change the text"

    # The hard safety: a corrected page is a pure reorder, so the whole-doc
    # substantial-word multiset (alphabetic tokens len>=2) must be UNCHANGED.
    ms_off = _word_multiset(text_off)
    ms_on = _word_multiset(text_on)
    assert ms_on == ms_off, (
        f"{stem}: flag-ON column correction changed the substantial-word "
        f"multiset — text was dropped or invented (rules 0a/0b). "
        f"only_off={list((ms_off - ms_on).elements())[:8]} "
        f"only_on={list((ms_on - ms_off).elements())[:8]}"
    )
