"""A minus the table backend emitted as a row of its own joins its NUMBER, never
the parenthesised standard error printed under it.

10.1093/sf/soaf022 p17 Table 5 prints the ordinal cutpoints as ``−75.52`` over
``(40.58)`` (rasterised 2026-10-24). The minus glyph comes from a symbol font set
1.7 pt higher than the digits, so the grid carries it as its own row between the
number and the standard error. The continuation merge then folded the SE row onto
that lone minus and the table html read ``−(40.58)`` while ``75.52`` lost its sign.
"""
from __future__ import annotations

from docpluck.tables.cell_cleaning import _merge_continuation_rows, cells_grid_to_html

M = "−"


def test_sign_row_after_its_number():
    g = [["Variables", "A", "B"],
         ["Cutpoint 1", "75.52", "86.26"],
         ["", M, M],
         ["", "(40.58)", "(33.58)"],
         ["Cutpoint 2", "73.06", "83.08"]]
    out = _merge_continuation_rows(g)
    assert out[1] == ["Cutpoint 1", M + "75.52 (40.58)", M + "86.26 (33.58)"] or \
        out[1][1].startswith(M + "75.52"), out
    flat = " | ".join(" ; ".join(r) for r in out)
    assert M + "(" not in flat and "-(" not in flat, out
    html = cells_grid_to_html(g)
    assert M + "(40.58)" not in html and "75.52" in html
    assert (M + "75.52") in html or ("-75.52") in html, html


def test_sign_row_before_its_number():
    g = [["Variables", "A", "B"],
         ["", M, M],
         ["Cutpoint 1", "75.52", "86.26"],
         ["", "(40.58)", "(33.58)"]]
    out = _merge_continuation_rows(g)
    flat = " | ".join(" ; ".join(r) for r in out)
    assert M + "75.52" in flat and M + "86.26" in flat, out
    assert M + "(" not in flat, out


def test_sign_row_with_no_bare_number_neighbour_is_left_alone():
    # Neither neighbour holds an unsigned number in those columns: no sign moves.
    g = [["Variables", "A", "B"],
         ["Cutpoint 1", "n/a", "n/a"],
         ["", M, M],
         ["", "(40.58)", "(33.58)"]]
    out = _merge_continuation_rows(g)
    flat = " | ".join(" ; ".join(r) for r in out)
    assert M + "(" not in flat, out
    assert "n/a" in flat and M + "n/a" not in flat, out


def test_real_table_cutpoints_keep_their_sign():
    from docpluck.testing import require_corpus_pdf
    from docpluck.extract_structured import extract_pdf_structured

    pdf = require_corpus_pdf("asa/social_forces_1.pdf")   # 10.1093/sf/soaf022
    res = extract_pdf_structured(pdf.read_bytes())
    t5 = [t for t in res["tables"] if t.get("label") == "Table 5"][0]
    html = t5["html"]
    assert M + "(" not in html and "-(" not in html, "a minus prefixed to a standard error"
    for v in ("75.52", "86.26", "95.25", "73.06", "83.08", "93.11"):
        assert (M + v) in html or ("-" + v) in html, v
    assert "(40.58)" in html and "(30.46)" in html
