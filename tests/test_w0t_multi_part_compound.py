"""W0t also restores the hyphen dropped inside a THREE-or-more-part compound.

10.1037/a0012616 prints ``intent-to-treat`` inline (3x, plus ``Intent-to-Treat``
4x) and once across a line end as ``intent-to-`` / ``treat``; pdftotext's join
gives ``intent-totreat``. The two-part gate cannot see it: its inline pattern
refuses a part that is itself hyphenated, so ``to-treat`` is never attested.

Same evidence, one level up: the paper prints the whole compound inline, the
page's words hold the line-end fragment ``intent-to-`` once per glued copy, and
never hold the glued variant.
"""
from __future__ import annotations

from types import SimpleNamespace

from docpluck.normalize import recover_semantic_hyphens_via_layout


def _layout(*words):
    page = SimpleNamespace(words=tuple({"text": w} for w in words))
    return SimpleNamespace(pages=(page,))


def test_glued_three_part_compound_is_restored():
    text = "An intent-to-treat analysis. The intent-totreat sample was larger."
    lay = _layout("An", "intent-to-treat", "analysis.", "The", "intent-to-", "treat", "sample")
    n = [0]
    out = recover_semantic_hyphens_via_layout(text, lay, n)
    assert "The intent-to-treat sample" in out
    assert n[0] == 1


def test_join_at_the_first_hyphen_is_restored():
    text = "face-to-face talks and faceto-face visits"
    lay = _layout("face-to-face", "face-", "to-face")
    out = recover_semantic_hyphens_via_layout(text, lay, None)
    assert out == "face-to-face talks and face-to-face visits"


def test_no_inline_whole_compound_no_rewrite():
    # `cross-sec-` / `tional` is a soft break inside the last part.
    text = "a cross-sectional design"
    lay = _layout("a", "cross-sec-", "tional", "design")
    assert recover_semantic_hyphens_via_layout(text, lay, None) == text


def test_more_glued_copies_than_fragments_is_refused():
    text = "intent-to-treat; intent-totreat and intent-totreat"
    lay = _layout("intent-to-treat", "intent-to-", "treat")
    assert recover_semantic_hyphens_via_layout(text, lay, None) == text


def test_layout_printing_the_glued_variant_blocks_it():
    text = "intent-to-treat; intent-totreat"
    lay = _layout("intent-to-treat", "intent-to-", "intent-totreat")
    assert recover_semantic_hyphens_via_layout(text, lay, None) == text


def test_a0012616_intent_to_treat_survives_extract_pdf():
    from docpluck.extract import extract_pdf
    from docpluck.testing.corpus import custody_path

    text, _ = extract_pdf(custody_path("fulltext", "10.1037__a0012616.pdf").read_bytes())
    assert "intent-totreat" not in text
