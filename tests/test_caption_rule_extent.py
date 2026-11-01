"""A caption_only table region is widened to the table's own top rule and bounded
by its closing rule (``detect._caption_rule_extent``, 2026-10-30).

Geometry measured on 10.1080/02699931.2024.2434156 (Taylor & Francis), where every
table rule is a filled 0.5pt-tall CURVE and the page has no ``lines`` at all:
p13 Table 8's caption ends at x=310.9 while its rules run x=48.0 -> 487.8, so the
caption-width region dropped correlation columns 2-5; p7 Table 2 draws three rules
(y=62/74/122) above two-column body prose.
"""

from __future__ import annotations

from types import SimpleNamespace

from docpluck.tables.detect import _caption_rule_extent, _caption_top_rule_x1


def _curve(x0, x1, top, h=0.5):
    return {"x0": x0, "x1": x1, "top": top, "bottom": top + h}


def _word(text, x0, top):
    return {"text": text, "x0": x0, "x1": x0 + 20, "top": top, "bottom": top + 8}


def _page(curves=(), lines=(), rects=(), words=()):
    return SimpleNamespace(curves=tuple(curves), lines=tuple(lines), rects=tuple(rects),
                           words=tuple(words))


CAPTION = (48.0, 52.8, 310.9, 61.0)  # x0, top, x1, bottom


def test_a_curve_drawn_top_rule_widens_the_region():
    page = _page(curves=[_curve(48.0, 487.8, 61.8), _curve(48.0, 487.8, 74.0),
                         _curve(48.0, 487.8, 122.0)])
    assert _caption_top_rule_x1(page, CAPTION) == 487.8
    assert _caption_rule_extent(page, CAPTION, band_bottom=310.8) == (487.8, 123.5)


def test_the_bottom_stops_before_a_stacked_tables_caption():
    """p13: Table 9's caption sits between Table 8's closing rule (y=221) and
    Table 9's own rules (y=282, 306)."""
    page = _page(
        curves=[_curve(48.0, 487.8, y) for y in (61.8, 74.0, 221.0, 282.0, 306.0)],
        words=[_word("Table", 48.0, 52.8), _word("8.", 70.0, 52.8),
               _word("Table", 48.0, 272.0), _word("9.", 70.0, 272.0)],
    )
    assert _caption_rule_extent(page, CAPTION, band_bottom=310.8) == (487.8, 222.5)


def test_a_word_table_in_prose_is_not_a_caption():
    """"Table" followed by a non-number ("Table of contents") never stops the walk."""
    page = _page(
        curves=[_curve(48.0, 487.8, y) for y in (61.8, 74.0, 221.0, 282.0)],
        words=[_word("Table", 48.0, 250.0), _word("of", 70.0, 250.0)],
    )
    assert _caption_rule_extent(page, CAPTION, band_bottom=310.8) == (487.8, 283.5)


def test_two_rules_change_nothing():
    """With only top and header rule there is no proven closing rule, and a
    region widened but left at the band's depth swallows the text under the
    table (10.1080/23743603.2021.1878340 p15 Table 3)."""
    page = _page(curves=[_curve(48.0, 487.8, 61.8), _curve(48.0, 487.8, 74.0)])
    assert _caption_rule_extent(page, CAPTION, band_bottom=310.8) is None


def test_a_tall_tables_closing_rule_below_the_old_band_counts():
    """p9 Table 4 closes at y=583, far below caption + 250pt."""
    page = _page(curves=[_curve(48.0, 487.8, y) for y in (61.8, 101.0, 583.0)])
    assert _caption_rule_extent(page, CAPTION, band_bottom=697.3) == (487.8, 584.5)


def test_a_rule_not_starting_at_the_caption_is_ignored():
    """A neighbouring column's table rule starts at that column's edge."""
    page = _page(curves=[_curve(275.0, 487.8, 61.8)])
    assert _caption_top_rule_x1(page, CAPTION) is None
    assert _caption_rule_extent(page, CAPTION, band_bottom=310.8) is None


def test_a_rule_far_below_the_caption_is_ignored():
    page = _page(curves=[_curve(48.0, 487.8, 120.0)])
    assert _caption_top_rule_x1(page, CAPTION) is None


