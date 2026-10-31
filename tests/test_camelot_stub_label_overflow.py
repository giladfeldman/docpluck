"""A row label that starts in the stub column and runs on across a narrow
second column stays in the stub.

10.1177/01461672251327169 Table 6 (p11, canary audit 2026-10-31): the row
"Overall negative: target article (Study 3)" is printed from the stub's left
edge across the empty "Actual prevalence average" column. Camelot gives a text
line to the column it covers the largest SHARE of: the label starts 0.04 pt
inside the stub, so it covers 0.9995 of the stub and all of the narrow second
column, and came out as ["", "Overall negative: target article (Study 3)", ...]
- the label under the prevalence column, the stub empty.

The repair reads only Camelot's own text lines and columns: a line that starts
inside column 0, covers more points of column 0 than of the column Camelot put
it in, and is that cell's whole text, moves to column 0 when column 0 is empty
in that row.
"""

from __future__ import annotations

from types import SimpleNamespace

import pandas as pd

from docpluck.tables.camelot_cell_join import return_overflowing_stub_labels

_COLS = [(66.0, 147.6), (147.6, 192.4), (192.4, 232.0), (232.0, 271.2)]
_ROWS = [(320.0, 305.0), (305.0, 290.0), (290.0, 275.0), (275.0, 260.0)]
_LABEL = "Overall negative: target article (Study 3)"


def _tl(x0, x1, y0, y1, text):
    return SimpleNamespace(x0=x0, x1=x1, y0=y0, y1=y1, get_text=lambda: text + "\n")


def _ct(df_rows, lines, flavor="stream", rotation="anticlockwise"):
    return SimpleNamespace(flavor=flavor, rotation=rotation, page=11, cols=_COLS, rows=_ROWS,
                           df=pd.DataFrame(df_rows), textlines=lines)


def _table6(stub=""):
    # The stub holds the other row labels (Had fight/argument, ...), as on p11.
    return _ct([["Overall negative", "69.64", "46.08", "-23.56"], [stub, _LABEL, "", "-21.4"],
                ["Had fight/argument", "71.04", "47.41", "-23.63"],
                ["Received low grade", "50.17", "42.60", "-7.57"]],
               [_tl(66.0, 118.7, 310.5, 318.5, "Overall negative"),
                _tl(159.0, 176.8, 310.5, 318.5, "69.64"),
                _tl(66.04, 195.9, 293.0, 301.0, _LABEL),
                _tl(240.0, 256.0, 293.0, 301.0, "-21.4")])


def test_an_overflowing_row_label_returns_to_the_stub():
    ct = _table6()
    assert return_overflowing_stub_labels(ct) == 1
    assert list(ct.df.iloc[1]) == [_LABEL, "", "", "-21.4"]
    assert list(ct.df.iloc[0])[:1] == ["Overall negative"]


def test_an_occupied_stub_is_not_overwritten():
    ct = _table6(stub="Something")
    assert return_overflowing_stub_labels(ct) == 0
    assert list(ct.df.iloc[1]) == ["Something", _LABEL, "", "-21.4"]


def test_a_line_starting_right_of_the_stub_stays():
    """A value or header that merely touches column 0 does not start there."""
    ct = _ct([["", "wide header text", "", ""], ["", "", "", ""]],
             [_tl(150.0, 230.0, 310.5, 318.5, "wide header text")])
    assert return_overflowing_stub_labels(ct) == 0
    assert ct.df.iloc[0, 1] == "wide header text"


def test_a_line_mostly_in_its_own_column_stays():
    """Starts in the stub by a hair but sits mostly in column 1 (45 pt vs 4 pt)."""
    ct = _ct([["", "Mean value", "", ""], ["", "", "", ""]],
             [_tl(143.6, 192.0, 310.5, 318.5, "Mean value")])
    assert return_overflowing_stub_labels(ct) == 0


def test_a_cell_holding_more_than_the_line_stays():
    ct = _ct([["", _LABEL + " extra", "", ""], ["", "", "", ""]],
             [_tl(66.04, 195.9, 310.5, 318.5, _LABEL)])
    assert return_overflowing_stub_labels(ct) == 0


def test_lattice_tables_are_not_touched():
    ct = _table6()
    ct.flavor = "lattice"
    assert return_overflowing_stub_labels(ct) == 0


def test_a_near_empty_first_column_is_not_made_the_stub():
    """10.1111/j.1558-5646.1994.tb01351.x p6: Camelot made column 0 a narrow,
    almost empty strip and put the row labels one column right. Moving the
    labels that started inside it split each value from its SE row."""
    ct = _ct([["", "Wing length (mm)", "", "126.6"], ["", "Tarsus length (mm)", "", "11.4"]],
             [_tl(66.04, 195.9, 310.5, 318.5, "Wing length (mm)"),
              _tl(66.04, 195.9, 293.0, 301.0, "Tarsus length (mm)")])
    assert return_overflowing_stub_labels(ct) == 0
    assert ct.df.iloc[0, 1] == "Wing length (mm)"


def test_a_caption_or_leader_line_in_an_empty_row_stays():
    """10.1098/rsos.170336 p5-6: a dot-leader line and caption lines started in
    column 0 too; moving them changed which rows the grid kept (empty rows
    appeared in Table 1). A row label has a letter and a value beside it."""
    ct = _table6()
    ct.df.iloc[1, 3] = ""
    assert return_overflowing_stub_labels(ct) == 0
    dots = ". . . . . . . ."
    ct = _table6()
    ct.df.iloc[1, 1] = dots
    ct.textlines[2] = _tl(66.04, 195.9, 293.0, 301.0, dots)
    assert return_overflowing_stub_labels(ct) == 0


def test_a_note_line_running_across_the_table_stays():
    """10.1037/a0025767 p12, p14 (Sonnet page check, 2026-10-31): a line of the
    table note started in column 0 and ran across every column; moving it split
    the note paragraph across rows."""
    note = "or a subgroup analysis (i) was performed and the degrees of freedom"
    ct = _table6()
    ct.df.iloc[1, 1] = note
    ct.textlines[2] = _tl(66.04, 268.0, 293.0, 301.0, note)
    assert return_overflowing_stub_labels(ct) == 0
