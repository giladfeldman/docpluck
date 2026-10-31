"""A table of words joins a wrapped cell line to its row only on evidence in the cells.

10.1177/01461672251327169 Table 5 (p9) is a deviations table with no data value
in it. Its wrapped lines came out as rows of their own: "Same, with an" /
"extension", "... in the United" / "States.", "Replication" / "classification".
"""

from __future__ import annotations

from docpluck.tables.cell_cleaning import _MERGE_SEPARATOR, _merge_continuation_rows

_HEAD = ["Design facet", "Replication", "Details of deviation", "Reasons for change"]


def _merge(rows):
    return [[c.replace(_MERGE_SEPARATOR, " / ") for c in r] for r in _merge_continuation_rows(rows)]


def test_a_line_under_a_cell_that_breaks_off_joins_it():
    out = _merge([
        _HEAD,
        ["IV construct", "Same, with an", "", ""],
        ["", "extension", "", ""],
        ["Contextual variables", "Similar", "recruited in the United", ""],
        ["", "", "States.", ""],
        ["Population", "Similar", "Students.", ""],
    ])
    assert out[1] == ["IV construct", "Same, with an / extension", "", ""]
    assert out[2] == ["Contextual variables", "Similar", "recruited in the United / States.", ""]
    assert len(out) == 4


def test_a_label_wrapped_with_its_cells_joins_its_row():
    out = _merge([
        _HEAD,
        ["Replication", "Close to far", "Mostly followed the target, yet", ""],
        ["classification", "replication", "adjustment to measuring both", ""],
        ["Population", "Similar", "Students.", ""],
    ])
    assert out[1][0] == "Replication classification"
    assert out[1][1] == "Close to far / replication"
    assert len(out) == 3


def test_a_capitalised_line_under_a_finished_cell_stays_its_own_row():
    out = _merge([
        _HEAD,
        ["IV construct", "Same.", "", ""],
        ["", "Different", "", ""],
        ["Population", "Similar", "Students.", ""],
    ])
    assert ["", "Different", "", ""] in out


def test_a_lone_lowercase_label_line_is_not_taken_as_a_wrap():
    """One lowercase line alone in the label column can be another column's text."""
    out = _merge([
        _HEAD,
        ["Replication", "Close to far", "Mostly followed.", ""],
        ["classification", "", "", ""],
        ["Population", "Similar", "Students.", ""],
    ])
    assert out[1][0] == "Replication"


def test_a_table_with_values_keeps_its_own_rules():
    """The word-table rule does not reach a table that holds data values."""
    out = _merge([
        ["Measure", "M", "SD"],
        ["Liking of the", "3.20", "1.10"],
        ["", "Extra", ""],
        ["Trust", "4.10", "0.90"],
    ])
    assert ["", "Extra", ""] in out


def test_a_table_set_in_lowercase_keeps_its_rows():
    """10.1098/rsos.140072 Table 2 prints every label and description in
    lowercase; a lowercase opening is no evidence of a wrap there, and its four
    behaviour rows were joined into one."""
    rows = [
        ["context", "behaviour", "description"],
        ["overt aggression", "chase ram bite", "focal fish quickly darts towards another fish"],
        ["restrained aggression", "aggressive posture frontal display", "focal fish lowers its head"],
        ["submission", "submissive posture", "the head of the focal fish is raised"],
        ["affiliation", "following parallel swim", "focal fish follows another cichlid"],
    ]
    out = _merge(rows)
    assert [r[0] for r in out] == [r[0] for r in rows]
