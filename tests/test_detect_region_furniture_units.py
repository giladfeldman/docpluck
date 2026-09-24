"""Unit tests for the v2.4.145 region-detection guards, on hand-built page objects.

Each guard is pinned on real papers in
``test_table_region_does_not_absorb_page_furniture_real_pdf.py``; these run
without the article repository, so the behaviour stays pinned on any machine.
The geometry in each case is the measured geometry of the named paper.
"""

from __future__ import annotations

from types import SimpleNamespace

from docpluck.tables import detect


def _glyphs(text: str, x0: float, top: float, pitch: float = 5.0) -> list[dict]:
    out, x = [], x0
    for ch in text:
        out.append({"text": ch, "x0": x, "x1": x + pitch - 0.5, "top": top,
                    "bottom": top + 9.0, "size": 9.0, "upright": True})
        x += pitch
    return out


# ---- the caption locator prefers a caption that starts a text block --------

def test_cross_reference_above_the_heading_loses_to_the_heading():
    # 10.5465/amj.2016.1196 p19: a body sentence mentioning "Table 4." sits
    # above the centred "TABLE 4" heading.
    prose = _glyphs("presented in Table 4. To test our", 46.0, 500.0)
    heading = _glyphs("TABLE 4", 279.0, 559.0)
    page = SimpleNamespace(chars=prose + heading, width=612.0)
    cap = SimpleNamespace(line_text="TABLE 4", label="Table 4")
    x0, top, _, _ = detect._bbox_of_caption_line(page, cap)
    assert (round(x0), round(top)) == (279, 559)


def test_caption_after_a_column_gutter_counts_as_a_block_start():
    # A right-column caption joined into one y-row with left-column prose.
    left = _glyphs("end of a left column", 46.0, 300.0)
    right = _glyphs("Table 2. Results", 320.0, 300.0)
    row = sorted(left + right, key=lambda c: c["x0"])
    assert detect._match_starts_text_block(row, "table2.")


def test_inline_mention_after_a_word_space_is_not_a_block_start():
    row = _glyphs("presented in Table 4. To test", 46.0, 500.0)
    assert not detect._match_starts_text_block(row, "table4")


def test_only_a_cross_reference_is_still_located_as_before():
    # No block-start match anywhere: the first containing row is returned, as
    # before the change, so a caption this cannot place is placed as it was.
    prose = _glyphs("presented in Table 4. To test our", 46.0, 500.0)
    page = SimpleNamespace(chars=prose, width=612.0)
    cap = SimpleNamespace(line_text="TABLE 4", label="Table 4")
    _, top, _, _ = detect._bbox_of_caption_line(page, cap)
    assert round(top) == 500


# ---- a lone rule wider than the table's recurring rules is furniture --------

def _rule(x0: float, x1: float, top: float) -> dict:
    return {"x0": x0, "x1": x1, "top": top, "bottom": top + 0.5}


def test_page_footer_rule_does_not_widen_a_ruled_table():
    # 10.1001/jamanetworkopen.2023.48333 p6: eight table rules at 47.9-395.1,
    # one page-footer rule at 47.9-562.8.
    table = [_rule(47.9, 395.1, y) for y in (638.0, 663.8, 682.0, 694.0, 705.9, 717.9)]
    spanner = _rule(118.6, 395.1, 651.8)
    footer = _rule(47.9, 562.8, 730.5)
    kept = detect._without_lone_overreaching_rules(table + [spanner, footer])
    assert footer not in kept
    assert spanner in kept  # inside the recurring extent: the table's own
    assert all(r in kept for r in table)


def test_rules_all_one_width_are_untouched():
    rules = [_rule(47.9, 562.8, y) for y in range(100, 300, 20)]
    assert detect._without_lone_overreaching_rules(rules) == rules


def test_no_recurring_width_means_nothing_is_judged():
    rules = [_rule(10, 100, 1), _rule(20, 200, 2), _rule(30, 300, 3)]
    assert detect._without_lone_overreaching_rules(rules) == rules


