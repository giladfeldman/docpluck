"""One concept, one table — the cell normaliser must have ONE definition.

``_normalize_cell_text`` existed verbatim in ``tables/whitespace.py`` AND
``tables/cluster.py``, and ``cluster`` additionally never called the glyph repair
chain (register H3e). ``cluster.lattice_cells`` has no non-test caller today, so
the divergence was dormant — but a dormant fourth capture path is exactly where
the pre-v2.4.133 unrepaired-cell defect would have come back, silently, the day
someone wired it in.

Per this project's standing rule, the guard is a test that the sites AGREE, not
a second copy of the constants: *"a library that can convert one input two ways
has no contract at all."* The precedent is the Greek table, where `normalize.py`
and `extract.py` each carried a Latin→Greek map and disagreed on 9 of 9 shared
letters, so a chi-square left docpluck as `chi2` or `ch2` depending purely on
which extraction path ran.
"""

from __future__ import annotations

import pytest

from docpluck.tables.cell_cleaning import normalize_cell_whitespace
from docpluck.tables.cluster import _normalize_cell_text as cluster_normalize
from docpluck.tables.whitespace import _normalize_cell_text as whitespace_normalize

# Shapes that actually distinguish the implementations: the soft hyphen and the
# U+2212 fold are the two transformations, and collapsing whitespace is the
# third. A pair of plain ASCII strings would agree under any implementation.
_PROBES = [
    "a­b",                     # soft hyphen
    "−0.45",                   # U+2212 minus -> ASCII hyphen
    "[−0.78, −0.67]",
    "  spaced   out  ",
    "M­ = 4.52 (SD = 1.13)",
    "",
    "Direction 3 manipulated attribute",
]


@pytest.mark.parametrize("probe", _PROBES)
def test_every_cell_normaliser_gives_the_same_answer(probe):
    canonical = normalize_cell_whitespace(probe)
    assert whitespace_normalize(probe) == canonical, "whitespace path diverged"
    assert cluster_normalize(probe) == canonical, "cluster path diverged"


def test_the_normaliser_does_not_repair_glyphs():
    """It must canonicalise whitespace and NOTHING else.

    The capture paths run their structural gates on what this returns, and
    repairing before a gate is the defect `test_repair_never_deletes_a_row`
    pins. If a future edit folds the repair chain back in here, the gates start
    judging repaired text again and the rows come back off.
    """
    assert normalize_cell_whitespace("Direction 3 attr") == "Direction 3 attr"
    assert normalize_cell_whitespace("\\.001") == "\\.001"
    assert normalize_cell_whitespace("(cid:0)0.23") == "(cid:0)0.23"


def test_the_dormant_lattice_path_repairs_on_the_way_out():
    """``cluster.lattice_cells`` is unwired, and must still be correct if wired.

    Asserted on the emission helper it now calls, since the module has no
    non-test caller to exercise end-to-end.
    """
    from docpluck.tables.cell_cleaning import repair_cells

    cells = [{"r": 0, "c": 0, "rowspan": 1, "colspan": 1,
              "text": "\\.001", "is_header": False, "bbox": (0.0, 0.0, 0.0, 0.0)}]
    assert repair_cells(cells)[0]["text"] == "<.001"
