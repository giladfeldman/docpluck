"""A TIE BETWEEN CAPTIONS WAS BROKEN BY TEXT ORDER, NOT BY THE PAGE.

`_find_caption_for_table` scores a Camelot grid against each same-page caption by
shared words; when both score 0 it took the earlier caption. 10.1525/collabra.90203
p9 (raster-checked 2026-11-11): Table 4 is a text design table, Table 5 the
descriptives (2.84 [1.89] ... (1004)). On 2.4.158 BOTH labels carried Table 5's
grid, so Table 4's content was lost. A grid belongs to the caption printed
directly above it.
"""

from __future__ import annotations

import pytest

from docpluck.testing.corpus import custody_path


def _text(t) -> str:
    return " ".join(c.get("text") or "" for c in (t.get("cells") or [])) + " " + (t.get("raw_text") or "")


@pytest.fixture(scope="module")
def maier():
    from docpluck.extract_structured import extract_pdf_structured

    p = custody_path("fulltext", "10.1525__collabra.90203.pdf")
    return {t.get("label"): t for t in extract_pdf_structured(p.read_bytes())["tables"]}


def test_maier_descriptives_sit_under_table_5(maier):
    t5 = maier["Table 5"]
    t5_cells = " ".join(c.get("text") or "" for c in (t5.get("cells") or []))
    for printed in ("2.84 [1.89]", "2.74 [1.98]", "2.23 [1.91]", "(1004)"):
        assert printed in t5_cells, f"Table 5 lost {printed!r}"


def test_maier_table_4_keeps_its_own_design_rows(maier):
    t4 = maier["Table 4"]
    text = _text(t4)
    assert "2.84 [1.89]" not in text, "Table 5's descriptives are filed under Table 4"
    for printed in ("IV operationalization", "DV operationalization", "Updated victim information"):
        assert printed in text, f"Table 4 lost {printed!r}"


@pytest.mark.xfail(strict=True, reason="d-c10801: the text body of a text-heavy table stops at its "
                   "first long wrapped line ('...information retrieved'), so the later rows are missing")
def test_maier_table_4_text_reaches_its_last_row(maier):
    text = _text(maier["Table 4"])
    for printed in ("Procedural details", "Far replication"):
        assert printed in text, f"Table 4 lost {printed!r}"
