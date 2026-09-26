"""Keep the textline Camelot 2.0 discards when it sits EXACTLY on a row boundary.

THE DEFECT (measured 2026-09-25, 10.1136/bmjopen-2022-066361 p5, Tables 1 and 2)
-------------------------------------------------------------------------------
Camelot's stream parser groups textlines into rows by ``y0`` within ``row_tol``
(2 pt). ``Imatinib+placebo`` (y0 195.35) and ``Imatinib+vitamin D3`` (y0 193.17
-- the subscript ``3`` drops the line's bottom) share a TOP edge (y1 204.35) but
their bottoms differ by 2.18 pt, so they become two row groups. Camelot 2.0.0's
``TextBaseParser._join_rows`` then puts the shared boundary at

    (min_y0(upper group) + max_y1(lower group)) / 2 = (195.346 + 204.346) / 2

which is bit-for-bit the upper line's own centre ``(y0 + y1) / 2``. And
``camelot.utils.get_table_index`` requires STRICT ``y_bot < y_mid < y_top``
on both sides, so the line belongs to no row and is discarded with
``return [], 1.0`` -- no warning, no count, and the column header
``Imatinib+placebo group (n=31)`` never reaches any cell.

Camelot 0.11.0 used the same strict test with a DIFFERENT ``_join_rows``
(boundaries at the midpoint between adjacent rows' mean centres), which cannot
land a boundary on a one-line row's own centre: swapping the 0.11.0
``_join_rows`` into 2.0.0 restores the header on the specimen. So the regression
is the ``_join_rows`` rewrite; the vectorised ``get_table_index`` is bit-identical
to the loop it replaced. Probe: ``tools/diag/camelot_text_drop_census.py``.

THE FIX, AND WHY IT IS EXTRACTION, NOT REPAIR
---------------------------------------------
When -- and only when -- Camelot has returned "no row" for a textline AND that
line's centre equals a row's lower edge exactly (``==`` on the same floats
Camelot compared), the line is assigned to that row: a half-open interval
``y_bot <= y_mid < y_top``. By construction that row is the line's OWN row
group (a line in the lower group has ``y0`` below every upper-group ``y0``, so
it cannot produce the tie), so this is where Camelot itself put it. The
decision reads nothing but the line's geometry and the grid Camelot built -- the
gate test in CLAUDE.md ("replace every surrounding word with garbage; is the
same output still justified?") answers yes. Every other textline takes Camelot's
own result, unchanged, byte for byte.

Each assignment is COUNTED (``camelot_row_boundary_tie_assigned``) with the page
and text as detail, because a channel repair that is not counted is a silent
one.

SCOPE
-----
The wrapper is installed into ``camelot.parsers.base`` once, and is inert
unless the current context is inside :func:`boundary_tie_scope` -- so any other
caller of Camelot in the same process gets Camelot's own behaviour. A
ContextVar rather than install/restore, because install/restore races between
threads: the second thread saves the first thread's wrapper as "the original"
and one of them runs unpatched.
"""

from __future__ import annotations

import threading
from contextlib import contextmanager
from contextvars import ContextVar

from docpluck.telemetry import record_fallback

TIE_EVENT = "camelot_row_boundary_tie_assigned"
UNAVAILABLE_EVENT = "camelot_row_boundary_tie_fix_unavailable"

# None -> inert. A list -> active; each assignment appends (page, text).
_ACTIVE: ContextVar[list | None] = ContextVar("docpluck_camelot_row_ties", default=None)
_INSTALL_LOCK = threading.Lock()
_MARK = "_docpluck_row_tie_wrapper"


class _ShiftedLine:
    """A textline seen a hair inside the row it ties with; every other attribute
    (text, x-extent, characters) is the real line's."""

    __slots__ = ("_t", "y0", "y1")

    def __init__(self, t, dy: float):
        self._t = t
        self.y0 = t.y0 + dy
        self.y1 = t.y1 + dy

    def __getattr__(self, name):
        return getattr(self._t, name)


def tied_row(rows, y_mid: float) -> int | None:
    """Index of the row whose LOWER edge is exactly ``y_mid`` and that has room
    above it, else ``None``."""
    for r_idx, (top, bot) in enumerate(rows):
        if bot == y_mid and top > y_mid:
            return r_idx
    return None


def _make_wrapper(original):
    def get_table_index(table, t, direction, **kw):
        res = original(table, t, direction, **kw)
        sink = _ACTIVE.get()
        if sink is None or res[0]:
            return res
        y_mid = (t.y0 + t.y1) * 0.5
        r_idx = tied_row(table.rows, y_mid)
        if r_idx is None:
            return res
        top = table.rows[r_idx][0]
        # Move the line's centre strictly inside (bot, top): a millionth of the
        # row height, far below any error Camelot's accuracy score can resolve.
        shifted = _ShiftedLine(t, (top - y_mid) * 1e-6)
        fixed = original(table, shifted, direction, **kw)
        if not fixed[0] or any(ix[0] != r_idx for ix in fixed[0]):
            return res  # could not place it in the tied row; Camelot's result stands
        sink.append((getattr(table, "page", None), t.get_text().strip()))
        return fixed

    setattr(get_table_index, _MARK, True)
    return get_table_index


def _install() -> bool:
    try:
        import camelot.parsers.base as pb
    except ImportError:
        return False
    with _INSTALL_LOCK:
        current = getattr(pb, "get_table_index", None)
        if current is None:
            return False
        if not getattr(current, _MARK, False):
            pb.get_table_index = _make_wrapper(current)
    return True


@contextmanager
def boundary_tie_scope():
    """Activate the tie assignment for Camelot calls made inside this block and
    record each assignment. If Camelot's internals have moved so the wrapper
    cannot be installed, that is RECORDED (never silently skipped) and Camelot
    runs unmodified."""
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
        for page, text in sink:
            record_fallback(TIE_EVENT, detail=f"p{page}:{text[:60]}")


__all__ = ["TIE_EVENT", "UNAVAILABLE_EVENT", "boundary_tie_scope", "tied_row"]
