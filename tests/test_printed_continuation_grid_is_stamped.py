"""A grid that opens with its own printed ``TABLE N (Continued)`` is Table N.

Rasterised 2026-10-24: 10.5465/amle.2017.0488 prints ``TABLE 6 (Continued)`` at the
head of pp15-16 and ``TABLE 8 (Continued)`` on p19; 10.5465/annals.2022.0049 prints
``TABLE 5 (Continued)`` on p13. Those grids were stamped
``caption_status="uncaptioned_candidate"`` with no label, and a consumer that
drops unverified candidates dropped every row of them. The page names the table,
so the grid is labelled with it, marked ``matched``, and carries the additive
``continuation_of`` key. A grid that does not open with such a line is untouched.
"""
from __future__ import annotations

from docpluck.tables.captions import printed_continuation_label


def _cells(rows):
    out = []
    for r, row in enumerate(rows):
        for c, text in enumerate(row):
            if text:
                out.append({"r": r, "c": c, "rowspan": 1, "colspan": 1, "text": text,
                            "is_header": False, "bbox": (0.0, 0.0, 0.0, 0.0)})
    return out


def test_split_across_two_rows():
    got = printed_continuation_label(_cells([["", "", "", "TABLE 6"], ["", "", "", "(Continued)"],
                                             ["Rank", "Source", "Year"]]))
    assert got == ("Table 6", "TABLE 6 (Continued)"), got


def test_one_line_forms():
    assert printed_continuation_label(_cells([["Table 3 (continued)"], ["a", "1"]]))[0] == "Table 3"
    assert printed_continuation_label(_cells([["TABLE 12. Continued"], ["a", "1"]]))[0] == "Table 12"
    assert printed_continuation_label(_cells([["Table A1 (Cont.)"], ["a", "1"]]))[0] == "Table A1"


def test_not_a_continuation():
    # Its own title, a running head, or a mention further down: untouched.
    assert printed_continuation_label(_cells([["TABLE 6"], ["Most Cited Articles"], ["a", "1"]])) is None
    assert printed_continuation_label(_cells([["2019", "Aguinis"], ["TABLE 6 (Continued)"]])) is None
    assert printed_continuation_label(_cells([["Rank", "Source"], ["1", "see Table 6 (continued)"]])) is None
    assert printed_continuation_label([]) is None


def _tables(name):
    from docpluck.testing import require_corpus_pdf
    from docpluck.extract_structured import extract_pdf_structured
    return extract_pdf_structured(require_corpus_pdf(name).read_bytes())["tables"]


def test_real_continuation_grids_are_labelled():
    tabs = _tables("aom/amle_1.pdf")   # 10.5465/amle.2017.0488
    by_page = {}
    for t in tabs:
        by_page.setdefault(t["page"], []).append(t)
    for page, label in ((15, "Table 6"), (16, "Table 6"), (19, "Table 8")):
        conts = [t for t in by_page.get(page, []) if t.get("continuation_of")]
        assert len(conts) == 1, (page, [(t["id"], t["label"], t["caption_status"]) for t in by_page.get(page, [])])
        t = conts[0]
        assert t["label"] == label and t["continuation_of"] == label, t["label"]
        assert t["caption_status"] == "matched" and "Continued" in (t["caption"] or "")
        assert t["cells"], "the continuation keeps its rows"
    # The opposite: the tables that start on their own page are not continuations.
    for t in tabs:
        if t["page"] in (14, 18) and t.get("label") in ("Table 6", "Table 8"):
            assert not t.get("continuation_of"), t["id"]
    # Flattened rows of a continuation are no longer unverified candidates.
    from docpluck.tables.flatten import flatten_tables_for_paper
    rows = [(f if isinstance(f, dict) else f.__dict__) for f in flatten_tables_for_paper(tabs)]
    p15 = [r for r in rows if r["page"] == 15]
    assert p15 and all(r["label"] == "Table 6" for r in p15)
    assert all(r.get("caption_status") == "matched" for r in p15)
