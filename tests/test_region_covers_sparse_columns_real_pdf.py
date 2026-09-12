"""Regression test: a table region must cover columns that are populated in only
the header and a summary row, not just the modal body row.

THE DEFECT (measured 2026-09-12, docpluck 2.4.142, canary TABLE class).
`10.1371/journal.pmed.1004323` Table 3 ("Anesthetic complications", page 10) is
printed with FIVE columns::

    Anesthetic complications | PSA N = 106 | GA N = 101 | Rel. risk (95% CI) | P value

docpluck captured THREE. The two lost columns carry the paper's effect size and
its test — `1.19 (0.33-4.31)` and `1.00` — which is the pair a meta-analysis
would consume. The same happens to Table 4, losing `0.79 (0.32-1.92)` and
`0.60`.

THE STRUCTURAL SIGNATURE — general, not a property of this paper.
`_detect_geometry` locates the grid as the longest contiguous run of rows with
the SAME word count and aligned column edges (`_longest_aligned_run`, which
requires rows of exactly ``width`` words). In a table whose right-hand columns
are populated on only the header and one summary row — the ordinary shape of a
medical or psychological results table, where the relative risk and its p-value
are stated once for the outcome and left blank on each breakdown row — the modal
body shape has FEWER columns than the table does. Measured on page 10 by binning
words into rows::

    y= 96  5 words  x 36.0 -> 574.0   Anesthetic complications PSA GA Rel.risk(95%CI) Pvalue
    y=117  5 words  x 36.0 -> 573.1   ...needing intervention 5(4.7%) 4(4.0%) 1.19(0.33-4.31) 1
    y=144  3 words  x 43.4 -> 394.2   desaturation 3/5(60.0%) 1/4(25.0%)
    ... 10 more rows, all 3 words, all ending at x=394.2

The run locks onto the eleven 3-word rows, so the region's x-range stops at
394.2 and the region — and therefore Camelot, and therefore the table — never
sees the two right-hand columns. The header row is the authoritative statement
of a table's column extent precisely because it is the one row guaranteed to
span every column; the modal body row is not.

THE FIX widens the located region's x-range to cover the word-rows inside its
y-range that share its LEFT edge. Sharing the left edge is what keeps this safe
on a genuine two-column page: the neighbouring text column starts far to the
right of this region's left edge, so it cannot be pulled in — which is the
`ieee_access_7` Table 3 regression that blocks a blanket widen. The widening is
applied ONLY when a grid was actually located (`whitespace` / `lattice`), never
to the `caption_only` fallback, where no grid was found, the band is a guess,
and widening is the documented `cog_emo` Table 8/9 regression (8 columns
collapsed to 2).

WHAT IS ASSERTED. The effect sizes must reach the STRUCTURED table, asserted
through `extract_pdf_structured` — the shipped path `render_pdf_to_markdown`
calls. Asserting against the rendered markdown would not do: these values also
appear in the body prose, so a whole-document substring check passes while the
table is still wrong.

Ground truth is the printed page: page 10 of the PDF, rasterized and read
(`pdftoppm -png -r 130 -f 10 -l 10`).
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

_VIBE = Path(os.environ.get("VIBE_ROOT") or Path.home() / "Vibe")
_PDF = _VIBE / "ArticleRepository" / "fulltext" / "10.1371__journal.pmed.1004323.pdf"


def _cells_text(table) -> str:
    return "\n".join(c["text"] for c in table["cells"])


@pytest.mark.skipif(not _PDF.is_file(), reason=f"corpus PDF not present: {_PDF}")
def test_page10_tables_keep_their_effect_size_columns() -> None:
    from docpluck.extract_structured import extract_pdf_structured

    tables = extract_pdf_structured(_PDF.read_bytes())["tables"]
    by_label = {t.get("label"): t for t in tables}
    assert {"Table 3", "Table 4"} <= set(by_label), (
        "Tables 3 and 4 were not both captured — the probe never reached the "
        f"tables under test. Got {sorted(k for k in by_label if k)}"
    )

    t3, t4 = by_label["Table 3"], by_label["Table 4"]

    # Column count first: it names the cause when this fails.
    assert t3["n_cols"] == 5, (
        f"Table 3 captured with {t3['n_cols']} columns; the printed table has 5 "
        "(label + PSA + GA + Rel. risk (95% CI) + P value). A count of 3 means "
        "the region stopped at the modal 3-word body run (x=394.2) and never "
        "covered the two right-hand columns, which are populated only on the "
        "header and the single summary row."
    )
    assert t4["n_cols"] == 5, (
        f"Table 4 captured with {t4['n_cols']} columns; the printed table has 5."
    )

    # Then the values themselves, so a region fixed but a value lost still fails.
    t3_text = _cells_text(t3)
    for needle in ("1.19", "0.33"):
        assert needle in t3_text, (
            f"Table 3 relative risk component {needle!r} absent from the "
            "structured table; the page prints 'Rel. risk (95% CI) 1.19 (0.33-4.31)'"
        )
    t4_text = _cells_text(t4)
    for needle in ("0.79", "0.32"):
        assert needle in t4_text, (
            f"Table 4 relative risk component {needle!r} absent from the "
            "structured table; the page prints 'Rel. risk (95% CI) 0.79 (0.32-1.92)'"
        )


@pytest.mark.skipif(not _PDF.is_file(), reason=f"corpus PDF not present: {_PDF}")
def test_table4_is_surgical_reinterventions_not_a_copy_of_table3() -> None:
    """Table 4's grid must hold its OWN data.

    Measured before the fix: Table 4 carried the caption "Surgical
    reinterventions." above Table 3's *Anesthetic complications* grid, so the
    six surgical-reintervention rows reached no structured table at all while
    the block looked complete. A caption over the wrong grid is worse than an
    empty one: nothing signals that the numbers belong to a different table.
    """
    from docpluck.extract_structured import extract_pdf_structured

    tables = extract_pdf_structured(_PDF.read_bytes())["tables"]
    by_label = {t.get("label"): t for t in tables}
    t4 = by_label.get("Table 4")
    assert t4 is not None, "Table 4 not captured"
    text = _cells_text(t4)

    assert "desaturation" not in text.lower(), (
        "Table 4 contains Table 3's 'desaturation' row — its caption "
        "('Surgical reinterventions.') sits above the anesthetic-complications "
        "grid, so the surgical-reintervention data reaches no structured table."
    )
    for row in ("Hysterectomy", "Endometrial ablation", "Laparoscopic myomectomy"):
        assert row.lower() in text.lower(), (
            f"Table 4 is missing its printed row {row!r}"
        )


@pytest.mark.skipif(not _PDF.is_file(), reason=f"corpus PDF not present: {_PDF}")
def test_table3_keeps_its_last_two_rows() -> None:
    """Table 3's `fenylefrine` and `ephedrine` rows must survive.

    These were nearly lost. Before the region work they appeared in the
    document ONLY inside Table 4's accidental copy of Table 3's grid; once
    Table 4 correctly carried its own data, the copy went with it and both rows
    vanished from the render entirely — a net data loss caused by a fix, which
    is the failure mode a fix must never introduce.

    The cause is separate and older: the aligned-row run compared only column
    START edges, and these two rows print bare counts (`0`, `3`) where the rows
    above print `3/5 (60.0%)`, so their right-aligned cells begin ~29pt further
    right and the run — and with it the region's bottom edge — stopped one row
    early. Their END edges were identical to the rest of the column all along.

    Asserted on the whole rendered document, not just the table: the point is
    that the values exist ANYWHERE for a consumer to find.
    """
    from docpluck.render import render_pdf_to_markdown

    md = render_pdf_to_markdown(_PDF.read_bytes())
    for token in ("fenylefrine", "ephedrine"):
        assert token in md, (
            f"{token!r} is absent from the rendered document; page 10 prints it "
            "as the second-to-last / last row of Table 3"
        )
