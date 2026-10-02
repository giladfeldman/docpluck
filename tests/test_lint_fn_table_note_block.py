"""lint_rendered_corpus FN: a table's own numbered note is not a leaked footnote.

WHY. FN ("inline footnote leaked into prose") flagged 10.1017/s1930297500009189
p469 Table 13 note 2 every release since at least 2.4.126. On the page that note
is printed directly under the table, after its significance legend and "Note:"
line, and matches the superscript on a column header; the render puts it in the
same place (read 2026-10-02, confirmed by a second model). In the 2.4.126 render
the same note was detached from the table (after a download footer) -- a real
misplacement, and FN still fires on it. Strings below are neutral: no paper text
lives in this repo.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import lint_rendered_corpus as lint  # noqa: E402


def _fn_hits(tmp_path: Path, md: str) -> list[int]:
    f = tmp_path / "x.md"
    f.write_text(md, encoding="utf-8")
    return [ln for ln, tag, *_ in lint.lint_file(f) if tag == "FN"]


@pytest.mark.parametrize("legend", ["Note: Values are means.", "*p<.05, **p<.01.", "∗∗∗ p<.001.", "Notes. Values are means."])
def test_a_numbered_note_inside_a_table_note_block_is_not_flagged(tmp_path, legend):
    md = f"<table></table>\n\n{legend}\n1 Values above the midpoint reflect alpha.\n2 See Table 4 in the supplement for the tests.\n\n## Next"
    assert _fn_hits(tmp_path, md) == []


def test_the_same_note_detached_from_its_table_is_still_flagged(tmp_path):
    md = "Body prose ends here.\n\nDownloaded from a site.\n2 See Table 4 in the supplement for the tests.\n\n## Next"
    assert _fn_hits(tmp_path, md) == [4]


def test_a_blank_line_ends_the_table_note_block(tmp_path):
    md = "Note: Values are means.\n\n4 Note that the results remained the same without the controls.\n"
    assert _fn_hits(tmp_path, md) == [3]
