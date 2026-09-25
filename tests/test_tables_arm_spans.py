"""`tables/arm_spans.py` reads a super-header label's span off the page.

The geometry below is the MEASURED geometry of 10.1525/collabra.90203 p14
Table 10 (pdfplumber, 2026-09-25): label glyph runs, sub-header glyphs, the two
vertical rules drawn as filled curves at x 222.9-223.6 and 319.4-320.1, and the
single horizontal rule under both labels (x 223.2-541.3, y 91.1). It is copied
here so the decision logic is pinned without the closed-access PDF; the real-PDF
tests in `test_tables_superheader_alignment_real_pdf.py` prove the shape occurs.
Each negative case removes or contradicts ONE piece of that evidence.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from docpluck.tables.arm_spans import anchor_super_header_spans, super_header_spans
from docpluck.tables.cell_cleaning import _merge_continuation_rows

# Camelot column rectangles (x0, x1) for Table 10, and row bands (top, bottom).
_COLS = [(54.0, 209.1), (209.1, 270.5), (270.5, 320.3), (320.3, 366.5),
         (366.5, 410.6), (410.6, 485.3), (485.3, 525.9)]
_ROWS = [(73.6, 92.2), (92.2, 107.1), (107.1, 121.6), (121.6, 135.7)]


def _chars(text: str, x0: float, x1: float, top: float) -> list[dict]:
    step = (x1 - x0) / max(len(text), 1)
    return [
        {"text": ch, "x0": x0 + i * step, "x1": x0 + (i + 1) * step,
         "top": top, "bottom": top + 8.0}
        for i, ch in enumerate(text)
    ]


@dataclass
class _Page:
    chars: list = field(default_factory=list)
    lines: list = field(default_factory=list)
    rects: list = field(default_factory=list)
    curves: list = field(default_factory=list)


@dataclass
class _Doc:
    pages: list


def _t10(*, vertical=True, underline=None, off_centre=0.0):
    words = [  # (text, x0, x1, top) as measured
        ("Target", 248.5 + off_centre, 270.7 + off_centre, 80.9),
        ("article", 272.3 + off_centre, 294.6 + off_centre, 80.9),
        ("Replication", 410.7, 450.3, 80.9),
        ("Conditions", 65.2, 103.5, 95.7), ("r", 245.0, 247.8, 95.7),
        ("p", 292.5, 296.7, 95.7), ("n", 340.8, 345.0, 95.7),
        ("r", 385.6, 388.4, 95.7), ("95%", 434.3, 449.9, 95.7),
        ("CI", 451.4, 459.4, 95.7), ("p", 511.4, 515.5, 95.7),
        ("Identifiable", 65.2, 110.0, 110.0), (".34", 240.0, 251.0, 110.0),
        ("N/A", 286.0, 301.0, 110.0), ("170", 336.0, 349.0, 110.0),
        (".63", 381.0, 392.0, 110.0), ("[0.53,", 421.0, 446.0, 110.0),
        ("0.72]", 448.0, 468.0, 110.0), ("<", 500.0, 504.0, 110.0),
        (".001", 506.0, 522.0, 110.0),
        ("Joint", 65.2, 85.0, 124.0), ("N/A", 237.0, 253.0, 124.0),
        ("N/A", 286.0, 301.0, 124.0), ("161", 336.0, 349.0, 124.0),
        (".59", 381.0, 392.0, 124.0), ("[0.58,", 421.0, 446.0, 124.0),
        ("0.80]", 448.0, 468.0, 124.0), ("<", 500.0, 504.0, 124.0),
        (".001", 506.0, 522.0, 124.0),
    ]
    chars = [c for w in words for c in _chars(*w)]
    page = _Page(chars=chars)
    page.rects.append({"x0": 223.2, "x1": 541.3, "top": 91.1, "bottom": 91.9})
    if vertical:
        page.curves += [
            {"x0": 222.9, "x1": 223.6, "top": 106.0, "bottom": 192.1},
            {"x0": 319.4, "x1": 320.1, "top": 106.0, "bottom": 192.1},
        ]
    if underline:
        page.lines += underline
    grid = [
        {0: None, 2: "Target article", 5: "Replication"},
        {0: "Conditions", 1: "r", 2: "p", 3: "n", 4: "r", 5: "95% CI", 6: "p"},
        {0: "Identifiable/ Explicit learning", 1: ".34", 2: "N/A", 3: "170",
         4: ".63", 5: "[0.53, 0.72]", 6: "< .001"},
        {0: "Joint/ No explicit learning", 1: "N/A", 2: "N/A", 3: "161",
         4: ".59", 5: "[0.58, 0.80]", 6: "< .001"},
    ]
    cells = [
        {"r": r, "c": c, "rowspan": 1, "colspan": 1, "text": text,
         "is_header": r == 0,
         "bbox": (_COLS[c][0], _ROWS[r][0], _COLS[c][1], _ROWS[r][1])}
        for r, row in enumerate(grid) for c, text in row.items() if text
    ]
    table = {"page": 1, "cells": cells, "rendering": "whitespace",
             "cell_geometry": "verified:0.95", "html": ""}
    return table, _Doc(pages=[page])


def _spans(table, doc):
    s = super_header_spans(table, doc)
    if s is None:
        return None
    return {table["cells"][i]["text"]: (a, b, ev) for i, (a, b, ev) in s.items()}


def test_vertical_rules_and_centring_give_the_printed_2_plus_4():
    table, doc = _t10()
    assert _spans(table, doc) == {
        "Target article": (1, 2, "vertical_rules+centred"),
        "Replication": (3, 6, "vertical_rules+centred"),
    }


def test_anchor_moves_labels_and_records_colspan():
    table, doc = _t10()
    assert anchor_super_header_spans(table, doc) is True
    top = {c["text"]: (c["c"], c["colspan"]) for c in table["cells"] if c["r"] == 0}
    assert top == {"Target article": (1, 2), "Replication": (3, 4)}
    assert "Target article" in table["html"]
    # Idempotent: a second pass finds nothing left to change.
    assert anchor_super_header_spans(table, doc) is False


def test_no_rules_no_change():
    # The one shared horizontal rule under BOTH labels is not an arm underline.
    table, doc = _t10(vertical=False)
    assert _spans(table, doc) is None
    assert anchor_super_header_spans(table, doc) is False


def test_rule_without_centring_is_refused():
    # Shift the Target-article label 20pt right: the rules still cut the table,
    # but the label is no longer centred over the segment -- two signals
    # disagree, so nothing is stated.
    table, doc = _t10(off_centre=20.0)
    assert _spans(table, doc) is None


def test_per_arm_underlines_are_read():
    table, doc = _t10(vertical=False, underline=[
        {"x0": 230.0, "x1": 310.0, "top": 90.5, "bottom": 90.5},
        {"x0": 330.0, "x1": 530.0, "top": 90.5, "bottom": 90.5},
    ])
    assert _spans(table, doc) == {
        "Target article": (1, 2, "underline_rule"),
        "Replication": (3, 6, "underline_rule"),
    }


def test_underline_contradicting_the_vertical_rules_is_refused():
    # Underlines say 3 + 3; the vertical rules say 2 + 4. State nothing.
    table, doc = _t10(underline=[
        {"x0": 230.0, "x1": 355.0, "top": 90.5, "bottom": 90.5},
        {"x0": 370.0, "x1": 530.0, "top": 90.5, "bottom": 90.5},
    ])
    assert _spans(table, doc) is None


def test_single_column_underlines_are_not_arms():
    # Per-cell top borders of a boxed grid sit under whatever is above them;
    # a one-column "span" groups nothing and must not move a label.
    table, doc = _t10(vertical=False, underline=[
        {"x0": 262.0, "x1": 300.0, "top": 90.5, "bottom": 90.5},
        {"x0": 420.0, "x1": 470.0, "top": 90.5, "bottom": 90.5},
    ])
    assert _spans(table, doc) is None
    assert anchor_super_header_spans(table, doc) is False


def test_no_verified_geometry_no_change():
    table, doc = _t10()
    table["cell_geometry"] = "no_layout"
    assert _spans(table, doc) is None
    table, _ = _t10()
    assert super_header_spans(table, None) is None


def test_docx_markup_is_never_touched():
    table, doc = _t10()
    table["rendering"] = "markup"
    assert _spans(table, doc) is None


# ── cell_cleaning: a prose line is not a continuation of a statistic ─────────


def test_heading_is_not_merged_onto_a_value():
    # 10.1525/collabra.90203 p12 Table 8, as Camelot emits it.
    rows = [
        ["Replication", "3.91", ".020", "1.77", ".01", "[.00, .021]"],
        ["", "H2: Interaction: Identifiability and Explicit Learning", "", "", "", ""],
        ["Without joint condition [S1]", "", "", "", "", ""],
    ]
    out = _merge_continuation_rows([list(r) for r in rows])
    assert out[0][1] == "3.91"
    assert out[1][1].startswith("H2: Interaction")


def test_wrapped_label_still_merges_onto_a_label():
    # The sibling shape on the same page: a hypothesis line under a label row
    # whose column-1 cell is EMPTY still joins it.
    rows = [
        ["With joint condition [E]", "", "", "", "", ""],
        ["", "H1b: Identifiable (Explicit & Control) vs. Statistical", "", "", "", ""],
        ["Replication", "3.91", ".020", "1.77", ".01", "[.00, .021]"],
    ]
    out = _merge_continuation_rows([list(r) for r in rows])
    assert len(out) == 2
    assert out[0][1].startswith("H1b:")


def test_wrapped_prose_still_merges_onto_prose():
    rows = [["2a", "People underestimate how much"], ["", "others value the gift"]]
    out = _merge_continuation_rows([list(r) for r in rows])
    assert len(out) == 1
