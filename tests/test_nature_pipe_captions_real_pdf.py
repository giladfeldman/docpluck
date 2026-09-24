"""Nature-family captions (`Fig. 1 |`, `Table 1 |`) must be read.

Why this file exists (2026-09-24). The caption pattern required a `.`/`:` or a
space plus a capital letter after the number. The Nature family prints
`Fig. 1 | Title` — a space and a PIPE — so every caption in that house style was
invisible, figures and tables alike:

    nature/nat_comms_1.pdf  prints 5 figures, 0 tables   -> docpluck: 0 figures
    nature/nat_comms_2.pdf  prints 4 figures, 1 table    -> docpluck: 0 and 0

Nothing went red, because the smoke count tolerance was ±6 and both fixtures
expected fewer than 6 of each, and because every figure test on the figure-only
fixture did `pytest.skip("no figures detected")` — a gate that could only pass.

Verified against the printed pages, not the text channel: both papers were
rasterized. Over all 102 corpus papers, accepting the pipe added 29 caption
matches in 5 papers (all Nature Communications) and 29 of 29 were real captions.
"""

import re

import pytest

import docpluck.tables.captions as captions
from docpluck.extract_structured import extract_pdf_structured
from docpluck.testing import require_corpus_pdf

pytest.importorskip("camelot", reason="camelot not installed (pip install docpluck[all])")

_FIGURE_ONLY = "nature/nat_comms_1.pdf"   # 10.1038/s41467-023-43885-w
_WITH_TABLE = "nature/nat_comms_2.pdf"    # 10.1038/s41467-023-42320-4


@pytest.fixture(scope="module")
def figure_only() -> bytes:
    # require_, not corpus_pdf: a paper this gate claims to test and cannot read
    # is a FAILURE, never a skip.
    return require_corpus_pdf(_FIGURE_ONLY).read_bytes()


@pytest.fixture(scope="module")
def with_table() -> bytes:
    return require_corpus_pdf(_WITH_TABLE).read_bytes()


def test_the_pipe_is_a_caption_separator_and_a_body_reference_is_not():
    assert captions.FIGURE_CAPTION_RE.match("Fig. 1 | Lethal effects of soil pathogens")
    assert captions.TABLE_CAPTION_RE.match("Table 1 | Clinical characteristics")
    # the guard the pattern exists for must survive the widening
    assert not captions.TABLE_CAPTION_RE.match("Table 13 below shows the effects")
    assert not captions.FIGURE_CAPTION_RE.match("Figure 2 shows that")


def test_every_caption_pattern_agrees_on_the_pipe():
    """ONE concept, ONE table: four patterns decide what a caption is.

    Before this, captions.py learned the pipe and camelot_extract.py's two did not,
    so `Table 1 | ...` was a caption for pairing but NOT a caption row to strip --
    and the caption line stayed inside the grid as the table's first cell.
    """
    from docpluck.tables import camelot_extract as ce

    row = "Table 1 | Clinical characteristics"
    assert captions.TABLE_CAPTION_RE.match(row)
    assert captions.FIGURE_CAPTION_RE.match("Fig. 1 | Lethal effects")
    assert ce._CAPTION_ROW_PATTERN.match(row)
    m = ce._TABLE_CAPTION_NUMBER_PATTERN.match(row)
    assert m and m.group(1) == "1"
    assert captions.CAPTION_PIPE_SEPARATOR in ce._CAPTION_ROW_PATTERN.pattern


def test_all_five_printed_figures_are_extracted(figure_only):
    r = extract_pdf_structured(figure_only)
    labels = [f.get("label") for f in r["figures"]]
    assert labels == [f"Figure {n}" for n in range(1, 6)], (
        f"nat_comms_1 prints Fig. 1-5 on pp. 3-7; extracted {labels}"
    )
    # docpluck keeps the label inside the caption text, as for every caption style
    assert r["figures"][0].get("caption", "").startswith("Figure 1 | Lethal effects")


def test_the_gray_band_table_is_extracted_with_its_cells(with_table):
    r = extract_pdf_structured(with_table)
    t1 = [t for t in r["tables"] if t.get("label") == "Table 1"]
    assert t1, f"Table 1 (p4, gray-band header) missing; tables={[t.get('label') for t in r['tables']]}"
    t1 = t1[0]
    assert t1.get("caption_status") == "matched"
    texts = {c.get("text", "") for c in t1.get("cells") or []}
    assert "Control (n = 60)" in texts, f"expected column header not captured: {sorted(texts)[:10]}"
    assert len(r["figures"]) == 4


def test_the_gate_detects_the_regression_it_exists_for(figure_only, monkeypatch):
    """Two-sided: restore the old separator set and the figures must vanish."""
    old = r"(?:[.:]|\s+[A-Z])"
    monkeypatch.setattr(captions, "FIGURE_CAPTION_RE", re.compile(
        r"^\s*(?:Figure|Fig\.?|FIGURE|FIG\.?)\s+(?P<num>\d+)" + old, re.MULTILINE))
    monkeypatch.setattr(captions, "TABLE_CAPTION_RE", re.compile(
        r"^\s*(?:Table|TABLE)\s+(?P<num>\d+)" + old, re.MULTILINE))
    r = extract_pdf_structured(figure_only)
    assert r["figures"] == [], (
        "with the pre-fix pattern the figures still appeared, so the tests above "
        "are not measuring the caption pattern at all"
    )
