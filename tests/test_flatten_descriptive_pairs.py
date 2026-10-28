"""Descriptive and coefficient cells that pack two numbers -- "M (SD)",
"n (%)", "b (SE)", "estimate [CI]" -- produce typed fields.

Until now a descriptive table flattened to label-only records: `fields` was
`{}` and the sentence was the row label, for every row of
10.1037/a0012616 Tables 1, 2 and 4 ("39.13 (10.87)" under each treatment arm,
note "Data are means (standard deviations)"), 10.1111/jasp.12453 Tables 1-2
(super-header "Means (SD)") and 10.1177/0956797615601103 Table 1
("M = 68.33, SD = 10.48"). The values reached consumers only in `raw_cells`.

What the parenthesised number IS is never guessed from the shape alone: "4.47
(0.81)" is a mean and SD, a coefficient and its SE, or a count and percentage
depending on what the table says. A pair is typed only on stated evidence:
the cell itself ("M = 4.4, SD = 0.8", "59%"), the column header ("M (SD)"),
the row label ("Age, mean (SD)"), or the table's own header rows, caption or
note ("Data are means (standard deviations)") when no other reading of the
parentheses is stated there. Each such column of a row becomes its own record,
its `group` the column header, so two arms' means are never merged into one
record.
"""
from __future__ import annotations

from docpluck.tables.flatten import flatten_table


def _table(rows, caption="Table 1. Results", footnote=None, header_rows=1):
    cells = []
    for r, row in enumerate(rows):
        for c, text in enumerate(row):
            if text:
                cells.append({"r": r, "c": c, "rowspan": 1, "colspan": 1, "text": text,
                              "is_header": r < header_rows, "bbox": (0.0, 0.0, 0.0, 0.0)})
    return {"id": "t1", "label": "Table 1", "page": 3, "cells": cells,
            "caption": caption, "footnote": footnote, "kind": "structured"}


def _recs(rows, **kw):
    return flatten_table(_table(rows, **kw))


def _by(recs):
    return {(r["row_label"], r["fields"].get("group")): r["fields"] for r in recs}


def test_note_states_means_and_sds_one_record_per_arm():
    recs = _recs(
        [["Variable", "Imaginal exposure", "In vivo exposure"],
         ["Age, in years", "39.13 (10.87)", "40.92 (15.82)"],
         ["NART score", "29.42 (10.30)", "27.67 (11.85)"],
         ["Male", "42", "25"]],
        footnote="Note. Data are means (standard deviations) unless otherwise noted.",
    )
    by = _by(recs)
    assert by[("Age, in years", "Imaginal exposure")] == {
        "group": "Imaginal exposure", "M": 39.13, "SD": 10.87}
    assert by[("Age, in years", "In vivo exposure")]["M"] == 40.92
    assert by[("NART score", "In vivo exposure")]["SD"] == 11.85
    # A bare count under a means note is not typed as a mean.
    male = [r for r in recs if r["row_label"] == "Male"]
    assert male and all("M" not in r["fields"] for r in male)
    rec = next(r for r in recs if r["row_label"] == "Age, in years")
    assert rec["fields_raw"] == {"M": "39.13", "SD": "10.87"}
    assert rec["sentence"] == "Age, in years (Imaginal exposure): M = 39.13, SD = 10.87"


def test_super_header_means_sd():
    recs = _recs(
        [["", "Means (SD)", "", ""],
         ["Condition", "Belief", "Dangers", "Intention"],
         ["Conspiracy", "4.47 (0.81)", "4.50 (1.26)", "4.42 (1.76)"],
         ["Control", "3.83 (1.12)", "3.55 (1.62)", "5.50 (1.21)"]],
        header_rows=2,
    )
    by = _by(recs)
    assert by[("Conspiracy", "Belief")] == {"group": "Belief", "M": 4.47, "SD": 0.81}
    assert by[("Control", "Intention")] == {"group": "Intention", "M": 5.5, "SD": 1.21}
    assert len(recs) == 6


