"""Unit tests for docpluck.tables.cell_cleaning.

Ported from docs/superpowers/plans/spot-checks/splice-spike/test_splice_spike.py
as part of the v2.3.0 Section F port. Synthetic inputs only — no PDF I/O.
"""

from __future__ import annotations

from docpluck.tables.cell_cleaning import (
    cells_grid_to_html,
    _MERGE_SEPARATOR,
    _SUP_OPEN,
    _SUP_CLOSE,
    _drop_running_header_rows,
    _fold_super_header_rows,
    _fold_suffix_continuation_columns,
    _html_escape,
    _is_header_like_row,
    _is_running_header_cell,
    _is_strong_running_header,
    _is_weak_running_header,
    _merge_continuation_rows,
    _merge_significance_marker_rows,
    _split_mashed_cell,
    _strip_leader_dots,
)


# ---------------------------------------------------------------------------
# cells_grid_to_html (orchestrator)
# ---------------------------------------------------------------------------


def test_simple_2x3_table_becomes_html_table():
    table = [
        ["Variable", "M", "SD"],
        ["Age", "24.3", "3.1"],
        ["IQ", "100.5", "15.2"],
    ]
    result = cells_grid_to_html(table)
    assert "<table>" in result
    assert "</table>" in result
    assert "<th>Variable</th>" in result
    assert "<th>M</th>" in result
    assert "<th>SD</th>" in result
    assert "<td>Age</td>" in result
    assert "<td>24.3</td>" in result
    assert "<td>IQ</td>" in result
    assert "<thead>" in result
    assert "<tbody>" in result


def test_none_cells_render_as_empty_string():
    table = [
        ["A", "B"],
        ["1", None],
        [None, "2"],
    ]
    result = cells_grid_to_html(table)
    assert "<th>A</th>" in result
    assert "<th>B</th>" in result
    assert "<td>1</td>" in result
    assert "<td>2</td>" in result
    assert "<td></td>" in result


def test_html_special_chars_escaped():
    table = [
        ["expression"],
        ["a < b & c > d"],
    ]
    result = cells_grid_to_html(table)
    assert "&lt;" in result
    assert "&gt;" in result
    assert "&amp;" in result


def test_empty_table_returns_empty_string():
    assert cells_grid_to_html([]) == ""


def test_single_row_returns_empty_string():
    assert cells_grid_to_html([["header only"]]) == ""


def test_continuation_rows_merge_with_br():
    table = [
        ["No", "Hypothesis"],
        ["2a", "People underestimate negative experiences."],
        ["", "Multi-line continuation."],
    ]
    result = cells_grid_to_html(table)
    assert "<td>2a</td>" in result
    assert (
        "People underestimate negative experiences.<br>"
        "Multi-line continuation." in result
    )


def test_group_separator_row_uses_colspan():
    table = [
        ["Ability", "Score", "Rank"],
        ["Easy", "", ""],
        ["Using a mouse", "3.1", "1"],
    ]
    result = cells_grid_to_html(table)
    assert 'colspan="3"' in result
    assert "<strong>Easy</strong>" in result


# ---------------------------------------------------------------------------
# _merge_continuation_rows
# ---------------------------------------------------------------------------


def test_case_c_label_modifier_merges_into_previous_row():
    rows = [
        ["H3", "Compared to the replication", "Domain", "Replication and"],
        ["(Extension)", "condition participants, the easy", "diﬃculty;", "easy domain"],
        ["", "domain condition participants", "ambiguity", "conditions"],
        ["", "assign lower domain diﬃculty.", "", ""],
    ]
    merged = _merge_continuation_rows(rows)
    assert len(merged) == 1
    parent = merged[0]
    assert "H3" in parent[0]
    assert "(Extension)" in parent[0]
    assert "Compared to the replication" in parent[1]
    assert "domain condition participants" in parent[1]
    assert "Replication and" in parent[3]
    assert "easy domain" in parent[3]


def test_case_c_does_not_fire_on_complete_data_rows():
    rows = [
        ["Age", "24.3", "3.1", "142"],
        ["IQ", "100.5", "15.2", "142"],
    ]
    merged = _merge_continuation_rows(rows)
    assert len(merged) == 2
    assert merged[0][0] == "Age"
    assert merged[1][0] == "IQ"


