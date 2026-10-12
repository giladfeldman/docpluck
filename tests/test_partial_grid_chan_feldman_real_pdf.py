"""A grid that covers part of its printed table is not delivered as complete.

10.1080/02699931.2024.2434156 (chan_feldman), checked on the rasterized pages
2026-10-12:

* Table 8 (p13) prints 10 columns -- Variable, M, SD, alpha, omega and five
  correlation columns 1-5. The grid has 6: correlation columns 2-5 (`.64***
  [.55, .70]`, `-.73*** [-.78, -.67]`, `-.32***`, `.37*** [.26, .47]`) are not in
  it; they survive only as loose lines in the body text.
* Table 4 (p9) is a ~45-line design table (dependent variables, item wordings,
  comprehension checks). The grid is 2 x 2 (level-of-empathy header + one row).

Both are reported `content_status="cells"`, i.e. complete. Either a real capture
fix (all printed columns/rows) or the partial-grid completeness guard (TODO
d-095325: demote with a label) satisfies this test; nothing else does.
strict=True: the day either lands, this XPASSes loudly and the marker comes off.
"""
from __future__ import annotations

import pytest

from docpluck.extract_structured import extract_pdf_structured
from docpluck.testing import require_corpus_pdf


def _tables():
    pdf = require_corpus_pdf("apa/chan_feldman_2025_cogemo.pdf").read_bytes()
    return {t.get("label"): t for t in extract_pdf_structured(pdf)["tables"]}


def _n_cols(t) -> int:
    return 1 + max((c.get("c", 0) for c in t.get("cells") or []), default=-1)


def _n_rows(t) -> int:
    return 1 + max((c.get("r", 0) for c in t.get("cells") or []), default=-1)


@pytest.mark.xfail(strict=True, reason="Blocked on d-095325 (partial-grid guard); TODO d-f74976.")
def test_table8_is_complete_or_not_called_complete():
    t = _tables()["Table 8"]
    assert t.get("content_status") != "cells" or _n_cols(t) >= 10, (
        f"Table 8 delivered as complete with {_n_cols(t)} of 10 printed columns"
    )


@pytest.mark.xfail(strict=True, reason="Blocked on d-095325 (partial-grid guard); TODO d-f74976.")
def test_table4_is_complete_or_not_called_complete():
    t = _tables()["Table 4"]
    assert t.get("content_status") != "cells" or _n_rows(t) >= 10, (
        f"Table 4 delivered as complete with {_n_rows(t)} rows of a ~45-line table"
    )
