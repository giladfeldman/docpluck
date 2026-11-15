"""Section.pages from the text channel's form feeds.

Synthetic text only. The raw form feeds are carried to the normalized text by
the line aligner; a page that collapses to nothing fails closed to () rather
than shifting later text onto a wrong page.
"""
from __future__ import annotations

from docpluck.sections import _text_page_offsets
from docpluck.telemetry import fallback_scope


def test_offsets_follow_each_page_start():
    raw = "Intro line one.\nIntro line two.\n\fMethod line.\nMore method.\n\fResults line.\n"
    norm = raw  # identity normalization: offsets are the raw ones
    offs = _text_page_offsets(raw, norm)
    assert offs == (0, raw.index("Method"), raw.index("Results"))


def test_no_form_feed_means_unknown():
    assert _text_page_offsets("one page only\n", "one page only\n") == ()


def test_a_page_that_collapses_fails_closed():
    page2 = "\n".join(f"Sentence {i} of a long second page with real content." for i in range(8))
    raw = "First page text.\n\f" + page2 + "\n\fThird page.\n"
    norm = "First page text.\nTOTALLY REWRITTEN BLOCK\nThird page.\n"   # page 2 gone
    with fallback_scope() as fb:
        assert _text_page_offsets(raw, norm) == ()
    assert fb.counters.get("section_pages_unmappable") == 1