def test_column_header_m_sd_single_column_joins_the_row_record():
    recs = _recs([["Measure", "M (SD)", "t", "p"],
                  ["Anxiety", "3.10 (0.90)", "2.40", ".020"],
                  ["Mood", "4.00 (1.10)", "1.10", ".280"]])
    assert len(recs) == 2
    f = recs[0]["fields"]
    assert (f["M"], f["SD"], f["t"], f["p"]) == (3.1, 0.9, 2.4, 0.02)
    assert "group" not in f


def test_two_m_sd_columns_and_a_test_column():
    recs = _recs([["Measure", "Control M (SD)", "Treatment M (SD)", "t", "p"],
                  ["Anxiety", "3.10 (0.90)", "2.50 (0.80)", "2.40", ".020"]])
    by = _by(recs)
    assert by[("Anxiety", "Control")] == {"group": "Control", "M": 3.1, "SD": 0.9}
    assert by[("Anxiety", "Treatment")] == {"group": "Treatment", "M": 2.5, "SD": 0.8}
    rest = by[("Anxiety", None)]
    assert rest["t"] == 2.4 and rest["p"] == 0.02 and "M" not in rest


def test_no_evidence_no_typing():
    recs = _recs([["Measure", "Study 1", "Study 2"],
                  ["Anxiety", "3.10 (0.90)", "2.50 (0.80)"],
                  ["Mood", "4.00 (1.10)", "3.90 (1.00)"]])
    assert all(r["fields"] == {} for r in recs)
    assert len(recs) == 2


def test_standard_errors_in_parentheses_are_not_sds():
    recs = _recs(
        [["Predictor", "Experiment 1", "Experiment 2"],
         ["Status", "1.16*** (0.28)", "0.60** (0.17)"],
         ["Constant", "–2.94*** (0.79)", "–0.81** (0.30)"]],
        footnote="Note: Robust standard errors are given in parentheses. *p < .05.",
    )
    by = _by(recs)
    assert by[("Status", "Experiment 1")] == {"group": "Experiment 1", "est": 1.16, "SE": 0.28}
    assert by[("Constant", "Experiment 2")] == {"group": "Experiment 2", "est": -0.81, "SE": 0.3}
    assert all("M" not in r["fields"] and "SD" not in r["fields"] for r in recs)


def test_conflicting_statements_type_nothing():
    recs = _recs(
        [["Variable", "Group A", "Group B"],
         ["Score", "3.10 (0.90)", "2.50 (0.80)"],
         ["Rating", "4.00 (1.10)", "3.90 (1.00)"]],
        footnote="Note. Means (SD) are shown; standard errors in parentheses for slopes.",
    )
    assert all(r["fields"] == {} for r in recs)


def test_self_labelled_cells():
    recs = _recs([["Variable", "HRS", "MIDUS"],
                  ["Age (years)", "M = 68.33, SD = 10.48", "M = 47.86, SD = 12.91"],
                  ["Female (%)", "59%", "53%"]])
    by = _by(recs)
    assert by[("Age (years)", "HRS")] == {"group": "HRS", "M": 68.33, "SD": 10.48}
    assert by[("Age (years)", "MIDUS")]["SD"] == 12.91
    assert by[("Female (%)", "MIDUS")] == {"group": "MIDUS", "pct": 53.0}


def test_row_label_states_the_pair():
    recs = _recs([["Characteristic", "Overall (N = 500)", "Treated (n = 250)"],
                  ["Age, mean (SD), y", "40.1 (10.2)", "39.8 (9.9)"],
                  ["Female, No. (%)", "260 (52.0)", "128 (51.2)"],
                  ["Smoker, No. (%)", "0 (0)", "0 (0)"],
                  ["Male (n, %)", "27 (54%)", "131 805 (95.1)"]])
    by = _by(recs)
    assert by[("Male (n, %)", "Overall (N = 500)")] == {
        "group": "Overall (N = 500)", "count": 27, "pct": 54.0}
    assert by[("Male (n, %)", "Treated (n = 250)")]["count"] == 131805
    assert by[("Age, mean (SD), y", "Overall (N = 500)")] == {
        "group": "Overall (N = 500)", "M": 40.1, "SD": 10.2}
    assert by[("Female, No. (%)", "Treated (n = 250)")] == {
        "group": "Treated (n = 250)", "count": 128, "pct": 51.2}
    assert by[("Smoker, No. (%)", "Overall (N = 500)")]["count"] == 0


