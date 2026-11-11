"""A page that prints "Table N (continued)" labels its topmost grid as Table N.

10.1017/s0007123424000024 p9 and p11 print "Table 1. (Continued.)" above their grids,
10.1016/j.joep.2020.102350 p3 "Table 1 (continued )", 10.1037/pspp0000586 p10 "Table 9
(continued)". On 2.4.158 these grids
shipped as `uncaptioned_candidate` (a consumer reading only captioned tables loses their rows): the geometric
continuation link needs the PREVIOUS page's lowest grid to carry the label with
the same column count, and in s0007123424000024 pages 9-10 (unlabelled, 6
columns against Table 1's 7) broke that chain.
"""
from __future__ import annotations

import pytest

from docpluck.extract_structured import _printed_head_link


def _grid(page, top, bottom):
    # Camelot boxes: PDF coordinates, y grows upward (x0, y0, x1, y1).
    return {"page": page, "bbox": (50.0, bottom, 500.0, top)}


def test_topmost_grid_under_a_printed_head_is_linked():
    g = _grid(11, 700, 300)
    assert _printed_head_link(g, [g], "902\nTable 1. (Continued.)\nStudy", {"Table 1"}) == (
        "Table 1", "Table 1. (Continued.)",
    )


@pytest.mark.parametrize(
    "page_text, earlier",
    [
        ("Table 1. (Continued.)", set()),                       # Table 1 never seen before
        ("Table 1. (Continued.)\nTable 2 (continued)", {"Table 1", "Table 2"}),  # two heads
        ("see Table 1 (continued) for the rest of the items in the long list", {"Table 1"}),  # prose
    ],
)
def test_refusals(page_text, earlier):
    g = _grid(11, 700, 300)
    assert _printed_head_link(g, [g], page_text, earlier) is None


def test_a_lower_grid_is_not_linked():
    upper, lower = _grid(11, 700, 500), _grid(11, 400, 100)
    assert _printed_head_link(lower, [upper, lower], "Table 1. (Continued.)", {"Table 1"}) is None


@pytest.mark.parametrize(
    "key, page, label",
    [("10.1017__s0007123424000024.pdf", 11, "Table 1"), ("10.1017__s0007123424000024.pdf", 9, "Table 1"),
     ("10.1016__j.joep.2020.102350.pdf", 3, "Table 1"), ("10.1037__pspp0000586.pdf", 10, "Table 9")],
)
def test_real_continuation_pages_are_labelled(key, page, label):
    from docpluck.extract_structured import extract_pdf_structured
    from docpluck.testing.corpus import custody_path

    tables = extract_pdf_structured(custody_path("fulltext", key).read_bytes())["tables"]
    on_page = [t for t in tables if t.get("page") == page]
    assert any(t.get("label") == label and t.get("continuation_of") == label
               and t.get("caption_status") == "matched" for t in on_page), [
        (t.get("label"), t.get("caption_status")) for t in on_page]
