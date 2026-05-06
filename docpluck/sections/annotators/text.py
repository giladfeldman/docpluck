"""Text-only heading-candidate annotator (Tier 1 fallback / primary for v1.6.1 PDF path)."""

from __future__ import annotations

import re

from ..blocks import BlockHint
from ..taxonomy import HEADING_TO_LABEL, lookup_canonical_label

# Build alternation regex from all canonical heading variants, longest first.
_CANONICAL_VARIANTS = sorted(
    {v for variants in HEADING_TO_LABEL.keys() for v in variants},
    key=len,
    reverse=True,
)
_CANONICAL_ALT = "|".join(re.escape(v) for v in _CANONICAL_VARIANTS)

# Match canonical heading at the start of a paragraph-leading line.
# Allows body text on the same line (e.g., "Abstract Jordan et al., 2011...").
_CANONICAL_PARA_HEADING = re.compile(
    rf"(?im)"
    rf"^[ \t]*"
    rf"(?:\d+(?:\.\d+)*\.?[ \t]+)?"
    rf"(?P<heading>{_CANONICAL_ALT})"
    rf"\b",
)

# Existing line-isolated heading pattern (kept for non-canonical / subheading capture).
_HEADING_LINE = re.compile(
    r"""(?xm)
    ^
    [ \t]*
    (?:\#{1,6}[ \t]+)?
    (?:\d+(?:\.\d+)*\.?[ \t]+)?
    (?P<heading>
        [A-Z][A-Za-z &\-/]{0,80}
        |
        [A-Z][A-Z &\-/]{0,80}
        |
        (?:[A-Z][ \t]){2,30}[A-Z]
    )
    [ \t]*[:.]?[ \t]*
    $
    """,
)

_UNDERLINED_HEADING = re.compile(
    r"""(?xm)
    ^[ \t]*(?P<heading>[A-Z][A-Za-z &\-/]{0,80})[ \t]*\n
    [ \t]*[-=]{2,}[ \t]*$
    """,
)


def annotate_text(text: str) -> list[BlockHint]:
    """Scan `text` for heading candidates.

    Three passes:
      1. Canonical taxonomy headings at paragraph-leading line starts (may be
         followed by body text on the same line — handles publishers that
         collapse heading and first-paragraph onto one wrapped line).
      2. Underlined headings (`Heading\\n=====` style).
      3. General heading-line pattern (line-isolated, capitalized) — catches
         non-canonical headings that become `subheadings` in Tier 2.
    """
    hints: list[BlockHint] = []
    seen_offsets: set[int] = set()

    # Pass 1: canonical heading at paragraph-leading line start.
    for m in _CANONICAL_PARA_HEADING.finditer(text):
        start = m.start("heading")
        if start in seen_offsets:
            continue
        # Require Title Case or ALL CAPS to reject body-text "abstract" usages.
        heading_text = m.group("heading")
        if not (heading_text == heading_text.title() or heading_text == heading_text.upper()):
            continue
        # Require paragraph-break-like context: preceded by blank line OR start-of-doc.
        line_start = m.start()
        if line_start > 0:
            # Look backwards through optional whitespace for a blank line.
            i = line_start - 1
            while i > 0 and text[i] in " \t":
                i -= 1
            if text[i] != "\n":
                continue
            # Need at least one blank line: another \n preceded only by whitespace.
            j = i - 1
            while j > 0 and text[j] in " \t":
                j -= 1
            if text[j] != "\n" and j != 0:
                # Allow direct line-after-line for cases like consecutive headings,
                # but only if the prior line itself ended a heading. Safer: require
                # blank line. Reject this candidate.
                continue
        seen_offsets.add(start)
        hints.append(BlockHint(
            text=heading_text,
            char_start=start,
            char_end=start + len(heading_text),
            page=None,
            is_heading_candidate=True,
            heading_strength="strong",
            heading_source="text_pattern",
        ))

    # Pass 2: underlined headings.
    for m in _UNDERLINED_HEADING.finditer(text):
        start = m.start("heading")
        if start in seen_offsets:
            continue
        seen_offsets.add(start)
        hints.append(BlockHint(
            text=m.group("heading"),
            char_start=start,
            char_end=m.end("heading"),
            page=None,
            is_heading_candidate=True,
            heading_strength="strong",
            heading_source="text_pattern",
        ))

    # Pass 3: general heading-line pattern (existing logic, unchanged shape).
    for m in _HEADING_LINE.finditer(text):
        start = m.start("heading")
        if start in seen_offsets:
            continue
        line_start = m.start()
        before = text[max(0, line_start - 2):line_start]
        if before and not before.endswith("\n\n") and not before.endswith("\n"):
            continue
        heading = m.group("heading").strip()
        if len(heading) < 2:
            continue
        strength = "strong" if lookup_canonical_label(heading) is not None else "weak"
        seen_offsets.add(start)
        hints.append(BlockHint(
            text=heading,
            char_start=start,
            char_end=m.end("heading"),
            page=None,
            is_heading_candidate=True,
            heading_strength=strength,
            heading_source="text_pattern",
        ))

    hints.sort(key=lambda h: h.char_start)
    return hints
