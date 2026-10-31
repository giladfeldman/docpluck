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


# --- Side-by-side text lines in one cell -------------------------------------
#
# THE DEFECT (10.1177/01461672251327169 p7, Table 4). Where Camelot's stream
# columns are fewer than the printed ones, two text lines printed SIDE BY SIDE
# (same baseline, a column gap between them) land in one cell. Camelot visits
# text lines by (-y0, x0), so a line whose baseline sits a fraction of a point
# higher is appended FIRST even when it is printed to the right, and the append
# carries no separator: the page's "IV1: estimation of positive emotional
# events" | "IV1: estimation of negative emotional events" came out as
# "...negative emotional eventsIV1: estimation of positive...".
#
# THE RULE. Only Camelot's own text lines are read, never the values. Lines a
# cell holds that overlap vertically by at least half the shorter line's height
# are one printed line: they are put in page order (left to right) with one
# space between them, because pdfminer only ends a text line at a gap wider than
# a word space. Lines on different printed lines keep Camelot's order and
# junction, byte for byte. A cell is rewritten only when its text is EXACTLY
# the concatenation of the lines assigned to it (whitespace aside); no glyph is
# added except the separating space, none is dropped.

SIDE_BY_SIDE_EVENT = "camelot_cell_side_by_side_lines"
_OVERLAP_FRACTION = 0.5


def _line_text(tl) -> str:
    try:
        return (tl.get_text() or "").replace("\n", "")
    except Exception:  # noqa: BLE001 - an unreadable line rewrites nothing
        return ""


def _span_index(v: float, spans, *, descending: bool):
    for i, (a, b) in enumerate(spans):
        lo, hi = (float(b), float(a)) if descending else (float(a), float(b))
        if lo <= v <= hi:
            return i
    return None


def _same_printed_line(a, b) -> bool:
    overlap = min(a.y1, b.y1) - max(a.y0, b.y0)
    shorter = min(a.y1 - a.y0, b.y1 - b.y0)
    return shorter > 0 and overlap >= _OVERLAP_FRACTION * shorter


def _segments(cell: str, texts: list[str]):
    """Split ``cell`` into one segment per line text (whitespace-insensitive),
    returning ``(junctions, segments)`` or ``None`` when they do not tile it."""
    pos, junctions, segments = 0, [], []
    for text in texts:
        want = "".join(text.split())
        if not want:
            return None
        start = pos
        while pos < len(cell) and cell[pos].isspace():
            pos += 1
        junctions.append(cell[start:pos])
        seg_start, got = pos, []
        while pos < len(cell) and len(got) < len(want):
            if not cell[pos].isspace():
                got.append(cell[pos])
            pos += 1
        if "".join(got) != want:
            return None
        segments.append(cell[seg_start:pos])
    if cell[pos:].strip():
        return None
    return junctions, segments


def separate_side_by_side_lines(ct, *, record: bool = True) -> int:
    """Rewrite each cell of ``ct.df`` that holds text lines printed side by side
    (see above). Returns how many cells changed; never raises. ``record=False``
    leaves the success event to the caller (``camelot_extract`` records it only
    when the rewritten table is the one kept)."""
    try:
        return _separate(ct, record=record)
    except Exception as exc:  # noqa: BLE001 - the grid as read is still valid
        record_fallback("camelot_cell_side_by_side_exception", detail=type(exc).__name__)
        return 0


def _separate(ct, *, record: bool = True) -> int:
    if getattr(ct, "rotation", "") or (getattr(ct, "flavor", "") or "") != "stream":
        return 0
    lines = [tl for tl in (getattr(ct, "textlines", None) or ()) if _line_text(tl).strip()]
    cols = list(getattr(ct, "cols", None) or ())
    rows = list(getattr(ct, "rows", None) or ())
    df = ct.df
    if not lines or not cols or not rows:
        return 0
    by_cell: dict = {}
    for tl in lines:
        ci = _span_index((tl.x0 + tl.x1) / 2.0, cols, descending=False)
        ri = _span_index((tl.y0 + tl.y1) / 2.0, rows, descending=True)
        if ci is None or ri is None or ri >= len(df) or ci >= len(df.columns):
            continue
        by_cell.setdefault((ri, ci), []).append(tl)
    changed = 0
    for (ri, ci), cell_lines in by_cell.items():
        if len(cell_lines) < 2:
            continue
        cell_lines.sort(key=lambda t: (-t.y0, t.x0))  # Camelot's visiting order
        groups = [[cell_lines[0]]]
        for tl in cell_lines[1:]:
            if any(_same_printed_line(tl, g) for g in groups[-1]):
                groups[-1].append(tl)
            else:
                groups.append([tl])
        if all(len(g) == 1 for g in groups):
            continue
        cell = str(df.iloc[ri, ci])
        tiled = _segments(cell, [_line_text(tl) for tl in cell_lines])
        if tiled is None:
            continue
        junctions, segments = tiled
        seg_of = {id(tl): seg.strip() for tl, seg in zip(cell_lines, segments)}
        out, k = [], 0
        for g in groups:
            if out:
                out.append(junctions[k])
            out.append(" ".join(seg_of[id(t)] for t in sorted(g, key=lambda t: t.x0)))
            k += len(g)
        new = junctions[0] + "".join(out)
        if new != cell:
            df.iloc[ri, ci] = new
            changed += 1
    if changed and record:
        record_fallback(SIDE_BY_SIDE_EVENT, detail=f"p{getattr(ct, 'page', '?')}:{changed}")
    return changed


