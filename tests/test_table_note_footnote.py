"""Table["footnote"] on the PDF paths: the printed note, located by the layout
channel and read from the text channel (docpluck/tables/notes.py).

Before this, `footnote` was the literal None on every PDF capture path while
`detect._detect_footnote_below` computed a note for every region and nothing
read it. The strings below are what the two channels actually emit for the
named papers; the real-PDF tests at the bottom run the whole pipeline.
"""

from __future__ import annotations

import pytest

from docpluck.extract_structured import (
    _flatten_snippet,
    _move_note_rows_to_footnote,
    _rows_survive_in,
)
from docpluck.tables.notes import _match_rows_in_text, _key, starts_with_note_label
from docpluck.tables.render import cells_to_html


# ---- helpers ------------------------------------------------------------------

def test_label_test_requires_the_label_punctuation():
    # 10.5465/amj.2016.1196 p9 body prose opens a line with "Note that ...".
    assert not starts_with_note_label("Note that it is the top-down evaluation that determines")
    assert starts_with_note_label("Note: n 5 225.")
    assert starts_with_note_label("Notes: n 5 356. Negative Feedback")
    assert starts_with_note_label("Note. Values are means.")
    assert starts_with_note_label("Source: McCullough et al. (1997)")
    assert not starts_with_note_label("Notes")


def test_key_folds_ligatures_and_drops_everything_but_letters_and_digits():
    # pdfplumber keeps the ligature glyph; pdftotext expands it.
    assert _key("Reﬂection") == "reflection"
    assert _key("† p , .10") == "p10"


def test_text_match_refuses_a_row_that_stops_mid_word():
    # The layout row lost the glyphs past "replicatio"; the text channel has
    # the whole word. Delivering the match would truncate the note.
    text = "Note: Hypothesis 3 is not included in the replication because it\n"
    done, _ = _match_rows_in_text(text, 0, [_key("Note: Hypothesis 3 is not included in the replicatio")])
    assert done == 0
    done, end = _match_rows_in_text(
        text, 0, [_key("Note:Hypothesis3isnotincludedinthereplicationbecauseit")]
    )
    assert done == 1 and text[:end].endswith("because it")


def test_text_match_skips_symbols_the_channels_decode_differently():
    # 10.5465/amj.2016.1196 p14: pdftotext puts the dagger on its own line.
    text = "Note: n 5 225.\n†\np , .10\n*p , .05\n"
    keys = [_key("Note:n5225."), _key("†p,.10"), _key("*p,.05")]
    done, end = _match_rows_in_text(text, 0, keys)
    assert done == 3 and text[:end].rstrip().endswith(".05")


def test_flatten_snippet_rejoins_soft_hyphen_wraps():
    # 10.1080/02699931.2024.2434156 p7, Table 2's note, as pdftotext emits it.
    assert _flatten_snippet("Conciliatory behav­\niour scores") == "Conciliatory behaviour scores"
    assert _flatten_snippet("a  b\n c") == "a b c"


def test_rows_survive_allows_only_a_wrap_hyphen_to_differ():
    fn = "Note: Apology scores ranged. Conciliatory behaviour scores ranged from 2 to 10."
    assert _rows_survive_in(["Note: Apology scores ranged. Conciliatory behav-",
                             "iour scores ranged from 2 to 10."], fn)
    # A glyph the grid holds and the footnote does not: the rows stay.
    assert not _rows_survive_in(["Note: Apology scores ranged. Conciliatory behav-",
                                 "iour scores ranged from 2 to 11."], fn)
    assert not _rows_survive_in(["iour scores", "Note: Apology"], fn)


def _grid(rows: list[list[str]]) -> dict:
    cells = [
        {"r": r, "c": c, "rowspan": 1, "colspan": 1, "text": t, "is_header": r == 0,
         "bbox": (0.0, 0.0, 0.0, 0.0)}
        for r, row in enumerate(rows) for c, t in enumerate(row) if t
    ]
    return {"cells": cells, "n_rows": len(rows), "n_cols": max(len(r) for r in rows),
            "html": cells_to_html(cells), "raw_text": "\n".join(" ".join(x for x in r if x) for r in rows),
            "accuracy": 99.0, "confidence": 0.5, "whitespace": 50.0}


