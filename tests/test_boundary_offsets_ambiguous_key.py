"""A page boundary is never placed on an earlier copy of its first line
(consult round 2, Sonnet seat, 2026-11-13).

`boundary_offsets` found a page's first 16 characters in the rewritten block
and took the FIRST hit; when the previous page's tail carried the same 16
characters, the boundary moved one page early. Now an ambiguous key is
lengthened to the whole line, then the page's next line is tried, and only
when no line of the page is unique does the first hit stand -- counted.
Refusing it outright blanked every page of 3 of 125 papers, all of whose
first hits agreed with the printed page. Text is invented. Failed on v2.4.160.
"""
from __future__ import annotations

from docpluck.sections._offsets import boundary_offsets
from docpluck.telemetry import fallback_scope

SRC = ("Intro\nthe effect was strong and it\nreplicated well in sample two\n"
       "\fthe effect was strong and again\nfinal words\n")
DST = ("Intro\nthe effect was strong and it replicated well in sample two "
       "the effect was strong and again\nfinal words\n")


def test_ambiguous_first_line_is_not_matched_early():
    off = SRC.index("\f")
    (got,) = boundary_offsets(SRC, DST, [off])
    assert got != DST.index("the effect was strong and it")
    # the whole first line is unique, so the boundary is exact
    assert got == DST.index("the effect was strong and again")


def test_unique_first_line_still_found():
    src = SRC.replace("\fthe effect was strong and again", "\fa different opening line here")
    dst = DST.replace("the effect was strong and again", "a different opening line here")
    (got,) = boundary_offsets(src, dst, [src.index("\f")])
    assert got == dst.index("a different opening line here")


def test_ambiguous_line_falls_to_the_next_unique_line():
    src = SRC.replace("strong and again", "strong and it")
    dst = DST.replace("strong and again", "strong and it")
    (got,) = boundary_offsets(src, dst, [src.index("\f")])
    assert got == dst.index("final words")


def test_no_unique_line_keeps_first_hit_and_counts_it():
    # the page's only line is ambiguous, and the next page starts at once
    src = SRC.replace("strong and again", "strong and it").replace("final words", "\fnext page")
    dst = DST.replace("strong and again", "strong and it").replace("final words", "next page")
    with fallback_scope() as fb:
        (got,) = boundary_offsets(src, dst, [src.index("\f")])
    assert got is not None
    assert fb.counters.get("section_page_boundary_ambiguous") == 1
