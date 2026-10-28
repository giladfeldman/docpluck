"""A table that runs onto the next page is linked to its parent, never stamped matched blind.

Measured 2026-10-27 on real multi-page tables (pages rasterised):

* 10.1177/0956797620916782 p10 prints ``Table 1. (continued)`` ABOVE the grid (the
  head is not inside the grid, so the 2.4.155 in-grid test cannot see it); the grid
  has Table 1's five columns at the same x-extent as p9's Table 1, which runs to the
  page foot. It was stamped ``uncaptioned_candidate`` with no label, and a consumer
  that drops unverified candidates dropped every row.
* 10.1080/07317115.2012.731474 p13 (landscape) continues Table 1 with no printed
  head at all.
* 10.1017/jdm.2023.48 p6 prints ``Table 1. (Continued)`` but the grid Camelot found
  there is a stimulus box with a different x-extent, not the table: it stays an
  unverified candidate.

A printed head plus the geometry -> ``matched`` with ``continuation_of``; geometry
alone -> the distinct status ``continuation`` with ``continuation_of`` (never
``matched``).
"""
from __future__ import annotations

import pytest

from docpluck.extract_structured import _continuation_link


def _cells(n_cols, n_rows=3):
    return [{"r": r, "c": c, "rowspan": 1, "colspan": 1, "text": f"{r}{c}"}
            for r in range(n_rows) for c in range(n_cols)]


def _t(page, bbox, n_cols, label=None):
    return {"page": page, "bbox": bbox, "cells": _cells(n_cols), "label": label}


PARENT = _t(9, (126.0, 49.0, 477.0, 759.0), 5, "Table 1")


def test_geometry_alone_links_as_continuation():
    cand = _t(10, (126.0, 239.0, 472.0, 761.0), 5)
    assert _continuation_link(cand, [PARENT], [cand], "Some page text\nmore") == ("Table 1", None)


def test_printed_head_on_the_page_is_returned():
    cand = _t(10, (126.0, 239.0, 472.0, 761.0), 5)
    got = _continuation_link(cand, [PARENT], [cand], "Beyond WEIRD 687\nTable 1. (continued)\nAmerican")
    assert got == ("Table 1", "Table 1. (continued)")


def test_head_naming_another_table_refuses_the_link():
    cand = _t(10, (126.0, 239.0, 472.0, 761.0), 5)
    assert _continuation_link(cand, [PARENT], [cand], "Table 2 (continued)\n") is None


def test_different_columns_or_extent_or_position_refuse():
    # different column count
    assert _continuation_link(_t(10, (126.0, 239.0, 472.0, 761.0), 4), [PARENT], [], "") is None
    # different x-extent (a stimulus box, jdm.2023.48 p6)
    box = _t(10, (81.0, 97.0, 410.0, 348.0), 5)
    assert _continuation_link(box, [PARENT], [box], "") is None
    # not the topmost grid on its page
    cand = _t(10, (126.0, 239.0, 472.0, 500.0), 5)
    above = _t(10, (126.0, 520.0, 472.0, 760.0), 3)
    assert _continuation_link(cand, [PARENT], [cand, above], "") is None
    # parent is not the lowest grid on its page
    below = _t(9, (126.0, 20.0, 472.0, 40.0), 2)
    cand = _t(10, (126.0, 239.0, 472.0, 761.0), 5)
    assert _continuation_link(cand, [PARENT, below], [cand], "") is None
    # no labelled table on the previous page
    assert _continuation_link(cand, [_t(9, (126.0, 49.0, 477.0, 759.0), 5)], [cand], "") is None


def _tables(doi_key):
    from docpluck.testing.corpus import custody_path
    from docpluck.extract_structured import extract_pdf_structured
    p = custody_path("fulltext", doi_key + ".pdf")
    if not p.is_file():
        pytest.skip(f"{doi_key} not held")
    return extract_pdf_structured(p.read_bytes())["tables"]


def test_real_printed_head_above_the_grid():
    tabs = _tables("10.1177__0956797620916782")
    for page, label in ((10, "Table 1"), (20, "Table 2")):
        got = [t for t in tabs if t["page"] == page and t.get("continuation_of")]
        assert len(got) == 1, [(t["id"], t["label"], t["caption_status"]) for t in tabs if t["page"] == page]
        t = got[0]
        assert t["label"] == label and t["continuation_of"] == label
        assert t["caption_status"] == "matched" and "continued" in (t["caption"] or "").lower()
        assert t["cells"]


def test_real_unprinted_continuation_and_stimulus_box():
    tabs = _tables("10.1080__07317115.2012.731474")
    p13 = [t for t in tabs if t["page"] == 13]
    assert len(p13) == 1 and p13[0]["continuation_of"] == "Table 1", p13
    assert p13[0]["caption_status"] == "continuation" and p13[0]["label"] == "Table 1"
    jdm = _tables("10.1017__jdm.2023.48")
    p6 = [t for t in jdm if t["page"] == 6]
    assert p6 and all(t["caption_status"] == "uncaptioned_candidate" for t in p6)
    assert not any(t.get("continuation_of") for t in p6)


def test_render_heads_a_later_page_as_continued():
    from docpluck.render import _table_heading_and_caption
    t = {"label": "Table 1", "page": 13, "continuation_of": "Table 1", "caption_status": "continuation"}
    head, cap = _table_heading_and_caption(t, "Table 1", "")
    assert head == "Table 1 (continued, page 13)"
    assert "no caption or continued head" in cap
    t = {"label": "Table 1", "page": 10, "continuation_of": "Table 1", "caption_status": "matched"}
    assert _table_heading_and_caption(t, "Table 1", "Table 1. (continued)") == (
        "Table 1 (continued, page 10)", "Table 1. (continued)")
    assert _table_heading_and_caption({"label": "Table 2"}, "Table 2", "Cap") == ("Table 2", "Cap")


def test_real_render_places_continuations_after_their_table():
    from docpluck.testing.corpus import custody_path
    from docpluck.render import render_pdf_to_markdown
    p = custody_path("fulltext", "10.1080__07317115.2012.731474.pdf")
    if not p.is_file():
        pytest.skip("not held")
    md = render_pdf_to_markdown(p.read_bytes())
    md = md[0] if isinstance(md, tuple) else md
    heads = [ln for ln in md.splitlines() if ln.startswith("### Table 1")]
    assert heads[:3] == ["### Table 1", "### Table 1 (continued, page 12)",
                         "### Table 1 (continued, page 13)"], heads


def test_real_render_keeps_printed_continued_pages_after_their_table():
    # 10.5465/amle.2017.0488: "TABLE 6 (Continued)" (p15, p16) and "TABLE 8
    # (Continued)" (p19) print their own head; each must stay right after its
    # table, ahead of the next table, not drift to the end of the list.
    from docpluck.testing.corpus import custody_path
    from docpluck.render import render_pdf_to_markdown
    p = custody_path("fulltext", "10.5465__amle.2017.0488.pdf")
    if not p.is_file():
        pytest.skip("not held")
    md = render_pdf_to_markdown(p.read_bytes())
    md = md[0] if isinstance(md, tuple) else md
    heads = [ln for ln in md.splitlines() if ln.startswith("### Table ")]
    i6, i7 = heads.index("### Table 6"), heads.index("### Table 7")
    assert heads[i6 + 1].startswith("### Table 6 (continued, page 15)"), heads
    assert i7 > i6 + 1, heads
    i8 = heads.index("### Table 8")
    assert heads[i8 + 1] == "### Table 8 (continued, page 19)", heads
