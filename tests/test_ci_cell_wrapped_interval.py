"""A combined estimate-and-interval cell is split at its wrapper, never on the
whole cell (Release B page check, 2026-11-16).

Two members of one class -- a number from the wrong side of the wrapper bound
as a field:
  * "1.00 [0.96–1.04]": a range split of the whole cell took the estimate as
    the lower bound (10.1186/s12889-023-17078-5 Table 6, every row);
  * "[0.32, 0.74]" alone in an estimate column (a wrapped continuation line):
    the interval's lower bound was read as the estimate
    (10.1177/17470218241255916 Table 7).
"""
from __future__ import annotations

import pytest

from docpluck.tables.flatten import _parse_ci_cell, _parse_leading_number


@pytest.mark.parametrize("cell, lo, hi", [
    ("1.00 [0.96–1.04]", 0.96, 1.04),       # en dash inside brackets
    ("2.50 [0.71—8.83]", 0.71, 8.83),       # em dash
    ("6.25 [1.29 to 30.35]", 1.29, 30.35),  # spelled-out range
    ("0.76 [.50, 1.02]", 0.50, 1.02),       # comma (already right)
    ("1.13 (1.07–1.20)", 1.07, 1.20),       # parentheses (already right)
    ("[0.32, 0.74]", 0.32, 0.74),           # interval only
])
def test_interval_is_read_inside_its_wrapper(cell, lo, hi):
    assert _parse_ci_cell(cell) == (lo, hi)


def test_hyphen_collision_in_parentheses_still_resolves():
    assert _parse_ci_cell("-1.01% (-10.36-8.34)", estimate=-1.01) == (-10.36, 8.34)


@pytest.mark.parametrize("cell, est", [
    ("[0.32, 0.74]", None),
    ("(0.95, 1.15)", None),
    ("0.53 [0.32, 0.74]", 0.53),
    ("-1.01% (-10.36-8.34)", -1.01),
])
def test_an_interval_only_cell_has_no_estimate(cell, est):
    assert _parse_leading_number(cell) == est


# Header words joined by a Unicode hyphen or no-break space are the same words
# (10.1186/s12889-023-17078-5 Table 6 prints "p‑value").
@pytest.mark.parametrize("header", ["p‑value", "p‐value", "p‒value"])
def test_a_unicode_hyphen_p_value_header_is_p(header):
    from docpluck.tables.flatten import _classify_column
    assert _classify_column(header) == "p"


def test_a_thin_space_ci_header_is_ci():
    from docpluck.tables.flatten import _classify_column
    assert _classify_column("95 % CI") == "CI"
