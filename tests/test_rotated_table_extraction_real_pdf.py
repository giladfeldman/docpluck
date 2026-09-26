"""Tables printed SIDEWAYS are read in their own frame (owner decision 2026-09-25, B).

`docpluck/tables/rotated.py` turns a rotated table's glyphs upright by their text
matrix and grids them with the whitespace path's clustering and gates. Every case
below is a real page of a real paper, rasterized and read when the behaviour was
built; every assertion is paired with its opposite, because a table that is
"not wrong" because it is empty proves nothing (L-033).

The cases, by what each one guards:

* 10.1038/s41467-024-45528-0 Table 4 (p6): a rotated table on the left half of a
  page with upright prose on the right. Camelot does not grid it; this path does.
* 10.1098/rsos.140072 Table 1 (p5): a wholly sideways page whose journal header
  reads the OTHER way round, and whose rows are separated by dotted rules drawn
  as leader-dot glyphs.
* 10.1177/23780231251314667 Table 3 (p39): a one-column list table -- no grid is
  possible; its text must come back in reading order, without the sideways
  ``Author Manuscript`` watermark.
* 10.1016/j.jesp.2020.103977 Table 4 (p8) and 10.1177/00031224241252079 Table 3
  (p15): grids the column finder under-segments. They must be REFUSED, never
  shipped with two published columns in one cell or a standard error beside the
  wrong estimate.
* 10.1001/jamanetworkopen.2023.39337 Table 2 (p8): a subscript (HbA1c) and a
  same-size note that must neither merge rows nor become cells.
"""

import pytest

from docpluck.testing import require_corpus_pdf

_NAT = "nature/nat_comms_4.pdf"          # 10.1038/s41467-024-45528-0
_RSOS = "harvard/ar_royal_society_rsos_140072.pdf"  # 10.1098/rsos.140072
_SOCIUS4 = "asa/socius_4.pdf"            # 10.1177/23780231251314667
_JESP = "apa/jamison_2020_jesp.pdf"      # 10.1016/j.jesp.2020.103977
_ASR = "asa/am_sociol_rev_4.pdf"         # 10.1177/00031224241252079
_JAMA = "ama/jama_open_1.pdf"            # 10.1001/jamanetworkopen.2023.39337


def _structured(name: str, *, camelot: bool, monkeypatch=None):
    from docpluck.extract_structured import extract_pdf_structured

    if not camelot:
        monkeypatch.setenv("DOCPLUCK_DISABLE_CAMELOT", "1")
    return extract_pdf_structured(require_corpus_pdf(name).read_bytes())


def _table(result, label: str):
    found = [t for t in result["tables"] if t.get("label") == label]
    assert len(found) == 1, [t.get("label") for t in result["tables"]]
    return found[0]


def _rows(table) -> dict[int, list[str]]:
    rows: dict[int, list[str]] = {}
    for c in sorted(table["cells"], key=lambda c: (c["r"], c["c"])):
        rows.setdefault(c["r"], []).append(c["text"])
    return rows


def _row_labelled(table, label: str) -> list[str]:
    hits = [r for r in _rows(table).values() if r and r[0] == label]
    assert len(hits) == 1, (label, [r[0] for r in _rows(table).values()])
    return hits[0]


@pytest.fixture(scope="module")
def nat():
    pytest.importorskip("camelot", reason="the production path runs Camelot first")
    return _structured(_NAT, camelot=True)


