"""One printed value belongs to one table (Release B page check, 2026-11-16).

10.15626/mp.2022.3108 p10 published the lower rows of Table 9 under the label
"Table 10". A captioned grid whose value cells are mostly another captioned
table's cells on the same page is cleared and labelled, never published.
"""
from __future__ import annotations

from docpluck.extract_structured import _drop_grids_copied_from_a_neighbour


def _t(label, page, texts):
    return {"label": label, "page": page,
            "cells": [{"r": i, "c": 0, "text": x} for i, x in enumerate(texts)],
            "n_rows": len(texts), "n_cols": 1, "html": "<table/>", "raw_text": "x",
            "content_status": "cells"}


NINE = ["4.72 [2.03, 10.96]", "1.38 [1.06, 1.80]", "5.93 [2.48, 14.20]",
        "1.67 [1.27, 2.19]", "3.29 [1.28, 8.45]", "0.66 [0.47, 0.94]",
        "4.31 [1.62, 11.46]", "0.75 [0.53, 1.05]", "1.86 [0.76, 4.57]"]
TEN = ["0.66 [0.47, 0.94]", "0.75 [0.53, 1.05]", "3.29 [1.28, 8.45]", "Table 10"]


def test_the_copy_is_cleared_and_labelled_the_owner_kept():
    t9, t10 = _t("Table 9", 10, NINE), _t("Table 10", 10, TEN)
    _drop_grids_copied_from_a_neighbour([t9, t10])
    assert t10["cells"] == [] and t10["content_status"] == "not_captured:grid_copies_another_table"
    assert len(t9["cells"]) == len(NINE) and t9["content_status"] == "cells"


def test_other_pages_and_small_overlaps_are_untouched():
    a, b = _t("Table 9", 10, NINE), _t("Table 10", 11, TEN)
    _drop_grids_copied_from_a_neighbour([a, b])
    assert b["cells"]
    c = _t("Table 3", 4, ["0.66 [0.47, 0.94]", "1.0", "2.0", "3.0", "4.0"])
    d = _t("Table 4", 4, ["0.66 [0.47, 0.94]", "9.0", "8.0"])
    _drop_grids_copied_from_a_neighbour([c, d])
    assert c["cells"] and d["cells"]


def _grid(label, page, rows):
    cells = [{"r": r, "c": c, "text": x} for r, row in enumerate(rows) for c, x in enumerate(row)]
    return {"label": label, "page": page, "cells": cells, "n_rows": len(rows),
            "n_cols": max(len(r) for r in rows), "html": "<table/>", "raw_text": "x",
            "content_status": "cells"}


def test_the_owner_is_kept_when_the_neighbour_grid_spans_both_tables():
    """10.5334/irsp.946 p5 prints Table 2 and Table 3 side by side, captions
    under each. Table 2's grid ran across both, so it holds Table 3's values in
    the same rows as its own. Table 3 owns those values and is kept."""
    t2 = _grid("Table 2", 5, [
        ["Past", "4.25", "1.39", "4.68", "0.72", "Past", "4.56", "0.92", "4.81", "1.22"],
        ["Future", "3.01", "1.39", "4.00", "1.08", "Future", "3.94", "1.36", "4.33", "1.34"],
        ["Overall", "3.63", "1.02", "4.34", "1.02", "Overall", "4.24", "0.95", "4.58", "1.15"]])
    t3 = _grid("Table 3", 5, [
        ["Past 4.56 0.92", "4.81", "1.22"], ["Future 3.94 1.36", "4.33", "1.34"],
        ["Overall 4.24 0.95", "4.58", "1.15"],
        ["Table 3 Study 1b: Predictability descriptives.", "", ""]])
    _drop_grids_copied_from_a_neighbour([t2, t3])
    assert t3["cells"] and t3["content_status"] == "cells"


def test_a_summary_table_repeating_values_is_kept():
    """Without its own label row under the data there is no evidence the grid
    was read from above its caption: a table may legitimately repeat values."""
    t9, t10 = _t("Table 9", 10, NINE), _t("Table 10", 10, TEN[:-1])
    _drop_grids_copied_from_a_neighbour([t9, t10])
    assert t10["cells"]


def test_the_cleared_copy_keeps_its_own_printed_text():
    """The copied grid is removed, never the table's own text read under its
    caption (10.15626/mp.2022.3108 Table 10 keeps its Signal/Directionality
    rows as text)."""
    t9, t10 = _t("Table 9", 10, NINE), _t("Table 10", 10, TEN)
    own = "Signal\nDirectionality\nYes\nConsistent"
    _drop_grids_copied_from_a_neighbour(
        [t9, t10], rebuild=lambda t: {"raw_text": own, "content_status": "raw_text"})
    assert t10["cells"] == [] and t10["raw_text"] == own and t10["content_status"] == "raw_text"


def test_a_rebuilt_text_carrying_the_neighbour_values_is_refused():
    """The rebuilt text is only kept when it is the table's OWN text. A read
    that crosses into the neighbour (a caption under its table, a side-by-side
    gutter) carries the copied values again, so it is refused and labelled."""
    t9, t10 = _t("Table 9", 10, NINE), _t("Table 10", 10, TEN)
    leaked = "Signal\n0.66 [0.47, 0.94]\n0.75 [0.53, 1.05]"
    _drop_grids_copied_from_a_neighbour(
        [t9, t10], rebuild=lambda t: {"raw_text": leaked, "content_status": "raw_text"})
    assert t10["raw_text"] == "" and t10["content_status"] == "not_captured:grid_copies_another_table"
