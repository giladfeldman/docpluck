"""Two text lines printed side by side in one Camelot cell keep page order and a space.

10.1177/01461672251327169 p7, Table 4: the page prints "IV1: estimation of
positive emotional events" left of "IV1: estimation of negative emotional
events"; with fewer stream columns than printed ones both land in one cell, and
Camelot appended the right-hand line first with no separator
("...negative emotional eventsIV1: estimation of positive...").
"""

from __future__ import annotations

from types import SimpleNamespace

import pandas as pd

from docpluck.tables.camelot_cell_join import separate_side_by_side_lines


def _tl(x0, x1, y0, y1, text):
    return SimpleNamespace(x0=x0, x1=x1, y0=y0, y1=y1, get_text=lambda: text + "\n")


def _ct(cell, lines, flavor="stream"):
    return SimpleNamespace(
        flavor=flavor, rotation="", page=7,
        cols=[(60.0, 200.0), (200.0, 566.0)],
        rows=[(705.0, 690.0), (690.0, 670.0)],
        df=pd.DataFrame([["IV1", cell], ["", ""]]),
        textlines=lines,
    )


_POS = "IV1: estimation of positive emotional events"
_NEG = "IV1: estimation of negative emotional events"


def test_side_by_side_lines_take_page_order_and_a_space():
    # The right-hand line's baseline sits 0.3 pt higher, so Camelot visited it first.
    ct = _ct(_NEG + _POS, [_tl(395, 563, 694.3, 702.3, _NEG), _tl(209, 374, 694.0, 702.0, _POS)])
    assert separate_side_by_side_lines(ct) == 1
    assert ct.df.iloc[0, 1] == _POS + " " + _NEG


def test_stacked_lines_keep_camelots_text():
    """Lines on different printed lines are not side by side: nothing changes."""
    cell = "maternalbehavior"
    ct = _ct(cell, [_tl(209, 260, 694, 702, "maternal"), _tl(209, 260, 684, 692.5, "behavior")])
    assert separate_side_by_side_lines(ct) == 0
    assert ct.df.iloc[0, 1] == cell


def test_a_cell_the_lines_do_not_tile_is_left_alone():
    """A cell whose text is not exactly its lines (a restored sign, another
    reader's edit) is never rewritten."""
    cell = _NEG + "-" + _POS
    ct = _ct(cell, [_tl(395, 563, 694.3, 702.3, _NEG), _tl(209, 374, 694.0, 702.0, _POS)])
    assert separate_side_by_side_lines(ct) == 0
    assert ct.df.iloc[0, 1] == cell


def test_lattice_tables_are_not_touched():
    cell = _NEG + _POS
    ct = _ct(cell, [_tl(395, 563, 694.3, 702.3, _NEG), _tl(209, 374, 694.0, 702.0, _POS)],
             flavor="lattice")
    assert separate_side_by_side_lines(ct) == 0
    assert ct.df.iloc[0, 1] == cell


def test_a_discarded_trial_records_nothing():
    """The second, trial conversion of a kept table (side-by-side lines
    separated) must not count its gate events twice."""
    from docpluck.telemetry import discarded_fallbacks, fallback_scope, record_fallback

    with fallback_scope() as scope:
        record_fallback("trial_probe_event", detail="kept")
        with discarded_fallbacks():
            record_fallback("trial_probe_event", detail="trial")
        record_fallback("trial_probe_event", detail="kept")
    assert scope.details.get("trial_probe_event") == {"kept": 2}
