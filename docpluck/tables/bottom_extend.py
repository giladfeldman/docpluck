"""Let a Camelot stream grid reach the end of its printed table.

THE DEFECT, ON A REAL PAGE
--------------------------
``10.1177/00031224241252079`` p12, Table 1 (printed sideways). The table ends with
four indented education rows, ``Individuals`` and ``Observations`` (the sample
sizes), then its bottom rule. Camelot's stream parser derives a table AREA from
text edges -- runs of text lines aligned on a left, right or middle x -- and only
lines that sit wholly inside that area are read. The label column's left edge
breaks where the education rows are indented, so the area, and the grid, ended at
the label-only row ``Partner's education``. The six rows below were in no cell.

THE EVIDENCE IS TYPOGRAPHIC
---------------------------
Only the text lines Camelot itself extracted (``ct.textlines``, in Camelot's own
frame, so a sideways page needs no coordinate mapping) and the grid's own row
pitch are read. Directly under the grid, a band of lines continues the table when:

* it sits within the row pitch rule: the gap from the previous row is at most
  ``MAX_GAP_PITCHES`` row pitches (a table's rows are evenly spaced; the space
  before a note or the next paragraph is wider);
* every line in it lies inside the grid's x-range (a prose line or a note set the
  full column width runs past a table narrower than the column, and a caption or
  note that fits inside is still one line -- see the next point);
* it is a ROW OF VALUES: at most one row label starting in the first column
  (it may run past that column's edge, never into a value), and value lines each
  centred in a different one of the grid's own columns, at least one of them a
  number (short, carrying a digit, or a lone dash / slash placeholder) and any
  text value at most ``MAX_TEXT_CELL_CHARS`` long; with no label, at least two
  value lines. Each value must also overlap the x-extent of the text already
  printed in its column (a panel below with its own column layout does not;
  tier-2 review, Sonnet, 2026-10-14). A one-line band (a sub-heading row such as ``Partner's
  education`` or ``Interaction term:``) is taken only when it starts in the
  first column and the band after it qualifies.

And the grid itself must already be a table of values: at least ``MIN_COLS``
columns and most body rows carrying a digit outside the first column. Measured
before these limits on the 101-PDF manifest (2026-10-14): 99 firings in 55
papers, most of them two-column PROSE appended to a page-wide pseudo-grid, or a
two-column header-only grid swallowing the real table below it with several
values glued into one cell.

Nothing is inferred from what the words say.

THE RE-READ MAY ONLY APPEND ROWS
--------------------------------
Camelot is re-run on the extended area with the grid's OWN column separators, so
the columns cannot change. The re-read is kept only if its first rows equal the
original grid cell for cell and it adds at least one row; anything else keeps the
original grid unchanged.
"""

from __future__ import annotations

from statistics import median
from typing import Any

MAX_GAP_PITCHES = 1.6
X_TOLERANCE_PT = 2.0
MIN_COLS = 3
MAX_VALUE_CHARS = 25
MAX_TEXT_CELL_CHARS = 40
_PLACEHOLDERS = {"-", "–", "—", "/", "−"}


def _text(tl: Any) -> str:
    try:
        return (tl.get_text() or "").strip()
    except Exception:
        return ""


def _bands(lines: list[Any], tol: float) -> list[list[Any]]:
    """Group text lines into horizontal bands, top to bottom (PDF y grows upward)."""
    out: list[list[Any]] = []
    for tl in sorted(lines, key=lambda t: -(t.y0 + t.y1) / 2.0):
        cy = (tl.y0 + tl.y1) / 2.0
        if out and abs(((out[-1][0].y0 + out[-1][0].y1) / 2.0) - cy) <= tol:
            out[-1].append(tl)
        else:
            out.append([tl])
    return out


def _is_value(text: str) -> bool:
    return len(text) <= MAX_VALUE_CHARS and (
        any(ch.isdigit() for ch in text) or text in _PLACEHOLDERS
    )


def _col_of(x: float, cols: list) -> int | None:
    for i, (a, b) in enumerate(cols):
        if float(a) <= x <= float(b):
            return i
    return None


def _grid_is_numeric(ct: Any) -> bool:
    try:
        rows = ct.df.values.tolist()
    except Exception:
        return False
    # rows with something beside the label: caption lines a caption-anchored
    # region carries in its first column do not dilute the count
    body = [r for r in rows if any(str(c).strip() for c in r[1:])]
    if len(body) < 3:
        return False
    with_digit = sum(1 for r in body if any(any(ch.isdigit() for ch in str(c)) for c in r[1:]))
    return with_digit * 2 > len(body)


def _column_extents(ct: Any, cols: list, y0: float) -> dict[int, tuple[float, float]]:
    """x-extent of the text already printed in each column of the grid (lines
    inside the grid's box), so an appended value must sit where that column's
    values sit -- not merely somewhere inside Camelot's column interval."""
    ext: dict[int, list[float]] = {}
    for tl in getattr(ct, "textlines", None) or ():
        if not _text(tl) or (tl.y0 + tl.y1) / 2.0 < y0:
            continue
        ci = _col_of((tl.x0 + tl.x1) / 2.0, cols)
        if ci is None:
            continue
        e = ext.setdefault(ci, [tl.x0, tl.x1])
        e[0], e[1] = min(e[0], tl.x0), max(e[1], tl.x1)
    return {k: (v[0], v[1]) for k, v in ext.items()}


