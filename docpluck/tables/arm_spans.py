"""Which columns does a spanning super-header label cover? Read it off the page.

A parallel-arm table prints a super-header row ("Target article" / "Replication",
"Original" / "Replication") whose labels each span several columns. Camelot's
stream flavour loses that span: every label becomes a one-column cell at whatever
column its text happened to fall in. `flatten._detect_column_groups` then has to
decide where each arm starts and ends from the header STRINGS alone, and until
v2.4.146 it guessed -- the data region was cut into equal-width blocks, one per
label.

That guess is wrong whenever the arms are unequal. Measured on
`10.1525/collabra.90203` p14, Table 10: the page prints `Target article` over
`r p` and `Replication` over `n r 95% CI p` (2 + 4 columns), with a vertical rule
between `p` and `n`. The equal-width cut made it 3 + 3 and bound the replication's
per-condition `n` to the target article, which (a) removed the `n` every
Replication confidence interval needs to be checked, and (b) published a
fabricated `r(168)` for a study whose N was about 118.

**The page states the span, so we read it instead of guessing.** Two kinds of
evidence are used, both TYPOGRAPHIC (what the renderer drew), neither inferred
from the numbers:

* **Underline rule (R).** A horizontal rule drawn between the label and the
  sub-header row, under exactly one label -- the `cmidrule` of a LaTeX table, the
  per-arm underline of a Word one. Its x-extent IS the span: the columns whose
  sub-header text is centred inside it. `10.1080/23743603.2021.1878340` p16
  Table 4 prints one per arm.
* **Vertical rules (V) + centring.** Vertical rules that separate two adjacent
  columns' text cut the table into ruled segments; a label's span is the segment
  under it. Because a segment can also swallow a row-label column, V is accepted
  only when the label is also CENTRED over the segment's text -- two signals of
  different physical origin (vector rules vs glyph positions) that must agree.

When the evidence is missing, ambiguous, or the two kinds disagree, NOTHING is
changed and flatten keeps its previous behaviour. Every label of the row must be
anchored or none is -- a table half-anchored by evidence and half by the guess
would bind columns by two different rules at once.

The result is recorded on the cell the file describes: the label cell moves to
its arm's first column and carries the printed `colspan` and the spanned
rectangle. `colspan` was already part of the `Cell` contract and was hard-coded
to 1 on every PDF path because nothing knew better.
"""
from __future__ import annotations

from itertools import pairwise
from typing import Any

from . import Cell, Table

# A rule is a thin vector object. 1.5pt covers hairlines drawn as filled rects
# (collabra.90203 draws its rules as 0.7-0.8pt filled rects and curves).
_RULE_THICKNESS = 1.5
# Label glyph runs further apart than this (pt) are different labels.
_LABEL_GAP = 6.0
# A V-segment is accepted only if the label's centre is within this fraction of
# the segment's text width of the segment's centre.
_CENTRE_TOL = 0.12


def _is_zero(b) -> bool:
    return not b or all(float(v) == 0.0 for v in b)


def _chars_in(chars, x0, top, x1, bottom):
    out = []
    for ch in chars:
        cx = (float(ch["x0"]) + float(ch["x1"])) / 2.0
        cy = (float(ch["top"]) + float(ch["bottom"])) / 2.0
        if x0 <= cx <= x1 and top <= cy <= bottom and (ch.get("text") or "").strip():
            out.append(ch)
    return out


def _thin_objects(page) -> tuple[list[tuple[float, float, float]], list[tuple[float, float, float]]]:
    """(horizontal, vertical) rules as (lo, hi, at) triples.

    Horizontal: (x0, x1, y). Vertical: (top, bottom, x). Lines, rects and curves
    are all consulted -- publishers draw the same rule as any of the three.
    """
    horiz, vert = [], []
    for obj in list(page.lines) + list(page.rects) + list(page.curves):
        try:
            x0, x1 = float(obj["x0"]), float(obj["x1"])
            top, bottom = float(obj["top"]), float(obj["bottom"])
        except (KeyError, TypeError, ValueError):
            continue
        w, h = x1 - x0, bottom - top
        if h <= _RULE_THICKNESS and w >= 8.0:
            horiz.append((x0, x1, (top + bottom) / 2.0))
        elif w <= _RULE_THICKNESS and h >= 8.0:
            vert.append((top, bottom, (x0 + x1) / 2.0))
    return horiz, vert


