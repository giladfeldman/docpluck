"""No public doc may describe the retired U+FFFD pdfplumber recovery as live.

2.4.145 retired the recovery that swapped pdftotext's text for pdfplumber's
when U+FFFD appeared (it could substitute a plausible wrong token). The release
cleanup still found two public docs naming it as pdfplumber's current purpose:
the dependency table in docs/DESIGN.md and an artifact row in
docs/BENCHMARKS.md. A reader of either would believe the library still repairs
those glyphs. Every line that names the mechanism must also say it is retired.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PUBLIC_DOCS = sorted((REPO / "docs").glob("*.md"))
MECHANISM = re.compile(
    r"pdfplumber[ _]recovery|pdfplumber_word_patch|SMP Unicode recovery", re.IGNORECASE
)


def _live_mentions(text: str) -> list[str]:
    return [
        line.strip()
        for line in text.splitlines()
        if MECHANISM.search(line) and "retire" not in line.lower()
    ]


def test_the_public_docs_exist():
    assert any(p.name == "DESIGN.md" for p in PUBLIC_DOCS), PUBLIC_DOCS


def test_no_public_doc_describes_the_recovery_as_live():
    offenders = {
        p.name: hits for p in PUBLIC_DOCS if (hits := _live_mentions(p.read_text(encoding="utf-8")))
    }
    assert not offenders, offenders


def test_the_detector_fires_on_the_pre_fix_wording():
    # The exact dependency-table row the release cleanup corrected.
    assert _live_mentions("| pdfplumber | MIT | PDF SMP Unicode recovery |")
    assert not _live_mentions("| pdfplumber | MIT | layout channel. (SMP Unicode recovery retired 2026-09-24.) |")
