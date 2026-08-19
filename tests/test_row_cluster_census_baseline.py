"""The row-cluster census must keep measuring the defect, and its two arms must differ.

`tools/diag/row_cluster_census.py` carries its own copy of the SHIPPED previous-word
rule plus the anchor-relative CANDIDATE, so it can report what the candidate would
buy. Both halves need pinning:

  * the SHIPPED copy must still exhibit the smear — a diagnostic whose baseline has
    quietly stopped reproducing the defect reports "0 smears" on a corpus full of
    them, the same false-clean this project met with the retired locale detector and
    with `repair_site_scan.py`'s zero over a corpus containing no known positive;
  * the two arms must remain DISTINCT — if someone "tidies" the tool by pointing both
    at one function, the before/after column becomes noise.

CORRECTED 2026-08-19. This file previously asserted that the census's copy differed
from `whitespace._cluster_into_rows`, on the assumption that the anchor rule had
shipped. It had not: the anchor rule regresses `efendic_2022_affect` by 11
sign-flipped B-coefficients and was reverted, so the census's `_cluster_prev_word`
now MATCHES the library. Asserting a difference there would have failed for the right
reason and told the wrong story. What matters is that the tool's own two arms differ.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.diag.row_cluster_census import (  # noqa: E402
    _cluster_anchor,
    _cluster_prev_word,
    _max_span,
)


def _w(top: float, x0: float = 0.0, height: float = 9.5) -> dict:
    return {"top": top, "bottom": top + height, "x0": x0, "x1": x0 + 20.0, "text": "x"}


# The reproduction from tests/test_whitespace_row_cluster_drift.py: 30 words, each
# a sub-threshold 5pt step below the last, spanning 145pt against an 11.4pt row
# threshold.
_CREEPING = [_w(50.0 + 5.0 * i, x0=float(i % 4) * 30.0) for i in range(30)]


def test_the_shipped_rule_still_chain_merges():
    """The census's "before" arm must still show the defect it measures."""
    rows = _cluster_prev_word(_CREEPING)
    assert len(rows) == 1, (
        f"the shipped previous-word rule produced {len(rows)} rows; it is supposed to "
        "chain-merge these 30 words into ONE. If this drifted, the census's before/after "
        "no longer measures anything."
    )
    assert _max_span(rows) > 100.0


def test_the_candidate_rule_does_not_chain_merge():
    """The "after" arm must differ from the "before" arm on the same input."""
    rows = _cluster_anchor(_CREEPING)
    assert len(rows) > 3
    assert _max_span(rows) <= 12.0


def test_the_two_arms_are_not_the_same_function():
    assert _cluster_prev_word is not _cluster_anchor
    assert len(_cluster_prev_word(_CREEPING)) != len(_cluster_anchor(_CREEPING))
