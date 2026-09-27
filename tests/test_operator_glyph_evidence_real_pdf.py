"""W0s -- operator glyphs the text layer labels as digits, corrected on two-origin evidence.

Real paper, DOI recorded: ``10.5465/amj.2016.1196`` (corpus ``aom/amj_1.pdf``).
Page 15 prints ``(b = −0.04, SE = 0.06, t = −0.63, p = .528)``; every extractor
reads ``(b 5 20.04, SE 5 0.06, t 5 20.63, p 5 .528)`` because ``=`` and ``−`` are
drawn by a five-glyph font whose character map says ``5`` and ``2``.

Measured 2026-09-27, every glyph of that font rasterized: 336/336 ``5`` render
as two bars (``=``), 190/190 ``2`` as one bar (``−``); ``,`` ``3`` ``;`` render as
neither and stay UNRESOLVED.
"""

from __future__ import annotations

import re

import pytest

from docpluck.glyph_evidence import (
    EQUALS,
    MINUS,
    classify_bar_shape,
    resolve_token,
)
from docpluck.testing import require_corpus_pdf


def _pixels(rows: list[str]) -> tuple[int, int, bytes]:
    h, w = len(rows), len(rows[0])
    return w, h, bytes(0 if ch == "#" else 255 for r in rows for ch in r)


# ── the shape test: what it accepts and, more importantly, what it refuses ──

def test_one_interior_bar_is_a_minus():
    rows = ["." * 20] * 8 + ["." + "#" * 18 + "."] * 2 + ["." * 20] * 8
    assert classify_bar_shape(*_pixels(rows)) == MINUS


def test_two_interior_bars_are_equals():
    bar = "." + "#" * 18 + "."
    rows = ["." * 20] * 5 + [bar] * 2 + ["." * 20] * 3 + [bar] * 2 + ["." * 20] * 5
    assert classify_bar_shape(*_pixels(rows)) == EQUALS


def test_a_tall_stroke_figure_is_refused():
    # A digit: ink over most of the glyph height. Must never pass as a bar.
    rows = ["." * 10] + [".." + "#" * 6 + ".."] * 14 + ["." * 10]
    assert classify_bar_shape(*_pixels(rows)) is None


def test_ink_touching_the_crop_edge_is_a_neighbour_not_the_glyph():
    # 10.5465/amj.2016.1196 p23: a descender from the line above sat in the crop.
    rows = ["####......"] + ["." * 10] * 6 + [".########."] * 2 + ["." * 10] * 6
    assert classify_bar_shape(*_pixels(rows)) == MINUS


def test_mixed_layout_evidence_is_refused_not_guessed():
    index = {"5": [("(b", "20.04,", ((0, "="),)), ("(b", "20.04,", ())]}
    assert resolve_token("5", "(b", "20.04,", index) == ("5", "refused")


def test_a_bare_isolated_digit_does_not_outvote_an_exact_context():
    index = {"5": [("(b", "20.04,", ((0, "="),)), (None, None, ())]}
    assert resolve_token("5", "(b", "20.04,", index) == ("=", "fixed")


# ── the real paper, end to end ──────────────────────────────────────────────

@pytest.fixture(scope="module")
def amj_md() -> str:
    from docpluck.render import render_pdf_to_markdown

    pdf = require_corpus_pdf("aom/amj_1.pdf")
    md = render_pdf_to_markdown(pdf.read_bytes())
    return md if isinstance(md, str) else md[0]


def test_amj_body_sentence_matches_the_printed_page(amj_md):
    assert "(b = -0.04, SE = 0.06, t = -0.63, p = .528)" in amj_md
    assert "t 5 20.63" not in amj_md


def test_amj_correlation_table_carries_its_negative_correlations(amj_md):
    tables = "".join(re.findall(r"<table.*?</table>", amj_md, re.S))
    # p13 prints r = −.48** between D1 and D2; before W0s it was `2.48**`.
    assert "<td>-.48**</td>" in tables
    assert "<td>2.48**</td>" not in tables


def test_amj_evidence_proves_only_the_bar_shaped_codes():
    from docpluck.extract_layout import extract_pdf_layout

    pdf = require_corpus_pdf("aom/amj_1.pdf")
    ev = extract_pdf_layout(pdf.read_bytes()).glyph_evidence
    assert ev is not None
    assert ev.proven == {("AdvOT463cc31e", "2"): MINUS, ("AdvOT463cc31e", "5"): EQUALS}
    # `<`, `3` and `;` are not bars; they must stay as declared, never guessed.
    assert {c for (_f, c) in ev.unresolved} == {",", "3", ";"}


def test_no_neighbour_match_falls_back_to_the_whole_document_and_refuses_mixed():
    # Sonnet review 2026-09-27: when a genuine digit's own layout record drops out
    # (the channels tokenised its neighbours differently), isolated proven glyphs
    # must not decide it. The whole document's instances must agree.
    index = {"5": [(None, None, ((0, "="),)), ("Study", "was", ())]}
    assert resolve_token("5", "Experiment", "showed", index) == ("5", "refused")
