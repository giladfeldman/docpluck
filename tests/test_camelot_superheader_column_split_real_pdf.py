"""A spanning super-header must not merge the columns beneath it.

Real paper, DOI recorded: ``10.1080/23743603.2021.1878340`` (corpus
``apa/xiao_2021_crsp.pdf``) p16, Table 4. ``Original`` and ``Replication`` each
span ``F | p | eta2p (90% CI)``; Camelot stream merged ``p`` with ``eta2p`` and
delivered ``< .010.240`` for the printed ``< .01`` and ``0.240``.
"""

from __future__ import annotations

import pytest

from docpluck.testing import require_corpus_pdf


@pytest.fixture(scope="module")
def xiao_t4():
    from docpluck.extract_structured import extract_pdf_structured

    pdf = require_corpus_pdf("apa/xiao_2021_crsp.pdf")
    r = extract_pdf_structured(pdf.read_bytes())
    t4 = [t for t in r["tables"] if (t.get("label") or "").startswith("Table 4")]
    assert len(t4) == 1
    return t4[0]


def test_xiao_table4_has_the_eight_printed_columns(xiao_t4):
    assert xiao_t4["n_cols"] == 8


def test_xiao_table4_p_and_eta_are_separate_cells(xiao_t4):
    texts = [c["text"] for c in xiao_t4["cells"]]
    assert not any(".010." in t for t in texts), texts
    assert texts.count("< .01") == 2
    assert "0.240" in texts and ".707" in texts
