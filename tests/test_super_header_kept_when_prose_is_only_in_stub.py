"""A super-header row survives when only its STUB cell is leaked caption prose
(ESCImate request, 2026-10-14, item 1).

10.1525/collabra.74820 p7, Table 2: five model groups, each "Model k: <scale>" over
B | SE | t | 95%CI. The caption's last line ("simple slope analysis, assessing the
relationship between ...") leaked into the stub cell of the super-header row. The
prose-leak guard then dropped the WHOLE row, so the five model labels were lost, no
groups were found, and flatten kept only the LAST model's t/CI per row (up to 28
t-statistics lost for ESCImate).
"""
from __future__ import annotations

from docpluck.tables.cell_cleaning import _MERGE_SEPARATOR, _fold_super_header_rows
from docpluck.tables.flatten import flatten_table

PROSE = ("simple slope analysis, assessing the relationship between US condition on CS "
         "evaluation at different levels of Neuroticism (H1 and H2)")


def test_stub_prose_is_blanked_and_labels_fold():
    sup = [PROSE, "", "Model 1:", "", "Model 2:", ""]
    sub = ["", "B", "t", "B", "t", "p"]
    out = _fold_super_header_rows([sup, sub])
    assert len(out) == 1, out
    h = out[0]
    assert h[0] == "" and h[2] == "Model 1:" + _MERGE_SEPARATOR + "t", h


def test_prose_in_a_data_column_still_drops_the_row():
    sup = ["", PROSE, "", "Model 2:"]
    sub = ["", "B", "t", "B"]
    assert _fold_super_header_rows([sup, sub]) == [sub]


def test_collabra_74820_table2_keeps_every_model():
    import pytest
    from docpluck.extract_structured import extract_pdf_structured
    from docpluck.testing.corpus import custody_path
    p = custody_path("fulltext", "10.1525__collabra.74820.pdf")
    if not p.exists():
        pytest.fail(f"article-finder copy of 10.1525/collabra.74820 missing: {p}")
    t = [t for t in extract_pdf_structured(p.read_bytes())["tables"] if t.get("label") == "Table 2"][0]
    rows = [fr["fields"] for fr in flatten_table(t) if fr["row_label"] == "US condition"]
    ts = sorted(f.get("t") for f in rows if "t" in f)
    assert ts == [12.02, 12.04, 12.09, 12.12, 12.14], rows
