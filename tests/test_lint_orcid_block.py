"""lint_rendered_corpus OR: an ORCID URL the paper prints under its own "ORCID"
label is back matter, not a leak.

WHY. Since 2.4.156 the render keeps the "ORCID iDs" back matter a paper prints
(10.1177/01461672251327169 p18: each author's name, an ORCID icon and the URL;
tests/test_back_matter_orcid_and_wrapped_heading_word.py). OR still flagged
every such URL, so /ship QA 2026-10-31 failed on five printed ORCID lines in four
papers, each a few lines under the paper's own "ORCID" / "ORCID iD" / "## ORCID
iDs" label. A URL with no such label above it is still flagged. Identifiers
below are placeholders.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import lint_rendered_corpus as lint  # noqa: E402

URL = "https://orcid.org/0000-0000-0000-0000"


def _or_hits(tmp_path: Path, md: str) -> list[int]:
    f = tmp_path / "x.md"
    f.write_text(md, encoding="utf-8")
    return [ln for ln, tag, *_ in lint.lint_file(f) if tag == "OR"]


def test_a_url_under_the_papers_orcid_label_is_not_flagged(tmp_path):
    for label in ("ORCID", "ORCID iD", "## ORCID iDs"):
        md = f"## Discussion\n\nText.\n\n{label}\nAuthor One\nAuthor Two\n\n{URL}\n{URL}\n"
        assert _or_hits(tmp_path, md) == [], label


def test_a_url_with_no_orcid_label_above_it_is_flagged(tmp_path):
    md = f"## Results\n\nParticipants completed the task.\n\n{URL}\n\nMore text.\n"
    assert _or_hits(tmp_path, md) == [5]


def test_a_new_section_ends_the_orcid_block(tmp_path):
    md = f"## ORCID iDs\n\nAuthor One\n\n## References\n\nSmith, J. (2020).\n\n{URL}\n"
    assert _or_hits(tmp_path, md) == [9]
