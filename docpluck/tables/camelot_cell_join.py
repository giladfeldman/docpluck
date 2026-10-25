"""Keep a separator between two VALUES Camelot appends into one cell.

THE DEFECT (measured 2026-10-24, 10.1177/23780231251314667 p38, rotated table)
------------------------------------------------------------------------------
``camelot.core.Cell.text`` is an *appending* setter: every textline Camelot
assigns to a cell is concatenated onto what the cell already holds, with no
separator. When stream column detection under-segments a table (6 grid columns
for the 10 the page prints there), two printed columns' values land in one cell
and come out as ``.7*.6***`` or ``2.01.91.9`` -- the published values ``.7*`` and
``.6***``, or ``2.0`` / ``1.9`` / ``1.9``, can no longer be told apart by any
consumer. Over the 125-paper manifest, 124 such cells in 21 papers.

THE RULE, AND WHY IT IS NARROW
------------------------------
Inside :func:`cell_join_scope` a textline appended to a non-empty cell gets one
space in front of it when the cell ENDS with a digit, a significance mark or a
closing bracket and the new textline STARTS a number (a digit, reached through at
most an opening bracket, a comparison operator, a sign and a decimal point; a lone
"." or "-" is punctuation and is left alone). That boundary is a value
followed by a value; no printed number continues across it. Every other append
is Camelot's own, byte for byte -- a wrapped word line (``maternal`` +
``behavior``) and a hyphen break keep their current text, so this changes only
the cells that carry two numbers glued together. It adds a character; it never
removes, moves or reorders one. Each separated cell is counted
(``camelot_cell_values_separated``).

SCOPE
-----
Installed into ``camelot.core.Cell`` once and inert unless the current context
is inside :func:`cell_join_scope` (a ContextVar, for the same thread-safety reason
as ``camelot_row_ties``).
"""

from __future__ import annotations

import re
import threading
from contextlib import contextmanager
from contextvars import ContextVar

from docpluck.telemetry import record_fallback

JOIN_EVENT = "camelot_cell_values_separated"
UNAVAILABLE_EVENT = "camelot_cell_join_unavailable"

_ACTIVE: ContextVar[list | None] = ContextVar("docpluck_camelot_cell_join", default=None)
_INSTALL_LOCK = threading.Lock()
_MARK = "_docpluck_cell_join_property"

# A value ends here (a digit, a significance mark -- "+" stands in for a dagger in
# some fonts -- a percent sign or a closing bracket) ...
_VALUE_END = re.compile(r"[0-9*+†‡§%)\]]$")
# ... and the appended textline begins another one: a digit, reached through at
# most a comparison operator, a sign, a decimal point or an opening bracket. A
# lone "." or "-" is punctuation, not a value -- a list number "2." whose point
# Camelot read as its own textline (10.15626/mp.2022.3108 p37) stays "2.".
_VALUE_START = re.compile(r"^[(\[]?(?:[<>=≤≥]\s*)?[+\-−–]?\.?\d")


def needs_separator(current: str, appended: str) -> bool:
    """True when ``appended`` is a second value glued onto a value in ``current``."""
    if not current or not appended:
        return False
    return bool(_VALUE_END.search(current) and _VALUE_START.match(appended))


def _install() -> bool:
    try:
        import camelot.core as cc
    except ImportError:
        return False
    with _INSTALL_LOCK:
        cell_cls = getattr(cc, "Cell", None)
        prop = getattr(cell_cls, "text", None) if cell_cls is not None else None
        if not isinstance(prop, property) or prop.fset is None:
            return False
        if cell_cls.__dict__.get(_MARK, False):
            return True
        original_get, original_set = prop.fget, prop.fset

        def _set(self, t):
            sink = _ACTIVE.get()
            if sink is not None:
                cur = original_get(self) or ""
                if needs_separator(cur, t or ""):
                    sink.append(f"{cur[-12:]}|{(t or '')[:12]}")
                    t = " " + t
            original_set(self, t)

        cell_cls.text = property(original_get, _set, prop.fdel, prop.__doc__)
        setattr(cell_cls, _MARK, True)
    return True


@contextmanager
def cell_join_scope():
    """Separate glued values for Camelot calls made inside this block. If
    Camelot's ``Cell`` has changed shape, that is RECORDED and Camelot runs
    unmodified."""
    if not _install():
        record_fallback(UNAVAILABLE_EVENT)
        yield
        return
    sink: list = []
    token = _ACTIVE.set(sink)
    try:
        yield
    finally:
        _ACTIVE.reset(token)
        if sink:
            record_fallback(JOIN_EVENT, detail=f"{len(sink)}:{sink[0]}")


@contextmanager
def stream_read_scope():
    """The scope every Camelot STREAM read in this library runs inside: the
    row-boundary tie repair (`camelot_row_ties`) and the value separator above.
    One per ``read_pdf`` call, so a tie split is joined when that call's scope
    closes -- a re-read that compares its rows with the first read's (bottom
    extension, column re-split) must see the first read's joined rows."""
    from docpluck.tables.camelot_row_ties import boundary_tie_scope

    with boundary_tie_scope(), cell_join_scope():
        yield


__all__ = [
    "JOIN_EVENT",
    "UNAVAILABLE_EVENT",
    "cell_join_scope",
    "needs_separator",
    "stream_read_scope",
]