def test_a_thick_shape_is_not_a_rule():
    page = _page(rects=[_curve(48.0, 487.8, 61.8, h=40.0)])
    assert _caption_top_rule_x1(page, CAPTION) is None


def test_a_rule_no_wider_than_the_caption_changes_nothing():
    page = _page(lines=[_curve(48.0, 300.0, 61.8)])
    assert _caption_top_rule_x1(page, CAPTION) is None


def _segments(xs, top, h=0.5):
    """One rule drawn as touching per-column segments."""
    return [_curve(a, b, top, h) for a, b in zip(xs, xs[1:])]


def test_a_rule_drawn_as_column_segments_counts_as_one_rule():
    """10.1177/01461672251327169 p9 (Table 5): the top rule at y=84 is one
    stroke from x=63 to 564; the header rule (y=103) and the closing rule
    (y=654) are four touching segments each. Read segment by segment the
    closing rule was never found and the region stopped at y=330, a third of
    the table."""
    cap = (63.0, 71.2, 323.3, 80.3)
    cols = (63.0, 144.0, 237.0, 442.0, 564.0)
    page = _page(lines=[_curve(63.0, 564.0, 84.0), *_segments(cols, 103.0), *_segments(cols, 654.0)])
    assert _caption_rule_extent(page, cap, band_bottom=792.0) == (564.0, 655.5)


def test_segments_with_a_gap_are_not_joined():
    """Two rules side by side with a real gap are two rules, not one."""
    cap = (63.0, 71.2, 323.3, 80.3)
    page = _page(lines=[_curve(63.0, 564.0, 84.0),
                        _curve(63.0, 300.0, 103.0), _curve(320.0, 564.0, 103.0),
                        _curve(63.0, 300.0, 654.0), _curve(320.0, 564.0, 654.0)])
    assert _caption_rule_extent(page, cap, band_bottom=792.0) is None


# ---- end to end: a table bounded by its own rules keeps every row ----------

def _tables_of(rel):
    from docpluck.extract_structured import extract_pdf_structured
    from docpluck.testing import require_corpus_pdf
    res = extract_pdf_structured(require_corpus_pdf(rel).read_bytes())
    return {t.get("label"): t for t in res["tables"]}


def _rows(t):
    rows: dict = {}
    for c in t.get("cells") or []:
        rows.setdefault(c["r"], {})[c["c"]] = c["text"]
    return rows


_IP = "apa/ip_feldman_2025_pspb.pdf"  # 10.1177/01461672251327169


def test_a_worded_table_bounded_by_its_rules_keeps_every_row():
    """p9 Table 5 (deviations, 4 columns, closing rule at y=654): before, the
    region stopped at y=330 and the prose-row trims cut the grid after
    "DV operationalization"; the last eight design facets were lost."""
    t5 = _tables_of(_IP)["Table 5"]
    text = " ".join(c["text"] for c in t5["cells"])
    for facet in ("Population", "Procedural details", "Physical settings",
                  "Contextual variables", "Statistical analyses", "Close to far"):
        assert facet in text, f"{facet!r} missing from Table 5"


def test_a_ruled_comparison_table_keeps_its_four_columns():
    """p6 Table 3: Study | Study 1b | Study 3 | Replication. Before, the region was
    the caption's width plus three lines of Method prose taken as a footnote, and
    two columns were fused ("not disclosenot disclose")."""
    t3 = _tables_of(_IP)["Table 3"]
    assert t3["n_cols"] == 4
    text = " ".join(c["text"] for c in t3["cells"])
    assert "disclosenot" not in text
    assert "We conducted the study using Qualtrics" not in text


def test_the_fallback_family_is_narrower_than_the_separator():
    """Consult 2026-10-31 (Sonnet): the fallback for a separator wider than the
    table (10.1177/01461672251327169 p4) admitted ANY other width, so a wider
    frame or page-wide rule under the caption could become the table's right
    edge. Only a narrower family is the table's."""
    wider = [_curve(48.0, 560.0, y) for y in (80.0, 120.0, 200.0)]
    page = _page(curves=[_curve(48.0, 487.8, 61.8), *wider])
    assert _caption_rule_extent(page, CAPTION, band_bottom=310.8) is None
    narrower = [_curve(48.0, 420.0, y) for y in (80.0, 120.0, 200.0)]
    page = _page(curves=[_curve(48.0, 487.8, 61.8), *narrower])
    assert _caption_rule_extent(page, CAPTION, band_bottom=310.8) == (420.0, 201.5)


