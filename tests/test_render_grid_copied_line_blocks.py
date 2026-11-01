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


_P_ROWS = [("p < .01", "a"), ("p < .02", "b"), ("p < .03", "c"), ("p < .04", "d"), ("p < .05", "and")]


def _p_table(one_line=False):
    rows = "".join(f"<tr><td>{a}</td><td>{b}</td></tr>" for a, b in _P_ROWS).replace("<", "&lt;").replace(
        "&lt;tr>", "<tr>").replace("&lt;/tr>", "</tr>").replace("&lt;td>", "<td>").replace("&lt;/td>", "</td>")
    sep = "" if one_line else "\n"
    return f"### Table 1\n\n<table>{sep}{rows}{sep}</table>\n"


def test_a_line_whose_operators_are_not_in_the_table_is_kept():
    """Consult 2026-10-31 (Sol, reproduced): "p > .01" .. "p > .04 and p > .05"
    vanished behind a duplicate marker for a table printing "p < .01" .. "p <
    .05": the numbers and words matched and the operators were not compared."""
    body = ["p > .01", "p > .02", "p > .03", "p > .04 and p > .05"]
    doc = "## Results\n\n" + "\n".join(body) + "\n\n" + _p_table()
    out = _suppress_grid_copied_line_blocks(doc)
    assert "table-text-duplicate" not in out
    for line in body:
        assert line in out


def test_text_after_a_one_line_table_is_still_judged():
    """Consult 2026-10-31 (Sonnet): a table emitted on one line never closed the
    table state, so every line after it was treated as table markup."""
    doc = ("## Results\n\n" + _p_table(one_line=True) + "\n## Discussion\n\n" + "\n".join(COPY)
           + "\n\n## Tables\n\n" + _table_block())
    out = _suppress_grid_copied_line_blocks(doc)
    assert "table-text-duplicate: 4 lines of Table 5" in out


def test_a_copy_with_the_tables_own_operators_is_still_a_copy():
    body = ["p < .01", "p < .02", "p < .03", "p < .04 and p < .05"]
    out = _suppress_grid_copied_line_blocks("## Results\n\n" + "\n".join(body) + "\n\n" + _p_table())
    assert "table-text-duplicate" in out


def test_values_reused_by_a_later_table_are_not_a_copy_of_the_earlier_one():
    """10.1017/s1930297500009189 Table 16 (p20) compares the original study's
    betas with the replication's, so its rows repeat values printed in Tables 1
    and 8. Table 16's grid caught one row of eight, and its body text, sitting
    past Table 15's caption, was replaced by markers pointing at Tables 1 and 8:
    the replication betas survived nowhere (/ship QA 2026-10-31). A block that
    sits past a later table's caption is that later table's text, not a copy of
    a table whose caption came before."""
    doc = ("## Method\n\nTable 5: Classification of the Replication.\n\n"
           + "\n".join(COPY)
           + "\n\n## Results\n\nTable 6: Comparison with the original study.\n\n"
           + "\n".join(COPY)
           + "\n\n" + _table_block("5")
           + "\n" + _grid("6", [("Effect", "Original", "Replication"),
                               ("Anchoring", "0.41", "0.38")]))
    out = _suppress_grid_copied_line_blocks(doc)
    assert out.count("lines of Table 5's text-channel copy") == 1, "the first copy still goes"
    tail = out.split("Table 6: Comparison with the original study.")[1]
    for line in COPY:
        assert line in tail.split("### Table 5")[0], "Table 6's own text is kept"