def test_a_half_page_rotated_table_is_gridded(nat):
    t4 = _table(nat, "Table 4")
    assert t4["kind"] == "structured" and t4["content_status"] == "cells"
    assert t4["cell_geometry"] == "whitespace_rotated"
    assert t4["n_cols"] == 5
    # Read off the rasterized page: Plasma C-Reactive Protein, all four arms.
    assert _row_labelled(t4, "Plasma C-Reactive Protein (mg/L)")[1:] == [
        "-5.9 (-10.3, -1.4) P = 0.03",
        "-4.8 (-9.2, -0.5) P = 0.07",
        "-3.0 (-7.2, 1.2) P = 0.24",
        "-5.2 (-9.6, -0.8) P = 0.05",
    ]
    # A two-line cell (estimate over CI) stays one cell, lines in order.
    assert _row_labelled(
        t4, "Composite score relative to Standard Care, adjusted for core covariates"
    )[1] == "-0.58 (-1.4, 0.23) P = 0.24"
    assert t4["caption"] == (
        "Table 4 | Effect sizes in ANCOVA modelsa compared to standard care, with 90% CIs"
    )
    assert (t4["footnote"] or "").startswith("Effect sizes are shown (with 90%CIs)")
    assert "Table 4:grid" in nat["fallback_details"]["rotated_table_read"]


def test_the_upright_prose_beside_it_is_not_read(nat):
    """Two-sided: the right half of p6 is upright body prose. None of it may reach
    the grid, and the paper's upright tables are not read as rotated."""
    t4 = _table(nat, "Table 4")
    text = " ".join(c["text"] for c in t4["cells"]) + " " + (t4["footnote"] or "")
    for upright in ("Ethics approval", "Recruitment, inclusion", "considered a biomarker"):
        assert upright not in text, upright
    for label in ("Table 1", "Table 2", "Table 3"):
        t = _table(nat, label)
        assert t["cell_geometry"] != "whitespace_rotated", label
        assert t["cells"], label


def test_rotated_cell_boxes_hold_exactly_their_glyphs(nat):
    """``whitespace_rotated`` claims REAL page rectangles. Check it on the page:
    the rotated glyphs whose centres fall in each cell box are that cell's text.
    Two-sided: the same box shifted one column over holds another cell's."""
    from docpluck.extract_layout import extract_pdf_layout
    from docpluck.tables.rotated import glyph_direction

    t4 = _table(nat, "Table 4")
    page = extract_pdf_layout(require_corpus_pdf(_NAT).read_bytes(), pages=[5]).pages[5]
    glyphs = [c for c in page.chars if glyph_direction(c) == 1 and c["text"].strip()]

    def inside(box):
        x0, top, x1, bottom = box
        return sorted(
            c["text"].replace("−", "-") for c in glyphs
            if x0 <= (c["x0"] + c["x1"]) / 2 <= x1 and top <= (c["top"] + c["bottom"]) / 2 <= bottom
        )

    data = [c for c in t4["cells"] if c["c"] >= 1 and c["r"] >= 1 and c["text"]]
    assert len(data) >= 40
    for c in data:
        assert inside(c["bbox"]) == sorted(c["text"].replace(" ", "")), c
    by_pos = {(c["r"], c["c"]): c for c in t4["cells"]}
    probe = next(c for c in data if (c["r"], c["c"] + 1) in by_pos and by_pos[(c["r"], c["c"] + 1)]["text"])
    neighbour = by_pos[(probe["r"], probe["c"] + 1)]
    assert inside(neighbour["bbox"]) != sorted(probe["text"].replace(" ", ""))


def test_sideways_furniture_reading_the_other_way_is_not_the_table(monkeypatch):
    """rsos.140072 p5: the whole page is sideways. Table 1 reads up the page, the
    journal header ``rsos.royalsocietypublishing.org`` down it. The header must be
    in no part of the table -- and must still be in the document (not deleted)."""
    result = _structured(_RSOS, camelot=False, monkeypatch=monkeypatch)
    t1 = _table(result, "Table 1")
    assert t1["cell_geometry"] == "whitespace_rotated"
    rows = list(_rows(t1).values())
    # Read off the rasterized page: all four fish, every value.
    assert ["breeder", "male", "9", "10.0 (9.6–11.2)", "71.6 (69.6–72.4)", "40.9 (37.4–41.2)",
            "0.5 (0.5–1.0)", "9.5 (6.0–10.0)", "0.0 (0.0–0.0)", "1.0 (0.0–1.5)"] in rows
    assert ["subordinate", "female", "11", "6.1 (4.8–7.0)", "59.0 (55.6–61.0)", "3.18 (2.95–3.49)",
            "0.0 (0.0–0.0)", "1.0 (0.5–3.5)", "4.0 (2.3–8.0)", "2.5 (0.8–3.5)"] in rows
    assert sum(1 for r in rows if r[0] in ("breeder", "subordinate")) == 4
    everything = " ".join(
        [t1["caption"] or "", t1["footnote"] or "", t1["raw_text"] or ""]
        + [c["text"] for c in t1["cells"]]
    )
    assert "royalsocietypublishing" not in everything
    from docpluck.extract import extract_pdf

    assert "royalsocietypublishing" in extract_pdf(require_corpus_pdf(_RSOS).read_bytes())[0]
    # The rows are separated by dotted rules drawn as glyphs: counted, not rows.
    assert not any(set(c["text"]) <= {".", " "} and c["text"] for c in t1["cells"])
    details = result["fallback_details"]["rotated_table_lines_not_read"]
    assert any(d.startswith("Table 1:") and "dotted_rules=5" in d for d in details), details