# ---------------------------------------------------------------------------
# _is_header_like_row + multi-row header detection
# ---------------------------------------------------------------------------


def test_header_like_row_label_only():
    assert _is_header_like_row(["Variable", "Mean", "SD"]) is True
    assert _is_header_like_row(["", "Estimation", "Average estimation", ""]) is True


def test_header_like_row_data_with_numbers_is_not_header_like():
    assert _is_header_like_row(["Age", "24.3", "3.1"]) is False
    assert _is_header_like_row(["IQ", "100.5", "15.2"]) is False


def test_header_like_row_with_long_prose_is_not_header_like():
    long = (
        "Compared to judgments of others' abilities, participants' judgments "
        "of their own abilities better predict their comparative ability judgments."
    )
    assert _is_header_like_row(["H1", long, "Replication"]) is False


def test_two_row_header_folds_super_into_sub():
    grid = [
        ["", "Estimation", "Average estimation", ""],
        ["Experiences", "errora", "error (%)", "t-statistics"],
        ["Negative experiences", "−17.2", "5.47**", ""],
    ]
    result = cells_grid_to_html(grid)
    head_block = result.split("<tbody>")[0]
    body_block = result.split("<tbody>")[1]
    assert head_block.count("<tr>") == 1
    assert "<th>Experiences</th>" in head_block
    assert "<th>Estimation<br>errora</th>" in head_block
    assert "<th>Average estimation<br>error (%)</th>" in head_block
    assert "<th>t-statistics</th>" in head_block
    assert "<th>errora</th>" not in head_block
    assert "<th>Estimation</th>" not in head_block
    assert "<td>Negative experiences</td>" in body_block
    assert "<th>Experiences</th>" not in body_block


def test_single_row_header_still_renders_one_thead_row():
    grid = [
        ["Variable", "Mean", "SD"],
        ["Age", "24.3", "3.1"],
        ["IQ", "100.5", "15.2"],
    ]
    result = cells_grid_to_html(grid)
    head_block = result.split("<tbody>")[0]
    assert head_block.count("<tr>") == 1


# ---------------------------------------------------------------------------
# _fold_super_header_rows
# ---------------------------------------------------------------------------


def test_fold_super_header_korbmacher_table7_pattern():
    grid = [
        ["", "", "", "Mean", "", "Effect", ""],
        ["Condition", "T-statistic", "df", "difference", "p-value", "size r", "95% CI"],
        ["Original", "668.5", "238", "2.78", "<.001", "0.82", "[0.79, 0.85]"],
    ]
    result = cells_grid_to_html(grid)
    head_block = result.split("<tbody>")[0]
    assert head_block.count("<tr>") == 1
    assert "<th>Condition</th>" in head_block
    assert "<th>Mean<br>difference</th>" in head_block
    assert "<th>Effect<br>size r</th>" in head_block
    assert "<th>95% CI</th>" in head_block
    assert "<th>Mean</th>" not in head_block
    assert "<th>Effect</th>" not in head_block


def test_fold_super_header_does_not_fold_real_two_row_header():
    rows = [
        ["Group A", "Group A", "Group B", "Group B"],
        ["Mean", "SD", "Mean", "SD"],
    ]
    out = _fold_super_header_rows([list(r) for r in rows])
    assert len(out) == 2
    assert out[0] == ["Group A", "Group A", "Group B", "Group B"]
    assert out[1] == ["Mean", "SD", "Mean", "SD"]


def test_fold_super_header_does_not_fold_when_sub_below_super_is_empty():
    rows = [
        ["", "Statistics", "Statistics", ""],
        ["Variable", "Mean", "SD", ""],
    ]
    out = _fold_super_header_rows([list(r) for r in rows])
    assert len(out) == 1
    rows2 = [
        ["", "Statistics", "Statistics", ""],
        ["Variable", "Mean", "", "t"],
    ]
    out2 = _fold_super_header_rows([list(r) for r in rows2])
    assert len(out2) == 2


def test_fold_super_header_drops_entirely_empty_super_row():
    rows = [
        ["", "", "", ""],
        ["Variable", "Mean", "SD", "n"],
    ]
    out = _fold_super_header_rows([list(r) for r in rows])
    assert len(out) == 1
    assert out[0] == ["Variable", "Mean", "SD", "n"]