def test_estimate_and_interval_under_a_stated_interval():
    # The header split is not under test here (whether an all-interval row is
    # a header row is its question): the table declares its one header row,
    # as a DOCX table does.
    t = _table(
        [["Predictor", "Model 1 (n = 13,692)", "Model 2 (n = 13,400)"],
         ["Age", "2.36 [2.26, 2.47]**", "2.34 [2.23, 2.45]**"],
         ["Gender (female)", "0.70 [0.64, 0.77]**", "0.65 [0.60, 0.72]**"],
         ["Underweight", "—", "2.55 [2.03, 3.21]**"]],
        footnote="Note: The table presents hazard ratios, with 95% confidence intervals "
                 "in brackets. **p < .01.",
    )
    t["rendering"] = "markup"
    recs = flatten_table(t)
    by = _by(recs)
    f = by[("Age", "Model 1 (n = 13,692)")]
    assert (f["est"], f["CI_lower"], f["CI_upper"]) == (2.36, 2.26, 2.47)
    assert (f["CI_level"], f["CI_kind"]) == (95.0, "CI")
    assert by[("Underweight", "Model 2 (n = 13,400)")]["est"] == 2.55
    assert ("Underweight", "Model 1 (n = 13,692)") not in by


def test_single_group_tables_are_unchanged():
    recs = _recs([["Measure", "t", "df", "p"],
                  ["Anxiety", "2.10", "48", ".050"],
                  ["Mood", "3.75", "48", "< .001"]])
    assert [r["fields"].get("t") for r in recs] == [2.1, 3.75]
    assert all("group" not in r["fields"] for r in recs)


def test_a_value_taken_for_the_header_blocks_pair_records():
    # When the header split took a data row for the header, a pair typed below
    # it would carry "2.36 [2.26, 2.47]" as its arm label: no pair records.
    from docpluck.tables import flatten as fl
    header = ["Age", "2.36 [2.26, 2.47]", "2.34 [2.23, 2.45]"]
    body = [["Gender (female)", "0.70 [0.64, 0.77]", "0.65 [0.60, 0.72]"],
            ["Black", "1.21 [1.06, 1.37]", "1.22 [1.08, 1.39]"]]
    t = _table([header] + body,
               footnote="Note: hazard ratios, with 95% confidence intervals in brackets.")
    recs = fl.flatten_table(t)
    assert all(not str(r["fields"].get("group", "")).startswith("2.") for r in recs)


# --- review cases (second-model review, 2026-10-27) -------------------------

def test_note_level_means_do_not_type_a_count_and_percentage():
    # "Data are means (SD) unless otherwise noted": the Female row prints a
    # count and a percentage. On the note's word alone a whole number is not
    # read as a mean.
    recs = _recs(
        [["Variable", "Imaginal exposure", "In vivo exposure"],
         ["Age, in years", "39.13 (10.87)", "40.92 (15.82)"],
         ["NART score", "29.42 (10.30)", "27.67 (11.85)"],
         ["Female", "12 (48)", "15 (52)"]],
        footnote="Note. Data are means (standard deviations) unless otherwise noted.",
    )
    female = [r for r in recs if r["row_label"] == "Female"]
    assert female and all("M" not in r["fields"] and "SD" not in r["fields"]
                          for r in female)
    assert _by(recs)[("Age, in years", "Imaginal exposure")]["M"] == 39.13


