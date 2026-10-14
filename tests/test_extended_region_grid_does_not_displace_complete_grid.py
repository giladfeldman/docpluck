"""Rows appended under a caption-region grid never let it displace a more complete grid.

10.1186/s12889-023-17078-5 p8, Table 3 (checked 2026-10-14): the page-wide Camelot grid
holds the whole page of the table, 50 rows x 5 columns. The caption-region grid is
narrower in height and had split a header column (6 columns). Before 2.4.154 it lost the
pick (wider, but under 60% of the cells). Once `bottom_extend` appended 13 rows to it,
it crossed the 60% bar and the 34-row grid with the split header replaced the complete one.
"""
from __future__ import annotations

from docpluck.extract_structured import extract_pdf_structured
from docpluck.testing import require_corpus_pdf


def test_table3_keeps_the_complete_grid():
    pdf = require_corpus_pdf("vancouver/bmc_pub_health_2.pdf").read_bytes()
    t = [t for t in extract_pdf_structured(pdf)["tables"] if t.get("label") == "Table 3"][0]
    assert t.get("n_cols") == 5, (t.get("n_rows"), t.get("n_cols"))
    assert t.get("n_rows", 0) >= 45, (t.get("n_rows"), t.get("n_cols"))
    assert all(not k.startswith("_appended") for k in t), sorted(t)
