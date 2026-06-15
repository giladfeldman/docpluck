"""Regression test for the LAYOUT-channel dropped-minus recovery (W0h, R5/B7).

Some tight-kerned PDFs (e.g. the 2009 Elsevier/JESP corpus) draw the U+2212
minus sign in a dedicated symbol font. pdftotext drops the glyph entirely, so a
body-prose coefficient `b = -.022, t(87) = .17, ns` (no confidence interval to
recover from) reaches the text channel as `b = .022` — a SILENT sign flip that
inverts the statistical conclusion. W0g's CI-pairing recovery cannot reach it
(there is no CI). W0h reads the minus directly from the layout channel, where
pdfplumber surfaces the dropped glyph as an unmapped `(cid:N)` character in the
`<stat> = <minus><coef>` slot.

Confirmed on ar_apa_j_jesp_2009_12_011 (M. Muraven, JESP 2010), page 3:
    gold  →  rendered@HEAD (pre-fix)
    β = -.022  →  b = .022     (recoverable: (cid:2) in font AdvP4C4E74)
    β = +.48   →  b = .48      (genuinely positive — must stay positive)
    β = -.88   →  b = .88      (recoverable)
    β = -.245  →  b = .245     (DOCUMENTED OCR-ONLY LIMIT — see below)
    β = -.428  →  b = .428     (recoverable)

DOCUMENTED LIMITATION (β = -.245): that minus is drawn as painted pixels —
absent from pdftotext AND from pdfplumber chars/lines/rects/curves AND from
pdfminer's raw LTChar/LTImage layer. It is recoverable only by OCR, which is
outside docpluck's MIT text+layout architecture. W0h recovers the three
layout-visible negatives and deliberately leaves -.245 rather than guessing.
This test therefore asserts the 3 recoverable flips + the genuinely-positive
.48, and does NOT assert on .245 (see TODO.md R5 / normalize.py W0h comment).
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("DOCPLUCK_DISABLE_CAMELOT", "1")

from docpluck.extract_layout import LayoutDoc, PageLayout
from docpluck.normalize import recover_dropped_minus_via_layout

TEST_PDFS = Path(__file__).resolve().parents[1].parent / "PDFextractor" / "test-pdfs"


# ── Unit tests on recover_dropped_minus_via_layout (synthetic layout) ────────

def _row_chars(spec: str, *, top: float = 100.0, size: float = 8.0,
               x0: float = 50.0) -> list[dict]:
    """Lay a string out as a single row of pdfplumber-style char dicts.

    Use the literal token ``<M>`` to inject an unmapped minus glyph
    ``(cid:2)`` touching the next character (the dropped-U+2212 shape). All
    other characters advance by a fixed width with normal spacing; a space
    advances without emitting a glyph.
    """
    chars: list[dict] = []
    x = x0
    i = 0
    while i < len(spec):
        if spec.startswith("<M>", i):
            chars.append({"text": "(cid:2)", "x0": x, "x1": x + size * 0.79,
                          "top": top, "bottom": top + size, "size": size,
                          "fontname": "MIICOM+AdvP4C4E74"})
            x += size * 0.79  # minus touches the following digit (gap ~0)
            i += 3
            continue
        ch = spec[i]
        if ch == " ":
            x += size * 0.5
            i += 1
            continue
        chars.append({"text": ch, "x0": x, "x1": x + size * 0.5,
                      "top": top, "bottom": top + size, "size": size,
                      "fontname": "HNKF+AdvGulliv-R"})
        x += size * 0.5 + size * 0.25  # advance + inter-char gap
        i += 1
    return chars


def _layout(*rows: list[dict]) -> LayoutDoc:
    pages = (PageLayout(page_index=0, width=600.0, height=800.0, spans=(),
                        chars=tuple(c for r in rows for c in r)),)
    return LayoutDoc(pages=pages, raw_text="", page_offsets=(0,))


def test_layout_recovers_dropped_minus_in_assignment_slot():
    layout = _layout(_row_chars("b =<M>.022, t(87) = .17"))
    out = recover_dropped_minus_via_layout("b = .022, t(87) = .17, ns", layout)
    assert "b = -.022" in out


def test_layout_leaves_genuine_positive_coefficient():
    # No (cid:2) before .48 → the layout proves nothing → never flipped.
    layout = _layout(_row_chars("b = .48, t(87) = 1.12"))
    out = recover_dropped_minus_via_layout("b = .48, t(87) = 1.12, ns", layout)
    assert "b = .48" in out and "-.48" not in out


def test_layout_does_not_flip_when_glyph_follows_a_number():
    # `5.2 <M> 0.3` (a ± between two numbers) is NOT the `= <minus><coef>`
    # slot — the glyph's left neighbour is a digit, not `=` → never flipped.
    layout = _layout(_row_chars("M = 5.2<M>0.3"))
    out = recover_dropped_minus_via_layout("M = 5.2 0.3", layout)
    assert "-0.3" not in out


def test_layout_no_layout_is_noop():
    assert recover_dropped_minus_via_layout("b = .022", None) == "b = .022"


# ── Real-PDF regression test ─────────────────────────────────────────────────

def test_ar_apa_betas_sign_recovered_in_render():
    pdf = TEST_PDFS / "apa" / "ar_apa_j_jesp_2009_12_011.pdf"
    if not pdf.exists():
        pytest.skip(f"fixture missing: {pdf}")
    from docpluck.render import render_pdf_to_markdown
    md = render_pdf_to_markdown(pdf.read_bytes())
    # The three layout-recoverable negatives must read negative.
    assert "b = -.022" in md, "beta -.022 not sign-recovered"
    assert "b = -.88" in md, "beta -.88 not sign-recovered"
    assert "b = -.428" in md, "beta -.428 not sign-recovered"
    # The genuinely-positive coefficient must stay positive (no over-flip).
    assert "b = .48," in md and "b = -.48" not in md
    # .245 is the documented OCR-only limitation — intentionally NOT asserted.
