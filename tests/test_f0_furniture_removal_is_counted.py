"""F0 says how many furniture lines it deleted (d-338ea7).

F0 dropped running heads and footers with no trace: `steps_changed` got F0
only when a footnote moved, and nothing counted the deletions, so a consumer
could not tell 0 lines removed from 300. Now each removal is counted as
`f0_furniture_line_removed` (surfaced in the normalization report's
`fallbacks`). Failed on v2.4.159.
"""
from __future__ import annotations

from docpluck.extract_layout import LayoutDoc, PageLayout, TextSpan
from docpluck.normalize import PAGE_BREAK, _f0_strip_running_and_footnotes
from docpluck.telemetry import fallback_scope


def _doc(n_pages: int) -> LayoutDoc:
    def page(i: int) -> PageLayout:
        mk = lambda t, y, sz: TextSpan(  # noqa: E731
            text=t, page_index=i, x0=49.6, y0=y, x1=545.0, y1=y + 9,
            font_size=sz, font_name="Times", bold=False)
        return PageLayout(i, 595.0, 842.0, spans=(
            mk("Journal of Constant Footers", 810.0, 7.0),
            mk(f"Body sentence {i} carrying the actual content of the page.", 400.0, 9.0),
        ))
    return LayoutDoc(pages=tuple(page(i) for i in range(n_pages)), raw_text="",
                     page_offsets=tuple(range(n_pages)))


def test_each_removed_furniture_line_is_counted():
    raw = PAGE_BREAK.join(
        f"Body sentence {i} carrying the actual content of the page."
        "\nJournal of Constant Footers" for i in range(8))
    with fallback_scope() as fb:
        body, _s, _t = _f0_strip_running_and_footnotes(raw, _doc(8))
    removed = raw.count("Journal of Constant Footers") - body.count("Journal of Constant Footers")
    assert removed == 8
    assert fb.counters.get("f0_furniture_line_removed") == removed


def test_nothing_removed_nothing_counted():
    raw = PAGE_BREAK.join(
        f"Body sentence {i} carrying the actual content of the page." for i in range(8))
    with fallback_scope() as fb:
        _f0_strip_running_and_footnotes(raw, _doc(8))
    assert "f0_furniture_line_removed" not in fb.counters
