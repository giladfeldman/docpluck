"""Carry character offsets from a text to its normalized form.

The markup annotators (DOCX, HTML) return BlockHints whose offsets index the
text they reconstructed. ``extract_sections`` normalizes that text so its
``normalized_text`` field is what it says it is, and the hints have to follow.

The alignment is LINE-level. Normalization edits within lines (glyphs, spacing,
joins) and deletes whole lines (banners, furniture); it does not reorder text.
So the lines of the two strings are aligned with ``difflib`` -- milliseconds on
a 60 k-character document, where a character-level ``SequenceMatcher`` took
349 s on the same file (measured 2026-10-08) -- and an offset inside an
aligned line keeps its column, clamped to the new line's length. A line that
normalization deleted or reshaped into a different number of lines maps to
the start of what replaced it.
"""
from __future__ import annotations

import bisect
import difflib
from collections.abc import Callable

from ..telemetry import record_fallback


def _line_starts(s: str) -> list[int]:
    out = [0]
    i = s.find("\n")
    while i != -1:
        out.append(i + 1)
        i = s.find("\n", i + 1)
    return out


def line_offset_mapper(src: str, dst: str) -> Callable[[int], int]:
    """Return ``f(offset_in_src) -> offset_in_dst`` (monotone, within bounds)."""
    a = src.split("\n")
    b = dst.split("\n")
    starts_a = _line_starts(src)
    starts_b = _line_starts(dst)
    # src line -> dst line (aligned), or ~dst_line (the start of a replacement).
    to_line: list[int] = [0] * len(a)
    matcher = difflib.SequenceMatcher(None, a, b, autojunk=False)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal" or (tag == "replace" and i2 - i1 == j2 - j1):
            for k in range(i2 - i1):
                to_line[i1 + k] = j1 + k
        else:
            for k in range(i1, i2):
                to_line[k] = ~j1

    def mapped(offset: int) -> int:
        if offset >= len(src):
            return len(dst)
        li = bisect.bisect_right(starts_a, offset) - 1
        j = to_line[li]
        if j >= 0:
            col = offset - starts_a[li]
            if col >= len(a[li]):
                # The END of a source line maps to the end of its counterpart,
                # whose length normalization may have changed (a ligature
                # expanded: consult 2026-10-09, Sonnet).
                return starts_b[j] + len(b[j])
            return starts_b[j] + min(col, len(b[j]))
        j = ~j
        return starts_b[j] if j < len(starts_b) else len(dst)

    return mapped


def boundary_offsets(src: str, dst: str, src_offsets: list[int]) -> list[int | None]:
    """Map BOUNDARY positions (each the start of a ``src`` line) into ``dst``.

    ``line_offset_mapper`` sends every line of a rewritten block to the block's
    start, which is right for a hint offset but wrong for a page boundary: a
    page that begins inside a block of rejoined reference lines got the
    block's start, so the previous page's tail was counted on it and two pages
    in one block collapsed to one point (125-paper check 2026-11-13: 59 papers
    failed closed, 5 headings one page early). Inside a rewritten block the
    boundary is the first line of the page that survives verbatim enough to be
    found: its first 16 non-blank characters, searched in that block's
    replacement. ``None`` when no line of the page can be found there -- the
    boundary is unknown, never guessed.
    """
    a = src.split("\n")
    b = dst.split("\n")
    starts_a = _line_starts(src)
    starts_b = _line_starts(dst)
    equal: dict[int, int] = {}
    matcher = difflib.SequenceMatcher(None, a, b, autojunk=False)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal" or (tag == "replace" and i2 - i1 == j2 - j1):
            for k in range(i2 - i1):
                equal[i1 + k] = j1 + k
    eq_src = sorted(equal)
    out: list[int | None] = []
    last = 0           # boundaries are monotone: never search behind the previous one
    for off in src_offsets:
        if off >= len(src):
            out.append(len(dst))
            continue
        li = bisect.bisect_right(starts_a, off) - 1
        if li in equal:
            j = equal[li]
            found = starts_b[j] + min(off - starts_a[li], len(b[j]))
            out.append(found)
            last = found
            continue
        found = None
        first_ambiguous = None
        for k in range(li, len(a)):
            if "\f" in a[k] and k > li:
                break          # the page ended without a findable line
            if k in equal:
                found = starts_b[equal[k]]
                break
            key = " ".join(a[k].replace("\f", "").split())[:16]
            if len(key) < 16:
                continue       # furniture-short, or deleted: try the next line
            # Search between the nearest unchanged lines around k: difflib
            # reports a rejoined run as delete + insert as often as replace,
            # so the opcode's own dst span can be empty.
            p = bisect.bisect_left(eq_src, k)
            lo = starts_b[equal[eq_src[p - 1]]] if p > 0 else 0
            hi = (starts_b[equal[eq_src[p]]] + len(b[equal[eq_src[p]]])
                  if p < len(eq_src) else len(dst))
            pos = dst.find(key, max(lo, last), hi)
            if pos != -1 and dst.find(key, pos + 1, hi) != -1:
                # The key occurs twice in the window: the first hit may be the
                # previous page's tail (consult round 2, 2026-11-13). Lengthen
                # it to the whole line; if that is still not unique, try the
                # page's next line. Only when no line of the page is unique
                # does the first hit stand, counted: refusing it outright sent
                # 3 of 125 papers to no pages at all (one unknown boundary
                # blanks a paper), and in all 3 the first hit agreed with the
                # printed page.
                whole = " ".join(a[k].replace("\f", "").split())
                wpos = dst.find(whole, max(lo, last), hi)
                if wpos != -1 and dst.find(whole, wpos + 1, hi) == -1:
                    pos = wpos
                else:
                    if first_ambiguous is None:
                        first_ambiguous = pos
                    continue
            if pos != -1:
                # Mid-line is right: a rejoined line puts the page's first
                # words after the previous page's last words on one line.
                found = pos
                break
        if found is None and first_ambiguous is not None:
            record_fallback("section_page_boundary_ambiguous")
            found = first_ambiguous
        out.append(found)
        if found is not None:
            last = found
    return out
