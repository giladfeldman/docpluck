"""A minus sign Camelot's text layer drops is restored from the page (2.4.154).

10.1098/rsos.140072 p7, Table 3, checked on the rasterized page 2026-10-14: the minus
signs are drawn in the MathTime symbol font (MTSY). pdftotext and pdfplumber read them
as U+2212; Camelot's own text lines do not contain them, so the grid published
"submission | 0.03 | 0.02 | 1.93" where the page prints "-0.03 ... -1.93", and
"affiliation | 0.04 | 0.04 | 0.91" for "-0.04 ... -0.91". A glyph the page prints
directly left of a cell's number, on its baseline, and that no Camelot text line
holds, is put back in that cell.
"""
from __future__ import annotations

import collections

import pytest

from docpluck.extract_structured import extract_pdf_structured
from docpluck.testing import require_corpus_pdf


@pytest.fixture(scope="module")
def rows():
    pdf = require_corpus_pdf("harvard/ar_royal_society_rsos_140072.pdf").read_bytes()
    t = [t for t in extract_pdf_structured(pdf)["tables"] if t.get("label") == "Table 3"][0]
    out = collections.defaultdict(dict)
    for c in t["cells"]:
        out[c["r"]][c["c"]] = c["text"]
    return [[r[c] for c in sorted(r)] for _, r in sorted(out.items())]


def _row(rows, label):
    hit = [r for r in rows if label in r]
    assert hit, rows
    return hit[0]


def _neg(s: str) -> bool:
    return s[:1] in ("−", "-")


def test_negative_estimates_keep_their_sign(rows):
    sub = _row(rows, "submission")
    assert _neg(sub[sub.index("submission") + 1]), sub      # estimate -0.03
    assert _neg(sub[sub.index("submission") + 3]), sub      # t-ratio -1.93
    aff = _row(rows, "affiliation")
    assert _neg(aff[aff.index("affiliation") + 1]), aff     # -0.04


def test_positive_values_are_untouched(rows):
    ov = _row(rows, "overt aggression")
    vals = ov[ov.index("overt aggression") + 1:]
    assert vals[:4] == ["0.19", "0.17", "1.13", "0.27"], ov
