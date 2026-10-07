"""Wrapped table lines rejoin their row; a table closed by its note keeps its body.

Case studies: 10.1177/01461672251327169 (Ip & Feldman 2025, PSPB) — Table 4 (p7),
Table 6 (p11), Table 8 (p13), Table 9 (p14), each read on the page raster
2026-10-07. Cell strings below are the printed cells of those tables.
"""
from __future__ import annotations

from docpluck.extract_structured import (
    _extract_table_body_text_and_reason,
    _note_closed_body_end,
)
from docpluck.tables.captions import CaptionMatch
from docpluck.tables.cell_cleaning import _MERGE_SEPARATOR, _merge_continuation_rows

V = ["78.79", "45.76", "−33.02"]


def test_lowercase_label_wraps_join_the_row_label():
    rows = [
        ["Negative experiences", "", "", ""],
        ["Thought about", *V],
        ["enormous", "", "", ""],
        ["workload", "", "", ""],
        ["Overall positive and", "70.24", "50.48", "−19.77"],
        ["negative combined", "", "", ""],
    ]
    out = _merge_continuation_rows([r[:] for r in rows])
    assert [r[0] for r in out] == [
        "Negative experiences",
        "Thought about enormous workload",
        "Overall positive and negative combined",
    ]
    assert out[1][1:] == V


def test_capitalised_label_only_row_stays_a_section_row():
    rows = [["Had fight/argument", *V], ["Positive experiences", "", "", ""], ["Had great meal", *V]]
    out = _merge_continuation_rows([r[:] for r in rows])
    assert [r[0] for r in out] == ["Had fight/argument", "Positive experiences", "Had great meal"]


def test_label_and_text_cell_wrapped_on_one_line():
    rows = [
        ["Participated in", "54.04", "−14.59", "Signal; opposite"],
        ["athletics", "", "", "direction"],
    ]
    out = _merge_continuation_rows([r[:] for r in rows])
    assert len(out) == 1
    assert out[0][0] == "Participated in athletics"
    assert out[0][3] == "Signal; opposite" + _MERGE_SEPARATOR + "direction"
    assert out[0][1:3] == ["54.04", "−14.59"]


def test_one_word_text_cell_wrap_joins_its_cell():
    rows = [["Loneliness", ".81", "−.30**", "Signal; inconsistent"], ["", "", "", "opposite"]]
    out = _merge_continuation_rows([r[:] for r in rows])
    assert len(out) == 1
    assert out[0][3] == "Signal; inconsistent" + _MERGE_SEPARATOR + "opposite"


def test_word_under_a_value_is_not_a_text_wrap():
    rows = [["Loneliness", ".81", "−.30**", ".08"], ["", "", "", "opposite"]]
    out = _merge_continuation_rows([r[:] for r in rows])
    assert len(out) == 2
    assert out[0][3] == ".08"


def test_a_row_with_its_own_values_is_not_glued_to_the_row_above():
    rows = [
        ["Overall negative", "69.64", "46.08", "−23.56", "16.40", "−4.30", "5"],
        ["", "Overall negative: target article (Study 3)", "", "−21.4", "8.7", "−5.99", "5"],
    ]
    out = _merge_continuation_rows([r[:] for r in rows])
    assert len(out) == 2
    assert out[0][3] == "−23.56" and out[1][3] == "−21.4"
    assert out[1][1] == "Overall negative: target article (Study 3)"


def test_stacked_ci_line_joins_the_coefficients_above():
    rows = [
        ["2—Prevalence estimates for", "54.9", "16.1", "—", "0.54***", ""],
        ["positive emotions", "", "", "", "[0.48, 0.60]", ""],
        ["4—Intensity estimates of", "54.2", "15.7", "—", "0.58***", "0.35***"],
        ["negative emotions (extension)", "", "", "", "[0.53, 0.63]", "[0.28, 0.42]"],
    ]
    out = _merge_continuation_rows([r[:] for r in rows])
    assert len(out) == 2
    assert out[0][0] == "2—Prevalence estimates for positive emotions"
    assert out[0][4] == "0.54*** [0.48, 0.60]"
    assert out[1][4:] == ["0.58*** [0.53, 0.63]", "0.35*** [0.28, 0.42]"]


