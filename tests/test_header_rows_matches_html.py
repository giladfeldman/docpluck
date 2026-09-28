"""`Table["header_rows"]` states the header split the table's own html used.

Before 2026-09-28 each capture path wrote its own guess: Camelot hardcoded `1`,
the layout path `1 if any is_header else 0`, the DOCX path `n_header or 1`. On
the same tables the html's `<thead>` held 0, 2 or 3 rows, so a consumer reading
the field was told a split that no channel had made. Now the field is set from
the html at the structured-extraction exit (`tables.render.sync_header_rows`).
"""
from __future__ import annotations

from docpluck.extract_structured import extract_pdf_structured
from docpluck.tables.render import header_rows_in_html, sync_header_rows
from docpluck.testing import require_corpus_pdf


def test_header_rows_in_html_counts_thead_rows():
    assert header_rows_in_html(None) is None
    assert header_rows_in_html("") is None
    assert header_rows_in_html("<table><tbody><tr><td>1</td></tr></tbody></table>") == 0
    two = "<table><thead><tr><th>a</th></tr><tr><th>b</th></tr></thead><tbody></tbody></table>"
    assert header_rows_in_html(two) == 2


def test_sync_overwrites_a_guessed_value_and_leaves_gridless_tables_alone():
    tables = [
        {"html": "<table><thead><tr><th>a</th></tr><tr><th>b</th></tr></thead></table>",
         "cells": [{}], "header_rows": 1},
        {"html": "", "cells": [{}], "header_rows": 1},
        {"html": None, "cells": [], "header_rows": None},
    ]
    sync_header_rows(tables)
    assert [t["header_rows"] for t in tables] == [2, 0, None]


def test_every_real_table_reports_its_own_thead():
    # 10.1525/collabra.90203: ten tables across Camelot and layout paths.
    r = extract_pdf_structured(require_corpus_pdf("apa/maier_2023_collabra.pdf").read_bytes())
    checked = 0
    for t in r["tables"]:
        if t.get("html"):
            assert t["header_rows"] == header_rows_in_html(t["html"]), t.get("label")
            checked += 1
    assert checked >= 5, f"only {checked} tables carried html -- the check saw almost nothing"
