"""A caption's last line belongs to the caption, not to the table's header.

10.1177/01461672251327169: Table 9 (p14) lost its caption's last line
("... Study 3 Versus" / "Replication."), and Table 10 (p15) carried its
caption's second line as the first header cell ("Outcomes (Extension).<br>Measure").
"""

from __future__ import annotations

from docpluck.extract_structured import _trim_table_caption_at_cell_region
from docpluck.tables.caption_rows import _caption_rows_at_top


def test_a_title_line_ending_on_a_connective_keeps_its_closing_line():
    region = (
        "Table 9. Prevalence Estimates Regression Coefficients Study 3 Versus\n"
        "Replication.\nJordan et al. (2011)\n\nReplication\nMeasure\n"
    )
    out = _trim_table_caption_at_cell_region(region)
    assert out.rstrip().endswith("Versus\nReplication.")


def test_a_complete_title_line_still_stops_before_the_header():
    region = (
        "Table 6. Aggregated Feelings Across Three Studies Descriptives\n"
        "Condition\nMean\nSD\nRange\n"
    )
    out = _trim_table_caption_at_cell_region(region)
    assert out.rstrip().endswith("Descriptives")


def test_a_short_caption_line_closing_the_caption_leaves_the_grid():
    rows = [
        ["Outcomes (Extension).", "", ""],
        ["Measure", "beta negative", "beta positive"],
        ["Loneliness", ".29***", "-.21***"],
    ]
    cap = "Table 10. Intensity Estimates Regression Coefficients with Outcomes (Extension)."
    assert _caption_rows_at_top(rows, "Table 10", cap) == 1


def test_a_short_spanner_without_the_closing_period_stays():
    rows = [
        ["Participant group, mean (SD)a", "", ""],
        ["Characteristic", "Treated", "Control"],
        ["Age, y", "45.1", "44.8"],
    ]
    cap = "Table 3. Baseline Characteristics by Participant group, mean (SD)a"
    assert _caption_rows_at_top(rows, "Table 3", cap) == 0
