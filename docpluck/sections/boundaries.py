"""End-of-section boundary patterns.

Lifted and consolidated from CitationGuard's `endPatterns`
(apps/worker/src/processors/referenceParser.ts ~lines 825-858).
These close a section ONLY when no canonical heading is found before
the next boundary. Primary boundary signal = next strong heading.
"""

from __future__ import annotations

import re

# Each pattern is anchored at the START of a line (the input is a single
# line trimmed). Line-by-line evaluation in the partitioner.
BOUNDARY_PATTERNS: tuple[re.Pattern[str], ...] = (
    # Figure / table captions
    re.compile(r"^(Figure|Table|Fig\.|Tab\.)\s+\d+", re.IGNORECASE),

    # Author bio variants
    re.compile(r"^[A-Z]{2,}(?:\s+[A-Z]\.?)*(?:\s+[A-Z]{2,})*\s+(?:is|was|has|holds)\s"),
    re.compile(
        r"^[A-ZÀ-Ÿ][a-zà-ÿā-ž'-]+(?:\s+[A-ZÀ-Ÿ]\.?)+\s*\([^)]*@[^)]*\)\s+(?:is|was|has|holds)"
    ),
    re.compile(
        r"^[A-ZÀ-Ÿ][a-zà-ÿā-ž'-]+(?:\s+[A-ZÀ-Ÿ]\.?\s*)*"
        r"(?:\s+[A-ZÀ-Ÿ][a-zà-ÿā-ž'-]+)?\s+(?:PhD|Ph\.D|MD|MPH|MSc|MSW|DrPH|RN|FRCPC|FRCP)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"^[A-ZÀ-Ÿ][a-zà-ÿā-ž'-]+(?:\s+[A-ZÀ-Ÿ]\.?\s*)*"
        r"(?:\s+[A-ZÀ-Ÿ][a-zà-ÿā-ž'-]+)*\s+is\s+(?:at|with|in)\s+"
        r"(?:the\s+)?(?:Department|School|Faculty|College|Division|Institute|Center|Centre)\b",
        re.IGNORECASE,
    ),

    # Corresponding author / contact metadata
    re.compile(r"^Corresponding\s+author\b", re.IGNORECASE),
    re.compile(r"^(?:Address|E-?mail|Tel|Fax|Contact)\s*:", re.IGNORECASE),
    re.compile(r"^ORCID\s*:", re.IGNORECASE),

    # Editorial metadata — high-discrimination terms: colon optional
    re.compile(r"^(?:Accepted by|Action Editor|Handling Editor)\s*:?\s", re.IGNORECASE),
    # Editorial metadata — lower-discrimination terms: colon required to avoid false positives
    re.compile(r"^(?:Received|Revised|Published)\s*:\s", re.IGNORECASE),
)


def is_section_boundary(line: str) -> bool:
    """Return True if `line` looks like an end-of-section boundary marker."""
    trimmed = line.strip()
    if not trimmed:
        return False
    return any(pat.match(trimmed) for pat in BOUNDARY_PATTERNS)