def _label_runs(chars) -> list[tuple[str, float, float]]:
    """Cluster one row's glyphs into (text-without-spaces, x0, x1) runs."""
    runs: list[list[dict]] = []
    for ch in sorted(chars, key=lambda c: float(c["x0"])):
        if runs and float(ch["x0"]) - float(runs[-1][-1]["x1"]) <= _LABEL_GAP:
            runs[-1].append(ch)
        else:
            runs.append([ch])
    return [
        (
            "".join((c.get("text") or "") for c in r).replace(" ", ""),
            min(float(c["x0"]) for c in r),
            max(float(c["x1"]) for c in r),
        )
        for r in runs
    ]


def _contiguous(cols: list[int]) -> bool:
    return bool(cols) and cols == list(range(cols[0], cols[-1] + 1))


def super_header_spans(table: Table, layout_doc: Any) -> dict[int, tuple[int, int, str]] | None:
    """Map each super-label cell index -> (first_col, last_col, evidence).

    Returns ``None`` when the table has no super-header row, carries no verified
    geometry, or the page does not state every label's span unambiguously.
    """
    if layout_doc is None or (table.get("rendering") or "") == "markup":
        return None
    if not str(table.get("cell_geometry") or "").startswith("verified"):
        return None
    cells: list[Cell] = list(table.get("cells") or [])
    if not cells or any(_is_zero(c.get("bbox")) for c in cells):
        return None
    try:
        page = layout_doc.pages[int(table.get("page") or 0) - 1]
    except (IndexError, TypeError, ValueError, AttributeError):
        return None
    chars = tuple(getattr(page, "chars", ()) or ())
    if not chars:
        return None

    r0 = min(c["r"] for c in cells)
    top = [i for i, c in enumerate(cells) if c["r"] == r0 and (c.get("text") or "").strip()]
    sub = [c for c in cells if c["r"] == r0 + 1 and (c.get("text") or "").strip()]
    if len(top) < 2 or len(sub) <= len(top):
        return None
    if any(int(cells[i].get("colspan") or 1) != 1 for i in top):
        return None  # already carries a span from somewhere else; leave it

    # Glyph extents per column (body + sub-header rows) and sub-header centres.
    n_cols = max(c["c"] for c in cells) + 1
    col_x0: dict[int, float] = {}
    col_x1: dict[int, float] = {}
    sub_centre: dict[int, float] = {}
    sub_top = None
    for c in cells:
        if c["r"] == r0:
            continue
        x0, t, x1, b = (float(v) for v in c["bbox"])
        g = _chars_in(chars, x0, t, x1, b)
        if not g:
            continue
        gx0 = min(float(ch["x0"]) for ch in g)
        gx1 = max(float(ch["x1"]) for ch in g)
        col_x0[c["c"]] = min(col_x0.get(c["c"], gx0), gx0)
        col_x1[c["c"]] = max(col_x1.get(c["c"], gx1), gx1)
        if c["r"] == r0 + 1:
            sub_centre[c["c"]] = (gx0 + gx1) / 2.0
            gt = min(float(ch["top"]) for ch in g)
            sub_top = gt if sub_top is None else min(sub_top, gt)
    if sub_top is None:
        return None

    # Label glyph runs across the whole label band (a centred label spills out
    # of the one-column cell Camelot gave it, so the cell bbox cannot bound it).
    band_top = min(float(cells[i]["bbox"][1]) for i in top)
    band_bot = max(float(cells[i]["bbox"][3]) for i in top)
    row_x0 = min(float(c["bbox"][0]) for c in cells)
    row_x1 = max(float(c["bbox"][2]) for c in cells)
    runs = _label_runs(_chars_in(chars, row_x0 - 40, band_top, row_x1 + 40, band_bot))
    label_x: dict[int, tuple[float, float]] = {}
    for i in top:
        want = (cells[i].get("text") or "").replace(" ", "")
        hits = [(x0, x1) for t, x0, x1 in runs if t == want]
        if len(hits) != 1:
            return None
        label_x[i] = hits[0]
    label_bottom = max(
        float(ch["bottom"])
        for ch in _chars_in(chars, row_x0 - 40, band_top, row_x1 + 40, band_bot)
    )
    centres = {i: (a + b) / 2.0 for i, (a, b) in label_x.items()}

    horiz, vert = _thin_objects(page)
    body_rows = [c for c in cells if c["r"] > r0 + 1]
    body_top = min((float(c["bbox"][1]) for c in body_rows), default=None)
    body_bot = max((float(c["bbox"][3]) for c in body_rows), default=None)

    # (R) an underline under exactly one label.
    span_r: dict[int, list[int]] = {}
    for i in top:
        own = [
            (x0, x1) for x0, x1, y in horiz
            if label_bottom - 1.0 <= y <= sub_top + 1.0
            and x0 <= centres[i] <= x1
            and not any(x0 <= centres[j] <= x1 for j in top if j != i)
        ]
        if len(own) == 1:
            x0, x1 = own[0]
            cols = sorted(c for c, cx in sub_centre.items() if x0 - 2.0 <= cx <= x1 + 2.0)
            if _contiguous(cols):
                span_r[i] = cols

    # (V) ruled segments, each confirmed by centring.
    span_v: dict[int, list[int]] = {}
    if body_top is not None and body_bot is not None:
        need = 0.5 * (body_bot - body_top)
        cuts = set()
        for t, b, x in vert:
            if min(b, body_bot) - max(t, body_top) < need:
                continue
            for c in range(n_cols - 1):
                if c in col_x1 and c + 1 in col_x0 and col_x1[c] <= x + 0.5 and col_x0[c + 1] >= x - 0.5:
                    cuts.add(c)
        if cuts:
            segs, cur = [], []
            for c in range(n_cols):
                cur.append(c)
                if c in cuts:
                    segs.append(cur)
                    cur = []
            if cur:
                segs.append(cur)
            for i in top:
                for seg in segs:
                    present = [c for c in seg if c in col_x0]
                    if not present:
                        continue
                    sx0, sx1 = col_x0[present[0]], col_x1[present[-1]]
                    if not sx0 <= centres[i] <= sx1:
                        continue
                    others = [j for j in top if j != i and sx0 <= centres[j] <= sx1]
                    mid = (sx0 + sx1) / 2.0
                    if not others and abs(centres[i] - mid) <= _CENTRE_TOL * (sx1 - sx0):
                        span_v[i] = present
                    break

    out: dict[int, tuple[int, int, str]] = {}
    for i in top:
        r, v = span_r.get(i), span_v.get(i)
        if r and v and r != v:
            return None  # the two kinds of evidence disagree: state nothing
        span, ev = (r, "underline_rule") if r else ((v, "vertical_rules+centred") if v else (None, ""))
        if not span:
            return None  # all or nothing
        if len(span) < 2:
            # A "span" of one column groups nothing. Measured 2026-09-25 over the
            # 102-paper test corpus: the only such case was a fully boxed grid
            # (10.15626/mp.2022.3108, supplement p37) whose per-cell
            # top borders sat under a running header -- furniture, not arms.
            return None
        out[i] = (span[0], span[-1], ev)
    ordered = [out[i] for i in sorted(top, key=lambda i: cells[i]["c"])]
    for (_a0, a1, _), (b0, _b1, _) in pairwise(ordered):
        if b0 <= a1:
            return None  # overlapping spans: not a partition
    return out


def anchor_super_header_spans(table: Table, layout_doc: Any) -> bool:
    """Move each super-label cell to its printed span; re-render html. Returns
    True when the table changed."""
    spans = super_header_spans(table, layout_doc)
    if not spans:
        return False
    cells = table["cells"]
    changed = False
    for i, (c0, c1, _ev) in spans.items():
        cell = cells[i]
        width = c1 - c0 + 1
        if cell["c"] == c0 and int(cell.get("colspan") or 1) == width:
            continue
        xs = [c["bbox"] for c in cells if c0 <= c["c"] <= c1 and c["r"] != cell["r"]]
        x0 = min(float(b[0]) for b in xs)
        x1 = max(float(b[2]) for b in xs)
        _, t, _, b = cell["bbox"]
        cell["c"] = c0
        cell["colspan"] = width
        cell["bbox"] = (x0, t, x1, b)
        changed = True
    if changed:
        from .render import cells_to_html
        table["html"] = cells_to_html(cells)
    return changed
