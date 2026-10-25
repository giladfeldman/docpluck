"""A Camelot patch that cannot be installed is RECORDED, never silent (review rule 40).

``camelot_cell_join._install`` and ``camelot_row_ties._install`` return False when
Camelot is absent or its internals have moved. Camelot then runs unmodified, which
changes the table text (glued values, a dropped row-boundary line), so the
fallback must reach ``fallback_scope`` -- otherwise the capability is gone while
every table test stays green.
"""
from __future__ import annotations

from docpluck.telemetry import fallback_scope
from docpluck.tables import camelot_cell_join, camelot_row_ties


def test_cell_join_unavailable_is_recorded(monkeypatch):
    monkeypatch.setattr(camelot_cell_join, "_install", lambda: False)
    ran = []
    with fallback_scope() as fb:
        with camelot_cell_join.cell_join_scope():
            ran.append(True)
    assert ran == [True]  # the block still runs, Camelot unmodified
    assert fb.counters.get(camelot_cell_join.UNAVAILABLE_EVENT) == 1


def test_row_tie_unavailable_is_recorded(monkeypatch):
    monkeypatch.setattr(camelot_row_ties, "_install", lambda: False)
    ran = []
    with fallback_scope() as fb:
        with camelot_row_ties.boundary_tie_scope():
            ran.append(True)
    assert ran == [True]
    assert fb.counters.get(camelot_row_ties.UNAVAILABLE_EVENT) == 1


def test_a_working_install_records_no_unavailable_event():
    """Healthy arm: with Camelot importable neither event fires."""
    import pytest

    pytest.importorskip("camelot")
    with fallback_scope() as fb:
        with camelot_cell_join.stream_read_scope():
            pass
    assert camelot_cell_join.UNAVAILABLE_EVENT not in fb.counters
    assert camelot_row_ties.UNAVAILABLE_EVENT not in fb.counters