def test_fold_super_header_uses_merge_separator_placeholder():
    rows = [
        ["", "Estimation", ""],
        ["Var", "error", "t"],
    ]
    out = _fold_super_header_rows([list(r) for r in rows])
    assert len(out) == 1
    assert out[0][1] == f"Estimation{_MERGE_SEPARATOR}error"


def test_fold_super_header_no_op_on_single_row():
    rows = [["Variable", "Mean", "SD"]]
    out = _fold_super_header_rows([list(r) for r in rows])
    assert out == rows


# ---------------------------------------------------------------------------
# _fold_suffix_continuation_columns
# ---------------------------------------------------------------------------


def test_suffix_fold_ziano_table2_pattern():
    rows = [
        ["", "N", "Pass-Fail", "Win-:", "Loss-"],
        ["", "",  "",          "Uncertain", "Uncertain"],
    ]
    out = _fold_suffix_continuation_columns([list(r) for r in rows])
    assert len(out) == 1
    assert out[0] == ["", "N", "Pass-Fail", "Win-:Uncertain", "Loss-Uncertain"]


def test_suffix_fold_does_not_fire_when_top_does_not_end_open_punct():
    rows = [
        ["", "Mean"],
        ["X", "difference"],
    ]
    out = _fold_suffix_continuation_columns([list(r) for r in rows])
    assert out == rows


def test_suffix_fold_does_not_fire_when_bottom_starts_with_digit():
    rows = [
        ["", "Section-"],
        ["", "1.2"],
    ]
    out = _fold_suffix_continuation_columns([list(r) for r in rows])
    assert out == rows


def test_suffix_fold_keeps_row1_when_some_cells_dont_merge():
    rows = [
        ["", "Win-",      "Real header A"],
        ["", "Uncertain", "Real header B"],
    ]
    out = _fold_suffix_continuation_columns([list(r) for r in rows])
    assert len(out) == 2
    assert out[0] == ["", "Win-Uncertain", "Real header A"]
    assert out[1] == ["", "", "Real header B"]


def test_suffix_fold_no_op_for_single_row_header():
    rows = [["Win-:", "Loss-"]]
    out = _fold_suffix_continuation_columns([list(r) for r in rows])
    assert out == rows


def test_suffix_fold_no_op_for_3_row_header():
    rows = [
        ["", "A-", "B-"],
        ["", "X",  "Y"],
        ["", "Z",  "W"],
    ]
    out = _fold_suffix_continuation_columns([list(r) for r in rows])
    assert out == rows


# ---------------------------------------------------------------------------
# _split_mashed_cell
# ---------------------------------------------------------------------------


def test_mash_split_camel_case_with_long_left_word():
    out = _split_mashed_cell("Original domain groupEasy domain group")
    rendered = out.replace(_MERGE_SEPARATOR, "<br>")
    assert rendered == "Original domain group<br>Easy domain group"


def test_mash_split_letter_digit_with_long_left_word():
    out = _split_mashed_cell("Sample size80")
    rendered = out.replace(_MERGE_SEPARATOR, "<br>")
    assert rendered == "Sample size<br>80"


def test_mash_split_does_not_split_short_left_word():
    out = _split_mashed_cell("macOS Big Sur")
    assert _MERGE_SEPARATOR not in out
    assert out == "macOS Big Sur"


def test_mash_split_does_not_split_iphone_or_ordinal():
    assert _MERGE_SEPARATOR not in _split_mashed_cell("iPhone")
    assert _MERGE_SEPARATOR not in _split_mashed_cell("WiFi")
    assert _MERGE_SEPARATOR not in _split_mashed_cell("Hypothesis 2a")
    assert _MERGE_SEPARATOR not in _split_mashed_cell("H1")


def test_mash_split_does_not_split_camel_case_brand_names():
    assert _MERGE_SEPARATOR not in _split_mashed_cell("JavaScript")
    assert _MERGE_SEPARATOR not in _split_mashed_cell("WordPress")
    assert _MERGE_SEPARATOR not in _split_mashed_cell("the JavaScript runtime")
    assert _MERGE_SEPARATOR not in _split_mashed_cell("uses WordPress on macOS")


