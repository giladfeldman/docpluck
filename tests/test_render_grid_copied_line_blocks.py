"""A text-channel copy of a structured table is replaced by a marker
(``render._suppress_grid_copied_line_blocks``, 2026-10-30).

Measured on 10.1177/01461672251327169: pdftotext linearizes Tables 2, 3, 5 and 6
into the body, and the render also places each as a structured ``### Table N``
block, so every cell appeared twice -- once in the grid and once as loose lines in
the Introduction, Method and Results. The fixtures below are built from that
shape; the cell text is invented.
"""

from __future__ import annotations

from docpluck.render import _suppress_grid_copied_line_blocks

ROWS = [
    ("Design facet", "Replication", "Details of deviation"),
    ("IV construct", "Same", "We separated the first measure from the second measure."),
    ("DV construct", "Similar", "We added an individual differences measure of comparison."),
    ("Population", "Similar", "The population was also students, with a larger sample."),
    ("Procedure", "Different", "We randomized the order of the rating tasks and scales."),
]


def _table_block(label="5"):
    rows = "\n".join(
        "    <tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in ROWS
    )
    return f"### Table {label}\n\n*Classification of the Replication.*\n\n<table>\n{rows}\n</table>\n"


COPY = [
    "We separated the first measure from the second measure.",
    "We added an individual differences measure of comparison.",
    "The population was also students, with a larger sample.",
    "We randomized the order of the rating tasks and scales.",
]

PROSE_BEFORE = "## Method\n\nParticipants completed the survey online and were paid for their time.\n"


def _doc(body_lines):
    return PROSE_BEFORE + "\n" + "\n".join(body_lines) + "\n\n## Results\n\n" + _table_block()


def test_a_verbatim_copy_of_a_table_becomes_a_marker():
    out = _suppress_grid_copied_line_blocks(_doc(COPY))
    assert "table-text-duplicate: 4 lines of Table 5" in out
    for line in COPY:
        assert out.count(line) == 1, "the copy stays in the grid only"
    assert "Participants completed the survey online" in out


def test_one_line_not_in_the_table_keeps_the_whole_block():
    body = COPY[:2] + ["This sentence was written by the authors and is not in any table."] + COPY[2:]
    out = _suppress_grid_copied_line_blocks(_doc(body))
    # Two lines each side of the foreign line: below the 4-line proof floor.
    assert "table-text-duplicate" not in out
    assert "This sentence was written by the authors" in out


def test_a_short_copy_is_not_enough_proof():
    out = _suppress_grid_copied_line_blocks(_doc(COPY[:2]))
    assert "table-text-duplicate" not in out
    assert out.count(COPY[0]) == 2


def test_prose_that_shares_words_with_the_table_is_kept():
    """Long lines must be exact substrings of the table's text, not word matches."""
    body = [
        "We separated the measures in our study, unlike the target article.",
        "We added a measure of comparison to examine individual differences.",
        "The population was students, and the sample was larger than before.",
        "We randomized the scales, and the order of the rating tasks too.",
    ]
    out = _suppress_grid_copied_line_blocks(_doc(body))
    assert "table-text-duplicate" not in out
    for line in body:
        assert line in out


def test_no_structured_table_no_change():
    text = PROSE_BEFORE + "\n" + "\n".join(COPY) + "\n"
    assert _suppress_grid_copied_line_blocks(text) == text


def test_text_after_the_table_note_is_not_the_tables_text():
    """10.2478/v10059-011-0005-y Table 4: the flat list ran past the table's note
    into a Discussion paragraph. That paragraph's body copy is the only copy in
    the body and must stay."""
    para = [
        "Two distinct areas of contents were distinguished in the analysis here,",
        "and the evaluations of morality were made independently of the others.",
        "This pattern held across both samples and in every model we compared.",
        "We return to the meaning of this result in the general discussion below.",
    ]
    fence = "\n".join(["Agency", ".39***", "Morality", "-.10", "Note. N = 195.", *para])
    block = (f"### Table 4\n\n*Regression of self-esteem.*\n\n```unstructured-table\n{fence}\n```\n")
    doc = "## Discussion\n\n" + "\n".join(para) + "\n\n## Study 2\n\n" + block
    out = _suppress_grid_copied_line_blocks(doc)
    assert "table-text-duplicate" not in out
    assert out.count(para[0]) == 2


def test_a_flat_list_that_ran_into_the_body_does_not_claim_its_prose():
    """10.1016/j.jesp.2021.104154 Table 1: no grid, so the table shipped as a flat
    list -- which ran on into the Results heading and paragraph. Sentence lines
    are matched against grid cells only, so the Results paragraph stays."""
    para = [
        "Because there are two events with four outcomes each, we conducted",
        "eight sets of rank tests on the estimates in the two conditions here.",
        "The results remained largely the same when we adjusted the p values.",
        "Historically, the correct outcomes of the events were the first ones.",
    ]
    fence = "\n".join(["Design facet", "Same", "Similar", "Results", *para])
    block = f"### Table 1\n\n*Classification.*\n\n```unstructured-table\n{fence}\n```\n"
    doc = block + "\n### Results\n\n" + "\n".join(para) + "\n"
    out = _suppress_grid_copied_line_blocks(doc)
    assert "table-text-duplicate" not in out
    assert out.count(para[1]) == 2


