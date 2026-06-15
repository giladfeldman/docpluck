"""Regression tests for RC-1 Step 2 — per-band region-aware column re-extraction.

The whole-page column corrector (``extract_page_text_columns``) rejects any page
that carries a full-width band (table row / banner / wide title) crossing the
column centre, so two-column prose above/below such a band stays interleaved.
``extract_page_text_banded`` segments the page into horizontal y-bands and
corrects the prose bands while keeping the full-width bands intact, reassembling
top-to-bottom. It is gated behind ``DOCPLUCK_COLUMN_CORRECT_BANDED`` (ship-dark)
and validated by the splice's unconditional word-preservation guard, so it can
only ADD a pure reorder, never drop/fabricate a word.

Synthetic-layout unit tests pin the geometry (gutter detection, full-width-row
discrimination, band segmentation); the real-PDF tests pin word-preservation +
the ship-dark flag default on actual two-column fixtures.
"""
from __future__ import annotations

import os
import re
from collections import Counter
from pathlib import Path

import pytest

os.environ.setdefault("DOCPLUCK_DISABLE_CAMELOT", "1")

from docpluck.extract import extract_pdf
from docpluck.extract_layout import LayoutDoc, PageLayout
from docpluck.extract_columns import (
    _band_gutter_x,
    _row_is_2col,
    _segment_bands,
    extract_page_text_banded,
)

TEST_PDFS = Path(__file__).resolve().parents[1].parent / "PDFextractor" / "test-pdfs"


def _w(text: str, x0: float, x1: float, top: float, size: float = 10.0) -> dict:
    return {"text": text, "x0": x0, "x1": x1, "top": top, "bottom": top + size}


def _two_col_words(n_rows: int = 20, y0: float = 50.0, step: float = 15.0) -> list[dict]:
    """A clean two-column page: left x in [50,250], right x in [350,550],
    a glyph-free gutter across [250,350]."""
    words: list[dict] = []
    y = y0
    for i in range(n_rows):
        words.append(_w(f"left{i}", 50, 250, y))
        words.append(_w(f"right{i}", 350, 550, y))
        y += step
    return words


def _page(words: list[dict], width: float = 600.0, height: float = 800.0) -> PageLayout:
    return PageLayout(page_index=0, width=width, height=height, spans=(),
                      words=tuple(words))


# ── _band_gutter_x ───────────────────────────────────────────────────────────

def test_band_gutter_x_finds_central_gutter():
    gx = _band_gutter_x(_two_col_words(), 600.0)
    assert gx is not None
    assert 250.0 <= gx <= 350.0  # the clean gutter sits between the columns


def test_band_gutter_x_none_when_too_few_rows():
    # <10 text rows -> not enough evidence for a gutter.
    assert _band_gutter_x(_two_col_words(n_rows=4), 600.0) is None


# ── _row_is_2col ─────────────────────────────────────────────────────────────

def test_row_is_2col_true_for_clean_gutter_row():
    row = [_w("L", 50, 250, 100), _w("R", 350, 550, 100)]
    assert _row_is_2col(row, 300.0) is True


def test_row_is_2col_false_for_full_width_line():
    # A title/table line whose word spans the centre must NOT be column-split.
    row = [_w("WIDE TITLE", 50, 550, 100)]
    assert _row_is_2col(row, 300.0) is False


def test_row_is_2col_false_when_glyph_in_gutter_strip():
    # A word ending inside [gx-4, gx+4] blocks the column split.
    row = [_w("L", 50, 302, 100), _w("R", 360, 550, 100)]
    assert _row_is_2col(row, 300.0) is False


# ── _segment_bands ───────────────────────────────────────────────────────────