def test_a_tables_unique_top_rule_is_kept():
    # 10.1038/s41598-023-50460-2 p4 Table 3: its one full-width rule is its top
    # rule, above shorter recurring ones. Also Sonnet's reproduction (consult
    # round 2026-09-24): two same-width furniture rules must not make a unique
    # table rule above them look like furniture.
    top = _rule(100.0, 500.0, 10.0)
    inner = [_rule(120.0, 480.0, 50.0), _rule(120.0, 480.0, 90.0)]
    assert top in detect._without_lone_overreaching_rules([top] + inner)


def test_only_a_lone_rule_below_the_table_is_dropped():
    table = [_rule(120.0, 480.0, y) for y in (50.0, 90.0, 130.0)]
    footer = _rule(40.0, 560.0, 700.0)
    kept = detect._without_lone_overreaching_rules(table + [footer])
    assert footer not in kept and all(r in kept for r in table)


# ---- a table note is upright and starts near the table -----------------------

def _layout(chars: list[dict]):
    page = SimpleNamespace(chars=chars, words=[], lines=[], width=612.0)
    return SimpleNamespace(pages=[page])


def _body(n_rows: int = 30, top: float = 400.0) -> list[dict]:
    # Running prose at 10pt, spanning the column: the modal size, and prose rows.
    out = []
    for i in range(n_rows):
        for g in _glyphs("body text of the article, running across the column", 40.0,
                         top + 12 * i):
            g["size"] = 10.0
            out.append(g)
    return out


def _table_rows(n_rows: int, top: float) -> list[dict]:
    # 10pt table rows: a label, a gutter, then values -- not prose.
    out = []
    for i in range(n_rows):
        for text, x in (("Anaemia", 40.0), ("7 (22.6)", 180.0), ("0.86", 260.0)):
            for g in _glyphs(text, x, top + 12 * i):
                g["size"] = 10.0
                out.append(g)
    return out


def test_note_directly_under_the_table_is_found():
    note = _glyphs("Note. Values are n (%).", 40.0, 310.0)
    fn = detect._detect_footnote_below(_layout(_body() + note), page=1,
                                       bbox=(40.0, 200.0, 300.0, 300.0))
    assert fn is not None and fn.bbox[1] == 310.0


def test_small_text_far_below_a_ruled_table_is_not_its_note():
    # 10.48550/arxiv.2410.21901 p6: the page footer 440pt below Table 5, a
    # ruled table whose last rule is its last row.
    # Body prose fills the gap between the table and the footer.
    footer = _glyphs("VOLUME 4, 2024", 200.0, 740.0)
    fn = detect._detect_footnote_below(_layout(_body(top=320.0) + footer), page=1,
                                       bbox=(40.0, 200.0, 300.0, 300.0),
                                       grid_bottom_known=True)
    assert fn is None


def test_a_note_below_unruled_table_rows_is_still_the_tables_note():
    # 10.1503/cmaj.230841 p6: the rules found stop part-way down Table 1, which
    # continues in rows down to its "Note:" 270pt below. Table rows, not prose,
    # fill the gap, so the note is kept.
    note = _glyphs("Note: ATC = Anatomic Therapeutic Chemical code.", 40.0, 580.0)
    fn = detect._detect_footnote_below(
        _layout(_body(top=620.0) + _table_rows(20, 310.0) + note), page=1,
        bbox=(40.0, 200.0, 300.0, 300.0), grid_bottom_known=True)
    assert fn is not None and fn.bbox[1] == 580.0


def test_distance_is_not_judged_where_the_grid_bottom_is_unknown():
    # A whitespace run or the caption-only box stops where DETECTION stopped;
    # the rows between it and a note further down can be the table's own
    # (10.1525/collabra.90203 Table 7). Behaviour there is unchanged.
    note = _glyphs("Note. Values are n (%).", 40.0, 520.0)
    fn = detect._detect_footnote_below(_layout(_body() + note), page=1,
                                       bbox=(40.0, 200.0, 300.0, 300.0))
    assert fn is not None and fn.bbox[1] == 520.0


def test_rotated_margin_text_is_not_a_note():
    # 10.1136/bmjopen-2022-066361 p6: the copyright strip, upright False.
    strip = _glyphs("Protected by copyright", 280.0, 305.0)
    for g in strip:
        g["upright"] = False
    fn = detect._detect_footnote_below(_layout(_body() + strip), page=1,
                                       bbox=(40.0, 200.0, 300.0, 300.0))
    assert fn is None
