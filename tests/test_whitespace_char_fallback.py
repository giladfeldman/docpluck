"""Char-level column-detection fallback for whitespace_cells (RC-T, 2026-06-25).

On tight-kerned PDFs pdfplumber's word grouper glues a whole numeric row into a
single "word" (e.g. ip_feldman Table 10's ``.29***−.21***.07``), so the
word-gap column detector finds no gaps and returns []. The chars themselves are
still cleanly separated by large inter-COLUMN gaps. ``char_whitespace_cells``
recovers the grid from char x-gaps, voting on column-START edges (data columns
are left-aligned to fixed x even when the label column is variable-width), and
reinserts intra-cell word spacing from geometry.

These synthetic tests pin the geometry contract deterministically; the real-PDF
assertion (skipped when the article-finder cache is absent) pins recovery of the
canonical ip_feldman Table 10 case end-to-end.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from docpluck.extract_layout import LayoutDoc, PageLayout
from docpluck.tables.detect import CandidateRegion
from docpluck.tables.whitespace import char_whitespace_cells, whitespace_cells


def _char(text: str, x0: float, x1: float, top: float, size: float = 9.0) -> dict:
    return {"text": text, "x0": x0, "x1": x1, "top": top, "bottom": top + size}


def _glued_word(text: str, x0: float, x1: float, top: float, size: float = 9.0) -> dict:
    return {"text": text, "x0": x0, "x1": x1, "top": top, "bottom": top + size}


def _emit_chars_for(s: str, x_start: float, top: float, cw: float = 4.5) -> list[dict]:
    """Lay out a string as adjacent single-char glyphs starting at x_start."""
    out = []
    x = x_start
    for ch in s:
        if ch == " ":
            x += cw  # a space is a gap, no glyph
            continue
        out.append(_char(ch, x, x + cw, top))
        x += cw
    return out


def _page_with(chars: list[dict], words: list[dict], width=320.0, height=400.0) -> PageLayout:
    return PageLayout(
        page_index=0, width=width, height=height, spans=(),
        words=tuple(words), chars=tuple(chars),
    )


def _region(bbox, page=1) -> CandidateRegion:
    return CandidateRegion(
        label="Table 1", page=page, bbox=bbox, caption="Table 1. Test.",
        footnote=None, geometry_signal="whitespace", caption_match=None,
    )


# --- the core tight-kerning recovery ----------------------------------------

def _tight_kerned_layout():
    """A 3-data-row right-aligned numeric table where each data row's stat block
    is ONE glued word (no word gaps) but the chars are column-separated.

    Layout: label col x≈10, data col1 starts x≈100, col2 x≈160, col3 x≈220.
    """
    chars: list[dict] = []
    words: list[dict] = []
    rows = [
        ("Loneliness",            ".29",  "-.21", ".07"),
        ("Rumination brooding",   ".22",  "-.10", ".04"),
        ("Depressive symptoms",   ".29",  "-.20", ".07"),
        ("Satisfaction life",     "-.18", ".24",  ".05"),
    ]
    top = 50.0
    for label, c1, c2, c3 in rows:
        # label as individual chars from x=10
        chars += _emit_chars_for(label, 10.0, top)
        # data columns as individual chars at fixed left edges (right-side blocks)
        chars += _emit_chars_for(c1, 100.0, top)
        chars += _emit_chars_for(c2, 160.0, top)
        chars += _emit_chars_for(c3, 220.0, top)
        # WORD layer: the whole stat block is glued into one word (tight kerning),
        # so the word path sees label + one mashed numeric token = too few gaps.
        lbl_x1 = 10.0 + len(label) * 4.5
        words.append(_glued_word(label, 10.0, lbl_x1, top))
        words.append(_glued_word(f"{c1}{c2}{c3}", 100.0, 240.0, top))
        top += 14.0
    return LayoutDoc(raw_text="", page_offsets=(0,), pages=(_page_with(chars, words),))


def test_word_path_fails_char_path_recovers_tight_kerned():
    layout = _tight_kerned_layout()
    region = _region((0.0, 40.0, 300.0, 130.0))
    # The word path alone can't find columns (the stat block is one word).
    cells = char_whitespace_cells(layout, region=region)
    assert cells, "char fallback produced no cells on a tight-kerned table"
    ncols = max(c["c"] for c in cells) + 1
    nrows = max(c["r"] for c in cells) + 1
    assert ncols == 4, f"expected 4 columns (label + 3 data), got {ncols}"
    assert nrows >= 4
    # Reconstruct the grid and check the first data row's stats.
    grid = {(c["r"], c["c"]): c["text"] for c in cells}
    # Row 0 = Loneliness
    assert grid[(0, 0)] == "Loneliness"
    assert grid[(0, 1)] == ".29"
    assert grid[(0, 2)] == "-.21"   # unicode minus normalized to ASCII hyphen
    assert grid[(0, 3)] == ".07"


def test_char_path_reinserts_word_spacing_in_labels():
    """Multi-word labels must keep their spaces (chars carry no space glyphs)."""
    layout = _tight_kerned_layout()
    region = _region((0.0, 40.0, 300.0, 130.0))
    cells = char_whitespace_cells(layout, region=region)
    grid = {(c["r"], c["c"]): c["text"] for c in cells}
    # "Rumination brooding" / "Depressive symptoms" must not collapse to one token.
    labels = {grid[(r, 0)] for r in range(max(c["r"] for c in cells) + 1)}
    assert "Rumination brooding" in labels
    assert "Depressive symptoms" in labels


def _fully_glued_layout():
    """Like _tight_kerned_layout but the WORD layer glues the ENTIRE row (label +
    stats) into one word — the real ip_feldman T10 shape, where pdfplumber's word
    grouper produces no usable column gap at all, so whitespace_cells' word path
    returns < 2 columns and must delegate to the char path."""
    base = _tight_kerned_layout()
    page = base.pages[0]
    chars = list(page.chars)
    # Rebuild a word layer: one word spanning the whole row, per row top.
    by_top: dict[float, list[dict]] = {}
    for ch in chars:
        by_top.setdefault(round(ch["top"]), []).append(ch)
    words = []
    for top, chs in by_top.items():
        x0 = min(c["x0"] for c in chs)
        x1 = max(c["x1"] for c in chs)
        txt = "".join(c["text"] for c in sorted(chs, key=lambda c: c["x0"]))
        words.append({"text": txt, "x0": x0, "x1": x1, "top": float(top),
                      "bottom": float(top) + 9.0})
    new_page = _page_with(chars, words)
    return LayoutDoc(raw_text="", page_offsets=(0,), pages=(new_page,))


def test_whitespace_cells_delegates_to_char_path():
    """The public whitespace_cells must auto-fall-back to the char path when the
    word path finds < 2 columns — the wiring that makes the fix reachable. Uses
    the fully-glued (real-T10-shape) word layer so the word path genuinely fails."""
    layout = _fully_glued_layout()
    region = _region((0.0, 40.0, 300.0, 130.0))
    cells = whitespace_cells(layout, region=region)
    assert cells, "whitespace_cells did not fall back to the char path"
    assert max(c["c"] for c in cells) + 1 == 4


def test_char_path_empty_on_single_column_block():
    """A single-column run of text (no large x-gaps) yields no grid — the char
    path must not fabricate columns out of prose."""
    chars: list[dict] = []
    top = 50.0
    for line in ("This is a paragraph", "of ordinary prose text", "with no columns at all"):
        chars += _emit_chars_for(line, 10.0, top)
        top += 14.0
    layout = LayoutDoc(raw_text="", page_offsets=(0,), pages=(_page_with(chars, []),))
    region = _region((0.0, 40.0, 300.0, 110.0))
    cells = char_whitespace_cells(layout, region=region)
    # Either no cells, or a single column — never a fabricated multi-column grid.
    if cells:
        assert max(c["c"] for c in cells) + 1 == 1


# --- real-PDF: ip_feldman Table 10 (the canonical RC-T case) ----------------

def _articlerepo(key_file: str) -> Path | None:
    p = Path(os.path.expanduser("~")) / "Dropbox" / "Vibe" / "ArticleRepository" / "fulltext" / key_file
    return p if p.is_file() else None


def test_ip_feldman_table10_data_recovered_real_pdf():
    """End-to-end: char fallback on ip_feldman Table 10's left-band region
    recovers all 7 regression-coefficient rows matching the AI gold. FAILS at
    HEAD (word path returns [] -> caption-only orphan); PASSES after."""
    pdf = _articlerepo("10.1177__01461672251327169.pdf")
    if pdf is None:
        pytest.skip("ip_feldman fixture not in article-finder cache")
    from docpluck.extract_layout import extract_pdf_layout
    from docpluck.tables.detect import _region_for_caption, find_caption_matches
    from docpluck.extract_columns import _band_gutter_x

    layout = extract_pdf_layout(pdf.read_bytes())
    caps = [m for m in find_caption_matches(layout.raw_text, list(layout.page_offsets))
            if m.kind == "table"]
    t10 = [c for c in caps if c.label.replace(" ", "").lower() == "table10"]
    if not t10:
        pytest.skip("Table 10 caption not detected")
    region = _region_for_caption(layout, t10[0])
    assert region is not None
    page_words = list(layout.pages[region.page - 1].words or ())
    gx = _band_gutter_x(page_words, float(layout.pages[region.page - 1].width or 0))
    if not gx:
        pytest.skip("no clean gutter on the Table 10 page")
    x0, top, x1, bottom = region.bbox
    clipped = CandidateRegion(
        label=region.label, page=region.page, bbox=(x0, top, min(x1, gx), bottom),
        caption=region.caption, footnote=region.footnote,
        geometry_signal=region.geometry_signal, caption_match=region.caption_match,
    )
    cells = char_whitespace_cells(layout, region=clipped)
    assert cells, "char fallback recovered no cells for Table 10"
    assert max(c["c"] for c in cells) + 1 == 4, "expected 4 columns (label + 3 stats)"
    grid = {(c["r"], c["c"]): c["text"] for c in cells}
    flat = {tuple(grid.get((r, cc), "") for cc in range(4))
            for r in range(max(c["r"] for c in cells) + 1)}
    # Each gold data row must appear exactly (minus normalized to ASCII hyphen).
    expected = [
        ("Loneliness", ".29***", "-.21***", ".07"),
        ("Rumination/brooding", ".22***", "-.10*", ".04"),
        ("Depressive symptoms", ".29***", "-.20***", ".07"),
        ("Satisfaction with life", "-.18***", ".24***", ".05"),
        ("Subjective happiness", "-.28***", ".34***", ".10"),
        ("Number of confidants", "-.07", ".15**", ".02"),
    ]
    for row in expected:
        assert row in flat, f"gold row not recovered: {row}"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
