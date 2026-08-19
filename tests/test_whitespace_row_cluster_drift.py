"""Row-clustering drift in ``_cluster_into_rows`` (RC-T cycle 5, 2026-08-04).

``_cluster_into_rows`` started a new row when ``w.top - current[-1].top > threshold``
— the gap to the PREVIOUSLY ADDED WORD rather than to the row's anchor. Words are
sorted by ``(top, x0)``, so in a table whose cells wrap onto several physical lines
(or whose columns are vertically staggered) the running "previous top" creeps forward
in sub-threshold steps and the threshold is never crossed. The result is an unbounded
CHAIN MERGE: an arbitrarily tall band of text collapses into ONE row.

Measured on chan_feldman Table 3 (2026-08-04): the region holds 266 words at **47
distinct y-positions**, consecutive top-gaps of 0.3–7.4pt against an 11.4pt threshold
— and clustering emitted **3 rows** spanning top=52.5 to top=292.6. A 10-row table
became a 3-row smear, which then failed every downstream grid guard on its own
"merits" (prose-dominant, no clean data rows) and fell to the truncating raw_text
fallback.

FIXED v2.4.134 (2026-08-19): the gap is now measured from the row's ANCHOR, and that
alone is the fix. Measured over the 26-paper baseline with
``tools/diag/row_cluster_census.py``, the previous-word rule smeared **30 of 60
caption-anchored regions across 8 papers** — a systematic failure, not one paper's
quirk. The 2026-08-04 attempt was reverted because the anchor test can split a wrapped
cell away from its own row; on this corpus it does not, because a wrapped continuation
sits within one line pitch and the threshold already covers it.

A CONTINUATION RE-MERGE WAS BUILT FOR THAT RISK AND DELETED IN THE SAME RUN — it
chained, re-creating the chain merge through its own repair. The measurement and the
reason are in ``_cluster_into_rows``'s docstring; do not re-add one without a corpus
guard-diff showing ``tables that LOST cells: 0``.

THE REVERT'S PREMISE WAS FALSE, and that is the lesson worth keeping. The 2026-08-04
findings doc justified the revert with *"a real row can legitimately be TALL: xiao
Table 4's row 2 spans 94.4pt as a multi-line stacked data block"*. Re-measured
2026-08-19 with ``tools/diag/row_cluster_census.py``: that 94.4pt "row" is the ENTIRE
table body — the stacked header plus all five product rows plus all five CI
continuation lines, 75 words — and the grid was rejected on its own merits, so
``xiao`` Table 4 emitted ``cells=0``. The example held up as the legitimate case was
itself the defect. After the fix it is 7 rows / 35 cells, matching the published table.

The companion tests below pin the behaviour the anchor rule must not break: a genuine
single row stays one row, clearly separated bands split, clustering partitions its
input, and the shapes that killed the re-merge stay separate.
"""

from __future__ import annotations

import pytest

from docpluck.tables.whitespace import _cluster_into_rows


def _w(top: float, x0: float = 0.0, height: float = 9.5) -> dict:
    return {"top": top, "bottom": top + height, "x0": x0, "x1": x0 + 20.0, "text": "x"}


@pytest.mark.xfail(
    strict=True,
    reason=(
        "REAL, still-open defect. Measured 2026-08-19 with "
        "tools/diag/row_cluster_census.py: the previous-word rule smears 30 of 60 "
        "caption-anchored regions across 8 papers. The 2026-08-04 revert's premise "
        "was FALSE (xiao T4's '94.4pt legitimate row' is the whole table body, and "
        "that table emitted cells=0) - but the anchor-relative fix has its OWN "
        "measured blocker: it regresses efendic_2022_affect, shipping 11 published "
        "negative B-coefficients as positive numbers (21.09 for -1.09) because the "
        "grid it enables separates each estimate from the CI proving it negative. A "
        "sign-flipped coefficient outranks a missing grid. Three containments were "
        "tried and failed - see _cluster_into_rows' docstring. Do NOT loosen this "
        "assertion. strict=True: a correct fix XPASSes loudly."
    ),
)
def test_creeping_tops_do_not_chain_merge_into_one_row():
    """The regression: many words each a sub-threshold step above the last.

    With a 9.5pt median height the threshold is 11.4pt. Each successive word sits
    only 5pt below its predecessor, so the previous-word test never fires and all
    30 words chain into a single row spanning 145pt. Anchor-relative clustering
    must break them into many rows instead.
    """
    words = [_w(50.0 + 5.0 * i, x0=float(i % 4) * 30.0) for i in range(30)]
    rows = _cluster_into_rows(words)
    assert len(rows) > 3, (
        f"chain merge: {len(rows)} row(s) for words spanning "
        f"{words[-1]['top'] - words[0]['top']:.0f}pt"
    )
    # No single row may span more than roughly the row threshold.
    for row in rows:
        span = max(w["top"] for w in row) - min(w["top"] for w in row)
        assert span <= 12.0, f"row spans {span:.1f}pt — anchor test not applied"


def test_genuine_single_row_stays_one_row():
    """Words on one visual line (jitter well inside the threshold) stay together."""
    words = [_w(100.0 + (i % 3) * 0.4, x0=float(i) * 25.0) for i in range(8)]
    rows = _cluster_into_rows(words)
    assert len(rows) == 1, [[w["top"] for w in r] for r in rows]


