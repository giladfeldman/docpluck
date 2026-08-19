"""`Table["confidence"]` must account for how much of the capture is EMPTY.

## The defect (register F1, fixed v2.4.133)

Camelot exposes a purpose-built quality score
(``camelot/core.py``, ``Table.confidence``)::

    (accuracy / 100) * (1 - whitespace / 100)

with its own docstring recommending ``>= 0.8`` as a first-cut production
threshold. docpluck ignored it and recomputed a worse score **under the same
name** from accuracy alone, so a 95%-accurate but 80%-empty capture reported
``0.95`` where Camelot says ``0.19``. A sparse mis-capture — exactly what a
caption-anchored region overshoot produces — was indistinguishable from a clean
one, in a field consumers read.

This is the register's A-pattern: the fact we needed was already computed by
something we already call, and we discarded it and rebuilt it worse.

## Two decisions that are NOT obvious, both measured

**1. We apply Camelot's FORMULA to OUR grid, not Camelot's number.**
``ct.whitespace`` describes Camelot's raw grid, and by the time docpluck emits
cells it has run ``_strip_running_header_rows``, ``_drop_caption_first_row``,
``_trim_prose_tail`` (and on the region path ``_trim_trailing_prose_rows``).
Measured over 591 tables from 40 papers: docpluck's shipped grid is CLEANER
than Camelot's raw grid on 345 and dirtier on 47 (median whitespace
41.7% -> 35.9%). Adopting ``ct.confidence`` verbatim would score our output
using their pre-trim measurement.

**2. The ACCEPT GATE IS DELIBERATELY NOT RE-GATED on this number.**
Measured over 1,751 accepted tables from 78 papers across 60 publishers,
Camelot's suggested ``>= 0.8`` would reject **79%** of them; ``>= 0.5`` still
rejects 30%. Academic tables are legitimately sparse — a correlation matrix
leaves its upper triangle empty. Re-gating would delete real tables wholesale,
which is the "delete furniture, never data" failure. Whitespace is REPORTED,
never GATED.
"""

from __future__ import annotations

import pytest


class _FakeCamelotTable:
    def __init__(self, rows, accuracy: float = 95.0, whitespace: float = 0.0):
        import pandas as pd
        self.df = pd.DataFrame(rows)
        self.accuracy = accuracy
        self.whitespace = whitespace     # Camelot's RAW-grid figure
        self.page = 1
        self.flavor = "stream"
        self._bbox = (0.0, 0.0, 100.0, 100.0)


def _build(rows, **kw):
    from docpluck.tables.camelot_extract import _camelot_table_to_dict
    td = _camelot_table_to_dict(_FakeCamelotTable(rows, **kw), 0)
    assert td is not None, "fixture did not survive the table-likeness gate"
    return td


DENSE = [
    ["Predictor", "b", "SE", "p"],
    ["Intercept", "0.31", "0.05", "0.001"],
    ["Condition", "0.44", "0.07", "0.002"],
]

# Same shape, but three quarters of the data cells empty — a sparse capture.
SPARSE = [
    ["Predictor", "b", "SE", "p"],
    ["Intercept", "0.31", "", ""],
    ["Condition", "", "", ""],
]


def test_a_sparse_capture_scores_lower_than_a_dense_one():
    """The whole point. Before the fix BOTH reported accuracy/100 = 0.95."""
    dense = _build(DENSE, accuracy=95.0)
    sparse = _build(SPARSE, accuracy=95.0)
    assert sparse["confidence"] < dense["confidence"], (
        f"sparse={sparse['confidence']} dense={dense['confidence']} — "
        "confidence ignored emptiness, which is the defect"
    )


def test_confidence_is_camelots_formula_on_the_shipped_grid():
    td = _build(SPARSE, accuracy=95.0)
    filled = len(td["cells"])
    slots = td["n_rows"] * td["n_cols"]
    expected_ws = 100.0 * (1 - filled / slots)
    assert td["whitespace"] == pytest.approx(expected_ws)
    assert td["confidence"] == pytest.approx(
        (95.0 / 100.0) * (1 - expected_ws / 100.0)
    )


def test_confidence_ignores_camelots_pre_trim_whitespace():
    """`ct.whitespace` describes a grid docpluck then modifies, so it must not
    be the number we ship. A wildly wrong `ct.whitespace` changes nothing."""
    honest = _build(DENSE, accuracy=95.0, whitespace=0.0)
    lying = _build(DENSE, accuracy=95.0, whitespace=99.0)
    assert honest["confidence"] == pytest.approx(lying["confidence"])


def test_the_components_are_shipped_alongside_the_composite():
    """Shipping only the composite would repeat the original mistake in a new
    place: one number, and no way to tell which half moved."""
    td = _build(DENSE, accuracy=95.0)
    assert td["accuracy"] == pytest.approx(95.0)
    assert td["whitespace"] is not None
    assert 0.0 <= td["whitespace"] <= 100.0
    assert td["confidence"] == pytest.approx(
        (td["accuracy"] / 100.0) * (1 - td["whitespace"] / 100.0)
    )


def test_confidence_stays_in_unit_range_when_accuracy_exceeds_100():
    """Camelot's accuracy is occasionally >= 100 through floating-point drift;
    the clip predates this change and must survive it."""
    td = _build(DENSE, accuracy=100.7)
    assert 0.0 <= td["confidence"] <= 1.0


def test_a_sparse_table_is_still_ACCEPTED():
    """The gate is not re-gated on confidence. Measured: Camelot's suggested
    0.8 threshold would reject 79% of the 1,751 tables docpluck accepts today.
    A correlation matrix's empty upper triangle is not a mis-capture."""
    td = _build(SPARSE, accuracy=95.0)
    assert td["confidence"] < 0.8      # would fail Camelot's suggested gate
    assert td["cells"], "the table was dropped — a real table just went missing"


def test_the_engine_that_produced_the_table_is_recorded():
    """register F7e: `rendering` was hardcoded to "whitespace" for every
    Camelot table, so a lattice capture was indistinguishable from a stream
    one — an unlabelled engine substitution."""
    td = _build(DENSE)
    assert td["camelot_flavor"] == "stream"
    assert td["rendering"] == "whitespace"


def test_a_lattice_capture_finally_emits_the_declared_lattice_vocabulary():
    from docpluck.tables.camelot_extract import _camelot_table_to_dict
    ct = _FakeCamelotTable(DENSE)
    ct.flavor = "lattice"
    td = _camelot_table_to_dict(ct, 0)
    assert td["camelot_flavor"] == "lattice"
    assert td["rendering"] == "lattice"
