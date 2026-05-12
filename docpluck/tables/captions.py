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
]
