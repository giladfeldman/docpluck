"""
Caption-regex pre-scan for tables and figures.

Returns the set of pages that contain at least one Table N or Figure N
caption — used by extract_pdf_structured() in default mode to skip
pdfplumber on caption-free pages (~5x speedup vs. thorough mode).

See spec §5.1 for the regex shape rationale.
"""

from __future__ import annotations

import bisect
import re
from dataclasses import dataclass
from typing import Literal


# v2.3.0: explicit Title-case + ALL-CAPS variants for the caption label.
# AOM-style and some IEEE PDFs print captions as "TABLE 13. ..." /
# "FIGURE 4. ..."; we now match both Title-case ("Table") and ALL-CAPS
# ("TABLE"). The trailing look-ahead ``(?:[.:]|\s+[A-Z])`` stays
# case-sensitive — it must see a literal Capital after the number so
# body references like "Table 13 below shows" don't false-match.
# (A bare ``re.IGNORECASE`` flag would defeat the trailing guard.)
TABLE_CAPTION_RE = re.compile(
    r"^\s*(?:Table|TABLE)\s+(?P<num>\d+)(?:[.:]|\s+[A-Z])",
    re.MULTILINE,
)

FIGURE_CAPTION_RE = re.compile(
    r"^\s*(?:Figure|Fig\.?|FIGURE|FIG\.?)\s+(?P<num>\d+)(?:[.:]|\s+[A-Z])",
    re.MULTILINE,
)


CaptionKind = Literal["table", "figure"]


@dataclass(frozen=True)
class CaptionMatch:
    kind: CaptionKind
    number: int
    label: str
    page: int
    char_start: int
    char_end: int
    line_text: str


def find_caption_matches(
    raw_text: str,
    page_offsets: list[int],
) -> list[CaptionMatch]:
    """Find all Table N / Figure N caption lines in raw_text.

    Args:
        raw_text: Linear extracted text (output of extract_pdf()).
        page_offsets: list[int] where page_offsets[i] is the char index
            where page i+1 starts in raw_text. Length = page_count.

    Returns:
        List of CaptionMatch in document order. Page is 1-indexed.
    """
    matches: list[CaptionMatch] = []

    for kind, regex in [("table", TABLE_CAPTION_RE), ("figure", FIGURE_CAPTION_RE)]:
        for m in regex.finditer(raw_text):
            num = int(m.group("num"))
            label_word = "Table" if kind == "table" else "Figure"
            label = f"{label_word} {num}"
            char_start = m.start()
            line_text = _line_at(raw_text, char_start)
            char_end = char_start + len(line_text)
            page = _page_for_offset(char_start, page_offsets)
            matches.append(CaptionMatch(
                kind=kind,
                number=num,
                label=label,
                page=page,
                char_start=char_start,
                char_end=char_end,
                line_text=line_text,
            ))

    matches.sort(key=lambda m: m.char_start)
    return matches


def caption_anchor_is_in_text_reference(raw_text: str, cap: CaptionMatch) -> bool:
    """True if a caption-regex match is actually a body-text *reference*
    to a figure/table (``… as summarised in Figure 10.``) rather than a
    real caption line.

    pdftotext line-wraps body prose, so a sentence like ``We summarised
    the effects in Figure 10.`` can place ``Figure 10.`` at the start of
    a line — where :data:`FIGURE_CAPTION_RE`'s ``^`` anchor matches it. A
    real caption is set off by a paragraph break (blank line) or starts a
    fresh sentence; an in-text reference *continues* the previous line's
    sentence, so that line ends mid-clause (a lowercase word, a comma).

    Used only as a dedup TIE-BREAKER (FIG-3b): when two anchors share a
    ``(kind, number)``, the non-reference one is the real caption.
    Deliberately conservative — returns ``False`` (treat as a real
    caption) whenever the preceding context is not unambiguously
    mid-sentence, so a figure/table is never dropped when its only
    anchor is uncertain.
    """
    # FIGURE_CAPTION_RE / TABLE_CAPTION_RE begin ``^\s*`` and the ``\s*``
    # can absorb blank lines, so ``cap.char_start`` may sit one or more
    # lines ABOVE the real "Figure N" / "Table N" token. Advance to the
    # token before inspecting the surrounding line structure.
    n = len(raw_text)
    tok = cap.char_start
    while tok < n and raw_text[tok] in " \t\r\n":
        tok += 1
    if tok >= n:
        return False
    line_start = raw_text.rfind("\n", 0, tok) + 1
    if line_start == 0:
        return False  # caption token on the first line — a real caption
    prev_nl = line_start - 1  # the '\n' ending the previous line
    if prev_nl == 0 or raw_text[prev_nl - 1] == "\n":
        return False  # blank line precedes the caption — paragraph break
    prev_line_start = raw_text.rfind("\n", 0, prev_nl) + 1
    prev_line = raw_text[prev_line_start:prev_nl].rstrip()
    if not prev_line:
        return False
    last = prev_line[-1]
    # Previous line ends a sentence → the caption starts a new one.
    if last in ".!?":
        return False
    if (
        last in "\"')]’”"
        and len(prev_line) >= 2
        and prev_line[-2] in ".!?"
    ):
        return False
    # Previous line ends mid-clause (a lowercase word, or a comma /
    # semicolon) → the sentence continues into the "Figure N" token,
    # so this anchor is an in-text reference, not a caption.
    return last.islower() or last in ",;"


def _line_at(text: str, offset: int) -> str:
    """Return the full line in text containing offset (without trailing newline)."""
    line_start = text.rfind("\n", 0, offset) + 1
    line_end = text.find("\n", offset)
    if line_end == -1:
        line_end = len(text)
    return text[line_start:line_end]


def _page_for_offset(offset: int, page_offsets: list[int]) -> int:
    """1-indexed page number for a char offset."""
    if not page_offsets:
        return 1
    idx = bisect.bisect_right(page_offsets, offset) - 1
    return max(idx + 1, 1)


__all__ = [
    "TABLE_CAPTION_RE",
    "FIGURE_CAPTION_RE",
    "CaptionMatch",
    "CaptionKind",
    "find_caption_matches",
    "caption_anchor_is_in_text_reference",
]