# --- A row label that runs on past the stub column ----------------------------
#
# THE DEFECT (10.1177/01461672251327169 p11, Table 6). Camelot gives a text line
# to the column it covers the largest SHARE of. The row label "Overall negative:
# target article (Study 3)" is printed from the stub's left edge across the empty
# narrow column beside it; starting 0.04 pt inside the stub it covers 0.9995 of
# the stub and all of the next column, so it landed in column 1 with the stub
# empty.
#
# THE RULE. Only Camelot's own text lines and columns are read. A line moves to
# column 0 when all of these hold: it has a letter; it STARTS inside column 0;
# it covers more points of column 0 than of the column holding it; it ends
# inside that column or less than half way into the next; it is that cell's
# whole text; its row carries another value; column 0 is empty in its row; and
# column 0 already holds at least twice as many labels as would move. Nothing
# is added or dropped; the text moves left.

STUB_LABEL_EVENT = "camelot_row_label_returned_to_stub"


def return_overflowing_stub_labels(ct, *, record: bool = True) -> int:
    """Move each overflowing row label back to the stub (see above). Returns how
    many moved; never raises."""
    try:
        return _return_stub_labels(ct, record=record)
    except Exception as exc:  # noqa: BLE001 - the grid as read is still valid
        record_fallback("camelot_row_label_stub_exception", detail=type(exc).__name__)
        return 0


def _overlap(a0: float, a1: float, b0: float, b1: float) -> float:
    return max(0.0, min(a1, b1) - max(a0, b0))


def _return_stub_labels(ct, *, record: bool = True) -> int:
    if (getattr(ct, "flavor", "") or "") != "stream":
        return 0
    lines = [tl for tl in (getattr(ct, "textlines", None) or ()) if _line_text(tl).strip()]
    cols = list(getattr(ct, "cols", None) or ())
    rows = list(getattr(ct, "rows", None) or ())
    df = ct.df
    if not lines or len(cols) < 2 or not rows:
        return 0
    s0, s1 = float(cols[0][0]), float(cols[0][1])
    moves = []
    for tl in lines:
        if not (s0 <= tl.x0 < s1):
            continue
        ri = _span_index((tl.y0 + tl.y1) / 2.0, rows, descending=True)
        if ri is None or ri >= len(df) or str(df.iloc[ri, 0]).strip():
            continue
        want = "".join(_line_text(tl).split())
        in_stub = _overlap(tl.x0, tl.x1, s0, s1)
        for ci in range(1, min(len(cols), len(df.columns))):
            if "".join(str(df.iloc[ri, ci]).split()) != want:
                continue
            c0, c1 = float(cols[ci][0]), float(cols[ci][1])
            # A row label: it has a letter, and its row carries another value
            # (a dot leader, a caption line or a prose line beside an empty
            # row is not one; 10.1098/rsos.170336 p5-6).
            others = [str(df.iloc[ri, k]).strip() for k in range(len(df.columns)) if k != ci]
            # ...and it ends inside the column holding it or less than half way
            # into the next: a note line running across the table is not a row
            # label (10.1037/a0025767 p12, p14).
            nxt = cols[ci + 1] if ci + 1 < len(cols) else (c1, c1)
            ends_near = tl.x1 <= c1 + (float(nxt[1]) - float(nxt[0])) / 2.0
            if (_overlap(tl.x0, tl.x1, c0, c1) < in_stub and any(ch.isalpha() for ch in want)
                    and any(others) and ends_near):
                moves.append((ri, ci))
            break
    # Only an outlier is returned: column 0 must already hold the row labels
    # (at least twice as many rows as would move). Where Camelot made column 0
    # a near-empty strip and put the labels one column right
    # (10.1111/j.1558-5646.1994.tb01351.x p6), moving some of them broke the
    # grid's value / SE pairing.
    in_stub_rows = sum(1 for r in range(len(df)) if str(df.iloc[r, 0]).strip())
    if not moves or in_stub_rows < 2 * len(moves):
        return 0
    for ri, ci in moves:
        df.iloc[ri, 0] = df.iloc[ri, ci]
        df.iloc[ri, ci] = ""
    moved = len(moves)
    if moved and record:
        record_fallback(STUB_LABEL_EVENT, detail=f"p{getattr(ct, 'page', '?')}:{moved}")
    return moved


__all__ = [
    "JOIN_EVENT",
    "STUB_LABEL_EVENT",
    "SIDE_BY_SIDE_EVENT",
    "return_overflowing_stub_labels",
    "UNAVAILABLE_EVENT",
    "cell_join_scope",
    "needs_separator",
    "separate_side_by_side_lines",
    "stream_read_scope",
]