def test_a_list_table_comes_back_in_reading_order(monkeypatch):
    """socius_4 Table 3 is one column of activity codes: no grid. Its text must
    be the table's own, in the order printed, without the watermark."""
    result = _structured(_SOCIUS4, camelot=False, monkeypatch=monkeypatch)
    t3 = _table(result, "Table 3")
    assert t3["cells"] == [] and t3["content_status"] == "raw_text"
    assert t3["caption"] == (
        "Table 3. American Time Use Survey Housework and Childcare Activity Codes."
    )
    raw = t3["raw_text"]
    assert "Cooking meals: food and drink preparation (020201); food presentation (020202)" in raw
    assert raw.index("Total Housework is the sum") < raw.index("Cooking meals:") < raw.index("Childcare")
    assert "Author Manuscript" not in raw and "Author Manuscript" not in t3["caption"]
    assert "Table 3:raw_text:no_stable_columns" in result["fallback_details"]["rotated_table_read"]


def test_an_under_segmented_grid_is_refused(monkeypatch):
    """jamison_2020 Table 4: most of its columns are filled on a few rows, so the
    column finder misses boundaries and a cell would hold a hypothesis, a rating
    attribute and two scenarios' estimates. REFUSED, and the values come back as
    reading-order text instead."""
    result = _structured(_JESP, camelot=False, monkeypatch=monkeypatch)
    t4 = _table(result, "Table 4")
    assert t4["cells"] == [] and t4["content_status"] == "raw_text"
    assert "Table 4:raw_text:column_fused_in_cell" in result["fallback_details"]["rotated_table_read"]
    raw = t4["raw_text"]
    assert raw.index("Omission will be associated with a bias towards lower") < raw.index("−0.45")
    assert "[−0.69," in raw and "Signal" in raw


def test_the_refusal_is_what_stops_the_fused_grid(monkeypatch):
    """Two-sided for the gate above: blind `_grid_has_inner_gutter` and the same
    table grids with two published columns in one cell."""
    from docpluck.tables import whitespace as W

    monkeypatch.setattr(W, "_grid_has_inner_gutter", lambda cells_words: False)
    t4 = _table(_structured(_JESP, camelot=False, monkeypatch=monkeypatch), "Table 4")
    fused = [c["text"] for c in t4["cells"] if "−1.21" in c["text"] and "−1.46" in c["text"]]
    fused += [c["text"] for c in t4["cells"] if "-1.21" in c["text"] and "-1.46" in c["text"]]
    assert fused, [c["text"] for c in t4["cells"]][:20]


def test_a_standard_error_never_shares_a_cell_with_the_next_estimate(monkeypatch):
    """ASR 4 Table 3 (p15): a raised significance star made the estimate lines'
    boxes 2.3pt taller, the row grouping paired each standard error with the NEXT
    row's estimate, and the grid shipped ``(.948) 8.441***`` in one cell. Row
    pitches are now measured on line bottoms. Both values must be delivered, and
    never in one cell."""
    result = _structured(_ASR, camelot=False, monkeypatch=monkeypatch)
    t3 = _table(result, "Table 3")
    for c in t3["cells"]:
        assert not ("(.948)" in c["text"] and "8.441" in c["text"]), c
    delivered = (t3["raw_text"] or "") + " " + " ".join(c["text"] for c in t3["cells"])
    assert "(.948)" in delivered and "8.441***" in delivered


