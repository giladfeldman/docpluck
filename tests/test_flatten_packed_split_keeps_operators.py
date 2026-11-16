"""A packed two-arm cell keeps each value's printed operator and mark.

Real case (ESCImate, 2026-11-15): 10.1080/23743603.2021.1878340 Table 3 (p15)
prints "< .001" for two arms whose grid rows were merged into one cell
("< .001 < .001"). The split kept only the numbers, so both arms read p = .001
with p_op "=". Every value below is invented.
"""
from __future__ import annotations

import pytest

from docpluck.tables.flatten import _split_value_groups


@pytest.mark.parametrize("cell, groups", [
    ("< .001 < .001", ["< .001", "< .001"]),
    ("< .001 .122", ["< .001", ".122"]),
    (".05 <.001", [".05", "<.001"]),
    ("> .99 = .04", ["> .99", "= .04"]),
    ("≤ .01 ≥ .20", ["≤ .01", "≥ .20"]),
    ("0.40* 0.12***", ["0.40*", "0.12***"]),
    ("4.76 (1.14) 5.01 (1.20)", ["4.76 (1.14)", "5.01 (1.20)"]),
    ("-1.2 [-.3, .1] 0.4 [.1, .7]", ["-1.2 [-.3, .1]", "0.4 [.1, .7]"]),
])
def test_split_keeps_operator_and_mark(cell, groups):
    assert _split_value_groups(cell, 2) == groups


@pytest.mark.parametrize("cell", ["0.3 - 0.4", "0.3 ± 0.4"])
def test_a_meaning_bearing_leftover_refuses_the_split(cell):
    # A detached dash or a ± outside every group would be lost: leave it whole.
    assert _split_value_groups(cell, 2) is None