def test_other_caption_labels_stop_the_walk_too():
    """Consult 2026-10-31 (Sonnet): "FIG. 3", "Exhibit 2", "Box 1" and
    "Supplementary Table 2" captions did not stop the walk, so the next
    object's rules were taken as this table's."""
    for first, second in (("FIG.", "3"), ("Exhibit", "2"), ("Box", "1"), ("Supplementary", "Table")):
        page = _page(
            curves=[_curve(48.0, 487.8, y) for y in (61.8, 74.0, 221.0, 282.0, 306.0)],
            words=[_word(first, 48.0, 272.0), _word(second, 80.0, 272.0)],
        )
        assert _caption_rule_extent(page, CAPTION, band_bottom=310.8) == (487.8, 222.5), first


# ---- page furniture is never a table's closing rule (/ship canary 2026-11-01) ----

_PLOS = "vancouver/plos_med_1.pdf"  # 10.1371/journal.pmed.1004323


def test_a_page_footer_rule_is_not_a_tables_closing_rule():
    """10.1371/journal.pmed.1004323 draws a full-width rule at y=744 on every page,
    the same width as its table rules. Taken as Table 5's closing rule (p11, the
    table closes at y=309), the region ran through the Results paragraph and the
    Discussion opening, which became grid rows; the body copy of "During the
    study, 15 SAEs occurred" was then dropped as a duplicate of the grid."""
    tables = _tables_of(_PLOS)
    for label in ("Table 2", "Table 4", "Table 5"):
        text = " ".join(c["text"] for c in tables[label]["cells"])
        assert "PLOS Medicine" not in text and "Discussion" not in text, label
    t5 = " ".join(c["text"] for c in tables["Table 5"]["cells"])
    assert "During the study" not in t5
    assert "Main findings" not in t5



def _frule(y, x0=50.0, x1=550.0):
    return {"x0": x0, "x1": x1, "top": y, "bottom": y + 0.5}


def _fpage(rules, caption: bool):
    words = [{"text": "Results", "x0": 50.0, "top": 30.0}]
    if caption:
        words = [{"text": "Table", "x0": 50.0, "top": 40.0}, {"text": "3.", "x0": 80.0, "top": 40.0}] + words
    return SimpleNamespace(words=words, _rules=rules)


def test_a_table_series_closing_rule_repeated_on_caption_pages_is_not_furniture(monkeypatch):
    """Consult 2026-11-01 (Sol reproduced, Sonnet concurred): one table per page
    in the same slot repeats its own rules at one position on every page. Taken
    as furniture, the closing rule was dropped and the region stopped at an inner
    rule or lost its extent. A running footer rule also sits on caption-free
    pages; only that one is furniture."""
    import docpluck.tables.detect as det
    monkeypatch.setattr(det, "_joined_horizontal_strokes", lambda p: [dict(r) for r in p._rules])
    det._FURNITURE_CACHE.clear()
    table = [_frule(62), _frule(74), _frule(100), _frule(122)]
    footer = _frule(744)
    series = SimpleNamespace(pages=[_fpage(table + [footer], caption=True) for _ in range(4)])
    found = det._furniture_rule_keys(series)
    assert det._rule_key(_frule(122)) not in found
    assert det._rule_key(footer) not in found  # never on a caption-free page here
    # The same footer, also on pages with no caption, is a running rule.
    det._FURNITURE_CACHE.clear()
    mixed = SimpleNamespace(pages=[_fpage(table + [footer], caption=True) for _ in range(2)]
                            + [_fpage([footer], caption=False) for _ in range(2)])
    found = det._furniture_rule_keys(mixed)
    assert det._rule_key(footer) in found
    assert det._rule_key(_frule(122)) not in found
    det._FURNITURE_CACHE.clear()
