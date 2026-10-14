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
def table3():
    pdf = require_corpus_pdf("harvard/ar_royal_society_rsos_140072.pdf").read_bytes()
    return [t for t in extract_pdf_structured(pdf)["tables"] if t.get("label") == "Table 3"][0]


@pytest.fixture(scope="module")
def rows(table3):
    t = table3
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


def test_restored_cells_say_so(table3):
    """Provenance (tier-2 review, Sonnet, 2026-10-14): a restored sign is marked on its
    cell, and a printed value is not."""
    marked = [c for c in table3["cells"] if c.get("restored") == "sign"]
    assert marked and all(c["text"][:1] in ("−", "-") for c in marked), marked[:3]
    plain = [c for c in table3["cells"] if c["text"] == "0.19"]
    assert plain and all("restored" not in c for c in plain)


def test_dash_glued_to_a_digit_is_not_a_sign():
    from docpluck.tables.dropped_glyphs import _glued_on_left
    two = {"text": "1", "x0": 90.0, "x1": 95.0, "bottom": 100.0}
    dash = {"text": "−", "x0": 95.2, "x1": 100.0, "bottom": 100.0, "size": 10.0}
    assert _glued_on_left(dash, [two, dash])
    paren = {"text": "(", "x0": 90.0, "x1": 95.0, "bottom": 100.0}
    assert not _glued_on_left(dash, [paren, dash])
    far = {"text": "1", "x0": 60.0, "x1": 65.0, "bottom": 100.0}
    assert not _glued_on_left(dash, [far, dash])


def test_line_text_must_start_a_token_once():
    from docpluck.tables.dropped_glyphs import _token_start_positions
    assert _token_start_positions("1.5 x 10 5", "5") == [9]
    assert _token_start_positions("0.3 0.3", "0.3") == [0, 4]   # ambiguous -> no repair
    assert _token_start_positions("(0.03)", "0.03") == [1]
