"""A1 statistic rejoin crosses ONE line break, never a blank line (W5a).

Census 2026-11-13 on 125 corpus papers: 27 of 440 A1 joins crossed a blank
line, 25 of them gluing a table header onto a body cell. Each refusal case
below is a shape seen in that census (DOI in the comment); each keep case is a
join that must still happen. Every refusal test failed on v2.4.159.
"""
from __future__ import annotations

import pytest

from docpluck.normalize import _a1_stat_linebreak_repair as a1
from docpluck.telemetry import fallback_scope


@pytest.mark.parametrize("text", [
    # 10.1111/jomf.13036: `Inflate OR` column header, blank, body cell `1`
    "Count IRR\n\nInflate OR\n\n1\n\n0.948",
    # 10.1098/rsos.250669: `p` column header, blank, cells
    "U-statistic\n\np\n\n<0.01\n\n<0.05",
    # 10.15626/mp.2022.3108: G*Power output laid out as a table
    "Actual power\n\n=\n\n0.9511280",
    # 10.1038/s41467-024-51459-7: display equation `p=` / blank / `1`
    "by the surface).\np=\n\n1\nAin",
])
def test_no_join_across_a_blank_line(text):
    with fallback_scope() as fb:
        out = a1(text)
    assert out == text
    assert fb.counters.get("a1_stat_split_by_blank_line_left", 0) >= 1


def test_p_inside_a_word_is_not_a_p_value():
    # 10.1017/s0007123424000012: `beta coup` / `= -0.024` -- the `p` ends `coup`.
    text = "associated with coup incidence (b coup\n= -0.024, p < 0.01)"
    out = a1(text)
    assert "coup =" not in out


def test_or_inside_a_word_is_not_an_odds_ratio():
    text = "the FACTOR\n2 loadings"
    assert a1(text) == text


@pytest.mark.parametrize("text, want", [
    ("t(23) = 2.34, p\n< .001", "p < .001"),
    ("F(1, 40) = 5.1, p =\n.03", "p = .03"),
    ("OR\n1.42 (1.1, 1.8)", "OR 1.42"),
    ("95%\nCI [0.1, 0.3]", "95% CI"),
    ("M =\n3.2", "= 3.2"),
    ("d = 0.45,\n95% CI [0.1, 0.8]", "0.45, 95% CI"),
    # the comma rules keep one blank line: 10.5334/irsp.571
    ("f = 0.09,\n\n95% CI [0.03, 0.13])", "0.09, 95% CI"),
    ("t(9) = 2.2,\n\np = .04", "2.2, p = .04"),
])
def test_single_break_joins_still_happen(text, want):
    assert want in a1(text)


def test_comma_rule_does_not_cross_two_blank_lines():
    text = "Table 3 footnote,\n\n\n95% CI of the mean"
    assert a1(text) == text


def test_page_break_still_a_wall():
    text = "p =\f.03"
    assert a1(text) == text