def test_ci_beside_a_capitalised_label_is_its_own_row():
    rows = [["Age", "24.3", "0.54***"], ["Positive emotions", "", "[0.48, 0.60]"]]
    out = _merge_continuation_rows([r[:] for r in rows])
    assert len(out) == 2
    assert out[0][2] == "0.54***"


# --- a table body closed by its own note --------------------------------------

_CAPTION = "Table 4. Replication and Extension: Experimental Design and Measures."
_BODY = (
    "IV1: positive vs. negative\n"
    "emotions (within; all\n"
    "participants rated both)\n"
    "Self ratings\n"
    "IV1: estimation of negative emotional events\n"
    "1. Had a fight or argument\n"
    "DV1: prevalence and intensity of own emotional experiences [replication + extension]\n"
    "“For each of the following emotional experiences, please indicate whether you have experienced those\n"
    "sometime in the past 2 weeks and if you have—the intensity of the emotion.\n"
    "Loneliness [replication]\n"
    "(1 = Never to 4 = Often)\n"
)
_NOTE = "Note. All materials are provided in the survey export provided in the OSF folder.\n"
_PROSE = (
    "Depressive Symptoms. We measured depressive symptoms using the 10-item short-form version of the "
    "scale, and respondents indicated the frequency of events in the week prior on the items.\n"
)


def _cap(text: str) -> CaptionMatch:
    return CaptionMatch(
        kind="table", number=4, label="Table 4", page=7,
        char_start=0, char_end=len(_CAPTION), line_text=_CAPTION,
    )


def test_note_closed_table_keeps_its_sentence_shaped_rows():
    text = _CAPTION + "\n" + _BODY + _NOTE + _PROSE
    body, reason = _extract_table_body_text_and_reason(text, _cap(text))
    assert reason is None
    assert "Loneliness [replication]" in body
    assert "(1 = Never to 4 = Often)" in body
    assert body.rstrip().endswith("OSF folder.")
    assert "Depressive Symptoms" not in body


def test_without_a_note_the_prose_stop_still_ends_the_body():
    text = _CAPTION + "\n" + _BODY + _PROSE
    body, _ = _extract_table_body_text_and_reason(text, _cap(text))
    assert "DV1: prevalence" in body
    assert "Loneliness [replication]" not in body


def test_a_note_on_the_next_page_does_not_close_this_table():
    text = _CAPTION + "\n" + _BODY + _PROSE + "\f" + _NOTE
    assert _note_closed_body_end(text, len(_CAPTION) + 1, None) is None


def test_a_note_past_the_next_caption_does_not_close_this_table():
    text = _CAPTION + "\n" + _BODY + "Table 5. Next.\n" + _NOTE
    nb = text.index("Table 5.")
    assert _note_closed_body_end(text, len(_CAPTION) + 1, nb) is None


# --- flatten: a label printed one column right of the stub ---------------------


def test_indented_label_moves_to_the_label_column():
    from docpluck.tables.flatten import _promote_indented_label

    row = ["", "Overall negative: target article (Study 3)", "", "−21.4", "8.7", "—", "<.01"]
    out = _promote_indented_label(row, [0])
    assert out[0] == "Overall negative: target article (Study 3)"
    assert out[1] == ""
    assert out[3:] == ["−21.4", "8.7", "—", "<.01"]


def test_a_value_is_never_promoted_to_a_label():
    from docpluck.tables.flatten import _promote_indented_label

    for row in (["", "—", "8.7"], ["", "<.01", "x y"], ["", "n.s", "3"], ["Age", "Some words here", "3"]):
        assert _promote_indented_label(list(row), [0]) == row


def test_unquoted_prose_between_caption_and_note_still_stops_the_body():
    # 10.1525/collabra.32572 Table 3 (p4): pdftotext interleaves the other
    # column's Results paragraph between the caption and the table's note.
    text = _CAPTION + "\n" + _BODY.split("\u201c")[0] + "Cash\n" + _PROSE + "Candy\nlow\n" + _NOTE
    body, _ = _extract_table_body_text_and_reason(text, _cap(text))
    assert "DV1: prevalence" in body
    assert "Depressive Symptoms" not in body
    assert "Note." not in body


