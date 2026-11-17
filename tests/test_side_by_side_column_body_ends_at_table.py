"""A side-by-side isolated table's column body ends at its note, not the page foot.

10.1016/j.evolhumbehav.2016.06.001 prints Table 2 (p4) and Table 5 (p6) in one
column of a two-column page, each closed by a "Note:" paragraph. The column-body
rebuild (``extract_structured._column_body_text``) read every line of that
column below the caption, so on 2.4.158 Table 2's raw_text ran on into
"2.2.5. Self-Harm", "3. Results" and "3.1. Preliminary Analyses", and Table 5's
into "3.2.3." / "3.2.4." body prose (measured 2026-11-11). The text-channel body
already ends at the note paragraph; the column rebuild now does the same.
"""
from __future__ import annotations

import pytest

from docpluck.testing.corpus import custody_path


@pytest.fixture(scope="module")
def hurst_tables():
    from docpluck.extract_structured import extract_pdf_structured

    p = custody_path("fulltext", "10.1016__j.evolhumbehav.2016.06.001.pdf")
    return {t.get("label"): t for t in extract_pdf_structured(p.read_bytes())["tables"]}


def test_table_2_body_ends_at_its_note(hurst_tables):
    raw = hurst_tables["Table 2"]["raw_text"]
    assert raw.rstrip().endswith("is required."), raw[-300:]
    for prose in ("Self-Harm", "Results", "Preliminary Analyses", "Deliberate Self-Harm Inventory"):
        assert prose not in raw, prose
    # Every printed row is kept, the last data row included.
    assert "Little interest or pleasure in doing things? 34.1" in raw
    assert "9.4" in raw


def test_table_5_body_ends_at_its_note(hurst_tables):
    t5 = hurst_tables["Table 5"]
    raw = t5["raw_text"]
    # The last printed row ends the body; the note is carried as the footnote.
    assert raw.rstrip().endswith("Hostility -.52 -.52"), raw[-300:]
    assert "are in bold." in (t5.get("footnote") or "")
    assert "Number of full biological siblings" in raw
    for prose in ("Life History Strategies and Attachment", "moderation analyses", "Hayes"):
        assert prose not in raw, prose
