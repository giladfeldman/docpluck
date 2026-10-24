"""A side-by-side table runs to its own bottom rule, not to its first blank gap.

10.1016/j.jesp.2021.104154 p12 prints Table 9 (left column) and Table 10 (right
column) side by side, each between a top rule and a bottom rule (checked on the
page raster 2026-10-24: Table 9 ends with "c. Places in Area C*  33.78 21.56
38.73 22.70", Table 10 with "c. Places in Area C*  4.95 ... 0.03 0.42"). Once the
two captions were assigned to their own columns, each column region ended where
the caption's search band ended -- the blank line before "Hurricane seeding
experiment" -- so 22 of Table 10's rows and most of Table 9's fell into the body
as one-number-per-line text.
"""
from __future__ import annotations

import pytest

from docpluck.testing.corpus import custody_path


@pytest.fixture(scope="module")
def chen_p12():
    from docpluck.extract_structured import extract_pdf_structured

    p = custody_path("fulltext", "10.1016__j.jesp.2021.104154.pdf")
    tables = extract_pdf_structured(p.read_bytes())["tables"]
    return {t.get("label"): t for t in tables if t.get("page") == 12}


def _text(t):
    return " ".join(c["text"] for c in t.get("cells") or [])


def test_table10_reaches_its_last_row(chen_p12):
    txt = _text(chen_p12["Table 10"])
    # first block, a middle block, and the last row before the bottom rule
    for v in ("9.26", "-11.14", "6.12", "-5.73", "4.95", "0.42"):
        assert v in txt, v
    # nothing of the left column's table
    assert "29.16" not in txt and "33.78" not in txt


def test_table9_reaches_its_last_row(chen_p12):
    txt = _text(chen_p12["Table 9"])
    for v in ("29.16", "47.74", "39.14", "59.62", "33.78", "38.73", "22.70"):
        assert v in txt, v
    assert "9.26" not in txt and "4.95" not in txt
    # the note below the bottom rule is not a row
    assert "Bolded options" not in txt and "Options and numbers" not in txt
