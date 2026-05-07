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

# Pattern A+B: canonical heading at line start — passes (a) Capital-letter body or
# (b) end-of-line disambiguator.  The preceded-by-blank check (c) is handled in
# annotate_text by inspecting the characters before the match start.
_CANONICAL_PARA_HEADING = re.compile(
    rf"(?im)"
    rf"^[ \t]*"
    rf"(?:\d+(?:\.\d+)*\.?[ \t]+)?"
    rf"(?P<heading>{_CANONICAL_ALT})"
    rf"\b",
)

# Pattern C: canonical heading preceded by a newline (single or blank line).
# Catches headings whose body starts with a lowercase word (e.g.
# "Keywords emotional pluralistic...") — these would fail the Capital-body
# disambiguator in Pattern A+B alone, AND fail the blank-line predecessor
# check when the gap is only one newline (common in PSPB-style PDFs where
# Keywords immediately follows the last sentence of the abstract).
# The Title-Case / ALL-CAPS post-filter prevents body-text false positives.
_CANONICAL_AFTER_BLANK = re.compile(
    rf"(?im)"
    rf"\n[ \t]*(?:\n[ \t]*)?"
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

# Case-sensitive match for a Capital letter immediately after whitespace.
# Used in Pass 1 to detect "Heading CapitalBodyWord" pattern.
_CAPITAL_WORD_AFTER = re.compile(r"[ \t]+[A-Z]")
# Matches end-of-line after the heading (optional trailing colon/period/space).
_END_OF_LINE = re.compile(r"[ \t]*[:.]?[ \t]*(?:\n|$)")


def _next_nonblank_line(text: str, after_pos: int) -> str | None:
    """Return the next non-blank line of text starting after `after_pos`,
    or None if no such line exists."""
    i = after_pos
    while i < len(text):
        # Skip blank lines (lines containing only whitespace).
        line_end = text.find("\n", i)
        if line_end < 0:
            line_end = len(text)
        line = text[i:line_end].strip()
        if line:
            return line
        i = line_end + 1
    return None


def _looks_like_table_cell(text: str, heading_end: int, heading_was_line_isolated: bool) -> bool:
    """A heading that was line-isolated and is followed by a tiny next line is
    likely a table row label (e.g., CRediT author-contribution table rows).

    Requires ALL of:
    1. The heading was line-isolated (not followed by a Capital body word on same line).
    2. The heading occupies its entire line — i.e., the text between `heading_end`
       and the next newline is blank (optional trailing colon/space only).
    3. There is a blank line immediately after the heading line.
    4. The first non-blank line after that blank line is tiny (< 20 chars).

    Condition 2 prevents false positives when a canonical heading word appears
    at the START of a long line (e.g. "Keywords emotional pluralistic ignorance...")
    — `heading_end` points mid-line there, not at end-of-line.
    Condition 3 prevents false positives when a heading is immediately followed
    by another heading or body text (e.g. "Introduction\\nBackground\\n").
    """
    if not heading_was_line_isolated:
        return False
    # Condition 2: heading must occupy the rest of its line.
    # Find the newline that ends the heading's line.
    line_end = text.find("\n", heading_end)
    if line_end < 0:
        return False  # No newline — end of text, not a table row.
    rest_of_line = text[heading_end:line_end].strip(" \t:.")
    if rest_of_line:
        # There is substantive text after the heading on the same line (e.g.
        # "Keywords emotional..." or "Methodology for data collection...").
        # This is NOT a table row label — it's a heading+body line.
        return False
    # Condition 3: the line immediately following the heading line must be blank.
    i = line_end + 1
    j = i
    while j < len(text) and text[j] in " \t":
        j += 1
    if j >= len(text) or text[j] != "\n":
        # Not blank — e.g. "Introduction\nBackground\n". Not a table cell.
        return False
    # Condition 4: first non-blank line after the blank separator is tiny.
    # Use a very conservative threshold (≤ 5 chars) to only catch genuine
    # single-character or very short table cells (e.g. "X", "✓", "Yes").
    # Real body text, even a short sentence fragment, is longer than this.
    next_line = _next_nonblank_line(text, i)
    if next_line is None:
        return False
    return len(next_line) <= 5


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

    # Pass 1a: canonical heading at line start — disambiguated by Capital-body (b)
    # or end-of-line (c), OR by a blank-line predecessor check (a) done inline.
    # "Funding acquisition" is rejected: no blank line before it (fails a),
    # "acquisition" is lowercase (fails b), and it's not at end-of-line (fails c).
    for m in _CANONICAL_PARA_HEADING.finditer(text):
        start = m.start("heading")
        if start in seen_offsets:
            continue
        heading_text = m.group("heading")
        # Reject body-text usages like "abstract concept" — require Title Case or ALL CAPS.
        if not (heading_text == heading_text.title() or heading_text == heading_text.upper()):
            continue

        line_start = m.start()
        heading_end = start + len(heading_text)
        after_heading = text[heading_end:]

        # (a) Preceded by blank line or at start-of-doc.
        preceded_by_blank = False
        if line_start == 0:
            preceded_by_blank = True
        else:
            i = line_start - 1
            while i > 0 and text[i] in " \t":
                i -= 1
            if text[i] == "\n":
                j = i - 1
                while j > 0 and text[j] in " \t":
                    j -= 1
                if text[j] == "\n" or j == 0:
                    preceded_by_blank = True

        # (b) Followed by a Capital-letter word on same line (case-sensitive).
        followed_by_capital = bool(_CAPITAL_WORD_AFTER.match(after_heading))

        # (c) At end-of-line (with optional trailing colon/period/space).
        at_end_of_line = bool(_END_OF_LINE.match(after_heading))

        if not (preceded_by_blank or followed_by_capital or at_end_of_line):
            continue

        # Table-cell filter: if the heading was line-isolated (not followed by a
        # Capital body word on the same line) and the next non-blank line is < 20
        # chars, this is likely a CRediT table row label, not a real heading.
        # Add to seen_offsets even on rejection so Pass 3 doesn't re-emit it.
        is_line_isolated = not followed_by_capital
        if _looks_like_table_cell(text, m.end(), is_line_isolated):
            seen_offsets.add(start)
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

    # Pass 1b: canonical heading preceded by a newline (Pattern C).
    # Catches headings whose body starts with a lowercase word — e.g.
    # "Keywords emotional pluralistic ignorance..." — where pass 1a's
    # Capital-body and end-of-line disambiguators both fail.  Matches
    # single-newline separation (common in PSPB PDFs: abstract body → Keywords
    # on next line) as well as blank-line separation.  seen_offsets deduplicates.
    for m in _CANONICAL_AFTER_BLANK.finditer(text):
        start = m.start("heading")
        if start in seen_offsets:
            continue
        heading_text = m.group("heading")
        if not (heading_text == heading_text.title() or heading_text == heading_text.upper()):
            continue
        # Pass 1b only catches blank-line-preceded headings, which means the
        # heading might be followed by either body or another tiny line.
        # Apply the table-cell filter here too — if next line is < 20 chars, reject.
        # For pass 1b, "is_line_isolated" is effectively True because the regex
        # didn't constrain what follows.
        # Add to seen_offsets even on rejection so Pass 3 doesn't re-emit it.
        if _looks_like_table_cell(text, m.end(), True):
            seen_offsets.add(start)
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

    # Pass 3: general heading-line pattern.
    # For canonical headings: accept if preceded by at least one newline.
    # For non-canonical (weak) headings that will become subheadings: require
    # ISOLATION (blank line before AND blank line after) so that table rows and
    # body-text sentences are filtered out. Also require ≥ 5 chars + ≥ 2 words,
    # and reject lines that end with a sentence-terminal period (heading lines
    # don't end with periods; body sentences do).
    for m in _HEADING_LINE.finditer(text):
        start = m.start("heading")
        if start in seen_offsets:
            continue
        line_start = m.start()
        line_end = m.end()
        heading = m.group("heading").strip()
        if len(heading) < 2:
            continue
        is_canonical = lookup_canonical_label(heading) is not None
        strength = "strong" if is_canonical else "weak"

        if is_canonical:
            # Canonical headings: just need a preceding newline (same as before).
            before = text[max(0, line_start - 2):line_start]
            if before and not before.endswith("\n\n") and not before.endswith("\n"):
                continue
        else:
            # Non-canonical (weak) headings: require full isolation + quality filters.
            # (1) ≥ 5 chars AND ≥ 2 words.
            if len(heading) < 5 or len(heading.split()) < 2:
                continue
            # (2) Reject lines that end with a period — those are body sentences.
            raw_line = text[line_start:line_end].rstrip()
            if raw_line.endswith("."):
                continue
            # (3) Require blank line BEFORE the heading line.
            before4 = text[max(0, line_start - 4):line_start]
            blank_before = (
                line_start == 0
                or "\n\n" in before4
                or before4.endswith("\n\n")
            )
            if not blank_before:
                continue
            # (4) Require blank line AFTER the heading line.
            after4 = text[line_end:min(len(text), line_end + 4)]
            blank_after = (
                line_end == len(text)
                or "\n\n" in after4
                or after4.startswith("\n\n")
            )
            if not blank_after:
                continue

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
