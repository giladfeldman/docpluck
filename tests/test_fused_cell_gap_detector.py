"""The fused-cell detector must refuse any cell whose glyphs are not its own text.

Register G6h. Camelot sometimes swallows a real inter-column gap, so two published
values arrive glued into one cell (`104594` is the sample sizes 104 and 594).
`tools/diag/fused_cell_census.py` says plainly that a text-only scan cannot see
the commonest case -- two plain integers -- and that a shippable detector needs
the LAYOUT channel. v2.4.135 closed that blocker by giving every Camelot cell a
verified rectangle, and `tools/diag/fused_cell_geometry_scan.py` is what it
unblocks.

WHY THE ATTRIBUTION CHECK IS THE WHOLE RULE, and why it is pinned here.
`cell_geometry`'s own docstring says a verified bbox is the GRID RECTANGLE and is
NOT a promise that ``cell["text"]`` is the text standing inside it. The first
draft of the scan ignored that and measured gaps between whatever
``chars_in_bbox`` returned, so a wide header rectangle that also covered its
neighbour produced gaps of **17.3 em** and three confident "fusions" on
``10.1001/jamanetworkopen.2023.39337`` Table 3 (`'TRE'`, `'Baseline'`,
`'11 h 55 min'`) -- every one of them the gutter BETWEEN two cells, doing exactly
its job.

Measured calibration over the 26-paper baseline (regenerate with
``python tools/diag/fused_cell_geometry_scan.py``): 71,733 intra-cell
adjacent-character gaps, ``p50=0.00 p90=0.00 p99=0.33 max=19.07`` ems. The
threshold at 0.75 em sits in an empty band well above ordinary spacing. On the
census's own known positives the detector fires with 15.15 em (136.4 pt) between
``'4'`` and ``'5'`` of ``104594``, and 12.22 em (77.9 pt) inside
``4.603.804.80``.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.diag.fused_cell_geometry_scan import FUSION_GAP_EM, fused_sites


def _chars(spec: list[tuple[str, float, float]], *, top: float = 100.0,
           size: float = 9.0) -> list[dict]:
    """``[(text, x0, x1)]`` -> pdfplumber-shaped char dicts on one baseline."""
    return [
        {"text": t, "x0": x0, "x1": x1, "top": top, "bottom": top + size,
         "size": size}
        for t, x0, x1 in spec
    ]


def _run(text: str, xs: list[tuple[str, float, float]], **kw):
    return fused_sites(text, _chars(xs, **kw))


def test_a_swallowed_column_gap_is_reported():
    """`104594` printed as `104` <gutter> `594` is a fusion."""
    xs = [("1", 0, 5), ("0", 5, 10), ("4", 10, 15),
          ("5", 95, 100), ("9", 100, 105), ("4", 105, 110)]
    sites = _run("104594", xs)
    assert sites, "the 80pt gutter inside 104594 was not reported"
    assert max(s["gap_em"] for s in sites) > FUSION_GAP_EM


def test_ordinary_letter_spacing_is_not_a_fusion():
    xs = [(c, i * 5.0, i * 5.0 + 5.0) for i, c in enumerate("104594")]
    assert _run("104594", xs) == []


def test_a_gap_the_text_already_records_is_not_a_fusion():
    """A space in the cell text means nothing was lost."""
    xs = [("1", 0, 5), ("0", 5, 10), ("4", 10, 15), (" ", 15, 95),
          ("5", 95, 100), ("9", 100, 105), ("4", 105, 110)]
    assert _run("104 594", xs) == []


def test_glyphs_that_are_not_the_cell_text_are_REFUSED_not_measured():
    """The rectangle covers a neighbour: refuse, never report a gutter as a fusion.

    This is the 17.3 em false-positive class from the first draft. A refusal is
    `None`; a clean cell is `[]`. A caller that cannot tell them apart would fold
    every unmeasurable cell into its denominator.
    """
    xs = [("T", 0, 5), ("R", 5, 10), ("E", 10, 15),
          ("C", 150, 155), ("t", 155, 160), ("l", 160, 165)]
    assert _run("TRE", xs) is None


def test_a_multiline_cell_does_not_measure_across_the_line_break():
    """The next line restarts at the left edge; that is not a horizontal gap."""
    line1 = [("a", 100, 105), ("b", 105, 110)]
    line2 = [("c", 0, 5), ("d", 5, 10)]
    chars = _chars(line1, top=100.0) + _chars(line2, top=120.0)
    assert fused_sites("abcd", chars) == []


def test_a_cell_too_short_to_speak_is_refused():
    assert _run("ab", [("a", 0, 5), ("b", 90, 95)]) is None
