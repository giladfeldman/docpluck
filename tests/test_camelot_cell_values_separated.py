"""Two values Camelot appends into one cell keep a separator.

10.1177/23780231251314667 p38 (rotated table, raster checked 2026-10-24): stream
column detection merges printed columns and ``camelot.core.Cell.text`` appends
textlines with nothing between them, so ``.7*`` and ``.6***`` arrived as
``.7*.6***`` and ``2.0``, ``1.9``, ``1.9`` as ``2.01.91.9``.
"""
from __future__ import annotations

import pytest

camelot = pytest.importorskip("camelot")

from docpluck.tables.camelot_cell_join import (
    cell_join_scope,
    needs_separator,
)


def _cell():
    from camelot.core import Cell

    return Cell(0, 0, 10, 10)


@pytest.mark.parametrize(
    "cur,new,expected",
    [
        (".7*", ".6***", True),
        ("2.0", "1.9", True),
        ("3.4+", "2.9***", True),
        ("< .01", "0.240", True),
        ("18.36", "-0.39", True),
        ("maternal", "behavior", False),
        ("be-", "tween", False),
        ("[0.12,", "0.52]", False),
        ("", "1.9", False),
        ("Model", "2", False),
        # a list number "2." whose point is its own textline (10.15626/mp.2022.3108 p37)
        ("2", ".", False),
        ("1", ".  Default condition:", False),
        ("12", "-", False),
        ("3.1", "< .001", True),
        ("0.20", "(0.014)", True),
    ],
)
def test_boundary_rule(cur, new, expected):
    assert needs_separator(cur, new) is expected


def test_scope_separates_values_and_nothing_else():
    with cell_join_scope():
        a = _cell()
        a.text = ".7*"
        a.text = ".6***"
        b = _cell()
        b.text = "maternal"
        b.text = "behavior"
    assert a.text == ".7* .6***"
    assert b.text == "maternalbehavior"


def test_outside_the_scope_camelot_is_unchanged():
    with cell_join_scope():
        pass  # installs the wrapper
    c = _cell()
    c.text = "2.0"
    c.text = "1.9"
    assert c.text == "2.01.9"


def test_socius_rotated_table_values_are_separable():
    from docpluck.extract_structured import extract_pdf_structured
    from docpluck.testing.corpus import custody_path

    p = custody_path("fulltext", "10.1177__23780231251314667.pdf")
    tables = extract_pdf_structured(p.read_bytes())["tables"]
    cells = [c["text"] for t in tables if t.get("page") == 38 for c in t.get("cells") or []]
    assert cells, "no table on p38"
    joined = " | ".join(cells)
    for glued in (".7*.6***", "2.01.91.9", "1.51.31.6"):
        assert glued not in joined, glued
    assert ".7* .6***" in joined or ".7*" in cells