def test_note_rows_leave_the_grid_only_when_the_footnote_holds_them():
    # 10.1080/02699931.2024.2434156 p7 Table 2 as the v2.4.145 grid carries it.
    rows = [
        ["Variables", "M", "SD"],
        ["5. Avoidance behaviour", "10.11", "3.89"],
        ["Note: Apology scores ranged from 2 to 10. Conciliatory behav-", "", ""],
        ["iour scores ranged from 2 to 10. **p < .01.", "", ""],
    ]
    t = _grid(rows)
    t["footnote"] = ("Note: Apology scores ranged from 2 to 10. Conciliatory "
                     "behaviour scores ranged from 2 to 10. **p < .01.")
    _move_note_rows_to_footnote(t, "Table 2")
    assert {c["r"] for c in t["cells"]} == {0, 1}
    assert t["n_rows"] == 2
    assert "Apology" not in t["html"] and "Apology" not in t["raw_text"]
    assert t["whitespace"] == 0.0


def test_note_rows_stay_when_the_footnote_differs():
    rows = [["Variables", "M"], ["Creativity", "3.79"], ["Note: n = 356.", ""]]
    t = _grid(rows)
    t["footnote"] = "Note: n 5 356."   # text channel decodes '=' as '5'
    _move_note_rows_to_footnote(t, "Table 4")
    assert {c["r"] for c in t["cells"]} == {0, 1, 2}


def test_isolated_raw_text_loses_its_note_tail_only_verbatim():
    # 10.1080/02699931.2024.2434156 p8 Table 3 (isolated): raw_text as shipped.
    t = {"cells": [], "raw_text": "Year\n1997\n2023\nNote: 1 Origin was not explicitly mentioned",
         "footnote": "Note: 1 Origin was not explicitly mentioned"}
    _move_note_rows_to_footnote(t, "Table 3")
    assert t["raw_text"] == "Year\n1997\n2023"


# ---- real PDFs ---------------------------------------------------------------

# Camelot off: the notes are keyed on the caption and attached after every
# capture path, so the whitespace/isolated fallback exercises them fully.
DISABLE_CAMELOT = True


@pytest.fixture(scope="module")
def cogemo():
    from docpluck import extract_pdf_structured
    from docpluck.testing import require_corpus_pdf
    res = extract_pdf_structured(require_corpus_pdf("apa/chan_feldman_2025_cogemo.pdf").read_bytes())
    return {t["label"]: t for t in res["tables"] if t.get("label")}


@pytest.fixture(scope="module")
def amj():
    from docpluck import extract_pdf_structured
    from docpluck.testing import require_corpus_pdf
    res = extract_pdf_structured(require_corpus_pdf("aom/amj_1.pdf").read_bytes())
    return {t["label"]: t for t in res["tables"] if t.get("label")}


def test_cogemo_table2_note_is_the_footnote(cogemo):
    # Printed under Table 2 on p7 (rasterized 2026-09-25).
    assert cogemo["Table 2"]["footnote"] == (
        "Note: Apology scores ranged from 2 to 10. Empathy scores ranged from 0 to 20. "
        "Forgiving Scale scores ranged from 5 to 25. Conciliatory behaviour scores ranged "
        "from 2 to 10. Avoidance behaviour scores ranged from 3 to 15. **p < .01. Adopted "
        "from McCullough et al. (1997), p. 325."
    )


def test_cogemo_tables_without_a_printed_note_stay_none(cogemo):
    # p11 prints Tables 5 and 6 with no note (rasterized 2026-09-25).
    assert cogemo["Table 5"]["footnote"] is None
    assert cogemo["Table 6"]["footnote"] is None


def test_cogemo_two_line_note_with_its_legend(cogemo):
    assert cogemo["Table 8"]["footnote"].endswith("* p < .05; ** p < .01; *** p < .001.")


def test_amj_table4_note_is_read_with_its_spaces(amj):
    # 10.5465/amj.2016.1196 p19. The layout channel reads this note as
    # "Notes:n5356.NegativeFeedback(..." -- no spaces. The text channel's '5'
    # and ',' are the file's own decoding of '=' and '<' (a file lie, passed
    # through as for every caption on this paper).
    assert amj["Table 4"]["footnote"] == (
        "Notes: n 5 356. Negative Feedback (neutral feedback 5 0, negative feedback 5 1). "
        "*p , .05 **p , .01 (all tests two-tailed)"
    )


def test_amj_table1_has_no_note_on_its_page(amj):
    assert amj["Table 1"]["footnote"] is None


# ---- the boundary shapes, each measured on a real page (rasterized 2026-09-25) ----

def _structured(rel: str):
    from docpluck import extract_pdf_structured
    from docpluck.testing import require_corpus_pdf
    res = extract_pdf_structured(require_corpus_pdf(rel).read_bytes())
    return {t["label"]: t for t in res["tables"] if t.get("label")}, res["fallback_details"]


