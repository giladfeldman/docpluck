"""After a table's text copy becomes a marker, its note joins the table and a
broken sentence is rejoined (10.1177/01461672251327169, Tables 9 and 10)."""

from __future__ import annotations

from docpluck.render import _settle_table_copy_markers

_MARK = ("<!-- table-text-duplicate: 37 lines of Table 10's text-channel copy omitted "
         "here; every line is in the structured Table 10. Other loose lines of this "
         "table, if any, were not verified and are kept -->")

_BLOCK = "\n".join([
    "### Table 10",
    "",
    "*Table 10. Intensity Estimates.*",
    "",
    "<table>",
    "<tr><td>Loneliness</td><td>.29</td></tr>",
    "</table>",
])


def test_the_note_under_the_copy_moves_into_the_table_block():
    md = "\n".join([
        "## Results", "", "Body before.", "", _MARK,
        "Note. Linear regression, N = 594.", "*", "p < .05. **p < .01.", "",
        "Next paragraph starts here.", "", _BLOCK, "",
    ])
    out = _settle_table_copy_markers(md)
    block = out[out.index("### Table 10"):]
    body = out[:out.index("### Table 10")]
    assert "Note. Linear regression, N = 594." in block
    assert "Note. Linear regression" not in body
    assert out.count("p < .05. **p < .01.") == 1


def test_a_note_the_block_already_shows_stays_where_it_is():
    block = _BLOCK + "\n\nNote. Linear regression, N = 594."
    md = "\n".join(["## Results", "", _MARK, "Note. Linear regression, N = 594.", "", block])
    out = _settle_table_copy_markers(md)
    assert out.count("Note. Linear regression, N = 594.") == 2


def test_a_copy_inside_a_sentence_moves_to_the_paragraph_end():
    md = "\n".join([
        "## Results", "", "the external reviewer who", "", "", _MARK, "",
        "was kind to review the results.", "Second line of it.", "",
        "Next paragraph.", "", _BLOCK,
    ])
    out = _settle_table_copy_markers(md)
    assert "the external reviewer who\nwas kind to review the results." in out
    assert out.index(_MARK) > out.index("Second line of it.")
    assert out.index(_MARK) < out.index("Next paragraph.")


def test_a_copy_between_two_paragraphs_stays_put():
    md = "\n".join([
        "## Results", "", "The paragraph ends here.", "", _MARK, "",
        "Another paragraph begins.", "", _BLOCK,
    ])
    assert _settle_table_copy_markers(md) == md


def test_footnotes_printed_as_lone_marks_move_into_the_block():
    """Table 2 p4: "a" / text / "b" / text under the copy are the table's
    footnotes; they move into the block, all of them."""
    block = _BLOCK.replace("Table 10", "Table 2")
    mark = _MARK.replace("Table 10", "Table 2")
    md = "\n".join([
        "## Intro", "", "Body before.", "", mark,
        "a", "The target article sometimes shifts its wording.",
        "b", "The hypothesis was not supported in the original.", "",
        "Next paragraph starts here.", "", block, "",
    ])
    out = _settle_table_copy_markers(md)
    head = out.index("### Table 2")
    assert "The target article sometimes shifts" in out[head:]
    assert "The hypothesis was not supported" in out[head:]
    assert "The target article sometimes shifts" not in out[:head]
    assert "Next paragraph starts here." in out[:head]