def test_segment_bands_isolates_full_width_table_band():
    # Two 2-col bands separated by a multi-row full-width band (a spanning table).
    # The band must be >1 row: a single isolated full-width line is absorbed
    # (tol=1) as a subhead, not split out — a real table band spans several rows.
    words = _two_col_words(n_rows=8, y0=50.0)              # rows 50..155
    for y in (200.0, 215.0, 230.0):                       # 3-row full-width band
        words.append(_w("FULLWIDTHTABLEROW", 50, 550, y))
    words += _two_col_words(n_rows=8, y0=270.0)            # rows 270..375
    bands = _segment_bands(words, 300.0)
    assert len(bands) == 3
    assert bands[0][0] is False   # 2-col
    assert bands[1][0] is True    # full-width
    assert bands[2][0] is False   # 2-col


def test_segment_bands_absorbs_single_full_width_subhead():
    # A lone full-width line between prose rows (a centred subheading) is NOT
    # split into its own band — tol=1 keeps the prose band coherent.
    words = _two_col_words(n_rows=8, y0=50.0)
    words.append(_w("CentredSubhead", 200, 400, 170.0))   # single full-width row
    words += _two_col_words(n_rows=8, y0=190.0)
    bands = _segment_bands(words, 300.0)
    assert len(bands) == 1
    assert bands[0][0] is False


def test_segment_bands_single_2col_band_for_clean_page():
    bands = _segment_bands(_two_col_words(n_rows=20), 300.0)
    assert len(bands) == 1
    assert bands[0][0] is False  # one two-column band, no full-width interruption


# ── real-PDF: word-preservation + ship-dark default ──────────────────────────

def _chan() -> bytes | None:
    pdf = TEST_PDFS / "apa" / "chan_feldman_2025_cogemo.pdf"
    return pdf.read_bytes() if pdf.exists() else None


def _subst_words(text: str) -> Counter:
    return Counter(re.findall(r"[^\W\d_]{2,}", text.casefold(), flags=re.UNICODE))


def test_banded_reextraction_is_word_preserving_real_pdf():
    """On a real table-bearing two-column page, the banded re-extraction is a
    pure reorder: the substantial-word multiset is unchanged (rules 0a/0b)."""
    from docpluck.extract_layout import extract_pdf_layout
    data = _chan()
    if data is None:
        pytest.skip("fixture missing: chan_feldman_2025_cogemo.pdf")
    text, _ = extract_pdf(data)  # flag off here -> plain pdftotext
    ff = [0] + [i + 1 for i, ch in enumerate(text) if ch == "\f"]
    layout = extract_pdf_layout(data)
    pidx = 6  # page 7: Table 2 (full-width) above two-column body
    start = ff[pidx]
    end = ff[pidx + 1] if pidx + 1 < len(ff) else len(text)
    original = text[start:end]
    out = extract_page_text_banded(layout, pidx, data)
    assert out.strip(), "banded re-extraction unexpectedly empty"
    assert out.split() != original.split(), "expected a reorder on an interleaved page"
    assert _subst_words(out) == _subst_words(original), "word multiset changed (not a pure reorder)"


def test_banded_flag_is_ship_dark_off_by_default_real_pdf():
    """With the flag unset the banded fallback must NOT fire — the legacy output
    is preserved. Turning it on corrects strictly more pages."""
    data = _chan()
    if data is None:
        pytest.skip("fixture missing: chan_feldman_2025_cogemo.pdf")

    def corrected_pages(method: str) -> set[int]:
        for part in method.split("+"):
            if part.startswith("column_corrected:"):
                return {int(n) for n in part.split(":", 1)[1].split(",") if n}
        return set()

    os.environ.pop("DOCPLUCK_COLUMN_CORRECT_BANDED", None)
    os.environ.pop("DOCPLUCK_COLUMN_CORRECT_GENERAL", None)
    _, m_off = extract_pdf(data)
    off_pages = corrected_pages(m_off)
    try:
        os.environ["DOCPLUCK_COLUMN_CORRECT_BANDED"] = "1"
        _, m_on = extract_pdf(data)
        on_pages = corrected_pages(m_on)
    finally:
        os.environ.pop("DOCPLUCK_COLUMN_CORRECT_BANDED", None)
    # Page 7 (Table-2-bearing) is corrected only under the flag.
    assert 7 not in off_pages
    assert 7 in on_pages
    assert off_pages <= on_pages  # ship-dark: flag only ADDS corrections