def test_a_page_footer_under_a_rule_is_not_the_notes_second_line():
    # 10.1001/jamanetworkopen.2023.16111 p7: the journal footer sits 23pt under
    # the one-line note, below a rule.
    tables, _ = _structured("ama/jama_open_11.pdf")
    assert tables["Table 3"]["footnote"] == "Abbreviation: PSM, propensity score matching."


def test_lettered_footnotes_after_extra_space_stay_in_the_note():
    # 10.1001/jamanetworkopen.2023.39337 p9: superscript-lettered footnotes set
    # further down than the abbreviation line; and p6's "HbA1c" subscript.
    tables, _ = _structured("ama/jama_open_1.pdf")
    assert tables["Table 3"]["footnote"].endswith("b Significantly different from baseline (P < .05).")
    assert "HbA1c, hemoglobin A1c;" in tables["Table 1"]["footnote"]


def test_a_significance_legend_half_a_line_lower_stays_in_the_note():
    # 10.1111/jomf.12989 p20.
    tables, _ = _structured("chicago-ad/jmf_3.pdf")
    assert tables["Table 3"]["footnote"].endswith("Standard errors in parentheses. * p < .05 ** p < .01 *** p < .001.")


def test_a_word_hyphenated_across_note_lines_is_read_whole():
    # 10.1525/collabra.90203 p7: "origi-" / "nal" on the page, "original" in the text.
    tables, _ = _structured("apa/maier_2023_collabra.pdf")
    fn = tables["Table 2"]["footnote"]
    assert "a fair comparison to the original article." in fn
    assert fn.endswith("added for completeness of reporting addressing peer review.")


def test_a_note_that_begins_above_its_label_is_refused_not_cut():
    # 10.1186/s12889-023-17078-5 p10: an unlabelled line precedes "Abbreviation:".
    tables, details = _structured("vancouver/bmc_pub_health_2.pdf")
    assert tables["Table 4"]["footnote"] is None
    assert "Table 4" in details["table_note_unlabelled_lead_refused"]


def test_a_note_the_two_channels_agree_on_only_in_part_is_refused():
    # 10.5465/annals.2016.0011 p13: the text channel dropped the source index
    # "10" before "Balluerka", so only the first line agrees.
    tables, details = _structured("aom/annals_2.pdf")
    assert tables["Table 4"]["footnote"] is None
    assert "Table 4:1/9" in details["table_note_partial_refused"]


def test_a_note_set_in_two_columns_is_read_to_its_end():
    # 10.1001/jamanetworkopen.2023.46085 p5: the abbreviation list and footnote
    # a continue in a second column beside the label's column.
    tables, _ = _structured("ama/jama_open_3.pdf")
    fn = tables["Table 1"]["footnote"]
    assert "PSG, polysomnography; REM, rapid eye movement;" in fn
    assert fn.endswith("multiracial, and others.")


def test_a_symbol_only_token_ending_the_note_is_kept():
    # 10.1017/jdm.2023.16 p10: the note ends "denoted by a cross (×)." and
    # "(×)." carries no letter or digit, so no row key covers it.
    tables, _ = _structured("apa/jdm_.2023.16.pdf")
    for label in ("Table 4", "Table 6", "Table 7"):
        assert tables[label]["footnote"].endswith("Interaction effects are denoted by a cross (×)."), label


def test_render_prints_a_note_only_when_the_text_lacks_it():
    # 10.5465/amd.20150115: the body normalization turns the text layer's
    # "N 5 763" into "N = 763", so the check compares LETTERS, not digits.
    from docpluck.render import _key_of, _letters, _note_already_in
    note = "Note: N 5 763. Unstandardized regression estimates. ***p , .001 **p , .01 *p , .05"
    body = ("Table rows\n\nNote: N = 763. Unstandardized regression estimates. "
            "***p < .001 **p < .01 *p < .05\n\nNext paragraph.")
    assert _note_already_in(_letters(body), _key_of(body), note)
    assert not _note_already_in(_letters("Unrelated body text only."), _key_of("Unrelated body text only."), note)
    # Under 20 letters: matched on letters AND digits (10.1017/s0007123424000346).
    legend = "Note: *p < 0.1, **p < 0.05, ***p < 0.001."
    doc = "rows\n\nNote: *p < 0.1, **p < 0.05, ***p < 0.001.\n\nmore"
    assert _note_already_in(_letters(doc), _key_of(doc), legend)
    assert not _note_already_in(_letters("rows"), _key_of("rows"), legend)