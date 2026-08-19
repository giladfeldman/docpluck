"""``_drop_running_header_rows`` must not delete a COUNTS row.

## The defect (register O11), and what the register got wrong about it

The register recorded that ``cell_cleaning._drop_running_header_rows`` has no
statistical-content guard and that ``["Positive", "245", "12"]`` "qualifies for
deletion". Checked against the source on 2026-08-15: **that exact example does
NOT reproduce** — the function's own ``has_real_below`` test finds no
non-header-looking cell in a grid where every row has that shape, so it stops.

The defect is real anyway, and one case is worse than the one that was filed. It
needs a following row carrying an ordinary label:

    [["Positive", "245", "12"],                          <- DELETED entirely
     ["Mean reaction time (ms)", "452.3", "18.7"]]

    [["Control", "120", "8"],                            <- DELETED entirely
     ["Total sample size", "1240", "96"]]  ->  ["Total sample size", "", ""]
                                                  ^^^^^^^^^^^^^^^^^^^^^^^^^^
                                              and the SURVIVING row's counts
                                              were blanked as well

``_WEAK_RH_PATTERNS`` matches any single capitalised word (``Positive``,
``Control``), ``_STRONG_RH_PATTERNS`` matches any 1-4 digit integer, and a
frequency table is made of exactly those two things. So the rows deleted are
precisely a counts table — the case ``render._carries_statistical_content``
already documents as the one where bare integers ARE the data and are the only
surviving copy of them.

## The fix: the sibling implementation already had the guard

``camelot_extract._looks_like_running_header`` rejects any row with more than two
populated cells, on the reasoning that a running header is a name and a page
number while a data row fills the grid. ``cell_cleaning``'s copy of the same
concept never had that cap. One concept, two implementations, and they diverged —
the drift this project has a standing rule about.

Reproduced against the unfixed code before the fix: both DELETED cases above
returned the truncated grid, and the ``Total sample size`` row came back as
``["Total sample size", "", ""]``.
"""

from __future__ import annotations

from docpluck.tables.cell_cleaning import _drop_running_header_rows


def test_a_counts_row_is_not_deleted_as_a_running_header():
    rows = [
        ["Positive", "245", "12"],
        ["Mean reaction time (ms)", "452.3", "18.7"],
    ]
    assert _drop_running_header_rows(rows) == rows


def test_a_surviving_rows_counts_are_not_blanked():
    """The second half of the function blanks every 'strong' cell of the top row
    when the row also holds a real label — which wipes the counts off a genuine
    data row."""
    rows = [
        ["Control", "120", "8"],
        ["Total sample size", "1240", "96"],
    ]
    out = _drop_running_header_rows(rows)
    assert out == rows, f"published counts were blanked: {out}"


def test_decimal_data_was_already_safe_and_stays_safe():
    """Pins the case that never broke, so a future 'fix' cannot regress it while
    the two above pass."""
    rows = [
        ["Anxiety", "3.42", "0.88"],
        ["Depression score (BDI-II)", "2.10", "0.71"],
    ]
    assert _drop_running_header_rows(rows) == rows


def test_a_real_running_header_is_still_dropped():
    """The guard must not be disarmed. A genuine leaked running header is a name
    and a page number — two populated cells, not a filled data row. Paired with
    the tests above so an absence assertion cannot be satisfied by data loss."""
    rows = [
        ["Ip and Feldman", "42"],
        ["Predictor", "b"],
        ["Age", "0.12"],
    ]
    out = _drop_running_header_rows(rows)
    assert out == rows[1:], f"the running header survived: {out}"


def test_a_page_number_only_row_is_still_dropped():
    rows = [
        ["", "1179"],
        ["Predictor", "b"],
        ["Age", "0.12"],
    ]
    out = _drop_running_header_rows(rows)
    assert out == rows[1:], f"the page-number row survived: {out}"


def test_the_deletion_is_recorded():
    """``cell_cleaning`` had ZERO telemetry — the register called it the darkest
    channel. A row removal that leaves no trace cannot be measured, and this one
    was removing published counts."""
    from docpluck.telemetry import fallback_scope

    rows = [
        ["Ip and Feldman", "42"],
        ["Predictor", "b"],
        ["Age", "0.12"],
    ]
    with fallback_scope() as fb:
        _drop_running_header_rows(rows)
    assert any(k.startswith("cell_cleaning_") for k in fb.counters), (
        f"a row was deleted with no telemetry at all: {fb.counters}"
    )
