"""Regression test: a LATTICE table region must not be clipped to the caption's
width, so a table wider than its caption keeps every data column.

THE DEFECT (measured 2026-09-12, docpluck 2.4.142, canary TABLE class).
`10.1001/jamanetworkopen.2023.39337` Table 3 ("Dietary Intake and Physical
Activity") is printed with SEVEN columns — `Variable` plus TRE / CR / Control,
each at Baseline and 6 mo. docpluck rendered it with TWO: `Variable` and
`TRE Baseline`. Five of six data columns — and additionally the `Sodium, mg/d`
and `Physical activity, steps/d` values of the one surviving column — appeared
ZERO times in the whole 59 KB render. Not mis-parsed, not duplicated into the
body text: absent. A consumer parsing statistics out of this output has no way
to notice.

THE STRUCTURAL SIGNATURE — and it is general, not a property of this paper.
`_region_for_caption` builds its search band at the CAPTION's x-range, because
a caption's width is unrelated to its table's. `_detect_geometry` then asks
`_horizontal_rules_in` for the ruled lines in that band, and that filter
required a rule to be entirely CONTAINED in it::

    if x0 - 2 <= ln["x0"] and ln["x1"] <= x1 + 2 and top - 2 <= ln["top"] <= bottom + 2:

The caption "Table 3. Dietary Intake and Physical Activity" spans 141pt. Table
3's twenty real horizontal rules each span x=47.9→562.8 (515pt), so
`ln["x1"] <= x1 + 2` is `562.8 <= 191.1` — FALSE for every one of them. The
filter is blind to precisely the rules that establish the grid. What it does
keep is ten 10pt-wide row decorations at x=47.9→57.9, which is enough to clear
`LATTICE_MIN_HORIZONTAL_RULES` (2), so the lattice branch fires, and
`_union_of_primitives` over those decorations yields a region no wider than the
caption. Camelot is then handed a 141pt strip and correctly reports 2 columns.

The second half is that `_detect_geometry_widen_aware` SHORT-CIRCUITS on
lattice, on the stated premise that "lattice detection is unaffected by
widening (it keys on ruled lines, not the word scan)". That premise is false:
the rule FILTER is band-scoped, so lattice is affected by the band's width
exactly as the whitespace path is.

THE FIX keys on the invariant, never on this paper: a horizontal rule that
OVERLAPS the band's x-range is evidence of a grid the band is too narrow to
see, not evidence of no grid. Overlap is the safe test here because a ruled
line, unlike a word, does not cross a page's column gutter — so a left-column
table's rules still cannot pull in a right-column table's.

WHAT IS ASSERTED. Published values from the columns that were dropped must be
present in the rendered markdown. They are asserted against the rendered
document (the shipped `render_pdf_to_markdown` path a consumer actually reads),
not against the detector, so a fix that repairs the region but loses the values
again downstream still fails.

Ground truth is the printed page: page 9 of the PDF, rasterized and read
(`pdftoppm -png -r 150 -f 9 -l 9`), not another extractor's opinion.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from docpluck.render import render_pdf_to_markdown

_VIBE = Path(os.environ.get("VIBE_ROOT") or Path.home() / "Vibe")
_PDF = (
    _VIBE
    / "ArticleRepository"
    / "fulltext"
    / "10.1001__jamanetworkopen.2023.39337.pdf"
)

# From the printed page 9, Table 3. Each is a value docpluck dropped entirely.
# Chosen to span all three dropped groups and both dropped rows of the surviving
# column, so a partial recovery cannot pass this test.
_DROPPED_VALUES = {
    "1665 (468)": "TRE / 6 mo — Energy intake, kcal/d",
    "1707 (319)": "CR / Baseline — Energy intake, kcal/d",
    "1510 (358)": "CR / 6 mo — Energy intake, kcal/d",
    "1834 (354)": "Control / Baseline — Energy intake, kcal/d",
    "1818 (14)": "Control / 6 mo — Energy intake, kcal/d",
    "3602 (1233)": "TRE / Baseline — Sodium, mg/d (dropped from the SURVIVING column)",
    "5568 (2908)": "TRE / Baseline — Physical activity, steps/d (dropped from the SURVIVING column)",
    "5512 (2545)": "Control / 6 mo — Physical activity, steps/d",
}


@pytest.mark.skipif(not _PDF.is_file(), reason=f"corpus PDF not present: {_PDF}")
def test_table3_keeps_every_published_column() -> None:
    """Table 3's CR and Control columns must survive into the rendered output."""
    md = render_pdf_to_markdown(_PDF.read_bytes())

    missing = {v: where for v, where in _DROPPED_VALUES.items() if v not in md}
    assert not missing, (
        "published Table 3 values absent from the rendered document "
        f"({len(missing)}/{len(_DROPPED_VALUES)} missing):\n"
        + "\n".join(f"  {v!r}  — {where}" for v, where in sorted(missing.items()))
    )


@pytest.mark.skipif(not _PDF.is_file(), reason=f"corpus PDF not present: {_PDF}")
def test_table3_captures_every_column() -> None:
    """Table 3 must be captured with all seven of its printed columns.

    The mechanism-level companion to the test above: it fails at the point the
    data is lost rather than where the loss becomes visible, so a regression
    names its own cause. Asserted through `extract_pdf_structured`, the shipped
    path `render_pdf_to_markdown` itself calls.

    The two sibling tables are asserted alongside as a two-sided control: they
    were ALREADY correct (7 and 9 columns) before the fix, so if they change
    here the fix has over-widened rather than repaired, and that is a
    regression this test must catch rather than wave through.
    """
    from docpluck.extract_structured import extract_pdf_structured

    tables = extract_pdf_structured(_PDF.read_bytes())["tables"]
    by_page = {t["page"]: t for t in tables}
    assert set(by_page) >= {6, 8, 9}, (
        "expected the three captioned tables on pages 6/8/9 — the probe never "
        f"reached the table under test. Got pages {sorted(by_page)}"
    )

    assert by_page[9]["n_cols"] == 7, (
        f"Table 3 (page 9) captured with {by_page[9]['n_cols']} columns; the "
        "printed table has 7 (Variable + TRE/CR/Control x Baseline/6 mo). A "
        "count of 2 means the region was clipped to the caption's 141pt width "
        "and the full-width ruled lines were filtered out by the containment "
        "test in _horizontal_rules_in."
    )
    # Control: these two were never broken and must stay byte-identical in shape.
    assert by_page[6]["n_cols"] == 7, "Table 1 (page 6) regressed"
    assert by_page[8]["n_cols"] == 9, "Table 2 (page 8) regressed"
