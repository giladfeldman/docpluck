"""PDF layout-aware heading-candidate annotator (Tier 1).

Heuristics (spec §5.1):
- Body font size = mode of all char font sizes weighted by char count.
- `strong` heading: font >= 1.15x body, OR bold + >= 1.05x body, AND <= 12 words,
  AND ends in line break, AND no terminal period (or has explicit numbering).
- `weak` heading: ALL CAPS or Title Case, <= 8 words, isolated line, body-size
  font.
- Numbered headings (^\\d+(\\.\\d+)*\\s+[A-Z]) -> strong regardless of font.
"""

from __future__ import annotations

import re
from collections import Counter

from ..blocks import BlockHint
from ...extract_layout import extract_pdf_layout, LayoutDoc, TextSpan


_NUMBERED_HEADING = re.compile(r"^\s*\d+(?:\.\d+)*\.?\s+[A-Z]")
_TERMINAL_PERIOD = re.compile(r"[.!?]\s*$")


def annotate_pdf(pdf_bytes: bytes) -> tuple[str, list[BlockHint]]:
    layout = extract_pdf_layout(pdf_bytes)
    return _annotate_layout(layout)


def _annotate_layout(layout: LayoutDoc) -> tuple[str, list[BlockHint]]:
    body_size = _body_font_size(layout)

    text = layout.raw_text
    hints: list[BlockHint] = []

    # Build a flat list of (text, char_start, char_end, page_index, span) for
    # every span. Map spans to char offsets in raw_text by linear scan within
    # each page.
    for page in layout.pages:
        page_start = layout.page_offsets[page.page_index]
        page_end = (
            layout.page_offsets[page.page_index + 1] - 1  # exclude the \f
            if page.page_index + 1 < len(layout.page_offsets)
            else len(text)
        )
        page_text = text[page_start:page_end]
        cursor = page_start
        for span in page.spans:
            # Find the span text within the page text starting from cursor.
            idx = page_text.find(span.text, cursor - page_start)
            if idx < 0:
                continue
            char_start = page_start + idx
            char_end = char_start + len(span.text)
            cursor = char_end
            hint = _classify_span(span, body_size, char_start, char_end)
            if hint is not None:
                hints.append(hint)

    hints.sort(key=lambda h: h.char_start)
    return text, hints


def _body_font_size(layout: LayoutDoc) -> float:
    counter: Counter[float] = Counter()
    for page in layout.pages:
        for span in page.spans:
            counter[round(span.font_size, 1)] += len(span.text)
    if not counter:
        return 11.0
    return max(counter.items(), key=lambda kv: kv[1])[0]


def _classify_span(
    span: TextSpan, body_size: float, char_start: int, char_end: int
) -> BlockHint | None:
    text = span.text.strip()
    if not text:
        return None
    word_count = len(text.split())

    is_numbered = bool(_NUMBERED_HEADING.match(text))
    has_terminal = bool(_TERMINAL_PERIOD.search(text))

    size_ratio = span.font_size / body_size if body_size > 0 else 1.0
    big_font = size_ratio >= 1.15
    bold_and_slightly_big = span.bold and size_ratio >= 1.05

    strong = (
        is_numbered
        or (big_font and word_count <= 12 and not has_terminal)
        or (bold_and_slightly_big and word_count <= 12 and not has_terminal)
    )
    if strong:
        return BlockHint(
            text=text,
            char_start=char_start,
            char_end=char_end,
            page=span.page_index + 1,
            is_heading_candidate=True,
            heading_strength="strong",
            heading_source="layout",
        )

    # Weak: ALL CAPS or Title Case, short, body-size font, no terminal period.
    is_all_caps = text == text.upper() and any(c.isalpha() for c in text)
    is_title_case = text == text.title()
    if (is_all_caps or is_title_case) and word_count <= 8 and not has_terminal:
        return BlockHint(
            text=text,
            char_start=char_start,
            char_end=char_end,
            page=span.page_index + 1,
            is_heading_candidate=True,
            heading_strength="weak",
            heading_source="layout",
        )

    return None