def test_lowercase_line_under_a_text_only_row_is_left_alone():
    # 10.1080/02699931.2024.2434156 Table 6 (p11): the grid holds the
    # neighbouring column's prose; no row carries a number.
    rows = [
        ["IV", "Same", "", "perceived apology, affective empathy, forgiving,"],
        ["operationalisation", "", "", ""],
    ]
    out = _merge_continuation_rows([r[:] for r in rows])
    assert [r[0] for r in out] == ["IV", "operationalisation"]


def test_column_wrapped_prose_before_the_note_stops_the_body():
    # 10.1016/j.jesp.2021.104154 Table 12 (p14): the other column's Method
    # paragraph, wrapped near 70 characters, runs between the last row and the
    # note; no single line is long enough for the per-line prose test.
    prose = (
        "In this study, we asked participants to predict the replicability of\n"
        "Experiment 2 of the target article and expected hindsight bias over the\n"
        "replicability of hindsight bias.\n"
    )
    rows = "".join(f"Outcome {i}\n-.12\n-.32\n.08\n" for i in range(120))  # past 1500 chars
    text = _CAPTION + "\n" + rows + prose + _NOTE
    body, _ = _extract_table_body_text_and_reason(text, _cap(text))
    assert body.rstrip().endswith(".08")
    assert "Outcome 119" in body
    assert "In this study" not in body


def test_inside_the_old_window_the_body_is_never_shorter_than_before():
    # 10.5465/annals.2016.0011 Table 4 (p13): wrapped sentence cells inside the
    # 1500-char window were cut by a first version of the extension.
    cells = (
        "1. Determine influence of study design and sample characteristics on\n"
        "research questions and inferences (e.g., use of cross-sectional versus\n"
        "experimental studies to assess causality), and overall internal and\n"
    )
    text = _CAPTION + "\n" + _BODY.split("DV1")[0] + cells + _NOTE
    body, _ = _extract_table_body_text_and_reason(text, _cap(text))
    assert "overall internal and" in body
    assert body.rstrip().endswith("OSF folder.")


def test_label_line_over_an_unlabelled_value_row_stays_that_rows_label():
    # 10.15626/mp.2022.3108 p46 and 10.1016/j.jesp.2021.104154 Table 9 (p12).
    rows = [
        ["Mturk Sample 1: Organ donor study in the", "Opt-out default", "161", "72.7%"],
        ["temporary organ-donor condition.", "", "", ""],
        ["", "No-default (no default)", "158", "74.7%"],
    ]
    out = _merge_continuation_rows([r[:] for r in rows])
    assert out[0][2] == "161"
    assert out[1][0] == "temporary organ-donor condition."


def test_a_colon_label_heads_the_rows_below_it():
    # 10.1371/journal.pmed.1004323 Table 1 (p8) and Table 3 (p10): an indented
    # "specification:" / "if complication, specification:" row with empty value
    # cells introduces the sub-rows beneath it; it is not a wrap of the row above.
    rows = [
        ["Parity (median, IQR)", "1 (0–2)", "1 (0–2)"],
        ["Previous uterine surgery", "18 (17.0%)", "24 (23.3%)"],
        ["specification:", "", ""],
        ["hysteroscopic myomectomy", "8/18 (44.4%)", "14/24 (58.3%)"],
        ["other", "10/18 (55.6%)", "10/24 (41.7%)"],
    ]
    out = _merge_continuation_rows([r[:] for r in rows])
    assert [r[0] for r in out] == [
        "Parity (median, IQR)",
        "Previous uterine surgery",
        "specification:",
        "hysteroscopic myomectomy",
        "other",
    ]
    rows = [
        ["Anesthetic complication needing intervention", "5 (4.7%)", "4 (4.0%)", "1.19 (0.33–4.31)", "1.00"],
        ["if complication, specification:", "", "", "", ""],
        ["desaturation", "3/5 (60.0%)", "1/4 (25.0%)", "", ""],
    ]
    out = _merge_continuation_rows([r[:] for r in rows])
    assert [r[0] for r in out] == [
        "Anesthetic complication needing intervention",
        "if complication, specification:",
        "desaturation",
    ]
