"""A page number or a figure's axis scale is not a statistic that saves a grid.

10.1177/0956797610361706 (measured 2026-10-23, docpluck 2.4.154 tree): four
uncaptioned candidates reached the rendered markdown's appendix. Every line of
every cell of each is found word for word on its own page -- they are copies --
and three were kept ONLY because the statistics veto in
`extract_structured._candidate_is_page_running_text` fired on a number that is
not data:

  p3, p7  "442 | Mortensen et al." -- the folio of the running head, gridded with
          the page's first body line;
  p4      "4.3, 4.2, ..., 3.3" + "Big Five Personality Trait Score" -- Figure 1's
          y-axis scale and title.

A folio (a bare integer printed as its page's first or last line) and an axis
scale (>= 4 bare numbers in one column with one constant step) are now set aside
before the veto and the word count. Everything else is unchanged: the p5
candidate, whose prose cells carry real percentages ("accuracy = 99.32%"), is
still kept -- the control.
"""

from pathlib import Path

import pytest

from conftest import pdf_path

pytest.importorskip("camelot", reason="camelot not installed (pip install docpluck[all])")

_EVENT = "camelot_candidate_is_page_running_text"


@pytest.fixture(scope="module")
def result():
    p = Path(pdf_path("articlerepo", "10.1177__0956797610361706.pdf"))
    if not p.is_file():
        pytest.fail(f"fixture not readable: {p} -- a gate that cannot read its paper must fail, never skip")
    from docpluck.extract_structured import extract_pdf_structured

    return extract_pdf_structured(p.read_bytes())


def _candidate_pages(r):
    return sorted(t["page"] for t in r["tables"] if t.get("caption_status") == "uncaptioned_candidate")


def test_folio_and_axis_grids_are_deduplicated_and_recorded(result):
    assert 3 not in _candidate_pages(result), "running-head grid (folio 442) still kept"
    assert 4 not in _candidate_pages(result), "Figure 1 axis-scale grid still kept"
    assert 7 not in _candidate_pages(result), "running-head grid (folio 446) still kept"
    assert result["fallbacks"].get(_EVENT, 0) >= 3, result["fallbacks"]


def test_a_grid_whose_prose_carries_statistics_is_still_kept(result):
    assert 5 in _candidate_pages(result), "control: the p5 grid carries real percentages"


def test_the_helpers_two_sided():
    from docpluck.extract_structured import _axis_scale_cells, _folio_cells

    page = "442\t\t\n\nMortensen et al.\n\nresponse to disease salience\n"
    cells = [{"text": "442", "r": 0, "c": 0}, {"text": "Mortensen et al.", "r": 0, "c": 1}]
    assert _folio_cells(cells, page) == {0}
    assert _folio_cells([{"text": "442", "r": 3, "c": 0}], "Results\n\n442 participants\n") == set()

    ticks = [{"text": t, "r": i, "c": 1} for i, t in enumerate(["4.3", "4.2", "4.1", "4.0", "3.9"])]
    assert _axis_scale_cells(ticks) == set(range(5))
    data = [{"text": t, "r": i, "c": 1} for i, t in enumerate(["4.3", "4.1", "4.0", "3.2", "3.9"])]
    assert _axis_scale_cells(data) == set(), "uneven steps are data, not an axis"
    short = [{"text": t, "r": i, "c": 1} for i, t in enumerate(["1", "2", "3"])]
    assert _axis_scale_cells(short) == set(), "three values are too few to call a scale"
    # Rows numbered downward are a table's item column, not a y-axis (a y-axis
    # DEcreases down the page). 10.1098/rsos.250979 p14 numbers its problems
    # 18, 19, 20, ... and lost the whole table when rising runs were taken.
    items = [{"text": t, "r": i, "c": 0} for i, t in enumerate(["18", "19", "20", "21", "22"])]
    assert _axis_scale_cells(items) == set(), "rising row numbers are data, not an axis"