def test_a_line_of_words_with_no_number_must_be_in_the_table_verbatim():
    """10.15626/MP.2022.3108 Table 2 (canary 2026-11-01): the label line
    "[Positive frame, Opt-out]:" was judged present by its words alone (each is
    in another condition's label), so the first condition, which only the body
    holds, was dropped with the copy."""
    stim = "Notify me about more health surveys."
    conds = ["Positive frame, Opt-out", "Positive frame, Opt-in", "Positive frame, No-default",
             "Negative frame, Opt-out", "Negative frame, Opt-in"]
    breaker = "This sentence was written by the authors and is not in any table."
    table = ("### Table 2\n\n*Study stimuli.*\n\n```unstructured-table\n"
             + "\n".join(f"[{c}]:\n{stim}\nYes\nNo" for c in conds[1:]) + "\n" + stim + "\n```\n")
    body = "\n".join(f"[{c}]:\n{stim}\nYes\nNo" for c in conds) + "\n" + breaker
    out = _suppress_grid_copied_line_blocks(PROSE_BEFORE + "\n" + body + "\n\n## Results\n\n" + table)
    assert "[Positive frame, Opt-out]:" in out
    # The same block, with the table holding every label, is a copy.
    full = "\n".join(f"[{c}]:\n{stim}\nYes\nNo" for c in conds)
    table_full = f"### Table 2\n\n*Study stimuli.*\n\n```unstructured-table\n{full}\n```\n"
    out = _suppress_grid_copied_line_blocks(PROSE_BEFORE + "\n" + body + "\n\n## Results\n\n" + table_full)
    assert "table-text-duplicate" in out


def test_a_table_line_the_methods_also_quote_does_not_keep_the_copy():
    """10.1177/01461672251327169 Table 4 (/ship QA 2026-11-01): the Measures
    section quotes a response-scale line that Table 4 also holds, so the body
    prints it twice and the table once. That is the paper quoting itself, not a
    sign the copy is ambiguous: the copy is still a copy."""
    quoted = COPY[0]
    doc = (PROSE_BEFORE + "\n" + quoted + "\n\n## Results\n\n" + "\n".join(COPY)
           + "\n\n" + _table_block())
    out = _suppress_grid_copied_line_blocks(doc)
    assert "table-text-duplicate" in out
    assert out.count(quoted) == 2  # the Methods quote and the grid cell


def test_a_word_line_is_matched_ignoring_spacing():
    """10.1177/01461672251327169 Table 6 (canary 2026-11-01): the grid holds
    "Thought about distant friends/family" and the text channel printed
    "friends/ family". Rejecting that one line split the copy, and its first
    lines stayed loose in the Results."""
    labels = ["Negative experiences", "Had fight/argument", "Thought about distant friends/family",
              "Received low grade", "Were rejected by someone"]
    cells = [(lab, "0.41 [0.22, 0.60]") for lab in labels]
    rows = "\n".join(f"    <tr><td>{a}</td><td>{b}</td></tr>" for a, b in cells)
    table = f"### Table 6\n\n*Misestimation by item.*\n\n<table>\n{rows}\n</table>\n"
    body = "\n".join(labels).replace("friends/family", "friends/ family") + "\n" + \
        "\n".join(b for _, b in cells)
    out = _suppress_grid_copied_line_blocks(PROSE_BEFORE + "\n" + body + "\n\n## Results\n\n" + table)
    assert "table-text-duplicate" in out
    assert "friends/ family" not in out


def test_a_word_line_must_match_on_word_boundaries():
    """Consult 2026-11-01 (Sol reproduced, Sonnet concurred): with every space
    removed, the body line "Notes" matched a table whose adjacent cells are "No"
    and "tes", and "Total" matched inside "Subtotal"; the real line was dropped
    with the copy block below it."""
    rows = list(ROWS) + [("No", "tes", "Subtotal of the replication facets."),
                         ("Overall", "Same", "Summary across the replication facets.")]
    body_rows = "\n".join(
        "    <tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    table = (f"### Table 5\n\n*Classification of the Replication.*\n\n<table>\n{body_rows}\n</table>\n")
    for real in ("Notes", "Total"):
        doc = PROSE_BEFORE + "\n" + real + "\n" + "\n".join(COPY) + "\n\n## Results\n\n" + table
        out = _suppress_grid_copied_line_blocks(doc)
        assert "table-text-duplicate" in out
        assert "\n" + real + "\n" in out, real
    # Spacing beside punctuation still matches: "friends/ family" is "friends/family".
    rows2 = list(ROWS) + [("Thought about distant friends/family", "Same", "x")]
    body_rows2 = "\n".join(
        "    <tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows2)
    table2 = (f"### Table 5\n\n*Classification of the Replication.*\n\n<table>\n{body_rows2}\n</table>\n")
    doc = (PROSE_BEFORE + "\nThought about distant friends/ family\n" + "\n".join(COPY)
           + "\n\n## Results\n\n" + table2)
    out = _suppress_grid_copied_line_blocks(doc)
    assert "friends/ family" not in out