def test_clearly_separated_rows_split():
    """Three bands separated by well over the threshold split into three rows."""
    words = (
        [_w(50.0, x0=float(i) * 25.0) for i in range(4)]
        + [_w(80.0, x0=float(i) * 25.0) for i in range(4)]
        + [_w(110.0, x0=float(i) * 25.0) for i in range(4)]
    )
    rows = _cluster_into_rows(words)
    assert len(rows) == 3, [[w["top"] for w in r] for r in rows]


def test_row_membership_is_preserved_not_dropped():
    """Clustering partitions: every input word appears exactly once."""
    words = [_w(50.0 + 5.0 * i, x0=float(i % 4) * 30.0) for i in range(30)]
    rows = _cluster_into_rows(words)
    assert sum(len(r) for r in rows) == len(words)


# --- what the anchor rule must and must not join (v2.4.134) -------------------
#
# A continuation re-merge was built here and REMOVED in the same run: it chained,
# re-creating the chain merge through its own repair (see `_cluster_into_rows`'s
# docstring for the jomf Table 6 measurement). These tests pin the behaviour the
# anchor rule delivers on its own, so a future attempt to re-add a re-merge has to
# keep them green.


def test_a_wrapped_continuation_within_one_pitch_stays_with_its_row():
    """`[0.094, 0.378] [0.000, 0.004]` belongs to the `Running shoes` row above it.

    Geometry taken from xiao_2021_crsp Table 4 p16: the data line sits at top=560,
    its CI continuation at top=568 — 8pt below, inside the 11.4pt row threshold, so
    the ANCHOR test keeps them together with no special continuation rule at all.
    This is the case that made the re-merge look unnecessary once it was measured.
    """
    data = [_w(560.0, x0=64.0), _w(560.0, x0=133.0), _w(560.0, x0=203.0)]
    cont = [_w(568.0, x0=190.6), _w(568.0, x0=299.0)]
    rows = _cluster_into_rows(data + cont)
    assert len(rows) == 1, [[w["x0"] for w in r] for r in rows]


def test_a_line_that_refills_the_label_column_starts_a_new_row():
    """`Microwaves 7.56 …` is a new record, not a continuation of `Running shoes`."""
    first = [_w(560.0, x0=64.0), _w(560.0, x0=133.0)]
    second = [_w(578.0, x0=64.0), _w(578.0, x0=133.0)]
    rows = _cluster_into_rows(first + second)
    assert len(rows) == 2


def test_a_creeping_band_below_a_row_is_split_off_it():
    """A creeping band is the chain merge itself — it must never rejoin the row above."""
    anchor = [_w(50.0, x0=0.0), _w(50.0, x0=30.0)]
    creeping = [_w(65.0, x0=60.0), _w(70.0, x0=90.0), _w(75.0, x0=120.0)]
    rows = _cluster_into_rows(anchor + creeping)
    assert len(rows) == 2, [[(w["top"], w["x0"]) for w in r] for r in rows]


def test_widely_spaced_indented_lines_stay_separate_rows():
    """20pt apart against an 11.4pt threshold: four rows, not one folded block.

    This is the shape that killed the re-merge — `10.1111/jomf.13036` Table 6's
    data rows are indented past the label column and would have folded into it.
    """
    words = [_w(100.0 + 20.0 * i, x0=200.0 + 10.0 * (i % 2)) for i in range(4)]
    rows = _cluster_into_rows(words)
    assert len(rows) == 4


@pytest.mark.xfail(
    strict=True,
    reason=(
        "Same open defect as the chain-merge reproduction above: xiao Table 4's grid "
        "is only recoverable under anchor-relative clustering, which does not ship "
        "because it costs efendic 11 sign recoveries. Kept, not deleted, because it "
        "is the gold-verified proof that the 2026-08-04 revert's counter-example was "
        "itself the defect. strict=True: XPASSes when clustering is fixed."
    ),
)
def test_xiao_table4_recovers_its_published_rows_real_pdf():
    """The real paper, end to end: 5 products + a stacked header + the caption.

    Before the fix this region clustered to 3 rows — the whole table body in one
    94.4pt smear — and `whitespace_cells` returned NOTHING (cells=0). The 2026-08-04
    findings doc recorded this same row as the *legitimately tall* case that
    justified reverting the anchor fix; it is the defect.
    """
    from pathlib import Path

    from docpluck.extract_layout import extract_pdf_layout
    from docpluck.tables.captions import find_caption_matches
    from docpluck.tables.detect import _region_for_caption
    from docpluck.tables.whitespace import whitespace_cells

    corpus = Path(__file__).resolve().parents[2] / "PDFextractor" / "test-pdfs" / "apa"
    pdf = corpus / "xiao_2021_crsp.pdf"
    if not pdf.exists():
        pytest.skip(f"corpus fixture missing: {pdf}")

    layout = extract_pdf_layout(pdf.read_bytes())
    cap = next(
        c for c in find_caption_matches(layout.raw_text, list(layout.page_offsets))
        if c.kind == "table" and c.label == "Table 4"
    )
    region = _region_for_caption(layout, cap)
    assert region is not None
    cells = whitespace_cells(layout, region=region)
    assert cells, "xiao Table 4 lost its whole grid again (was cells=0 before v2.4.134)"
    text = " ".join((c.get("text") or "") for c in cells)
    for product in ("Running shoes", "Microwaves", "Computers", "TVs", "Bicycles"):
        assert product in text, f"{product!r} row missing from the recovered grid"
