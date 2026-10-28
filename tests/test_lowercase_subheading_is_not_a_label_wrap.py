"""A value-less lowercase sub-heading is not the second line of the row above.

10.1098/rsos.250908 Table 15 (p22, rasterized 2026-10-27) prints two groups of
items under the sub-headings "conservative change" and "liberal change". The
whole table labels its rows in lowercase ("homosexuality", "global warming"),
so a lowercase start is no evidence of a wrapped line there: the continuation
merge glued "liberal change" onto the previous row, which read "monogamy
liberal change", and the heading vanished as a row.

A lowercase line still joins the row above in a table whose own labels are
capitalised (10.1177/01461672251327169 Table 6: "Thought about" / "enormous" /
"workload"), and in a lowercase table when the row above visibly breaks off
("financial success in" / "life").
"""
from __future__ import annotations

from docpluck.tables.cell_cleaning import _merge_continuation_rows

_ROWS = [
    ["item", "M (s.d.)", "t", "p"],
    ["conservative change", "", "", ""],
    ["homosexuality", "−35.9 (50.8)", "−20.0", "< 0.001"],
    ["patriotism", "−41.3 (43.8)", "−26.8", "< 0.001"],
    ["theism", "−40.1 (45.0)", "−25.2", "< 0.001"],
    ["monogamy", "−22.1 (39.2)", "−16.0", "< 0.001"],
    ["liberal change", "", "", ""],
    ["global warming", "60.1 (42.2)", "40.4", "< 0.001"],
    ["gender equality", "56.1 (38.7)", "41.1", "< 0.001"],
]


def test_lowercase_subheading_in_a_lowercase_table_stays_its_own_row():
    out = _merge_continuation_rows([r[:] for r in _ROWS])
    labels = [r[0] for r in out]
    assert "monogamy" in labels
    assert "liberal change" in labels
    assert labels.index("liberal change") == labels.index("monogamy") + 1


def test_a_visibly_broken_lowercase_label_still_joins():
    rows = [
        ["item", "M", "t", "p"],
        ["homosexuality", "−35.9", "−20.0", "< 0.001"],
        ["financial success in", "34.0", "21.4", "< 0.001"],
        ["life", "", "", ""],
        ["abortion", "50.6", "28.0", "< 0.001"],
    ]
    out = _merge_continuation_rows([r[:] for r in rows])
    assert [r[0] for r in out] == ["item", "homosexuality", "financial success in life", "abortion"]


def test_capitalised_table_still_joins_its_lowercase_wraps():
    v = ["78.79", "45.76", "−33.02"]
    rows = [
        ["Negative experiences", "", "", ""],
        ["Thought about", *v],
        ["enormous", "", "", ""],
        ["workload", "", "", ""],
        ["Had great meal", *v],
    ]
    out = _merge_continuation_rows([r[:] for r in rows])
    assert [r[0] for r in out] == [
        "Negative experiences", "Thought about enormous workload", "Had great meal",
    ]


def test_rsos_250908_table_15_monogamy_row_label():
    from docpluck.extract_structured import extract_pdf_structured
    from docpluck.tables.flatten import flatten_table
    from docpluck.testing.corpus import custody_path

    p = custody_path("fulltext", "10.1098__rsos.250908.pdf")
    tables = extract_pdf_structured(p.read_bytes())["tables"]
    t15 = next(t for t in tables if t.get("label") == "Table 15")
    labels = [r["row_label"] for r in flatten_table(t15)]
    assert "monogamy" in labels
    assert not any("liberal change" in lb and lb != "liberal change" for lb in labels)


def test_enumerated_labels_are_not_lowercase_labels():
    # 10.1016/j.jesp.2021.104154 Table 12 (p14): "a. Virgin rat", "b. Hurricane"
    # / "seeding" -- an enumerator is not a lowercase label; the wrap joins.
    rows = [
        ["Hindsight vs. Foresight", "t", "df", "p"],
        ["a. Virgin rat", "-1.48", "399", ".140"],
        ["b. Hurricane", ".88", "399", ".382"],
        ["seeding", "", "", ""],
        ["c. Gosling", "-.67", "399", ".320"],
        ["imprinting", "", "", ""],
        ["d. Y-test", "-1.54", "399", ".124"],
    ]
    out = _merge_continuation_rows([r[:] for r in rows])
    assert [r[0] for r in out][1:] == [
        "a. Virgin rat", "b. Hurricane seeding", "c. Gosling imprinting", "d. Y-test",
    ]
