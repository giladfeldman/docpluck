"""Unit tests for the figure-caption chart-data trim, on the copy production runs.

These tests used to live in ``tests/test_figure_detect.py`` and import
``docpluck.figures.detect._trim_caption_at_chart_data`` -- a SECOND copy of this
function, in a module nothing in production imported. ``extract_pdf_structured``
builds every Figure through ``extract_structured._extract_caption_text``, which
calls ``extract_structured._trim_caption_at_chart_data``, so the tests were
guarding code that never ran while the live copy (which has since grown two more
signatures, see ``test_chart_data_trim_real_pdf.py``) had no synthetic coverage.
``figures/detect.py`` was deleted on 2026-09-25; the tests were pointed at the live
copy unchanged, and every one passes there.
"""

from __future__ import annotations


# v2.4.3: caption truncation at chart-data boundary
# (digit runs ≥ 6 chars indicate pdftotext joined raw chart values into the
# caption paragraph — common in clinical / biological flowcharts).


def test_trim_caption_at_chart_data_truncates_long_digit_run():
    from docpluck.extract_structured import _trim_caption_at_chart_data
    cap = (
        "Figure 1. Flowchart of Study Sample Selection 4876956 Pairs enrolled "
        "before April 1, 2015 1117269 Pairs excluded 741469 Withdrawal 148414 "
        "Withdrawal after baseline 137787 With spouses onset of CVD 84585 "
        "With onset of depression 5014 Duplicated couples 3792142 Eligible "
        "pairs Matched by age and income"
    )
    out = _trim_caption_at_chart_data(cap)
    # 6-digit run "4876956" triggers truncation just before it.
    assert out == "Figure 1. Flowchart of Study Sample Selection"
    assert "4876956" not in out


def test_trim_caption_preserves_short_caption():
    from docpluck.extract_structured import _trim_caption_at_chart_data
    cap = "Figure 2. A short caption with a year reference 2020 here."
    out = _trim_caption_at_chart_data(cap)
    # Under 150-char threshold AND no 6-digit run; no-op.
    assert out == cap


def test_trim_caption_preserves_legitimate_5digit_numbers():
    from docpluck.extract_structured import _trim_caption_at_chart_data
    cap = (
        "Figure 3. Sample selection diagram including all participants from "
        "the original cohort (N = 12345) and the analytic subsample of 9876 "
        "individuals who completed both waves of the longitudinal survey "
        "between 2018 and 2024 with no missing data on the focal outcomes."
    )
    out = _trim_caption_at_chart_data(cap)
    # 5-digit "12345" does NOT trigger; whole caption preserved.
    assert out == cap


def test_trim_caption_preserves_prose_with_no_digits():
    from docpluck.extract_structured import _trim_caption_at_chart_data
    cap = (
        "Figure 4. Cumulative incidence of depression by spouses cardiovascular "
        "event among the entire study sample. The horizontal axis shows the "
        "time in months and the vertical axis is cumulative incidence of "
        "depression in percent. Lines represent the four sex-age subgroups."
    )
    out = _trim_caption_at_chart_data(cap)
    # No 6-digit run; full caption preserved.
    assert out == cap


def test_trim_caption_keeps_minimum_post_label_content():
    from docpluck.extract_structured import _trim_caption_at_chart_data
    # 6-digit run lands right after the label — truncation would leave
    # just "Figure 1." (under 40-char sanity check) — return original.
    short_pre_label = "Figure 5. 1234567 chart data " + "y" * 200
    out = _trim_caption_at_chart_data(short_pre_label)
    # Sanity check fires; return original.
    assert out == short_pre_label

    # The OTHER case the docstring describes — a digit run far AFTER the label,
    # where truncation leaves plenty of content and is therefore allowed. This
    # fixture was built and then never exercised (bound to `long_cap` and
    # dropped), so the test named "keeps minimum post-label content" only ever
    # checked the branch that returns the input unchanged. Restored 2026-08-15.
    long_cap = "Figure 5. " + "x" * 200 + " 1234567 stuff"
    out_long = _trim_caption_at_chart_data(long_cap)
    assert out_long.startswith("Figure 5. "), "the label must survive trimming"
    assert len(out_long) >= 40, "trimming must respect the minimum-content check"


# v2.4.4: caption truncation extended to short-token tick runs (5+ short
# numeric tokens in a row — axis-tick label sequences from charts).


def test_trim_caption_at_tick_run_truncates_axis_labels():
    """v2.4.4: detect chart axis-tick sequences (5+ short numeric tokens
    separated only by whitespace) — jama_open_3-style Kaplan-Meier
    captions absorb gridline values like ``0 0 5 10 15`` that the 6-digit
    rule didn't catch."""
    from docpluck.extract_structured import _trim_caption_at_chart_data
    cap = (
        "Figure 1. Unadjusted Kaplan-Meier Curves Across Groups With "
        "Different Objective Sleep Duration for All-Cause Mortality 100 "
        "90 Survival probability, % 80 70 Sleep duration 60 seven hours "
        "6 to 7 hours 50 5 to 6 hours less than 5 hours 0 0 5 10 15 "
        "Follow-up time y No at risk Sleep duration seven hours 340 321 "
        "280 5 Sleep duration"
    )
    out = _trim_caption_at_chart_data(cap)
    assert "0 0 5 10 15" not in out
    # Trim should preserve the prose lead-in.
    assert out.startswith("Figure 1. Unadjusted Kaplan-Meier Curves")


def test_trim_caption_preserves_legitimate_prose_with_inline_numbers():
    """Real caption prose references numbers in stats ('n = 1234', 'p < .001'),
    but each number is followed by a word — not 5+ stacked numerics in a row."""
    from docpluck.extract_structured import _trim_caption_at_chart_data
    cap = (
        "Figure 2. Mean reaction times across the four experimental "
        "conditions, with n = 1234 participants total (95% CI [120.5, "
        "180.3] ms for condition A; 95% CI [110.2, 175.4] for condition "
        "B). Significant differences observed at p < .001 between paired "
        "conditions in all 4 contrasts of interest, as predicted."
    )
    out = _trim_caption_at_chart_data(cap)
    assert out == cap


def test_trim_caption_picks_earliest_match_across_both_rules():
    """When both the 6-digit-run and the 5-token-tick rules match,
    truncate at the earlier offset so we don't keep chart data past the
    first signal."""
    from docpluck.extract_structured import _trim_caption_at_chart_data
    # Tick run appears first; 6-digit run appears later.
    cap = (
        "Figure 3. Bar plot of conditions A through F across the years "
        "of interest 2020 2021 2022 2023 2024 2025 with later analytic "
        "subsample participant total 4876956 in the secondary cohort "
        "described in the methods section above and detailed in the "
        "supplementary materials accompanying this paper."
    )
    out = _trim_caption_at_chart_data(cap)
    # The tick run "2020 2021 2022 2023 2024 2025" appears earlier; trim
    # there.
    assert "2020 2021" not in out
    assert "4876956" not in out