def test_mash_split_relaxed_3char_with_whitespace_anchor():
    out = _split_mashed_cell("Risk is lowPositive affect")
    rendered = out.replace(_MERGE_SEPARATOR, "<br>")
    assert rendered == "Risk is low<br>Positive affect"

    out2 = _split_mashed_cell("Benefit is lowNegative affect")
    rendered2 = out2.replace(_MERGE_SEPARATOR, "<br>")
    assert rendered2 == "Benefit is low<br>Negative affect"


def test_mash_split_relaxed_anchored_at_string_start():
    out = _split_mashed_cell("lowPositive affect")
    rendered = out.replace(_MERGE_SEPARATOR, "<br>")
    assert rendered == "low<br>Positive affect"


def test_mash_split_relaxed_does_not_split_macos_in_prose():
    out = _split_mashed_cell("running on macOS daily")
    assert _MERGE_SEPARATOR not in out


def test_mash_split_relaxed_does_not_split_two_caps_in_a_row():
    out = _split_mashed_cell("the lowCI bound")
    assert _MERGE_SEPARATOR not in out


def test_mash_split_letter_digit_with_capital_start_word():
    out = _split_mashed_cell("Year2011 or earlier")
    rendered = out.replace(_MERGE_SEPARATOR, "<br>")
    assert rendered == "Year<br>2011 or earlier"


def test_mash_split_handles_us_initials_after_long_word():
    out = _split_mashed_cell("U.S. American studentsU.S. American students")
    rendered = out.replace(_MERGE_SEPARATOR, "<br>")
    assert rendered == "U.S. American students<br>U.S. American students"


# ---------------------------------------------------------------------------
# _drop_running_header_rows + _is_running_header_cell
# ---------------------------------------------------------------------------


def test_running_header_cell_pure_page_number():
    assert _is_running_header_cell("725")
    assert _is_running_header_cell("1236")
    assert _is_running_header_cell(" 232 ")
    assert not _is_running_header_cell("12345")
    assert not _is_running_header_cell("0.5")


def test_running_header_cell_pipe_prefixed():
    assert _is_running_header_cell("|232 Stacey et al.")
    assert _is_running_header_cell("| 232")


def test_running_header_cell_journal_caps():
    assert _is_running_header_cell("COGNITION AND EMOTION 1231")
    assert _is_running_header_cell("JOURNAL OF SCIENCE 42")


def test_running_header_cell_author_only():
    assert _is_running_header_cell("Nussio")
    assert _is_running_header_cell("Stacey et al.")
    assert _is_running_header_cell("Smith and Jones")


def test_running_header_cell_does_not_match_punctuated_headers():
    assert not _is_running_header_cell("p-value")
    assert not _is_running_header_cell("95% CI")
    assert not _is_running_header_cell("T-statistic")
    assert not _is_running_header_cell("Sample size")
    assert _is_weak_running_header("Mean")
    assert not _is_strong_running_header("Mean")


def test_drop_running_header_rows_drops_top_row_with_pure_numbers():
    grid = [
        ["Nussio", "725"],
        ["Variable", "Mean"],
        ["Trust", "1.5"],
    ]
    out = _drop_running_header_rows(grid)
    assert len(out) == 2
    assert out[0] == ["Variable", "Mean"]
    assert out[1] == ["Trust", "1.5"]


def test_drop_running_header_rows_drops_multiple_top_rows():
    grid = [
        ["725", "726"],
        ["COGNITION AND EMOTION 1231", ""],
        ["Variable", "Mean"],
        ["Trust", "1.5"],
    ]
    out = _drop_running_header_rows(grid)
    assert len(out) == 2
    assert out[0] == ["Variable", "Mean"]


def test_drop_running_header_rows_preserves_row_with_real_content():
    grid = [
        ["Variable", "Mean"],
        ["Trust", "1.5"],
    ]
    out = _drop_running_header_rows(grid)
    assert out == grid


def test_drop_running_header_rows_does_not_drop_below_2_rows():
    grid = [
        ["725", ""],
        ["726", ""],
    ]
    out = _drop_running_header_rows(grid)
    assert len(out) == 2


def test_drop_running_header_rows_skips_empty_top_row():
    grid = [
        ["", ""],
        ["Variable", "Mean"],
    ]
    out = _drop_running_header_rows(grid)
    assert out == grid


