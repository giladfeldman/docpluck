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
            return starts_b[j] + min(offset - starts_a[li], len(b[j]))
        j = ~j
        return starts_b[j] if j < len(starts_b) else len(dst)

    return mapped
