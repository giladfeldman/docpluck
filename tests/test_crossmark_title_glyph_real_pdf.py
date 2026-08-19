"""Regression test for the Elsevier CrossMark "T" title-glyph artifact (v2.4.106).

The cycle-5 broad-read (2026-07-03) found multiple Elsevier / ScienceDirect
(JESP) papers rendering a stray uppercase "T" INSIDE the H1 title — e.g.
"Choosing persuasion targets: How expectations of qualitative change T increase
advocacy intentions" and "…the criminal justice T system". Diagnosis: the
CrossMark "Check for updates" widget renders as a lone "T"-shaped glyph in the
title y-band (often at the right edge, in a slightly smaller font), so the
layout-title assembler picks it up as a title word and merges it mid-run.

Fix (v2.4.106): `_compute_layout_title` drops a bare single-character "T" title
word. A real title never contains a standalone uppercase "T" as its own word, so
this is safe and general across Elsevier / ScienceDirect papers.
"""

from __future__ import annotations

import os

from pathlib import Path

import pytest

# Camelot is not needed by this module's tests; skipping it keeps them fast.
# Declarative on purpose: this was `os.environ.setdefault(...)` at module scope,
# which executes during COLLECTION and was never undone, so importing this file
# disabled Camelot for the WHOLE pytest process and every real-PDF table test
# collected afterwards found no tables. `conftest._camelot_disabled_per_module`
# reads this flag and restores the prior value when the module finishes.
DISABLE_CAMELOT = True

from docpluck.render import render_pdf_to_markdown

# Article-finder fulltext repository (the JESP CrossMark papers live here).
REPO = Path(os.environ.get("VIBE_ROOT") or Path.home() / "Vibe") / "ArticleRepository" / "fulltext"


def _title_of(md: str) -> str:
    for line in md.split("\n"):
        if line.startswith("# ") and not line.startswith("## "):
            return line
    return ""


@pytest.mark.parametrize(
    "pdf_name,expect_fragment",
    [
        ("10.1016__j.jesp.2019.103911.pdf", "qualitative change increase advocacy"),
        ("10.1016__j.jesp.2019.103913.pdf", "criminal justice system"),
    ],
)
def test_crossmark_t_not_in_title(pdf_name: str, expect_fragment: str):
    pdf = REPO / pdf_name
    if not pdf.exists():
        pytest.skip(f"fixture missing: {pdf}")
    md = render_pdf_to_markdown(pdf.read_bytes())
    title = _title_of(md)
    assert title, "no H1 title rendered"
    # The stray CrossMark "T" must be gone — the title words that flanked it now
    # join directly.
    assert " T " not in title, f"stray CrossMark 'T' still in title: {title!r}"
    assert not title.rstrip().endswith(" T"), f"trailing CrossMark 'T': {title!r}"
    assert expect_fragment in title, f"title lost real content: {title!r}"