def _band_is_value_row(band: list[Any], cols: list, extents: dict | None = None) -> bool:
    first_right = float(cols[0][1]) - X_TOLERANCE_PT
    # the row label starts in the first column; it may run past that column's
    # edge (a long label) but never into a value
    labels = [tl for tl in band if tl.x0 < first_right]
    values = [tl for tl in band if tl.x0 >= first_right]
    if len(labels) > 1 or not values:
        return False
    if not labels and len(values) < 2:
        # a lone unlabelled number under a pseudo-grid is a chart axis tick
        # (10.1001/jamanetworkopen.2023.39337 p7, 10.1098/rsos.140072 p8)
        return False
    if labels and labels[0].x1 > min(tl.x0 for tl in values):
        return False
    seen: set[int] = set()
    numeric = 0
    for tl in values:
        text = _text(tl)
        if _is_value(text):
            numeric += 1
        elif len(text) > MAX_TEXT_CELL_CHARS:
            return False
        ci = _col_of((tl.x0 + tl.x1) / 2.0, cols)
        if ci is None or ci == 0 or ci in seen:
            return False
        if extents is not None:
            # a value must overlap the printed content of its column (a panel
            # below with its own column layout does not; tier-2 review, Sonnet,
            # 2026-10-14)
            lo, hi = extents.get(ci, (None, None))
            if lo is None or tl.x1 < lo - X_TOLERANCE_PT or tl.x0 > hi + X_TOLERANCE_PT:
                return False
        seen.add(ci)
    return numeric >= 1


def continuation_bottom(ct: Any) -> float | None:
    """The PDF-space bottom y the grid should extend to, or ``None`` when no
    continuation rows sit directly below it."""
    if getattr(ct, "flavor", "") != "stream":
        return None
    rows = list(getattr(ct, "rows", None) or ())
    cols = list(getattr(ct, "cols", None) or ())
    bbox = getattr(ct, "_bbox", None)
    if len(rows) < 3 or len(cols) < MIN_COLS or not bbox or not _grid_is_numeric(ct):
        return None
    x0, y0, x1, _y1 = (float(v) for v in bbox)
    pitch = median(abs(float(a) - float(b)) for a, b in rows)
    if pitch <= 0:
        return None
    lines = [
        tl for tl in (getattr(ct, "textlines", None) or ())
        if _text(tl) and (tl.y0 + tl.y1) / 2.0 < y0
        and tl.x1 > x0 and tl.x0 < x1
    ]
    if not lines:
        return None
    first_right = float(cols[0][1]) - X_TOLERANCE_PT
    prev_cy = (float(rows[-1][0]) + float(rows[-1][1])) / 2.0
    accepted_bottom: float | None = None
    pending: list[Any] | None = None  # a one-line band waiting for its next band
    extents = _column_extents(ct, cols, y0)
    for band in _bands(lines, tol=pitch / 2.0):
        cy = (band[0].y0 + band[0].y1) / 2.0
        if prev_cy - cy > MAX_GAP_PITCHES * pitch:
            break
        if any(tl.x0 < x0 - X_TOLERANCE_PT or tl.x1 > x1 + X_TOLERANCE_PT for tl in band):
            break
        if _band_is_value_row(band, cols, extents):
            members = band + (pending or [])
            accepted_bottom = min(tl.y0 for tl in members)
            pending = None
        elif len(band) == 1 and pending is None and band[0].x0 < first_right:
            pending = band
        else:
            break
        prev_cy = cy
    return accepted_bottom


def extend_to_table_bottom(camelot: Any, tmp_path: str, ct: Any) -> Any:
    """Return a re-read of ``ct`` that also holds the continuation rows directly
    below it, or ``ct`` unchanged. Never raises."""
    try:
        bottom = continuation_bottom(ct)
        if bottom is None:
            return ct
        x0, _y0, x1, y1 = (float(v) for v in ct._bbox)
        cols = list(ct.cols)
        seps = ",".join(f"{float(c[1]):.2f}" for c in cols[:-1])
        new = list(camelot.read_pdf(
            tmp_path, pages=str(ct.page), flavor="stream", strip_text="\n",
            table_areas=[f"{x0:.2f},{y1:.2f},{x1:.2f},{bottom - 1.0:.2f}"],
            columns=[seps], suppress_stdout=True,
        ))
        if len(new) != 1:
            return ct
        old_rows = ct.df.values.tolist()
        new_rows = new[0].df.values.tolist()
        if (len(new_rows) <= len(old_rows)
                or len(new[0].df.columns) != len(ct.df.columns)
                or new_rows[: len(old_rows)] != old_rows):
            return ct
        # How many non-empty cells the appended rows carry: the table picker
        # must not let these alone flip a choice (see extract_structured).
        new[0]._docpluck_appended_cells = sum(
            1 for row in new_rows[len(old_rows):] for cell in row if str(cell).strip()
        )
        return new[0]
    except Exception:
        return ct
