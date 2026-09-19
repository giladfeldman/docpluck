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

from scripts.harness.corpus import resolve as _harness_resolve  # noqa: E402

_TABLE_HEADING_RE = re.compile(r"^#{2,4}\s+Table\b", re.M)


def _assert_every_table_has_a_heading(doc_id: str):
    """Both skips here were removed 2026-09-17.

    A doc id absent from the manifest and a fixture absent from disk are exactly
    the two things this test exists to notice; skipping on either reported a pass
    for a paper it never opened.
    """
    doc = _BY_ID.get(doc_id)
    assert doc is not None, (
        f"doc id {doc_id!r} is not in scripts/harness/corpus_manifest.json. "
        "Regenerate it with `python -m scripts.harness.corpus --write`."
    )
    pdf = _harness_resolve(doc)
    data = pdf.read_bytes()
    md = render_pdf_to_markdown(data)
    n_headings = len(_TABLE_HEADING_RE.findall(md))
    n_tables = len(extract_pdf_structured(data)["tables"])
    # Assert the INPUT before the output. `0 == 0` is the pass this test would
    # print if detection silently stopped finding anything, and that is the
    # false green the whole corpus-repoint was done to remove.
    assert n_tables > 0, (
        f"{doc_id}: extract_pdf_structured detected NO tables, so the heading "
        "invariant below would pass vacuously (0 == 0). Either detection "
        "regressed or this paper no longer exercises the caption-only path."
    )
    assert n_headings == n_tables, (
        f"{doc_id}: {n_headings} `### Table` headings in the rendered .md "
        f"but extract_pdf_structured detected {n_tables} tables — a detected "
        f"table is missing its `### Table N` block"
    )


# table_parity-fail documents from the harness Tier-D baseline at v2.4.53 —
# each carried >=1 caption-only table that rendered with no `### Table` heading.

def test_jama_open_5_every_table_has_a_heading():
    _assert_every_table_has_a_heading("corpus__ama__jama-open-5")


def test_sci_rep_3_every_table_has_a_heading():
    _assert_every_table_has_a_heading("corpus__nature__sci-rep-3")


def test_chan_2025_every_table_has_a_heading():
    # RE-POINTED 2026-09-18, and the reason is recorded rather than hidden.
    # This asserted on a fixture drawn from a sibling project's own test set --
    # a paper that is NOT in the article custodian's docpluck corpus, and whose
    # source root does not exist on this machine, so
    # `scripts/harness/corpus.discover()` dropped its whole family,
    # 51 PDFs, from the manifest. The id was simply absent and the test failed
    # loudly, which is the new corpus contract working as designed.
    #
    # WHAT WAS LOST, stated plainly: that specific v2.4.53 table_parity fixture
    # no longer exercises this invariant. The substitute is a paper the
    # custodian does hold, measured before it was chosen so it cannot pass
    # vacuously -- 9 detected tables, 9 `### Table` headings. DECISION OWED to
    # the owner: re-admit that sibling fixture family to the corpus, or accept
    # the narrower fixture set.
    _assert_every_table_has_a_heading("corpus__apa__chan-feldman-2025-cogemo")
