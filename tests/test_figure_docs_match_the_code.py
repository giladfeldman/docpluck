"""The architecture tables must describe figures the way the code produces them.

WHY. `docpluck/figures/detect.py` -- a layout-channel figure detector that inferred a
bbox from nearby drawing primitives -- was on no production path from 2026-05-09 and
was deleted on 2026-09-25. Production builds every figure from its caption
(`extract_structured._figure_from_caption`) and emits `bbox == (0.0, 0.0, 0.0, 0.0)`,
meaning "not computed". Three hand-maintained architecture tables (CLAUDE.md,
LESSONS.md, docs/DESIGN.md) still listed figures as a layout-channel consumer with
"image bboxes"; two were corrected in the deleting commit and the third was found
only by the cleanup pass, because a grep for the module name cannot see a row that
names the DIRECTORY (`docpluck/figures/`). A reader of that row would believe figure
geometry is measured.

WHAT THIS PINS. While production emits the zero bbox, every table row that describes
the figures channel -- its first cell starts with "Figures", or it lists `figures/`
as a consumer -- must say the bbox is "not computed". The day a real bbox is wired,
`test_production_figure_bbox_is_the_uncomputed_placeholder` goes red and forces the
docs (and this test) to be revisited together.

CONTROL. `_figure_rows` must find at least one row per file, so a table that was
renamed or reformatted cannot turn this into a test that checks nothing.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from docpluck.extract_structured import _figure_from_caption
from docpluck.tables.captions import CaptionMatch

_REPO = Path(__file__).resolve().parents[1]
# LESSONS.md left this list on 2026-10-02: it became a table-free index (no
# architecture table left to check), so the control below failed on it by design.
_DOCS = ("CLAUDE.md", "docs/DESIGN.md")
# Maintainer file, untracked since 2.4.146: checked where it exists (the
# maintainer's checkout), skipped in a clean clone. docs/DESIGN.md must exist.
_LOCAL_ONLY = {"CLAUDE.md"}

_FIGURE_ROW = re.compile(r"^\|\s*(?:\*\*)?Figures\b|`figures/`", re.IGNORECASE)


def _figure_rows(rel: str) -> list[str]:
    text = (_REPO / rel).read_text(encoding="utf-8")
    return [
        line for line in text.splitlines()
        if line.lstrip().startswith("|") and _FIGURE_ROW.search(line)
    ] + [
        # A row that lists consumers of a channel and mentions figures there.
        line for line in text.splitlines()
        if line.lstrip().startswith("|")
        and not _FIGURE_ROW.search(line)
        and "extract_pdf_layout" in line
        and "figure" in line.lower()
    ]


def test_production_figure_bbox_is_the_uncomputed_placeholder():
    cap = CaptionMatch(
        kind="figure", number=1, label="Figure 1", page=3,
        char_start=0, char_end=9, line_text="Figure 1. A caption.",
    )
    fig = _figure_from_caption(cap, "Figure 1. A caption.\n\nBody text.")
    assert fig["bbox"] == (0.0, 0.0, 0.0, 0.0), (
        "production now emits a real figure bbox -- update the architecture tables in "
        f"{', '.join(_DOCS)} and this test together"
    )


@pytest.mark.parametrize("rel", _DOCS)
def test_every_figures_row_says_the_bbox_is_not_computed(rel):
    if rel in _LOCAL_ONLY and not (_REPO / rel).is_file():
        pytest.skip(f"{rel} is a maintainer file, not tracked in this repository")
    rows = _figure_rows(rel)
    assert rows, f"{rel}: found no architecture-table row describing figures -- the control failed"
    stale = [r for r in rows if "not computed" not in r.lower()]
    assert not stale, (
        f"{rel} describes the figures channel without saying bbox is not computed "
        "(production emits (0,0,0,0)):\n" + "\n".join(stale)
    )
