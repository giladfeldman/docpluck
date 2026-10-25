"""H0b joins a letter-spaced label pdftotext split in two when the layout prints it on
one baseline.

10.1016/j.jesp.2009.12.011 p1 (raster checked 2026-10-14) prints the Elsevier box label
"A R T I C L E   I N F O" on ONE line, beside "A B S T R A C T". pdftotext emits
`a r t i c l e`, a blank line, `i n f o`, so the render showed two one-word lines.
"""
from __future__ import annotations

from types import SimpleNamespace

from docpluck import NormalizationLevel, normalize_text
from docpluck.normalize import _rejoin_letterspaced_lowercase_labels
from docpluck.testing import require_corpus_pdf


def _layout_line(text: str, bottom: float = 100.0):
    chars, x = [], 10.0
    for ch in text:
        chars.append({"text": ch, "x0": x, "bottom": bottom, "upright": True})
        x += 5.0
    return chars


def test_split_label_joins_on_one_baseline():
    text = "Mark Muraven\n\na r t i c l e\n\ni n f o\n\nArticle history:\n"
    lay = SimpleNamespace(pages=[SimpleNamespace(chars=_layout_line("a r t i c l e  i n f o      a b s t r a c t"))])
    out = _rejoin_letterspaced_lowercase_labels(text, lay)
    assert "\narticle info\n" in out and "\ninfo\n" not in out, out


def test_labels_on_different_baselines_stay_apart():
    text = "a r t i c l e\n\ni n f o\n"
    lay = SimpleNamespace(pages=[SimpleNamespace(
        chars=_layout_line("a r t i c l e", 100.0) + _layout_line("i n f o", 300.0))])
    out = _rejoin_letterspaced_lowercase_labels(text, lay)
    assert out == "article\n\ninfo\n", out


def test_no_layout_no_join():
    assert _rejoin_letterspaced_lowercase_labels("a r t i c l e\n\ni n f o\n") == "article\n\ninfo\n"


def test_real_render_has_one_label_line():
    from docpluck.render import render_pdf_to_markdown
    pdf = require_corpus_pdf("apa/ar_apa_j_jesp_2009_12_011.pdf").read_bytes()
    md = render_pdf_to_markdown(pdf)
    md = md if isinstance(md, str) else md[0]
    lines = [ln.strip() for ln in md.splitlines()]
    assert "article info" in lines, lines[:20]
    assert "info" not in lines, lines[:20]
