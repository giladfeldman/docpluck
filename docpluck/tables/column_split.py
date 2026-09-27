"""Re-split a Camelot stream column that a spanning super-header merged.

THE DEFECT, ON A REAL PAGE
--------------------------
``10.1080/23743603.2021.1878340`` p16, Table 4. The page prints eight columns --
``Product category | F | p | eta2p (90% CI) | F | p | eta2p (90% CI) | Interpretation``
-- under two super-headers, ``Original`` and ``Replication``, each centred over
three of them. Camelot's stream parser derives columns from the x-extent of the
text on every row and merges any ranges that overlap; ``Original`` overlaps both
``p`` and ``eta2p``, so the two collapse into ONE column and every cell reads
``< .010.240`` -- the printed ``< .01`` and ``0.240`` concatenated, two
published numbers destroyed at once. Neither half can be recovered from the
fused string, so this is data loss, not formatting.

THE EVIDENCE IS TYPOGRAPHIC
---------------------------
The decision reads only what the renderer placed on the page: the x-positions of
the glyphs inside each Camelot cell. On the page above, ``< .01`` ends at
x=177.2 and ``0.240`` starts at x=203.2 -- a 26 pt gap in every data row, while
ordinary word spacing inside a cell is ~2 pt. No value is interpreted and no
number is judged plausible; a column is split only where the page itself leaves
an empty vertical band that every body row respects.

THE RULE
--------
Within one Camelot column:

1. Group each row's glyphs into runs, breaking where the horizontal gap exceeds
   ``GAP_FACTOR`` x the glyph size (a gap no word space reaches).
2. Rows with exactly two runs, both carrying a digit, are GAP ROWS. Their gaps
   are intersected into one candidate band.
3. Every row BELOW the first gap row is body: a body run that crosses the whole
   band vetoes the split; a run that enters the band from one side narrows it.
   Rows above the first gap row are the header zone and may cross -- that is
   exactly where the super-header that caused the merge lives.
4. The split is taken only with at least ``MIN_GAP_ROWS`` gap rows and a free
   band at least ``MIN_FREE_BAND_PT`` wide, at the band's midpoint.

The re-read passes the old separators plus the new ones to Camelot with
``split_text=False``, so a super-header stays whole (``split_text=True`` cuts
``Original`` into ``Origi | nal``, measured on the page above). The re-read is
KEPT ONLY IF it delivers the same non-space glyph multiset as the original grid
-- a re-split may move text between cells, never add or drop it.
"""

from __future__ import annotations

from collections import Counter
from statistics import median
from typing import Any

#: A gap wider than this many glyph-sizes is not a word space. Measured on the
#: xiao page: word spaces 2.2 pt at 9 pt type (0.24x), the column gap 26 pt (2.9x).
GAP_FACTOR = 1.5
#: Fewer gap rows than this is not a column, it is a coincidence of spacing.
MIN_GAP_ROWS = 3
#: The empty band left after body runs narrow it must still be this wide.
MIN_FREE_BAND_PT = 3.0
#: Camelot and pdfplumber must agree on the page size to share coordinates.
PAGE_SIZE_TOLERANCE_PT = 2.0


def _runs(chars: list[dict]) -> list[tuple[float, float, str]]:
    """Group glyphs into horizontal runs, breaking at a non-word-space gap."""
    chars = sorted(
        (c for c in chars if (c.get("text") or "").strip()),
        key=lambda c: float(c["x0"]),
    )
    if not chars:
        return []
    size = median(float(c.get("size") or 0.0) for c in chars) or 8.0
    thr = GAP_FACTOR * size
    runs: list[list[Any]] = [[float(chars[0]["x0"]), float(chars[0]["x1"]), chars[0]["text"]]]
    for c in chars[1:]:
        x0, x1 = float(c["x0"]), float(c["x1"])
        if x0 - runs[-1][1] > thr:
            runs.append([x0, x1, c["text"]])
        else:
            runs[-1][1] = max(runs[-1][1], x1)
            runs[-1][2] += c["text"]
    return [(a, b, t) for a, b, t in runs]


def _has_digit(s: str) -> bool:
    return any(ch.isdigit() for ch in s)


