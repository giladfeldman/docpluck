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

THE SPLIT ROW, AND WHEN IT IS JOINED
------------------------------------
The rescued line lands in its own group's row -- a row Camelot had already built
and, before this fix, left EMPTY. So each printed line stays split across two
grid rows: measured on 10.1177/23780231251314667 p35 Table 1,

    ['Total housework', '18.5', '', '', '', '', '', '18.8', '18.1', '']
    ['', '', '17.8*', '17.8*', '17.8*', '17.9+', '17.2**', '', '', '17.7+']

The tie is itself the evidence that the two rows are one printed line: the
boundary can sit on the rescued line's centre only because its top edge is the
lower group's top edge. So after the parse, for each row a tie was assigned to,
if that row and the row directly below share that boundary AND their filled
columns are disjoint, the upper row's text moves down into the empty cells of the
lower one (``camelot_row_boundary_tie_rows_merged``). The grid keeps its shape --
the upper row is left empty, exactly as Camelot left it before the fix -- so
per-cell geometry indices stay valid. Where the columns collide (Camelot merged
several printed columns into one, e.g. socius_4 p38) nothing moves: joining two
texts in one cell would invent an order the page does not state.

A line Camelot drops and this module does NOT rescue is counted too
(``camelot_textline_unassigned``), so a future miss is visible rather than silent.
Measured 2026-09-25 over the 102-paper corpus: all 1,042 stream drops were exact
ties and all were rescued; the counter's first job is to stay at zero.

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
MERGE_EVENT = "camelot_row_boundary_tie_rows_merged"
MERGE_FAILED_EVENT = "camelot_row_boundary_tie_merge_failed"
DROP_EVENT = "camelot_textline_unassigned"
UNAVAILABLE_EVENT = "camelot_row_boundary_tie_fix_unavailable"


class _Sink:
    """What one scope saw: tie assignments (table, row, page, text) and lines
    Camelot dropped that were not rescued (page, text)."""

    __slots__ = ("drops", "ties")

    def __init__(self):
        self.ties: list = []
        self.drops: list = []


# None -> inert. A _Sink -> active.
_ACTIVE: ContextVar[_Sink | None] = ContextVar("docpluck_camelot_row_ties", default=None)
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
        page = getattr(table, "page", None)
        text = t.get_text().strip()
        y_mid = (t.y0 + t.y1) * 0.5
        r_idx = tied_row(table.rows, y_mid)
        if r_idx is None:
            if text:
                sink.drops.append((page, text))
            return res
        top = table.rows[r_idx][0]
        # Move the line's centre strictly inside (bot, top): a millionth of the
        # row height, far below any error Camelot's accuracy score can resolve.
        shifted = _ShiftedLine(t, (top - y_mid) * 1e-6)
        fixed = original(table, shifted, direction, **kw)
        if not fixed[0] or any(ix[0] != r_idx for ix in fixed[0]):
            if text:
                sink.drops.append((page, text))
            return res  # could not place it in the tied row; Camelot's result stands
        sink.ties.append((table, r_idx, {ix[1] for ix in fixed[0]}, page, text))
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
    sink = _Sink()
    token = _ACTIVE.set(sink)
    try:
        yield
    finally:
        _ACTIVE.reset(token)
        for _table, _r, _cols, page, text in sink.ties:
            record_fallback(TIE_EVENT, detail=f"p{page}:{text[:60]}")
        for page, text in sink.drops:
            record_fallback(DROP_EVENT, detail=f"p{page}:{text[:60]}")
        _join_tie_split_rows(sink.ties)


def _row_texts(table, r: int) -> list[str]:
    return [(cell.text or "").strip() for cell in table.cells[r]]


def join_tie_split_rows(table, tie_cells) -> list[int]:
    """Join each tied row into the row below it when they are one printed line.

    ``tie_cells``: ``{row: {columns a tie assignment was placed in}}``. Returns
    the upper-row indices that were joined. Conditions, all required:

      * row ``r + 1`` exists and its top edge IS row ``r``'s bottom edge (the
        boundary the tie sat on, compared exactly, as the tie was);
      * both rows carry text (joining into an empty row changes nothing);
      * EVERY filled cell of row ``r`` was placed there by a tie -- never move a
        cell Camelot placed on its own (tightened after consult round 2; measured
        2026-09-26 the row-level rule moved 0 such cells in 852 moves, so this
        changes nothing on the corpus and closes the case rather than trusting it);
      * no column is filled in both rows (a collision is left split).

    Rows are visited bottom-up so a chain of ties collapses no further than one
    step and every decision reads rows no earlier join has touched.
    """
    joined: list[int] = []
    rows = table.rows
    n = len(table.cells)
    for r in sorted(tie_cells, reverse=True):
        if r + 1 >= n or r + 1 >= len(rows) or rows[r][1] != rows[r + 1][0]:
            continue
        upper, lower = _row_texts(table, r), _row_texts(table, r + 1)
        if not any(upper) or not any(lower):
            continue
        if any(u and c not in tie_cells[r] for c, u in enumerate(upper)):
            continue
        if any(u and lo for u, lo in zip(upper, lower)):
            continue
        df = getattr(table, "df", None)
        for c, text in enumerate(upper):
            if text:
                table.cells[r + 1][c]._text = table.cells[r][c]._text
                table.cells[r][c]._text = ""
                # `df` was built from the cells at the end of the parse. Edit it IN
                # PLACE, never replace it: a caller already holding `table.df`
                # must see the same grid as one that reads it afterwards.
                if df is not None and r + 1 < df.shape[0] and c < df.shape[1]:
                    df.iat[r + 1, c] = df.iat[r, c]
                    df.iat[r, c] = ""
        joined.append(r)
    return joined


def _join_tie_split_rows(ties) -> None:
    by_table: dict[int, tuple] = {}
    for table, r_idx, cols, _page, _text in ties:
        by_table.setdefault(id(table), (table, {}))[1].setdefault(r_idx, set()).update(cols)
    for table, tie_cells in by_table.values():
        try:
            joined = join_tie_split_rows(table, tie_cells)
        except Exception as exc:  # noqa: BLE001 - recorded; the unjoined grid stands
            record_fallback(MERGE_FAILED_EVENT, detail=type(exc).__name__)
            continue
        # Recorded per stream table as parsed, BEFORE `_pick_best_per_page` may
        # prefer a lattice grid: this counts joins made, not joins delivered.
        for r in joined:
            first = next((t for t in _row_texts(table, r + 1) if t), "")
            record_fallback(MERGE_EVENT,
                            detail=f"p{getattr(table, 'page', None)}:r{r}:{first[:40]}")


__all__ = [
    "DROP_EVENT",
    "MERGE_EVENT",
    "MERGE_FAILED_EVENT",
    "TIE_EVENT",
    "UNAVAILABLE_EVENT",
    "boundary_tie_scope",
    "join_tie_split_rows",
    "tied_row",
]