# --- 2026-10-30, second canary pass on 10.1177/01461672251327169 -------------

def _grid(label, rows, caption="A Table."):
    body = "\n".join(
        "    <tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows
    )
    return f"### Table {label}\n\n*{caption}*\n\n<table>\n{body}\n</table>\n"


def _in_body(out, line):
    return line in out[:out.index("### Table")]


def test_a_cell_the_grid_wraps_over_rows_is_found_as_one_line():
    """Table 4 p7: "Participants were asked to make" / "estimations of U.S.
    American student" / ... is one cell over four grid rows, one body line."""
    rows = [
        ("Others ratings", "DV1a: prevalence of others' experiences"),
        ("Participants were asked to make", "Please estimate the percentage"),
        ("estimations of student participants", "of other student participants"),
        ("taking the survey.", "(0% to 100%)"),
    ]
    copy = [
        "Participants were asked to make estimations of student participants taking the survey.",
        "Please estimate the percentage of other student participants",
        "DV1a: prevalence of others' experiences",
        "Others ratings",
    ]
    md = PROSE_BEFORE + "\n" + "\n".join(copy) + "\n\n## Results\n\n" + _grid("4", rows)
    out = _suppress_grid_copied_line_blocks(md)
    assert "table-text-duplicate: 4 lines of Table 4" in out
    assert not _in_body(out, copy[0])


def test_a_double_hyphen_matches_the_grids_em_dash():
    rows = [(f"{i}\u2014Scale number {i} of the battery", f"{i}.{i}5") for i in range(1, 6)]
    copy = [f"{i}--Scale number {i} of the battery" for i in range(1, 6)]
    md = PROSE_BEFORE + "\n" + "\n".join(copy) + "\n\n## Results\n\n" + _grid("8", rows)
    out = _suppress_grid_copied_line_blocks(md)
    assert "table-text-duplicate: 5 lines of Table 8" in out
    assert not _in_body(out, copy[0])


def test_cells_of_one_row_on_one_line_are_judged_by_their_tokens():
    """Table 8: "[-0.01, 0.16] [0.04, 0.20]" -- two CIs of one row, other cells
    between them in the grid, so the line is not a substring of it."""
    rows = [
        ("1", "0.06", "[-0.01, 0.16]", "0.11", "[0.04, 0.20]"),
        ("2", "0.02", "[-0.15, 0.01]", "0.08", "[-0.02, 0.14]"),
        ("3", "0.15", "[-0.07, 0.10]", "0.20", "[0.03, 0.19]"),
    ]
    copy = ["[-0.01, 0.16] [0.04, 0.20]", "0.06", "[-0.15, 0.01] [-0.02, 0.14]", "0.02",
            "[-0.07, 0.10] [0.03, 0.19]"]
    md = PROSE_BEFORE + "\n" + "\n".join(copy) + "\n\n## Results\n\n" + _grid("8", rows)
    out = _suppress_grid_copied_line_blocks(md)
    assert "table-text-duplicate: 5 lines of Table 8" in out
    assert not _in_body(out, copy[0])


def test_a_sentence_is_never_matched_by_its_tokens():
    """The token fallback is for lines that are not sentences: a body sentence
    whose words all occur in the grid but not in this order stays."""
    rows = [(w, "1.5") for w in "the participants were asked about their own experience in study".split()]
    sentence = "In the study the participants were asked about their own experience."
    md = PROSE_BEFORE + "\n" + "\n".join([sentence] * 4) + "\n\n## Results\n\n" + _grid("3", rows)
    out = _suppress_grid_copied_line_blocks(md)
    assert "table-text-duplicate" not in out


def test_a_footnote_mark_line_ends_the_copy():
    """Table 2 p4: the copy is followed by "a" / footnote text; the lone mark is
    in any grid, but it opens the table's footnotes, not more copy."""
    md = (PROSE_BEFORE + "\n" + "\n".join(COPY + ["a", "The target article sometimes shifts its wording."])
          + "\n\n## Results\n\n" + _table_block())
    out = _suppress_grid_copied_line_blocks(md)
    assert "table-text-duplicate: 4 lines of Table 5" in out
    body = out[:out.index("### Table")]
    assert "\na\nThe target article sometimes shifts its wording." in body


def test_a_grid_the_render_later_strips_does_not_count():
    """10.1098/rsos.241348 Table 1: the grid is removed by
    `_strip_phantom_camelot_tables` after this pass, so its body copy is the
    only copy left and must stay."""
    from docpluck.render import _strip_phantom_camelot_tables

    cells = COPY
    grid = (
        "### Table 5\n\n*A Table.*\n\n<table>\n  <thead>\n    <tr><th>and we examined those who were "
        "tested and repeatedly measured below the threshold</th><th>x</th><th>y</th><th>z</th></tr>\n  </thead>\n  <tbody>\n    <tr>"
        + "".join(f"<td>{c}</td>" for c in cells) + "</tr>\n  </tbody>\n</table>\n"
    )
    assert "<table>" not in _strip_phantom_camelot_tables(grid), "fixture must be a phantom"
    md = PROSE_BEFORE + "\n" + "\n".join(COPY) + "\n\n## Results\n\n" + grid
    out = _suppress_grid_copied_line_blocks(md)
    assert "table-text-duplicate" not in out
    assert all(line in out[:out.index("### Table")] for line in COPY)
