"""Column labels printed as stacks of short lines become one header row.

10.1177/01461672251327169 Table 7 (p12): "Actual / intensity / average" and
three more stacks under a "Participant-level analyses" spanner came out as three
header rows, and the column row ("Experiences | average | mean ...") as a body
row.
"""

from __future__ import annotations

from docpluck.tables.cell_cleaning import _MERGE_SEPARATOR as BR
from docpluck.tables.cell_cleaning import _fold_stacked_label_rows, cells_grid_to_html

_SPANNER = ["", "", "", "", "Participant-level analyses", "", "", "Item-level analyses", ""]
_STACK = [
    ["", "Actual", "Intensity", "", "", "", "", "", ""],
    ["", "intensity", "estimate", "Error", "Error", "", "", "", ""],
    ["Experiences", "average", "mean", "mean", "SD", "t-stat", "p", "t-stat", "p"],
]
_DATA = [
    ["Had fight/argument", "42.63", "59.64", "17.01", "22.27", "18.62", "<.001", "/", "/"],
    ["Received low grade", "37.05", "53.65", "16.60", "22.46", "18.01", "<.001", "/", "/"],
]


def test_a_stack_folds_and_the_spanner_stays():
    out = _fold_stacked_label_rows([_SPANNER, *_STACK])
    assert out[0] == _SPANNER
    # stacked lines keep their line breaks, as the super-header fold does
    assert out[1][:5] == ["Experiences", f"Actual{BR}intensity{BR}average",
                          f"Intensity{BR}estimate{BR}mean", f"Error{BR}mean", f"Error{BR}SD"]
    assert len(out) == 2


def test_a_hyphenated_line_joins_without_a_space():
    out = _fold_stacked_label_rows([["", "Well-", ""], ["Item", "being", "SD"]])
    assert out == [["Item", "Well-being", "SD"]]


def test_a_line_with_a_gap_under_it_is_not_folded():
    """A cell with nothing printed directly below it is a spanner, not a stack:
    "Group" stays its own row while the stacked "x" / "SD" folds."""
    rows = [["", "Group", ""], ["", "", "x"], ["Item", "M", "SD"]]
    assert _fold_stacked_label_rows(rows) == [["", "Group", ""], ["Item", "M", f"x{BR}SD"]]


def test_the_html_names_every_column():
    html = cells_grid_to_html([_SPANNER, *_STACK, *_DATA])
    head = html[html.index("<thead>"):html.index("</thead>")]
    assert "Actual<br>intensity<br>average" in head
    assert "Experiences" in head
    body = html[html.index("<tbody>"):]
    assert "Experiences" not in body
    assert "42.63" in body and "37.05" in body


def test_a_spanner_split_across_columns_is_not_folded():
    """10.1080/01650250143000102 Table 3: "Boys (N = 15)" and "Girls (N = 27)"
    span two columns each and came out split ("Boys (N" | "15)"); folding them
    onto the column row gave "Boys (N Mean" and "15) (SD)" (Sonnet page check,
    2026-10-31). A cell with an unclosed parenthesis is part of a spanner."""
    rows = [["", "Boys (N", "15)", "Girls (N", "27)"],
            ["Frequency", "Mean", "(SD)", "Mean", "(SD)"]]
    assert _fold_stacked_label_rows(rows) == rows


def test_nothing_folds_onto_a_data_row():
    """10.1525/collabra.117677 Table 1: the header count took the first data
    row ("Thompson et | 3360 Starcraft | game rank | ... | NA") as the last
    header row, and the label line "variable" was folded into it ("variable
    game rank"; Sonnet page check, 2026-10-31). A row holding a data value is
    not a column row."""
    rows = [["Study", "Study sample", "Esports performance", "Correlate", "Effect size"],
            ["", "", "variable", "", ""],
            ["Thompson et", "3360 Starcraft", "game rank", "actions per", "NA"]]
    assert _fold_stacked_label_rows(rows) == rows


def test_a_lost_glyph_line_is_not_a_stacked_label():
    """10.1080/01650250143000102 Table 3: the "=" of "N = 15" was printed on a
    line of its own and came out as a spacing circumflex (U+02C6); folding it
    shrank the header to two rows, and the super-header fold then glued
    "Boys (N" onto "Mean" (Sonnet page check, 2026-10-31). A line with no
    letter, digit or % is not a label; a modifier letter or accent is not a
    letter here."""
    for glyph in ("\u02c6", "\ufffd"):
        rows = [["", "Boys (N", "15)", "Girls (N", "27)"],
                ["", "", glyph, "", glyph],
                ["Frequency", "Mean", "(SD)", "Mean", "(SD)"]]
        assert _fold_stacked_label_rows(rows) == rows, glyph


def test_a_panel_label_over_the_stub_is_not_folded_into_it():
    """10.1177/01461672251327169 Table 2 (canary audit, 2026-10-31): the panel
    label "Replication: prevalence estimations" is printed on its own line above
    the "No | Hypothesis" column row, running across the table. It was folded
    into the stub ("Replication: prevalence estimations<br>No"). A line set
    only over the stub, at least three times as long as the stub label below
    it, is not a stacked line of that label (one label's lines share its column
    width); it stays its own header row, text intact."""
    from docpluck.tables.cell_cleaning import _fold_super_header_rows

    rows = [["Replication: prevalence estimations", ""], ["No", "Hypothesis"]]
    assert _fold_super_header_rows(rows) == rows
    html = cells_grid_to_html([*rows, ["2a", "People underestimate the prevalence."]])
    head = html[html.index("<thead>"):html.index("</thead>")]
    assert "estimations<br>No" not in head
    assert "Replication: prevalence estimations" in head and "<th>No</th>" in head


def test_a_short_stub_super_label_still_folds():
    from docpluck.tables.cell_cleaning import _fold_super_header_rows

    assert _fold_super_header_rows([["Variable", ""], ["name", "M"]]) == [[f"Variable{BR}name", "M"]]


def test_an_already_folded_paragraph_is_not_split_back():
    """10.1037/a0025767 p13 (Sonnet page check, 2026-10-31): a table note
    spread over three header rows was folded line by line; the panel-label
    rule then split the third line off as a row of its own."""
    from docpluck.tables.cell_cleaning import _fold_super_header_rows

    rows = [["k indicates number of samples; Mean r is the point estimate; 95% CI provides lower", ""],
            ["and upper bounds of the confidence interval for the point estimate", ""],
            ["or a subgroup analysis", "Test statistic"]]
    out = _fold_super_header_rows(rows)
    assert len(out) == 1 and out[0][0].endswith("or a subgroup analysis"), out


def test_a_wrapped_stub_label_with_its_unit_still_folds():
    """Consult 2026-10-31 (Sol, reproduced): "Response latency" over "ms" is
    one printed stub label; the panel-label rule kept it as two header rows.
    Every confirmed panel label or stray line in the 128-paper sample was 35+
    characters, so the rule needs 25."""
    from docpluck.tables.cell_cleaning import _fold_super_header_rows

    assert _fold_super_header_rows([["Response latency", ""], ["ms", "Mean"]]) == [
        [f"Response latency{BR}ms", "Mean"]]
