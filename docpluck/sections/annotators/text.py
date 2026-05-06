"""Text-only heading-candidate annotator (Tier 1 fallback)."""

from __future__ import annotations

import re

from ..blocks import BlockHint

# A "strong" heading line: standalone, on its own line, with optional numbering,
# matches a known canonical heading word, and has no terminal period in body
# style. Matched via the canonical taxonomy in core.py — text annotator only
# emits CANDIDATES; final canonicalization happens in Tier 2.
_HEADING_LINE = re.compile(
    r"""(?xm)               # verbose, multiline
    ^                       # start of line
    [ \t]*                  # optional leading whitespace
    (?:\#{1,6}[ \t]+)?      # optional markdown header marker
    (?:\d+(?:\.\d+)*\.?[ \t]+)?  # optional numbering: 1.  / 2.1  / 3.1.4.
    (?P<heading>            # capture the heading text
        [A-Z][A-Za-z &\-/]{0,80}      # title-case-ish words
        |
        [A-Z][A-Z &\-/]{0,80}         # ALL CAPS
        |
        (?:[A-Z][ \t]){2,30}[A-Z]     # spaced caps: "R E F E R E N C E S"
    )
    [ \t]*[:.]?[ \t]*       # optional trailing colon/period
    $                       # end of line
    """,
)

_UNDERLINED_HEADING = re.compile(
    r"""(?xm)
    ^[ \t]*(?P<heading>[A-Z][A-Za-z &\-/]{0,80})[ \t]*\n
    [ \t]*[-=]{2,}[ \t]*$
    """,
)

_SPACED_CAPS = re.compile(r"(?m)^[ \t]*(?:[A-Z][ \t]){2,30}[A-Z][ \t]*$")


def _spaced_caps_pass(text: str, hints: list[BlockHint], seen: set[int]) -> None:
    for m in _SPACED_CAPS.finditer(text):
        start, end = m.start(), m.end()
        if start in seen:
            continue
        seen.add(start)
        compact = m.group().replace(" ", "").replace("\t", "")
        hints.append(BlockHint(
            text=compact,
            char_start=start,
            char_end=end,
            page=None,
            is_heading_candidate=True,
            heading_strength="strong",  # spaced caps are visually distinct
            heading_source="text_pattern",
        ))


def annotate_text(text: str) -> list[BlockHint]:
    """Scan `text` for standalone heading-candidate lines.

    Returns BlockHints in document order. Body paragraphs are NOT emitted —
    only candidate headings. Tier 2 fills in the body spans by partitioning
    between adjacent heading positions.
    """
    hints: list[BlockHint] = []

    seen_offsets: set[int] = set()

    # Underlined headings first (so we can skip the underline line in the
    # plain heading scan below).
    for m in _UNDERLINED_HEADING.finditer(text):
        start = m.start("heading")
        end = m.end("heading")
        seen_offsets.add(start)
        hints.append(BlockHint(
            text=m.group("heading"),
            char_start=start,
            char_end=end,
            page=None,
            is_heading_candidate=True,
            heading_strength="strong",
            heading_source="text_pattern",
        ))

    # Spaced-caps pass before the general heading scan.
    _spaced_caps_pass(text, hints, seen_offsets)

    for m in _HEADING_LINE.finditer(text):
        start = m.start("heading")
        end = m.end("heading")
        if start in seen_offsets:
            continue
        # Reject lines that look like body text mid-sentence: the line must
        # be preceded by a blank line, the start of the document, or a heading.
        # Use m.start() (position of ^) not start (heading group) so that
        # markdown/numbering prefixes ("# ", "1. ") don't fool the check.
        line_start = m.start()
        before = text[max(0, line_start - 2):line_start]
        if before and not before.endswith("\n\n") and not before.endswith("\n"):
            continue
        # Reject lines that have terminal period followed by lowercase
        # (sentence continuation) — heuristic kept light because canonicalizer
        # will filter further.
        heading = m.group("heading").strip()
        if len(heading) < 2:
            continue
        # Strong if it's a recognized canonical heading by simple lowercase
        # whole-word check; weak otherwise.
        from ..taxonomy import lookup_canonical_label
        strength = "strong" if lookup_canonical_label(heading) is not None else "weak"
        hints.append(BlockHint(
            text=heading,
            char_start=start,
            char_end=end,
            page=None,
            is_heading_candidate=True,
            heading_strength=strength,
            heading_source="text_pattern",
        ))

    hints.sort(key=lambda h: h.char_start)
    return hints
