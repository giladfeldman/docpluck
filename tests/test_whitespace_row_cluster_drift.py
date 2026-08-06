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

A FIX WAS ATTEMPTED AND REVERTED (2026-08-04). Measuring the gap from the row's ANCHOR
instead of the previous word fixed the smear beautifully in isolation (chan_feldman T3
3→22 rows; T2 0→108 cells; T9 0→14 cells; maier T8/T11 gained cells) but **broke 9
real-PDF tests across 4 files**, because a real row can legitimately be TALL: xiao
Table 4's row 2 spans **94.4pt** as a multi-line stacked data block, and a hard anchor
cap shatters it. The previous-word test under-splits; a naive anchor cap over-splits.
Neither rule alone is correct — see
``an internal findings doc (2026-08-04)`` for the measured evidence and
three candidate directions.

The chain-merge test below is therefore ``xfail(strict)``: it pins a REAL, still-open
defect. **Do NOT "fix" it by loosening the assertion, and do not delete it** — when a
structurally-correct fix lands it will XPASS loudly and should become a plain assert
then. The three companion tests are plain asserts: they pin behaviour that must NOT
regress while the chain merge is being solved.
"""

from __future__ import annotations

import pytest

from docpluck.tables.whitespace import _cluster_into_rows


def _w(top: float, x0: float = 0.0, height: float = 9.5) -> dict:
    return {"top": top, "bottom": top + height, "x0": x0, "x1": x0 + 20.0, "text": "x"}


@pytest.mark.xfail(
    strict=True,
    reason=(
        "REAL, still-open defect (RC-T cycle 5). _cluster_into_rows measures the y-gap "
        "to the PREVIOUS WORD, so wrapped/staggered cells chain-merge an arbitrarily "
        "tall band into one row (chan_feldman T3: 266 words at 47 distinct y-positions "
        "-> 3 rows spanning 240pt, then truncated by the raw_text fallback). The "
        "anchor-relative fix was attempted and REVERTED: it broke 9 real-PDF tests "
        "because a real row can legitimately be tall (xiao T4 row 2 spans 94.4pt as a "
        "multi-line stacked block). Do NOT loosen this assertion to make it pass — see "
        "an internal findings doc (2026-08-04). strict=True: a correct "
        "fix XPASSes loudly; make it a plain assert then."
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
