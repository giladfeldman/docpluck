"""A text-channel copy of a table gives way to a labelled marker ONLY when the
structured grid of the same table holds every number, operator/marker and word
of it, and the copy is specific enough that the coverage is not coincidence.

Case: 10.1016/j.jesp.2009.12.011 (ar_apa) p3 Table 1 -- the body carried a
104-line one-value-per-line copy of the table whose 72 values are all in the
structured grid. Tightened after a tier-2 consult (Sonnet, 2026-10-13):
operators are compared, ranges are not negatives, small-integer runs never fire.
"""
from docpluck.render import _grid_tokens, _suppress_orphan_table_cell_text

GRID = """### Table 1

*Table 1 Practice variables.*

<table><tr><th></th><th>Mean</th><th>SD</th></tr>
<tr><td>Effort</td><td>3.10</td><td>.72</td></tr>
<tr><td>Help</td><td>2.77</td><td>.75</td></tr>
<tr><td>SSRT</td><td>211.74</td><td>64.07</td></tr></table>
"""


def _doc(run: str) -> str:
    return (
        "Body text before.\n\nTable 1\nPractice variables.\n" + run
        + "\n\n\nThe results we report next follow from the analysis plan that was preregistered.\n\n"
        + GRID
    )


def test_a_fully_covered_copy_becomes_a_marker():
    out = _suppress_orphan_table_cell_text(_doc("Effort\nHelp\nSSRT\n\nMean\nSD\n\n3.10\n2.77\n211.74\n\n.72\n.75\n64.07"))
    assert "table-text-duplicate" in out
    assert "Practice variables." in out          # caption kept
    assert "211.74" in out                       # value still in the grid
    assert out.count("211.74") == 1              # the copy is gone


def test_a_value_the_grid_lacks_keeps_the_whole_copy():
    out = _suppress_orphan_table_cell_text(_doc("Effort\nHelp\n\n3.10\n2.77\n211.74\n9.99"))
    assert "table-text-duplicate" not in out
    assert "9.99" in out


def test_an_operator_the_grid_lacks_keeps_the_copy():
    out = _suppress_orphan_table_cell_text(_doc("Effort\n3.10\n2.77\n211.74\np < .72"))
    assert "table-text-duplicate" not in out
    assert "p < .72" in out


def test_small_integer_runs_never_fire():
    grid = GRID.replace("3.10", "1").replace("2.77", "2").replace("211.74", "3")
    doc = _doc("Effort\nHelp\n1\n2\n3\n.72").replace(GRID, grid)
    assert "table-text-duplicate" not in _suppress_orphan_table_cell_text(doc)
    # Control: the same doc with specific values does fire, so the block above
    # is the specificity rule, not something else.
    assert "table-text-duplicate" in _suppress_orphan_table_cell_text(
        _doc("Effort\nHelp\n3.10\n2.77\n211.74\n.72")
    )


def test_a_range_is_not_a_negative():
    nums, _, _ = _grid_tokens("12-15")
    assert nums == {"12": 1, "15": 1}
    nums, _, _ = _grid_tokens("b = -.32")
    assert "-.32" in nums


def test_a_greek_or_single_letter_label_the_grid_lacks_keeps_the_copy():
    # Consult round 2 (Sonnet, 2026-10-13) finding 11: `[A-Za-z]{2,}` never
    # compared `β`, `η`, `p`, `F`, so a statistic label only the copy carries
    # could be deleted with it.
    for label in ("β", "p", "η2p"):
        out = _suppress_orphan_table_cell_text(_doc(f"Effort\nHelp\nSSRT\n{label}\n\n3.10\n2.77\n211.74"))
        assert "table-text-duplicate" not in out, label


def test_a_star_or_times_marker_the_grid_lacks_keeps_the_copy():
    # `∗` (U+2217) is korbmacher's footnote star; `×` an interaction term.
    for mark in ("∗", "×", "≈", "+"):
        out = _suppress_orphan_table_cell_text(_doc(f"Effort{mark}\nHelp\nSSRT\n\n3.10\n2.77\n211.74"))
        assert "table-text-duplicate" not in out, mark


def test_a_range_with_an_en_dash_or_hyphen_reads_as_two_numbers():
    # Consult round 3 (Sonnet, 2026-10-13): `2008–2013` (grid) and `2008-2013`
    # (body) must tokenize alike, with no negative 2013.
    for s in ("2008–2013", "2008-2013"):
        assert sorted(_grid_tokens(s)[0].elements()) == ["2008", "2013"], s
    assert sorted(_grid_tokens("x -3.84")[0].elements()) == ["-3.84"]
