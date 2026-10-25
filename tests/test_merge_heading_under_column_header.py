"""A spanning section heading is not a wrapped line of the column-header row above it.

Real case: 10.1525/collabra.90203 Table 9 (p13). Once Camelot's dropped header
line is kept (tables/camelot_row_ties.py), the grid's first row is the printed
column header ``df | F | p | BF01 | (eta2p) | 95% CI`` and the next row is the
section heading ``Identifiability main effect, without joint [S1] *`` in column 1
with an empty stub. The prose-continuation merge glued that heading onto the
``df`` label, so flatten no longer saw a ``df`` column and every record lost its
df pair and eta2. The real-PDF check is
``test_tables_flatten_blank_header_recovery.py::test_collabra_90203_tables_8_9_real_pdf``.
"""

from __future__ import annotations

from docpluck.tables.cell_cleaning import _MERGE_SEPARATOR, _merge_continuation_rows

HEADER = ["", "df", "F", "p", "BF01", "", "95% CI"]
HEADING = ["", "Identifiability main effect, without joint [S1] *", "", "", "", "", ""]
DATA = ["Target article", "1, 114", "1.80", ".18", "N/A", ".02", "[.00, .09]"]


def test_heading_under_column_header_row_stays_its_own_row():
    out = _merge_continuation_rows([list(HEADER), list(HEADING), list(DATA)])
    assert out[0] == HEADER
    assert out[1][1] == HEADING[1]
    assert out[2] == DATA


def test_two_line_column_header_still_joins():
    # "Underfilled" over "M (SD)" in one column (10.1525/collabra.77859 Table 2):
    # short header words under a header word are the same cell's second line.
    rows = [["", "Underfilled", "Overfilled", "t"], ["", "M (SD)", "M (SD)", ""],
            ["Attractive", "3.1 (1.0)", "3.2 (1.1)", "0.60"]]
    out = _merge_continuation_rows([list(r) for r in rows])
    assert len(out) == 2
    assert out[0][1] == "Underfilled" + _MERGE_SEPARATOR + "M (SD)"


def test_hypothesis_prose_wrap_still_joins():
    # A wrapped prose cell continues the prose cell above it.
    rows = [["2a", "People underestimate how much others", ""],
            ["", "enjoy receiving gratitude letters", ""]]
    out = _merge_continuation_rows([list(r) for r in rows])
    assert len(out) == 1


# ── the same table once its header row is kept: a labelled df column holds the
# F-test's df PAIR, and the eta2p column's header is drawn as vector art (no
# text at all on the page), so its header cell is blank.


def _row(header, row):
    from docpluck.tables.flatten import _flatten_one_row

    return _flatten_one_row("T", 13, "Table 9", 0, header, row)["fields"]


def test_labelled_df_column_reads_a_df_pair():
    f = _row(HEADER, DATA)
    assert (f.get("df1"), f.get("df2")) == (1, 114)


def test_single_blank_proportion_column_of_an_f_table_is_eta2():
    f = _row(HEADER, DATA)
    assert f.get("eta2") == 0.02
    assert (f["F"], f["p"], f["CI_lower"], f["CI_upper"]) == (1.8, 0.18, 0.0, 0.09)


def test_blank_column_outside_eta2_domain_is_not_typed():
    f = _row(HEADER, ["Replication", "1, 114", "1.80", ".18", "3.2", "4.5", "[.00, .09]"])
    assert "eta2" not in f and "est" not in f


def test_blank_column_is_not_eta2_when_a_competing_effect_is_named():
    hdr = ["", "df", "F", "p", "d", "", "95% CI"]
    f = _row(hdr, ["Replication", "1, 114", "1.80", ".18", "0.30", ".02", "[.00, .09]"])
    assert "eta2" not in f


def test_heading_below_a_data_row_is_not_glued_onto_its_df_pair():
    # Same page: the next section heading follows the "Replication" row and
    # landed on its "1, 114" df cell, so that row lost its df pair.
    rep = ["Replication", "1, 114", "0.09", ".764", "11.08", ".00", "[.00, .01]"]
    nxt = ["", "Explicit learning intervention main effect, without joint [S1] *",
           "", "", "", "", ""]
    out = _merge_continuation_rows([list(HEADER), list(rep), list(nxt), list(DATA)])
    assert out[1] == rep
    assert out[2][1] == nxt[1]
