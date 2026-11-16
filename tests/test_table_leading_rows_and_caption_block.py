"""A table's caption and worded header are not trailing prose; a two-line caption
is measured from its last line.

Three rules, one mechanism family -- a grid deleted or narrowed because its TOP
rows were read as something below or beside it:

1. ``whitespace._trim_trailing_prose_rows`` cut from the first run of
   prose-like rows to the end. A region grid begins with its own caption lines
   and worded headers, so the run began at row 0 and the whole grid went
   (10.1016/j.jesp.2009.12.010 p5 Table 3: 7 -> 0 rows). Runs above the first
   data row (non-prose, two or more filled cells) are now skipped. The Camelot
   sibling (``camelot_extract._keep_after_prose_tail_trim``) is deliberately
   left as it was: changing it the same way changed no output on this paper and
   turned two body-text fragments of 10.1177/01461672251327169 p14 into an
   uncaptioned "table" (canary audit 2026-11-16).
2. ``_whitespace_grid_is_clean`` counted a long row label with clean numbers
   beside it as prose on upright pages (the same Table 3: 3 of 3 data rows).
3. ``detect._caption_top_rule_x1`` measured the 12pt gap to the table's top rule
   from the caption's LABEL line; a label line over a title line puts the rule
   under the title (same paper, p4 Table 2: 12.6pt), so the region stayed the
   width of the word "Table 2" and Camelot's whole-page grid gave Table 2
   Table 1's "Total %" rows.

Synthetic cells and glyphs below are invented; the real-PDF test reads the
paper through the article custodian and asserts the printed values (pages 4
and 5 rasterized and read 2026-11-16).
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from docpluck.tables.detect import _caption_block_bottom, _caption_top_rule_x1
from docpluck.tables.whitespace import _trim_trailing_prose_rows, _whitespace_grid_is_clean


def _cells(rows):
    out = []
    for r, row in enumerate(rows):
        for c, text in enumerate(row):
            if text:
                out.append({"r": r, "c": c, "text": text, "rowspan": 1, "colspan": 1,
                            "is_header": r == 0, "bbox": (0, 0, 0, 0)})
    return out


_HEADED = [
    ["Table 3"],
    ["Assessments and feelings of the participants in the study"],
    ["", "Fairness of", "Generosity", "Mood after", "Feelings about the other party"],
    ["", "final offer", "of final offer", "decision", "after the decision"],
    ["Group one members (all of whom accepted the offer)", "7.24", "6.41", "5.59", "5.53"],
    ["Group two members who accepted the final offer (n = 5)", "5.40", "4.60", "3.80", "4.80"],
    ["Group two members who rejected the final offer (n = 12)", "3.75", "3.75", "4.08", "4.75"],
]


def test_leading_caption_and_header_rows_are_not_trailing_prose():
    cells = _cells(_HEADED)
    kept = _trim_trailing_prose_rows(cells)
    assert {c["r"] for c in kept} == set(range(len(_HEADED)))


def test_trailing_prose_below_the_data_is_still_cut():
    prose = [
        ["the participants were then asked to rate how fair the offer had been and why"],
        ["and whether they would accept a similar proposal from the other negotiator"],
        ["in a later round of the same negotiation task with the same partner again"],
    ]
    cells = _cells(_HEADED + prose)
    kept_rows = {c["r"] for c in _trim_trailing_prose_rows(cells)}
    assert kept_rows == set(range(len(_HEADED)))


def test_long_row_labels_beside_clean_numbers_pass_the_clean_gate():
    assert _whitespace_grid_is_clean(_cells(_HEADED), own_caption_number=3)


def test_absorbed_prose_still_fails_the_clean_gate():
    prose = [
        ["the participants were then asked to rate how fair the offer had been", "and"],
        ["whether they would accept a similar proposal from the other negotiator", "in"],
        ["a later round of the same negotiation task with the same partner again", "so"],
        ["the confederate then made a second offer that was somewhat more generous", "to"],
    ]
    assert not _whitespace_grid_is_clean(_cells(prose))


def _char(text, x0, top, size=6.0):
    return {"text": text, "x0": x0, "x1": x0 + size * 0.5, "top": top,
            "bottom": top + size, "size": size, "upright": True, "fontname": "F"}


def _page(rule_top):
    chars = [_char(ch, 42.5 + 3.0 * i, 686.0) for i, ch in enumerate("Table 2")]
    chars += [_char(ch, 42.5 + 3.0 * i, 695.0) for i, ch in enumerate("A title line")]
    rule = {"x0": 42.5, "x1": 562.5, "top": rule_top, "bottom": rule_top + 0.5}
    return SimpleNamespace(chars=chars, lines=[rule], rects=[], curves=[], words=[],
                           width=595.0, height=794.0)


def test_caption_block_extends_through_the_title_line():
    page = _page(705.0)
    assert _caption_block_bottom(page, (42.5, 686.0, 64.0, 692.0), []) == pytest.approx(701.0)


def test_top_rule_under_a_two_line_caption_sets_the_table_width():
    page = _page(705.0)  # 13pt below the label line, 4pt below the title
    assert _caption_top_rule_x1(page, (42.5, 686.0, 64.0, 692.0)) == pytest.approx(562.5)


def test_rule_far_below_the_caption_block_is_not_its_top_rule():
    page = _page(730.0)
    assert _caption_top_rule_x1(page, (42.5, 686.0, 64.0, 692.0)) is None


def _rows(table):
    rows: dict[int, dict[int, str]] = {}
    for c in table.get("cells") or []:
        rows.setdefault(c["r"], {})[c["c"]] = (c.get("text") or "").strip()
    return [[rows[r].get(i, "") for i in range(max(rows[r]) + 1)] for r in sorted(rows)]


def test_real_paper_tables_2_and_3_carry_their_printed_values():
    from docpluck.extract_structured import extract_pdf_structured
    from docpluck.testing import require_corpus_pdf

    pdf = require_corpus_pdf("apa/ar_apa_j_jesp_2009_12_010.pdf")
    res = extract_pdf_structured(pdf.read_bytes())
    by_label = {t.get("label"): t for t in res["tables"]}

    t2 = [[x for x in row if x] for row in _rows(by_label["Table 2"])]
    assert ["Positive Expectations", "7.24 (+2.06)", "6.40 (+1.12)", "5.59 (+0.35)", "5.53 (+0.41)"] in t2
    assert ["Neutral Expectations", "4.24 (+0.59)", "4.00 (+0.47)", "4.00 (-0.35)", "4.76 (+0.29)"] in t2
    assert not any("Total %" in " ".join(row) for row in t2)

    t3 = _rows(by_label["Table 3"])
    data = [row[1:] for row in t3 if row and row[0]]
    assert data == [
        ["7.24", "6.41", "5.59", "5.53"],
        ["5.40", "4.60", "3.80", "4.80"],
        ["3.75", "3.75", "4.08", "4.75"],
    ]


def test_chan_feldman_tables_2_and_8_keep_their_correlation_columns():
    """10.1080/02699931.2024.2434156 pages 7 and 13 (read 2026-11-16): both
    correlation tables carry every printed column. A regression guard: 2.4.160
    already published these values, but the long row labels ("4 - Conciliatory
    motivation") now also pass the whitespace builder's clean gate, so this
    pins the result whichever builder wins."""
    from docpluck.extract_structured import extract_pdf_structured
    from docpluck.testing import require_corpus_pdf

    res = extract_pdf_structured(require_corpus_pdf("apa/chan_feldman_2025_cogemo.pdf").read_bytes())
    by_label = {t.get("label"): t for t in res["tables"]}
    t8 = [[x for x in row if x] for row in _rows(by_label["Table 8"])]
    revenge = next(row for row in t8 if row and "Revenge" in row[0])
    assert revenge[1:] == [
        "9.06", "4.73", "0.89", "0.89", ".03", "-.11", "-.43***", "-.05", ".37***"]
    # The Camelot path keeps the printed U+2212 through its cleaning steps; the
    # table must still reach the consumer with ASCII minus signs (hard rule).
    for t in res["tables"]:
        assert "−" not in (t.get("html") or "") + (t.get("raw_text") or "")
        assert not any("−" in (c.get("text") or "") for c in t.get("cells") or [])
    t2 = [[x for x in row if x] for row in _rows(by_label["Table 2"])]
    avoid = next(row for row in t2 if row and "Avoidance" in row[0])
    assert avoid[1:] == ["10.11", "3.89", ".90", "-.47**", "-.58**", "-.73**", "-.56**", "_"]
