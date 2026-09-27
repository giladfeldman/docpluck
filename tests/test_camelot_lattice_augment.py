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
    # bbox widened downward to the LAST APPENDED ROW's bottom (500), not the
    # stream table's bottom (485): a stream block can run on past the rows that
    # were appended, and a box drawn over it lands on whatever sits below.
    assert out._bbox[1] == 500.0


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


# ---- v2.4.145: the rows below a box are not all this table's ---------------
#
# Stream flavor does not stop at a table. On a page of stacked tables it returns
# one block running through the NEXT caption and the NEXT table, and every row
# of it below the lattice box used to be appended. Measured on Scimeto's
# contract fixture: Table 1's lattice grid gained Table 2's caption line and
# Table 2's rows, one of which flattened to the fabricated F(0.003, -0.31) = 98.


def _upper_lattice():
    # Table 1: a fully ruled 2-row grid, box y 425..497.
    return FakeTable(
        [["Effect", "F", "p"], ["Condition", "5.20", ".025"]],
        bbox=(70.0, 425.0, 295.0, 497.0),
        rows=[[497, 479], [479, 425]],
    )


def _lower_lattice():
    # Table 2: its own ruled box, y 342..397, directly under Table 1.
    return FakeTable(
        [["Contrast", "t", "d"], ["Sleep vs Nap", "-3.07", "-0.31"]],
        bbox=(70.0, 342.0, 266.0, 397.0),
        rows=[[397, 379], [379, 342]],
    )


def _stream_block(with_caption=True):
    # One stream block spanning BOTH tables (Camelot's actual output shape).
    data = [
        ["Effect", "F", "p"],
        ["Condition", "5.20", ".025"],
    ]
    rows = [[495, 480], [478, 430]]
    if with_caption:
        data.append(["Table 2. Planned contrasts.", "", ""])
        rows.append([418, 395])
    data += [["Contrastt", "d", ""], ["Sleep vs Nap-3.07", "-0.31", ""]]
    rows += [[394, 379], [378, 347]]
    return FakeTable(data, bbox=(60.0, 337.0, 298.0, 542.0), rows=rows)


def test_augment_stops_at_a_caption_row():
    out = _augment_lattice_with_stream_rows(_upper_lattice(), [_stream_block()], [])
    labels = [out.df.iloc[r, 0] for r in range(len(out.df))]
    assert labels == ["Effect", "Condition"], labels
    assert out._bbox[1] == 425.0  # nothing appended -> box untouched


def test_augment_stops_at_a_sibling_ruled_table():
    # No caption row between them: the sibling's ruled box alone must stop it.
    out = _augment_lattice_with_stream_rows(
        _upper_lattice(), [_stream_block(with_caption=False)], [_lower_lattice()]
    )
    labels = [out.df.iloc[r, 0] for r in range(len(out.df))]
    assert "Sleep vs Nap-3.07" not in labels and "Contrastt" not in labels, labels


def test_sibling_below_does_not_stop_rows_above_it():
    # Truncated rows directly under the box, ABOVE the sibling, still append.
    lat = _upper_lattice()
    block = FakeTable(
        [["Effect", "F", "p"], ["Time", "12.50", "<.001"], ["Contrast", "t", "d"]],
        bbox=(60.0, 337.0, 298.0, 500.0),
        rows=[[495, 480], [423, 405], [394, 379]],
    )
    out = _augment_lattice_with_stream_rows(lat, [block], [_lower_lattice()])
    labels = [out.df.iloc[r, 0] for r in range(len(out.df))]
    assert labels == ["Effect", "Condition", "Time"], labels
    assert out._bbox[1] == 405.0


def test_ruled_table_in_the_other_column_bounds_nothing():
    # A ruled box in the OTHER column, its top (420) above the truncated row's
    # centre (414): below this box by y alone, but beside it by x. It must not
    # stop the row, which is this table's own.
    beside = FakeTable(
        [["a", "b", "c"], ["d", "e", "f"]],
        bbox=(320.0, 300.0, 560.0, 420.0),
        rows=[[420, 400], [400, 300]],
    )
    block = FakeTable(
        [["Effect", "F", "p"], ["Time", "12.50", "<.001"]],
        bbox=(60.0, 400.0, 298.0, 500.0),
        rows=[[495, 480], [423, 405]],
    )
    out = _augment_lattice_with_stream_rows(_upper_lattice(), [block], [beside])
    labels = [out.df.iloc[r, 0] for r in range(len(out.df))]
    assert labels == ["Effect", "Condition", "Time"], labels
