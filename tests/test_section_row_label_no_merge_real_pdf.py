"""Real-PDF regression tests for v2.4.27 section-row label detection
in table cell-cleaning (cycle 12, deferred item C from cycle-9
handoff).

xiao_2021_crsp.pdf Table 6 has spanning section-row labels
(``Control (n = 339, 2 selected the decoy, 0.6%)``,
``Regret-Salient (n = 331, ...)``) that pdftotext / Camelot output as
single-cell rows with all other columns empty. Pre-v2.4.27,
``_merge_continuation_rows`` interpreted these as continuation rows
and merged them into the data cell above, producing garbage like::

    <td>112/172<br>Regret-Salient (n = 331, ...)</td>

v2.4.27 added ``_is_section_row_label`` (single non-empty cell with
noun-phrase + ``(n = ...)`` parenthetical) to the merge gate.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from docpluck.render import render_pdf_to_markdown
from docpluck.tables.cell_cleaning import _merge_continuation_rows


TEST_PDFS = Path(__file__).resolve().parents[1].parent / "PDFextractor" / "test-pdfs"


# ---- Contract tests ---------------------------------------------------------


def test_section_row_label_not_merged():
    rows = [
        ["Choice set 2", "112/172", "65.1%", "4.59 (1.72)"],
        ["", "Regret-Salient (n = 331, 5 selected the decoy, 1.5%)", "", ""],
        ["Overall", "185/326", "56.7%", "4.72 (1.71)"],
    ]
    result = _merge_continuation_rows(rows)
    assert len(result) == 3, result
    # The middle row stays separate.
    assert "Choice set 2" in result[0]
    assert "Regret-Salient" in result[1][1]
    assert "Regret-Salient" not in result[0][1]
    assert result[2][0] == "Overall"


def test_normal_continuation_row_still_merged():
    rows = [
        ["1a", "People underestimate"],
        ["", "the importance of small daily actions"],
    ]
    result = _merge_continuation_rows(rows)
    assert len(result) == 1, result
    assert "underestimate" in result[0][1]
    assert "small daily actions" in result[0][1]


def test_pure_empty_row_not_treated_as_section_row():
    rows = [
        ["x", "y"],
        ["", ""],
        ["a", "b"],
    ]
    result = _merge_continuation_rows(rows)
    assert len(result) == 3
    assert result[1] == ["", ""]


def test_section_row_with_M_descriptor():
    rows = [
        ["Cond A", "5.2", "1.3"],
        ["", "Female (n = 50, M = 4.7, SD = 1.2)", ""],
        ["Cond B", "5.8", "1.4"],
    ]
    result = _merge_continuation_rows(rows)
    assert len(result) == 3
    assert "Female" in result[1][1]
    assert "Female" not in result[0][1]


def test_long_section_row_label_not_merged_due_to_length_cap():
    long_content = "Group A " + ("x " * 200) + "(n = 50, M = 4.7)"
    rows = [
        ["Cond A", "5.2"],
        ["", long_content],
    ]
    result = _merge_continuation_rows(rows)
    # Too long to be a section-row label — falls through to normal merge path.
    assert len(result) == 1, result


# ---- Real-PDF regression test (rule 0d) ------------------------------------


@pytest.mark.skipif(
    not (TEST_PDFS / "apa" / "xiao_2021_crsp.pdf").exists(),
    reason="xiao_2021_crsp.pdf fixture not present",
)
def test_xiao_table_6_no_section_row_leak_into_data_cells():
    """Cycle-9 handoff item C — xiao_2021_crsp Table 6 must NOT have
    a section-row label (``Regret-Salient (n = 331, ...)``) collapsed
    into the data cell above it (``112/172``)."""
    pdf = TEST_PDFS / "apa" / "xiao_2021_crsp.pdf"
    md = render_pdf_to_markdown(pdf.read_bytes())
    idx = md.find("### Table 6")
    assert idx >= 0, "Table 6 not rendered"
    table_chunk = md[idx:idx + 3500]
    # The bad pattern: a data cell that combines a fraction count with
    # the next group's section-row label via a <br>.
    bad_pattern = re.compile(
        r"<td>\d+/\d+<br>(?:Regret-Salient|Control|Group)"
    )
    assert not bad_pattern.search(table_chunk), (
        f"section-row label merged into data cell: "
        f"{bad_pattern.search(table_chunk).group()!r}"
    )
