"""Tier-2 (v2.4.94): cross-flavor lattice-augmentation unit tests.

`_augment_lattice_with_stream_rows` recovers rows a lattice extraction
vertically TRUNCATED by appending the rows a same-page, same-column-count
stream table captured below the lattice bbox. Grounded in PROSECCO Table 2
(`10.1371/journal.pmed.1004323`), where lattice stops at the ruled box (1 data
row) while stream sees the whole table.

These tests use lightweight stand-ins for Camelot's table object (only `.df`,
`._bbox`, `.rows` are read) so they run without a PDF.
"""

from __future__ import annotations

import pandas as pd

from docpluck.tables.camelot_extract import _augment_lattice_with_stream_rows


class FakeTable:
    """Minimal stand-in for a camelot.core.Table (only the attributes the
    augmenter reads). `rows` is the list of [y_top, y_bottom] bands camelot
    exposes; PDF y increases upward."""

    def __init__(self, data, bbox, rows=None):
        self.df = pd.DataFrame(data)
        self._bbox = bbox
        # Default each row to a 10pt band stacked downward from bbox top.
        if rows is None:
            top = bbox[3]
            rows = [[top - 10 * i, top - 10 * (i + 1)] for i in range(len(data))]
        self.rows = rows


def _lattice():
    # 3 rows (2 header + 1 data), bbox y 637..705 (the ruled box).
    return FakeTable(
        [
            ["", "ITT", "PP"],
            ["label", "RD (95% CI)", "RD (95% CI)"],
            ["Resection", "-1.01 (-10-8)", "0.06 (-9-9)"],
        ],
        bbox=(34.0, 637.0, 577.0, 705.0),
        rows=[[700, 690], [690, 660], [660, 638]],
    )


def _stream_full():
    # 4 rows; the lower 2 sit BELOW the lattice box bottom (y 637).
    return FakeTable(
        [
            ["Resection", "-1.01 (-10-8)", "0.06 (-9-9)"],
            ["", "", ""],
            ["adjusted", "-1.83 (-11-7)", "0.82 (-8-10)"],
            ["remnant", "7.7 (-3-18)", "8.4 (-3-19)"],
        ],
        bbox=(26.0, 485.0, 583.0, 677.0),
        rows=[[670, 656], [656, 641], [633, 620], [615, 500]],
    )


def test_augment_appends_rows_below_lattice_box():
    lat = _lattice()
    out = _augment_lattice_with_stream_rows(lat, [_stream_full()])
    labels = [out.df.iloc[r, 0] for r in range(len(out.df))]
    # Lattice's 3 rows kept, plus the two stream rows whose centre is below 637.
    assert "adjusted" in labels
    assert "remnant" in labels
    assert len(out.df) == 5
    # bbox widened downward to cover the appended rows.
    assert out._bbox[1] == 485.0


def test_no_augment_when_column_count_differs():
    lat = _lattice()  # 3 cols
    stream4 = FakeTable(
        [["a", "1", "2", "3"], ["b", "4", "5", "6"]],
        bbox=(26.0, 485.0, 583.0, 677.0),
        rows=[[600, 590], [560, 550]],
    )
    out = _augment_lattice_with_stream_rows(lat, [stream4])
    assert len(out.df) == 3  # unchanged — 4 cols != 3 cols


def test_no_augment_when_stream_does_not_extend_below():
    lat = _lattice()
    # Stream wholly inside the lattice y-range → nothing to recover.
    stream_inside = FakeTable(
        [["Resection", "x", "y"], ["other", "p", "q"]],
        bbox=(30.0, 640.0, 580.0, 700.0),
        rows=[[695, 680], [675, 660]],
    )
    out = _augment_lattice_with_stream_rows(lat, [stream_inside])
    assert len(out.df) == 3  # unchanged


def test_no_augment_when_bboxes_do_not_overlap():
    lat = _lattice()
    # A different table elsewhere on the page (no x/y overlap) is never merged.
    far = FakeTable(
        [["z", "1", "2"], ["w", "3", "4"]],
        bbox=(26.0, 100.0, 200.0, 300.0),
        rows=[[250, 240], [220, 210]],
    )
    out = _augment_lattice_with_stream_rows(lat, [far])
    assert len(out.df) == 3  # unchanged