def test_drop_running_header_rows_blanks_in_row_strong_rh_cell():
    grid = [
        ["1236", "Target article", "Replication", "Reason for change"],
        ["Study design", "between", "between", "—"],
        ["Sample size",  "100",     "200",      "+100"],
    ]
    out = _drop_running_header_rows(grid)
    assert len(out) == 3
    assert out[0] == ["", "Target article", "Replication", "Reason for change"]


# ---------------------------------------------------------------------------
# _merge_significance_marker_rows
# ---------------------------------------------------------------------------


def _sup(marker: str) -> str:
    return f"{_SUP_OPEN}{marker}{_SUP_CLOSE}"


def test_merge_sig_marker_row_attaches_to_estimate_row():
    rows = [
        ["Mother born in USA", "3.02", "0.54", "0.64", "0.67"],
        ["",                    "(1.34)", "(0.13)", "(0.12)", "(0.12)"],
        ["",                    "∗",      "∗∗",     "∗",      "∗"],
        ["Mother age 14 rural", "0.91", "1.10", "1.07", "1.08"],
    ]
    out = _merge_significance_marker_rows(rows)
    assert len(out) == 3
    assert out[0] == [
        "Mother born in USA",
        f"3.02{_sup('∗')}",
        f"0.54{_sup('∗∗')}",
        f"0.64{_sup('∗')}",
        f"0.67{_sup('∗')}",
    ]
    assert out[1] == ["", "(1.34)", "(0.13)", "(0.12)", "(0.12)"]
    escaped = _html_escape(out[0][1])
    assert escaped == "3.02<sup>∗</sup>"


def test_merge_sig_marker_skips_non_marker_row():
    rows = [
        ["Variable", "1.0", "2.0"],
        ["",         "*",   "footnote text"],
    ]
    out = _merge_significance_marker_rows(rows)
    assert len(out) == 2
    assert out[1] == ["", "*", "footnote text"]


def test_merge_sig_marker_handles_no_target_above():
    rows = [
        ["", "*", "**"],
        ["Header A", "Header B", "Header C"],
    ]
    out = _merge_significance_marker_rows(rows)
    assert len(out) == 2
    assert out[0] == ["", "*", "**"]


def test_merge_sig_marker_walks_past_se_row():
    rows = [
        ["Variable", "1.0", "2.0", "3.0"],
        ["",         "(0.1)", "(0.2)", "(0.3)"],
        ["",         "(extra notes)", "", ""],
        ["",         "*",     "**",    "*"],
    ]
    out = _merge_significance_marker_rows(rows)
    assert len(out) == 3
    assert out[0] == [
        "Variable",
        f"1.0{_sup('*')}",
        f"2.0{_sup('**')}",
        f"3.0{_sup('*')}",
    ]


def test_merge_sig_marker_preserves_dagger_markers():
    rows = [
        ["Var", "1.0", "2.0"],
        ["",    "†",   "‡"],
    ]
    out = _merge_significance_marker_rows(rows)
    assert len(out) == 1
    assert out[0] == ["Var", f"1.0{_sup('†')}", f"2.0{_sup('‡')}"]


def test_merge_sig_marker_skips_empty_target_cell():
    rows = [
        ["Var", "1.0", "", "3.0"],
        ["",    "*",   "**", "*"],
    ]
    out = _merge_significance_marker_rows(rows)
    assert len(out) == 1
    assert out[0] == ["Var", f"1.0{_sup('*')}", "", f"3.0{_sup('*')}"]


def test_merge_sig_marker_preserves_row_when_no_attach_possible():
    rows = [
        ["Var", "", "", ""],
        ["",    "*", "**", "*"],
    ]
    out = _merge_significance_marker_rows(rows)
    assert len(out) == 2
    assert out[1] == ["", "*", "**", "*"]


def test_merge_sig_marker_does_not_attach_to_text_anchor_row():
    rows = [
        ["0 ACEs", "Ref.", "Ref.", "Ref."],
        ["",       "*",    "**",   "*"],
        ["1 ACE",  "2.25", "0.56", "0.74"],
    ]
    out = _merge_significance_marker_rows(rows)
    assert len(out) == 2
    assert out[0] == ["0 ACEs", "Ref.", "Ref.", "Ref."]
    assert out[1] == [
        "1 ACE",
        f"2.25{_sup('*')}",
        f"0.56{_sup('**')}",
        f"0.74{_sup('*')}",
    ]


