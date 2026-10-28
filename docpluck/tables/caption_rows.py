"""Take a table's own label and caption lines out of the top of its grid.

A capture region that starts at, or inside, the caption puts the caption's
lines in the grid's first rows. Every consumer of the grid then read them as
table content: the html put them in ``<thead>`` (10.1016/j.jesp.2021.104154
Table 3, p6: the header was "Table 3"), and a region that began on the
caption's last line shipped that line as the column header
(10.1177/0956797615601103 Table 1, p4). ``flatten`` already blanked the label
and caption rows for its own records, so the html and the records disagreed
about the same table's header.

DELETE FURNITURE, NEVER DATA -- the same rule as the note rows at the bottom of
the grid (``extract_structured._move_note_rows_to_footnote``):

* only rows at the TOP of the grid, contiguously, are taken;
* a row leaves only when its text is the label itself, or is found verbatim
  (case, spacing and punctuation aside) in the table's caption, in order with
  the rows taken before it -- so the text is not lost, it is the caption;
* without the printed label row, the rows taken must together END the caption
  (the region began inside it), and be at least 30 letters/digits long; a
  header word that merely appears in the caption is never matched;
* a lone page running head is taken only when the label row is directly below
  it (nothing above a table's own label is that table's content);
* a row holding a data value never leaves, and at least two rows must remain.

Each move is recorded (``table_caption_rows_moved_to_caption``).
"""

from __future__ import annotations

import re
from typing import Optional

from ..telemetry import record_fallback
from .cell_cleaning import _is_data_value_cell

_CONT_KEYS = ("continued", "cont", "contd")
#: A caption tail taken WITHOUT the printed label must be long: a short spanner
#: the caption absorbed ("Participant group, mean (SD)a", 23 letters/digits,
#: 10.1001/jamanetworkopen.2023.39337 Table 3) is a header line, not a tail.
_MIN_UNLABELLED_KEY = 30
_MIN_LINE_KEY = 12


def _key(s: str) -> str:
    return re.sub(r"[^0-9a-z]", "", (s or "").lower())


def _caption_rows_at_top(rows: list[list[str]], label: Optional[str],
                         caption: Optional[str]) -> int:
    """How many of ``rows`` (non-empty rows, top first) are the table's own
    running head / label / caption lines. 0 when none qualify."""
    lab = _key(label or "")
    cap = _key(caption or "")
    if not cap and not lab:
        return 0

    def is_label_row(row: list[str]) -> bool:
        k = "".join(_key(c) for c in row)
        return bool(lab) and (k == lab or k in tuple(lab + c for c in _CONT_KEYS))

    def has_value(row: list[str]) -> bool:
        return any(_is_data_value_cell((c or "").strip()) for c in row if (c or "").strip())

    i = 0
    labelled = False
    # A running head directly above the label row.
    if (
        len(rows) >= 2
        and not is_label_row(rows[0])
        and is_label_row(rows[1])
        and sum(1 for c in rows[0] if (c or "").strip()) <= 2
        and not has_value(rows[0])
    ):
        i = 1
    if i < len(rows) and is_label_row(rows[i]):
        labelled = True
        i += 1
    block = ""
    j = i
    while j < len(rows):
        row = rows[j]
        if has_value(row):
            break
        k = "".join(_key(c) for c in row)
        if not k:
            break
        cand = block + k
        # The row's text must continue the caption text already taken.
        if cap.find(cand) == -1:
            break
        single = sum(1 for c in row if (c or "").strip()) == 1
        if len(k) < _MIN_LINE_KEY and not (block and single):
            break
        block = cand
        j += 1
    # "Table 3 Study 1: ..." on one row carries the label too.
    if lab and block.startswith(lab):
        labelled = True
    if j > i and not labelled:
        if len(block) < _MIN_UNLABELLED_KEY or not cap.endswith(block):
            return 0
    return j


def move_caption_rows_out_of_grid(tables: list | None) -> None:
    """Drop the label / caption rows at the top of each captioned PDF grid and
    re-render its html. Leaves a table untouched unless its html is exactly
    what its cells render to (so no other channel's edit is undone)."""
    from .render import cells_to_html

    for t in tables or ():
        cells = t.get("cells") or []
        if not cells or t.get("rendering") == "markup":
            continue
        label, caption = t.get("label"), t.get("caption")
        if not label and not caption:
            continue
        by_row: dict[int, list] = {}
        for c in cells:
            by_row.setdefault(c["r"], []).append(c)
        order = [r for r in sorted(by_row)
                 if any((c.get("text") or "").strip() for c in by_row[r])]
        rows = [[(c.get("text") or "") for c in sorted(by_row[r], key=lambda c: c["c"])]
                for r in order]
        n = _caption_rows_at_top(rows, label, caption)
        if n <= 0 or len(order) - n < 2:
            continue
        if (t.get("html") or "") != cells_to_html(cells):
            record_fallback("table_caption_rows_kept_html_not_from_cells", detail=str(label))
            continue
        gone = {r for r in sorted(by_row) if r <= order[n - 1]}
        kept_rows = [r for r in sorted(by_row) if r not in gone]
        renum = {r: i for i, r in enumerate(kept_rows)}
        new_cells = []
        for c in cells:
            if c["r"] in gone:
                continue
            nc = dict(c)
            nc["r"] = renum[c["r"]]
            new_cells.append(nc)
        t["cells"] = new_cells
        t["n_rows"] = len(kept_rows)
        t["html"] = cells_to_html(new_cells)
        def row_text(r: int) -> str:
            return " ".join((c.get("text") or "") for c in
                            sorted(by_row[r], key=lambda c: c["c"])).strip()

        # Where raw_text IS the grid's rows (Camelot), keep it the grid's rows;
        # any other raw_text is left exactly as it was.
        if (t.get("raw_text") or "") == "\n".join(
            x for r in sorted(by_row) if (x := row_text(r))
        ):
            t["raw_text"] = "\n".join(x for r in kept_rows if (x := row_text(r)))
        if t.get("accuracy") is not None:
            from .camelot_extract import capture_quality
            t["confidence"], t["whitespace"] = capture_quality(
                t["accuracy"], len(new_cells), len(kept_rows), t.get("n_cols")
            )
        record_fallback("table_caption_rows_moved_to_caption", detail=f"{label}:{n}")


__all__ = ["move_caption_rows_out_of_grid"]
