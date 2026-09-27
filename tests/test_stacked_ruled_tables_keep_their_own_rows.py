"""Two ruled tables stacked on one page must each keep their own rows.

WHAT BROKE (v2.4.143 -> v2.4.144, reported by Scimeto's contract suite)
------------------------------------------------------------------------
On a page carrying two fully ruled tables one above the other, the table
captioned "Table 2" came out holding TABLE 1's F-tests, then Table 2's caption
line as a data row, then Table 2's t-tests with the ``t`` column fused into the
label column (``Sleep vs Nap-3.07``). Placed under Table 1's header
``Effect | F | df1 | df2 | p``, that row flattened to ``F(0.003, -0.31) = 98`` —
a statistic no page printed. Table 2's own t-tests reached no structured table,
so they dropped out of every consumer's consistency check.

WHO BUILT IT
------------
``camelot_extract._augment_lattice_with_stream_rows``. Camelot's lattice flavor
finds both ruled grids correctly; its stream flavor returns ONE block spanning
both tables and both captions. The augmentation (v2.4.94, for a ruled table
whose last rows fall below its ruling) appended every stream row below Table 1's
box — which on a stacked page is the next caption and the next table.

It was latent before v2.4.143: the region-driven candidates were clipped to
three columns, so the mis-built grid was never compared against a correct one
and Table 2's clean lattice grid survived under the wrong caption. 2c8b0dd made
the region candidates correct, and the arbiter's equal-columns tie-break
("more cells wins") then chose the 8-row merged grid over Table 2's own 3-row
grid.

THE FIXTURE IS CONSTRUCTED, ON PURPOSE
--------------------------------------
It is built here with reportlab to the geometry of Scimeto's contract
fixture (two ruled 5-column tables, 18pt rows, the second caption ~8pt below
the first box), because a published article may not be committed to this
public repository. A constructed page proves what the CODE does, not that
the shape occurs; the real-paper evidence is recorded in the CHANGELOG entry for this fix.
"""

from __future__ import annotations

import io

import pytest

from docpluck.extract_structured import extract_pdf_structured


def _stacked_ruled_tables_pdf() -> bytes:
    pytest.importorskip("reportlab")
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    styles = getSampleStyleSheet()
    grid = TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.8, colors.black),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
    ])
    t1 = Table([
        ["Effect", "F", "df1", "df2", "p"],
        ["Condition (main effect)", "5.20", "1", "98", ".025"],
        ["Time (main effect)", "12.50", "2", "196", "<.001"],
        ["Condition x Time", "0.45", "2", "196", ".64"],
    ], hAlign="LEFT", rowHeights=18)
    t1.setStyle(grid)
    t2 = Table([
        ["Contrast", "t", "df", "p", "d"],
        ["Sleep vs Control", "2.41", "98", ".018", "0.15"],
        ["Sleep vs Nap", "-3.07", "98", ".003", "-0.31"],
    ], hAlign="LEFT", rowHeights=18)
    t2.setStyle(grid)

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter)
    body = styles["BodyText"]
    doc.build([
        Paragraph("Results", styles["Heading1"]),
        Paragraph(
            "A repeated-measures analysis of variance was conducted. Table 1 "
            "reports the omnibus effects and Table 2 reports the planned contrasts.",
            body,
        ),
        Spacer(1, 8),
        Paragraph("Table 1. Analysis of variance results.", body),
        t1,
        # <= 12pt reproduces the merge; the consumer's page has ~9pt of air
        # between Table 1's box and Table 2's caption.
        Spacer(1, 8),
        Paragraph("Table 2. Planned contrasts.", body),
        t2,
        Spacer(1, 12),
        Paragraph(
            "The main effect of condition was reliable, F(1, 98) = 5.20, p = .025.",
            body,
        ),
    ])
    return buf.getvalue()


def _rows(table) -> list[list[str]]:
    by_r: dict[int, list[tuple[int, str]]] = {}
    for c in table.get("cells") or []:
        by_r.setdefault(c["r"], []).append((c["c"], (c.get("text") or "").strip()))
    return [[t for _, t in sorted(v)] for _, v in sorted(by_r.items())]


@pytest.fixture(scope="module")
def tables():
    pytest.importorskip("camelot")
    result = extract_pdf_structured(_stacked_ruled_tables_pdf())
    by_label = {t.get("label"): t for t in result["tables"]}
    assert set(by_label) >= {"Table 1", "Table 2"}, [t.get("label") for t in result["tables"]]
    return by_label


def test_table_2_holds_its_own_t_tests(tables):
    rows = _rows(tables["Table 2"])
    assert rows[0] == ["Contrast", "t", "df", "p", "d"], rows
    assert ["Sleep vs Control", "2.41", "98", ".018", "0.15"] in rows, rows
    assert ["Sleep vs Nap", "-3.07", "98", ".003", "-0.31"] in rows, rows


def test_table_2_does_not_carry_table_1_rows(tables):
    text = " ".join(" ".join(r) for r in _rows(tables["Table 2"]))
    for foreign in ("Condition (main effect)", "12.50", "Condition x Time"):
        assert foreign not in text, text


def test_table_1_stops_at_its_own_box(tables):
    rows = _rows(tables["Table 1"])
    assert rows[0] == ["Effect", "F", "df1", "df2", "p"], rows
    assert len(rows) == 4, rows
    text = " ".join(" ".join(r) for r in rows)
    # The next caption and the next table's rows are not Table 1's.
    assert "Planned contrasts" not in text, text
    assert "Sleep vs" not in text, text


def test_no_table_row_fuses_a_label_with_a_value(tables):
    """``Sleep vs Nap-3.07`` is stream's column split, appended by docpluck: it
    is the source of the fabricated ``F(0.003, -0.31) = 98`` flattened row."""
    for label, t in tables.items():
        for row in _rows(t):
            for cell in row:
                assert "Nap-3.07" not in cell and "Control2.41" not in cell, (label, row)