def test_a8_forward_attach_after_text_anchor():
    rows = [
        ["0 ACEs", "Ref.", "Ref.", "Ref.", "Ref."],
        ["",       "***",  "***",  "**",   "**"],
        ["1 ACE",  "2.25", "0.56", "0.74", "0.76"],
    ]
    out = _merge_significance_marker_rows(rows)
    assert len(out) == 2
    assert out[0] == ["0 ACEs", "Ref.", "Ref.", "Ref.", "Ref."]
    assert out[1] == [
        "1 ACE",
        f"2.25{_sup('***')}",
        f"0.56{_sup('***')}",
        f"0.74{_sup('**')}",
        f"0.76{_sup('**')}",
    ]


def test_a8_does_not_forward_attach_when_back_attach_works():
    rows = [
        ["Var1", "1.0", "2.0", "3.0"],
        ["",     "*",   "**",  "***"],
        ["Var2", "4.0", "5.0", "6.0"],
    ]
    out = _merge_significance_marker_rows(rows)
    assert len(out) == 2
    assert out[0] == [
        "Var1", f"1.0{_sup('*')}", f"2.0{_sup('**')}", f"3.0{_sup('***')}",
    ]
    assert out[1] == ["Var2", "4.0", "5.0", "6.0"]


def test_a8_does_not_forward_attach_when_no_text_anchor_above():
    rows = [
        ["",       "*",    "**",   "***"],
        ["1 ACE",  "2.25", "0.56", "0.74"],
    ]
    out = _merge_significance_marker_rows(rows)
    assert len(out) == 2
    assert out[0] == ["", "*", "**", "***"]
    assert out[1] == ["1 ACE", "2.25", "0.56", "0.74"]


def test_a8_does_not_forward_attach_when_next_is_not_numeric():
    rows = [
        ["0 ACEs", "Ref.", "Ref.", "Ref."],
        ["",       "*",    "**",   "*"],
        ["1 ACE",  "Ref.", "Ref.", "Ref."],
    ]
    out = _merge_significance_marker_rows(rows)
    assert len(out) == 3
    assert out[1] == ["", "*", "**", "*"]


def test_merge_sig_marker_only_merges_columns_with_markers():
    rows = [
        ["Var", "1.0", "2.0", "3.0"],
        ["",    "*",   "",    "**"],
    ]
    out = _merge_significance_marker_rows(rows)
    assert len(out) == 1
    assert out[0] == ["Var", f"1.0{_sup('*')}", "2.0", f"3.0{_sup('**')}"]


# ---------------------------------------------------------------------------
# _strip_leader_dots
# ---------------------------------------------------------------------------


def test_strip_leader_dots_removes_long_run():
    s = "behaviour" + _MERGE_SEPARATOR + ". " * 50 + "."
    out = _strip_leader_dots(s)
    assert out == "behaviour"


def test_strip_leader_dots_preserves_short_dot_runs():
    cases = [
        "e.g. some example",
        "i.e. another",
        "5. Numbered list item",
        "Hello. World!",
        ". . one two",
        ". . . three",
    ]
    for c in cases:
        assert _strip_leader_dots(c) == c.strip(), f"changed: {c!r}"


def test_strip_leader_dots_handles_inline_run():
    s = "label . . . . . . . . . . . . . . value"
    out = _strip_leader_dots(s)
    assert out in ("label  value", "label value")


def test_strip_leader_dots_cleans_doubled_br_placeholders():
    s = "chase" + _MERGE_SEPARATOR + ". " * 50 + _MERGE_SEPARATOR + "ram"
    out = _strip_leader_dots(s)
    assert out == "chase" + _MERGE_SEPARATOR + "ram"


def test_strip_leader_dots_strips_trailing_br():
    s = "bite" + _MERGE_SEPARATOR + ". " * 50
    out = _strip_leader_dots(s)
    assert out == "bite"


def test_strip_leader_dots_empty_input():
    assert _strip_leader_dots("") == ""
    assert _strip_leader_dots(None) is None