def test_a_column_header_m_sd_still_types_whole_numbers():
    recs = _recs([["Variable", "Control M (SD)", "Treatment M (SD)"],
                  ["Days", "12 (4)", "15 (5)"]])
    assert _by(recs)[("Days", "Control")] == {"group": "Control", "M": 12.0, "SD": 4.0}


def test_estimate_interval_key_comes_from_the_column_not_the_caption():
    # "vitamin D" in the caption names no Cohen's d.
    t = _table(
        [["Outcome", "Placebo", "Vitamin D"],
         ["Fatigue", "0.76 [0.50, 1.02]", "0.41 [0.20, 0.62]"],
         ["Pain", "0.30 [0.10, 0.50]", "0.28 [0.05, 0.51]"]],
        caption="Table 1. Effects of vitamin D supplementation",
        footnote="Note: estimates with 95% confidence intervals in brackets.",
    )
    t["rendering"] = "markup"
    f = _by(flatten_table(t))[("Fatigue", "Placebo")]
    assert "d" not in f and f["est"] == 0.76


def test_fields_raw_takes_each_number_from_its_own_position():
    recs = _recs([["Variable", "Group A", "Group B"],
                  ["Score", "0.50 (0.5)", "1.50 (1.5)"]],
                 footnote="Note. Means (SD).")
    rec = next(r for r in recs if r["fields"].get("group") == "Group A")
    assert rec["fields_raw"] == {"M": "0.50", "SD": "0.5"}
    recs = _recs([["Variable", "Group A", "Group B"],
                  ["Smokers, n (%)", "0 (0.0)", "3 (1.0)"]])
    rec = next(r for r in recs if r["fields"].get("group") == "Group A")
    assert rec["fields_raw"] == {"count": "0", "pct": "0.0"}
    t = _table([["Predictor", "Model 1", "Model 2"],
                ["Age", "0.50 [0.5, 0.9]", "0.40 [0.4, 0.8]"]],
               footnote="Note: 95% confidence intervals in brackets.")
    t["rendering"] = "markup"
    rec = next(r for r in flatten_table(t) if r["fields"].get("group") == "Model 1")
    assert rec["fields_raw"]["CI_lower"] == "0.5"
    assert rec["fields_raw"]["est"] == "0.50"


def test_a_count_printed_with_thousands_separators_keeps_them_raw():
    recs = _recs([["Characteristic", "Overall", "Treated"],
                  ["Male (n, %)", "66,471 (48.2)", "131 805 (95.1)"]])
    raw = {r["fields"]["group"]: r["fields_raw"] for r in recs if "count" in r["fields"]}
    assert raw["Overall"] == {"count": "66,471", "pct": "48.2"}
    assert raw["Treated"] == {"count": "131 805", "pct": "95.1"}


def test_the_tables_title_line_is_not_an_arm_label():
    t = _table(
        [["", "Table 2  Comparisons of procedural data between groups", "", ""],
         ["Variables", "HPSD group (n = 50)", "Conventional group (n = 50)", "P value"],
         ["Cardioversion (n, %)", "11 (22%)", "19 (38%)", "0.054"]],
        caption="Table 2 Comparisons of procedural data between groups",
        header_rows=2,
    )
    t["label"] = "Table 2"
    groups = {r["fields"].get("group") for r in flatten_table(t) if "count" in r["fields"]}
    assert groups == {"HPSD group (n = 50)", "Conventional group (n = 50)"}


def test_other_readings_of_brackets_and_parentheses_type_nothing():
    t = _table([["Variable", "Group A", "Group B"],
                ["Score", "3.10 [2.00, 4.00]", "2.50 [1.00, 3.00]"]],
               footnote="Note: medians with 95% confidence intervals in brackets.")
    t["rendering"] = "markup"
    assert all(r["fields"] == {} for r in flatten_table(t))
    recs = _recs([["Predictor", "Model 1", "Model 2"],
                  ["Status", "1.16 (2.80)", "0.60 (1.70)"]],
                 footnote="Note. Means (SD); t-values are in parentheses for slopes.")
    assert all(r["fields"] == {} for r in recs)
