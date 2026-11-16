"""The letter-marker scan is computed once per layout, not once per table.

`LayoutDoc` is a frozen dataclass; the cache was written with a plain
assignment, which raised, was caught, and was recorded as
``layout_letter_marker_cache_unavailable`` -- so every table rescanned the whole
paper (ESCImate measured ~44% of its browser time on table-heavy papers,
2026-11-15). Synthetic layout; every glyph below is invented.
"""
from __future__ import annotations

from docpluck.extract_layout import LayoutDoc, PageLayout
from docpluck.normalize import layout_letter_marker_fusions
from docpluck.telemetry import fallback_scope


def _char(text, x0, top, size=10.0):
    w = size * 0.5
    return {"text": text, "x0": x0, "x1": x0 + w, "top": top, "bottom": top + size,
            "size": size, "upright": True, "fontname": "F1"}


def _layout():
    chars = []
    x = 50.0
    for ch in "error":
        chars.append(_char(ch, x, 100.0))
        x += 5.0
    chars.append(_char("a", x, 97.0, size=6.0))   # raised, smaller: a footnote letter
    page = PageLayout(page_index=0, width=600.0, height=800.0, spans=(), chars=tuple(chars))
    return LayoutDoc(pages=(page,), raw_text="errora", page_offsets=(0,))


def test_second_call_returns_the_cached_object():
    lay = _layout()
    with fallback_scope() as fb:
        first = layout_letter_marker_fusions(lay)
        second = layout_letter_marker_fusions(lay)
    assert second is first
    assert "layout_letter_marker_cache_unavailable" not in fb.counters, fb.counters


def test_cache_does_not_change_equality():
    a, b = _layout(), _layout()
    layout_letter_marker_fusions(a)
    assert a == b
