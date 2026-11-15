"""The A1 column-bleed and garbage rules need `p` to be a whole token, and every
deletion they make is counted (consult round 2, Sonnet + Haiku, 2026-11-13).

"Group\n12\n= .28" became "Group = .28" -- the `p` of "Group" opened the
rule and the 12 was deleted -- and "group = A\n\n.45" became "group = .45"
across a blank line. Text is invented. Failed on v2.4.160.
"""
from __future__ import annotations

import pytest

from docpluck.normalize import _a1_stat_linebreak_repair
from docpluck.telemetry import fallback_scope


@pytest.mark.parametrize("src", ["Group\n12\n= .28", "Group\n\n12\n\n= .28", "group = A\n\n.45",
                                 "Step\n7\n< .05"])
def test_word_ending_in_p_is_not_a_p_value(src):
    out = _a1_stat_linebreak_repair(src)
    assert "12" in out or "7" in out or "A" in out
    assert out.replace(" ", "") != src.replace("\n", "").replace(" ", "").replace("12", "").replace("7", "")


def test_group_keeps_its_number_exactly():
    assert _a1_stat_linebreak_repair("Group\n12\n= .28") == "Group\n12\n= .28"
    assert _a1_stat_linebreak_repair("group = A\n\n.45") == "group = A\n\n.45"


def test_real_column_bleed_still_joined_and_counted():
    with fallback_scope() as fb:
        out = _a1_stat_linebreak_repair("t(20) = 2.1, p\n01\n11\n< .05")
    assert "p < .05" in out
    assert fb.counters.get("a1_column_bleed_fragments_dropped") == 1


def test_garbage_between_operator_and_value_counted():
    with fallback_scope() as fb:
        out = _a1_stat_linebreak_repair("F(1, 30) = 4.2, p = xyz\n.045")
    assert "p = .045" in out
    assert fb.counters.get("a1_column_garbage_dropped") == 1


def test_comma_join_across_blank_line_counted():
    with fallback_scope() as fb:
        out = _a1_stat_linebreak_repair("t(20) = 2.1,\n\np < .05")
    assert "2.1, p < .05" in out
    assert fb.counters.get("a1_comma_join_across_blank_line") == 1