def test_a_subscript_neither_splits_its_word_nor_merges_rows(monkeypatch):
    """jama_open_1 Table 2 (p8): the ``1c`` of HbA1c is set low and small. It
    belongs to its label, and it must not chain the HbA1c row to the next."""
    result = _structured(_JAMA, camelot=False, monkeypatch=monkeypatch)
    t2 = _table(result, "Table 2")
    assert t2["cell_geometry"] == "whitespace_rotated"
    hba = _row_labelled(t2, "HbA1c level, %")
    assert hba[1:4] == ["72", "66", "-0.72 (-1.25 to -0.18)"]
    tir = _row_labelled(t2, "Time in euglycemic range, %")
    assert tir[1:4] == ["67", "56", "4.78 (-3.52 to 13.08)"]
    # Its note is set in the cells' own size: it goes to `footnote`, not to cells.
    assert (t2["footnote"] or "").startswith("Abbreviations: BMI, body mass index")
    assert not any("Abbreviations" in c["text"] or "Indicates statistical" in c["text"] for c in t2["cells"])
    assert _row_labelled(t2, "Triglycerides")[1:3] == ["71", "60"]


def test_the_other_rotation_direction_is_read_correctly():
    """No rotated TABLE in the corpus reads down the page, so the ``-1`` frame is
    checked on the one real downward text there is: rsos.140072 p5's header."""
    from docpluck.extract_layout import extract_pdf_layout
    from docpluck.tables.rotated import upright_view
    from docpluck.tables.whitespace import _visual_lines

    page = extract_pdf_layout(require_corpus_pdf(_RSOS).read_bytes(), pages=[4]).pages[4]

    def lines(direction):
        return [" ".join(w["text"] for w in ln) for ln in _visual_lines(list(upright_view(page, direction).words))]

    down = lines(-1)
    assert any(ln.startswith("rsos.royalsocietypublishing.org") for ln in down), down
    assert not any("royalsocietypublishing" in ln for ln in lines(1))


def _w(text, x0, top, size=7.0):
    """A word in the table's upright frame (code-behaviour fixture, not a paper)."""
    return {"text": text, "x0": x0, "x1": x0 + 0.5 * size * len(text), "top": top,
            "bottom": top + size, "size": size}


def test_a_label_row_cannot_pull_data_rows_into_the_note():
    """Second-model review (Sonnet, 2026-09-25), constructed from the logic, not
    observed in the corpus: a label-only row at the table's left edge could OPEN a
    note, and the label-and-value rows after it came along as "continuation"
    because their gap was under 12pt. A wrapped line may now only follow note
    text. This pins what the CODE does; the 31 corpus tables' notes are unchanged."""
    from docpluck.tables.rotated import _note_start

    body = [
        [_w("Age", 10, 0), _w("34.1", 200, 0)],
        [_w("Income", 10, 12), _w("51,000", 200, 12)],
        [_w("Tenure", 10, 24), _w("7.2", 200, 24)],
        [_w("Subtotal", 10, 36)],                         # label-only row, left edge
        [_w("Men only", 10, 48), _w("12.5", 46, 48)],    # label + value, 8pt gap
        [_w("Women only", 10, 60), _w("11.9", 53, 60)],  # (under the 12pt wrap limit)
        [_w("Note. " + "values are means across all participants in the sample", 10, 76)],
    ]
    start = _note_start(body, 5.0)
    note = [" ".join(w["text"] for w in ln) for ln in body[start:]]
    assert not any("12.5" in ln or "11.9" in ln for ln in note), note
    # Two-sided: the real note is still found.
    assert note and note[-1].startswith("Note."), note