def merged_column_split_points(ct: Any, layout: Any, page: int) -> list[float]:
    """Separator x-positions (PDF space) to add, or ``[]`` when none is justified."""
    if layout is None or getattr(ct, "rotation", ""):
        return []
    pages = getattr(layout, "pages", None) or ()
    if not (1 <= page <= len(pages)):
        return []
    page_obj = pages[page - 1]
    height = float(getattr(page_obj, "height", 0.0) or 0.0)
    width = float(getattr(page_obj, "width", 0.0) or 0.0)
    if height <= 0.0:
        return []
    pdf_size = getattr(ct, "pdf_size", None)
    if pdf_size:
        try:
            if (abs(float(pdf_size[0]) - width) > PAGE_SIZE_TOLERANCE_PT
                    or abs(float(pdf_size[1]) - height) > PAGE_SIZE_TOLERANCE_PT):
                return []
        except (TypeError, ValueError, IndexError):
            return []
    cols = list(getattr(ct, "cols", None) or ())
    rows = list(getattr(ct, "rows", None) or ())
    if len(cols) < 2 or len(rows) < MIN_GAP_ROWS:
        return []
    page_chars = list(getattr(page_obj, "chars", None) or ())

    splits: list[float] = []
    for cx0, cx1 in cols:
        # Per row: the runs inside this column's rectangle (pdfplumber top-down).
        row_runs: list[list[tuple[float, float, str]]] = []
        for ytop, ybot in rows:
            top, bottom = height - float(ytop), height - float(ybot)
            inside = [
                c for c in page_chars
                if cx0 <= (float(c["x0"]) + float(c["x1"])) / 2 <= cx1
                and top <= (float(c["top"]) + float(c["bottom"])) / 2 <= bottom
            ]
            row_runs.append(_runs(inside))
        gap_rows = [
            i for i, rr in enumerate(row_runs)
            if len(rr) == 2 and _has_digit(rr[0][2]) and _has_digit(rr[1][2])
        ]
        if len(gap_rows) < MIN_GAP_ROWS:
            continue
        lo = max(row_runs[i][0][1] for i in gap_rows)
        hi = min(row_runs[i][1][0] for i in gap_rows)
        if hi - lo < MIN_FREE_BAND_PT:
            continue
        vetoed = False
        for i in range(gap_rows[0], len(row_runs)):
            for a, b, _t in row_runs[i]:
                if a < lo and b > hi:
                    vetoed = True
                    break
                if lo <= a < hi:
                    hi = a
                if lo < b <= hi:
                    lo = b
            if vetoed:
                break
        if vetoed or hi - lo < MIN_FREE_BAND_PT:
            continue
        splits.append((lo + hi) / 2.0)
    return splits


def _glyphs_of_row(ct: Any, r: int) -> Counter | None:
    try:
        df = ct.df
        return Counter(
            ch for c in range(len(df.columns))
            for ch in str(df.iloc[r, c]) if not ch.isspace()
        )
    except Exception:  # noqa: BLE001 - an unreadable row is never "equal"
        return None


def resplit_merged_columns(camelot: Any, tmp_path: str, ct: Any, layout: Any) -> Any:
    """Return a re-read of ``ct`` with super-header-merged columns split, or ``ct``.

    Stream tables only: a lattice grid takes its columns from ruled lines, not
    from text extent, so it cannot merge this way.
    """
    from docpluck.telemetry import record_fallback

    if (getattr(ct, "flavor", "") or "") != "stream":
        return ct
    try:
        page = int(getattr(ct, "page", 0) or 0)
    except (TypeError, ValueError):
        return ct
    extra = merged_column_split_points(ct, layout, page)
    if not extra:
        return ct
    bbox = tuple(getattr(ct, "_bbox", ()) or ())
    if len(bbox) != 4:
        return ct
    x0, y0, x1, y1 = (float(v) for v in bbox)
    seps = sorted({round(float(c[0]), 2) for c in ct.cols[1:]} | {round(s, 2) for s in extra})
    try:
        tables = list(camelot.read_pdf(
            tmp_path, pages=str(page), flavor="stream",
            table_areas=[f"{x0},{y1},{x1},{y0}"],
            columns=[",".join(f"{s:.2f}" for s in seps)],
            split_text=False, strip_text="\n", suppress_stdout=True,
        ))
    except Exception as exc:  # noqa: BLE001 - the original grid is still valid
        record_fallback("camelot_column_resplit_exception", detail=type(exc).__name__)
        return ct
    if len(tables) != 1:
        record_fallback("camelot_column_resplit_refused", detail=f"tables={len(tables)}")
        return ct
    new = tables[0]
    if len(new.df.columns) != len(ct.df.columns) + len(extra):
        record_fallback("camelot_column_resplit_refused",
                        detail=f"cols={len(new.df.columns)}")
        return ct
    # PER ROW, not per table: a whole-table multiset passes a re-read whose row
    # boundaries moved and shifted values between rows (Sonnet review,
    # 2026-09-27). A split may only move text sideways within its own row.
    if len(new.df) != len(ct.df) or any(
        _glyphs_of_row(ct, r) is None or _glyphs_of_row(new, r) != _glyphs_of_row(ct, r)
        for r in range(len(ct.df))
    ):
        record_fallback("camelot_column_resplit_refused", detail="row_glyphs_changed")
        return ct
    # A split must create a column that HOLDS something. Measured 2026-09-27 over
    # 251 papers: 10 of 17 firings only inserted a near-empty column (the band sat
    # beside, not between, the content), which is noise in the rendered table.
    # Each split must yield one more column populated in >= MIN_GAP_ROWS rows.
    if _dense_columns(new) < _dense_columns(ct) + len(extra):
        record_fallback("camelot_column_resplit_refused", detail="no_new_populated_column")
        return ct
    record_fallback("camelot_column_resplit", detail=f"p{page}+{len(extra)}")
    return new


def _dense_columns(ct: Any) -> int:
    """Columns holding text in at least ``MIN_GAP_ROWS`` rows."""
    df = ct.df
    return sum(
        1 for c in range(len(df.columns))
        if sum(1 for r in range(len(df)) if str(df.iloc[r, c]).strip()) >= MIN_GAP_ROWS
    )


__all__ = ["merged_column_split_points", "resplit_merged_columns"]
