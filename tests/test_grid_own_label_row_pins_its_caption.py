"""A grid whose first row is its own printed ``Table N`` label is Table N's.

10.1016/j.jesp.2021.104154 p6 (rasterised 2026-10-24) prints Tables 1, 2 and 3 on
one page in Elsevier style: the label ``Table 2`` alone on its line, the title on
the next. Camelot's grid of Table 2 opens with that ``Table 2`` row, but the
caption hint only recognised ``Table N.`` / ``Table N:``, so pairing fell back to
token overlap and handed the Table 2 grid the Table 1 caption and the Table 3 grid
the Table 2 caption: every flattened row of those tables carried the wrong label.
"""
from __future__ import annotations

from docpluck.tables.camelot_extract import _leading_table_caption_number


def test_bare_label_row_is_an_identity_hint():
    assert _leading_table_caption_number([["Table 2"], ["Study 1: Means and SDs"], ["a", "b"]]) == 2
    assert _leading_table_caption_number([["", "TABLE 7", ""], ["x", "y"]]) == 7


def test_existing_forms_and_non_labels():
    assert _leading_table_caption_number([["Table 9. Summary of results"], ["a"]]) == 9
    assert _leading_table_caption_number([["Condition", "M"], ["see Table 2", "1"]]) is None
    assert _leading_table_caption_number([["Table 2 shows", "x"], ["a", "b"]]) is None
    assert _leading_table_caption_number([["Table 6 (Continued)"], ["a"]]) is None


def _cell_text(t):
    return " ".join(c.get("text") or "" for c in t.get("cells") or [])


def test_real_page_labels_follow_the_printed_label():
    from docpluck.testing import require_corpus_pdf
    from docpluck.extract_structured import extract_pdf_structured

    pdf = require_corpus_pdf("apa/chen_2021_jesp.pdf")   # 10.1016/j.jesp.2021.104154
    tabs = [t for t in extract_pdf_structured(pdf.read_bytes())["tables"] if t["page"] == 6]
    by_label = {}
    for t in tabs:
        by_label.setdefault(t.get("label"), []).append(t)
    # Table 2's grid (Experimental Condition / Sample Size ...) is labelled Table 2.
    holders = [t.get("label") for t in tabs if "Experimental Condition" in _cell_text(t)]
    assert holders == ["Table 2"], holders
    # No table other than Table 3 holds the Mann-Whitney U grid.
    u_holders = {t.get("label") for t in tabs if "After - Before" in _cell_text(t)}
    assert u_holders == {"Table 3"}, u_holders
    # And nothing labelled Table 1 holds another table's content.
    for t in by_label.get("Table 1", []):
        assert "Experimental Condition" not in _cell_text(t)
