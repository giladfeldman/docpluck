"""A data row the continuation merge stacked is data, not a third header row.

10.1080/23743603.2021.1878340 p13 Table 2 (rasterised 2026-10-24) prints two item
rows per product ("A" over "C"). The merge stacks them into one row whose cells
hold two values joined by the internal line-break marker, and the header test
counted such a cell as non-numeric -- so the first product's row became a third
header row, its values became "group" names ("50.26 (19.63) (502)", ".001") and
every record of the table had empty fields.
"""
from __future__ import annotations

from docpluck.tables.cell_cleaning import _MERGE_SEPARATOR as S, _is_header_like_row


def test_stacked_values_count_as_data():
    row = ["Running shoes", f"A{S}C", f"50.26 (19.63) (502){S}24.05 (15.51) (502)",
           f"\u22123.23 (993.46){S}\u22123.50 (997.65)", f".001{S}< .001",
           f"\u22120.20 [\u22120.33, \u22120.08]{S}\u22120.22 [\u22120.34, \u22120.10]",
           "0.14", ".707", "", f"< 0.001{S}[0.000, 0.004]", "< 0.001"]
    assert not _is_header_like_row(row)


def test_stacked_header_words_are_still_a_header():
    assert _is_header_like_row(["", f"Points{S}M (SD)", f"Cond.{S}1A", "t", "p"])


def test_real_table_has_no_value_named_groups():
    from docpluck.testing import require_corpus_pdf
    from docpluck.extract_structured import extract_pdf_structured
    from docpluck.tables.flatten import flatten_table

    pdf = require_corpus_pdf("apa/xiao_2021_crsp.pdf")   # 10.1080/23743603.2021.1878340
    t = [t for t in extract_pdf_structured(pdf.read_bytes())["tables"] if t.get("label") == "Table 2"][0]
    rows = [(f if isinstance(f, dict) else f.__dict__) for f in flatten_table(t)]
    groups = {r["fields"].get("group") for r in rows}
    assert not any(g and g[0] in "0123456789.<\u2212-" for g in groups), groups
    shoes = [r["fields"] for r in rows if r["row_label"] == "Running shoes"]
    assert shoes and all(f.get("F") == 0.14 and f.get("p") == 0.707 for f in shoes), shoes
