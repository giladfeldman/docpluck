"""Regression test for the abstract-zone affiliation-remnant strip (v2.4.115).

chandrashekar_2023_mp rendered "Department of Philosophy, Lake Forest College" +
"*Joint first authors" right after the "## Abstract" heading, before the abstract
body. The masthead strip stops AT "## Abstract" (so it caught the other two
affiliations, which precede the heading), and the >=3-line body-affiliation strip
could not reach a single surviving affiliation line — the section partitioner had
inserted "## Abstract" mid-affiliation-block, orphaning the last one.

Fix (v2.4.115): `_strip_abstract_zone_affiliation_remnant` removes an affiliation
line (+ companion note) that is the FIRST non-blank content after "## Abstract".
A real Abstract opens with PROSE, so an affiliation LINE in that slot is
unambiguously a boundary-split front-matter remnant. An abstract that merely
MENTIONS a university mid-sentence is prose (not an affiliation line) and is kept.
"""

from __future__ import annotations

from pathlib import Path

import pytest

# Camelot is not needed by this module's tests; skipping it keeps them fast.
# Declarative on purpose: this was `os.environ.setdefault(...)` at module scope,
# which executes during COLLECTION and was never undone, so importing this file
# disabled Camelot for the WHOLE pytest process and every real-PDF table test
# collected afterwards found no tables. `conftest._camelot_disabled_per_module`
# reads this flag and restores the prior value when the module finishes.
DISABLE_CAMELOT = True

from docpluck.render import (
    _strip_abstract_zone_affiliation_remnant,
    render_pdf_to_markdown,
)

TEST_PDFS = Path(__file__).resolve().parents[1].parent / "PDFextractor" / "test-pdfs"


def test_chandrashekar_affiliation_not_in_abstract():
    pdf = TEST_PDFS / "apa" / "chandrashekar_2023_mp.pdf"
    if not pdf.exists():
        pytest.skip(f"fixture missing: {pdf}")
    md = render_pdf_to_markdown(pdf.read_bytes())
    lines = md.split("\n")
    ai = next((i for i, ln in enumerate(lines) if ln.strip() == "## Abstract"), None)
    assert ai is not None, "## Abstract heading missing"
    # ⚠️ THIS GUARD WAS PASSING BY ACCIDENT UNTIL 2026-08-22, and the window is
    # the reason. The affiliation remnant is emitted into the abstract zone
    # either way; what used to push it past a SIX-line window was the
    # page-number strip deleting the two bare affiliation markers (`2`, `3`)
    # sitting above it — a rule with nothing to do with abstracts, which was
    # also deleting published table cells (see
    # `tests/test_page_number_strip_never_deletes_data.py`) and no longer
    # removes anything but a pagination run.
    #
    # The window is widened to what the guard actually intends to assert: the
    # affiliation must not open the abstract. The remnant's presence FURTHER
    # down remains an open defect owned by the abstract-zone logic, registered
    # in `todo.md` — a positional window that any unrelated line deletion can
    # satisfy is not a guard, and pinning the accidental value would have
    # re-armed exactly that.
    zone = "\n".join(lines[ai:ai + 3])
    assert "Department of Philosophy, Lake Forest College" not in zone
    assert "*Joint first authors" not in zone
    # The abstract body prose is intact and is the first content after the heading.
    assert "People tend to stick with a default option" in md


def test_remnant_stripped_unit():
    text = (
        "## Abstract\n\n"
        "Department of Philosophy, Lake Forest College\n"
        "*Joint first authors\n"
        "People tend to stick with a default option instead of switching.\n\n"
        "## Keywords\n"
    )
    out = _strip_abstract_zone_affiliation_remnant(text)
    assert "Lake Forest College" not in out
    assert "Joint first authors" not in out
    assert "People tend to stick" in out
    assert "## Abstract" in out


def test_real_abstract_untouched():
    # Prose immediately after ## Abstract → nothing stripped.
    text = (
        "## Abstract\n\n"
        "We conducted three studies examining the effect of framing on choice.\n\n"
        "## Keywords\n"
    )
    assert _strip_abstract_zone_affiliation_remnant(text) == text


def test_abstract_that_mentions_a_university_untouched():
    # A university MENTION inside abstract prose is not an affiliation line.
    text = (
        "## Abstract\n\n"
        "Data were collected at the University of Hong Kong and analysed centrally.\n\n"
        "## Keywords\n"
    )
    out = _strip_abstract_zone_affiliation_remnant(text)
    assert out == text
    assert "Data were collected at the University of Hong Kong" in out
