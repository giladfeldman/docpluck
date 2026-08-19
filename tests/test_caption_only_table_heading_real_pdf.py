"""Regression test: every detected table emits a `### Table N` heading
(cycle 2, v2.4.55).

A table that ``extract_pdf_structured`` detects only by its caption (Camelot
found no grid AND there is no ``raw_text`` fallback) was emitted by render.py
as a bare italic ``*Table N. ...*`` line with NO ``### Table N`` heading — so
the table was invisible as a table in the rendered view. The harness Tier-D
``table_parity`` check (the count of ``### Table`` headings must match the
count of tables in ``tables.json``) failed on 15 corpus documents for exactly
this reason.

Fix (v2.4.55): render.py's in-section caption-only-table branch emits
``### {label}`` + caption, consistent with the appendix leftover-table path.

The invariant under test: the number of ``### Table N`` headings in the
rendered .md equals the number of tables ``extract_pdf_structured`` detects —
every detected table is structurally visible.
"""

from __future__ import annotations

import os

import json
import re
from pathlib import Path

import pytest

# Camelot is not needed by this module's tests; skipping it keeps them fast.
# Declarative on purpose: this was `os.environ.setdefault(...)` at module scope,
# which executes during COLLECTION and was never undone, so importing this file
# disabled Camelot for the WHOLE pytest process and every real-PDF table test
# collected afterwards found no tables. `conftest._camelot_disabled_per_module`
# reads this flag and restores the prior value when the module finishes.
DISABLE_CAMELOT = True

from docpluck.extract_structured import extract_pdf_structured
from docpluck.render import render_pdf_to_markdown

_REPO = Path(__file__).resolve().parents[1]
_VIBE = Path(os.environ.get("VIBE_ROOT") or Path.home() / "Vibe")
_MANIFEST = json.loads(
    (_REPO / "scripts" / "harness" / "corpus_manifest.json").read_text(encoding="utf-8")
)
_BY_ID = {d["id"]: d for d in _MANIFEST["documents"]}

_TABLE_HEADING_RE = re.compile(r"^#{2,4}\s+Table\b", re.M)


def _assert_every_table_has_a_heading(doc_id: str):
    doc = _BY_ID.get(doc_id)
    if doc is None:
        pytest.skip(f"doc id not in manifest: {doc_id}")
    pdf = _VIBE / doc["rel_path"]
    if not pdf.is_file():
        pytest.skip(f"fixture missing: {pdf}")
    data = pdf.read_bytes()
    md = render_pdf_to_markdown(data)
    n_headings = len(_TABLE_HEADING_RE.findall(md))
    n_tables = len(extract_pdf_structured(data)["tables"])
    assert n_headings == n_tables, (
        f"{doc_id}: {n_headings} `### Table` headings in the rendered .md "
        f"but extract_pdf_structured detected {n_tables} tables — a detected "
        f"table is missing its `### Table N` block"
    )


# table_parity-fail documents from the harness Tier-D baseline at v2.4.53 —
# each carried >=1 caption-only table that rendered with no `### Table` heading.

def test_jama_open_5_every_table_has_a_heading():
    _assert_every_table_has_a_heading("pdfextractor__ama__jama-open-5")


def test_sci_rep_3_every_table_has_a_heading():
    _assert_every_table_has_a_heading("pdfextractor__nature__sci-rep-3")


def test_chan_2025_every_table_has_a_heading():
    _assert_every_table_has_a_heading(
        "escicheck__chan-etal-2025-pcirr-rsos-tsang2006-replication-extension-print-no-supp"
    )
