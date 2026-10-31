"""Regression guard for the 13 canary findings on 10.1177/01461672251327169
(audited 2026-10-30, each checked against the rasterized page).

One structured extraction and one render, shared by every test here.
"""

from __future__ import annotations

import re

import pytest

from docpluck.extract_structured import extract_pdf_structured
from docpluck.render import render_pdf_to_markdown
from docpluck.testing import require_corpus_pdf

_PAPER = "apa/ip_feldman_2025_pspb.pdf"


@pytest.fixture(scope="module")
def tables():
    pdf = require_corpus_pdf(_PAPER).read_bytes()
    return {t["label"]: t for t in extract_pdf_structured(pdf)["tables"]}


@pytest.fixture(scope="module")
def md():
    pdf = require_corpus_pdf(_PAPER).read_bytes()
    out = render_pdf_to_markdown(pdf)
    return out if isinstance(out, str) else out[0]


def _cells(t) -> list[str]:
    return [c.get("text") or "" for c in t.get("cells") or []]


def _n_rows(t) -> int:
    return 1 + max((c["r"] for c in t.get("cells") or []), default=-1)


def _body(md: str) -> str:
    """The render with every ``### Table N`` block cut out."""
    return re.sub(r"^### Table \d+\n.*?(?=^## |^### (?!Table))", "", md, flags=re.M | re.S)


def _block(md: str, label: str) -> str:
    m = re.search(rf"^### Table {label}\n.*?(?=^## |^### )", md, flags=re.M | re.S)
    assert m, f"no Table {label} block"
    return m.group(0)


def test_every_table_is_a_grid(tables):
    for n in range(1, 11):
        assert tables[f"Table {n}"].get("content_status") == "cells", n


def test_table2_holds_both_printed_panels(tables):
    """p4: the hypotheses table continues below a second rule; the region
    stopped at the first panel."""
    t = tables["Table 2"]
    assert _n_rows(t) >= 40
    assert any("negatively associated with subjective happiness" in c for c in _cells(t))


def test_table4_side_by_side_columns_keep_page_order(tables):
    cells = _cells(tables["Table 4"])
    assert any(
        "IV1: estimation of positive emotional events IV1: estimation of negative emotional events" in c
        for c in cells
    )
    assert not any("eventsIV1" in c for c in cells)


def test_table7_column_labels_are_one_header_row(md):
    head = _block(md, "7")
    head = head[head.index("<thead>"):head.index("</thead>")]
    assert "Actual<br>intensity<br>average" in head
    assert "Experiences" in head


def test_headings_set_in_the_heading_style_are_headings(md):
    assert re.search(r"^### Data Analysis Strategy$", md, flags=re.M)
    # p8: set in the heading face one size smaller (11.6 pt under 14 pt), so
    # one level below (second canary audit, 2026-10-31; page checked at 200 dpi).
    for h in ("Replication Measures", "Extension Measures"):
        assert re.search(rf"^#### {h}$", md, flags=re.M), h


def test_a_word_attached_footnote_mark_is_marked(md):
    assert "positive emotions,^1 and" in md


def test_a_digit_printed_inline_in_a_reference_survives(md):
    assert "Registered report stage 1 manuscript template" in md


def test_table_text_copies_are_out_of_the_body(md):
    body = _body(md)
    for line in (
        "Negative indicators--higher well-being",
        "Participants were asked to make estimations of U.S. American student",
        "Replication: Emotional prevalence and emotional intensity in self were combined",
        "[-0.01, 0.16] [0.04, 0.20]",
        "4--Intensity estimates of negative emotions (extension)",
    ):
        assert line not in body, line


def test_table2_footnotes_move_into_its_block(md):
    assert "The target article sometimes shifts from referring" in _block(md, "2")
    assert "The target article sometimes shifts from referring" not in _body(md)


# ---- second canary audit, 2026-10-31 (each checked on the rasterized page) ----

def test_table6_target_article_rows_keep_their_label_in_the_stub(tables):
    """p11: the label runs from the stub across the empty prevalence column;
    Camelot put it under that column and left the stub empty."""
    t = tables["Table 6"]
    by_rc = {(c["r"], c["c"]): c.get("text") or "" for c in t["cells"]}
    for label in ("Overall negative: target article (Study 3)",
                  "Overall positive: target article (Study 3)"):
        at = [rc for rc, v in by_rc.items() if v == label]
        assert at and all(c == 0 for _, c in at), (label, at)


def test_table2_panel_label_is_not_folded_into_the_no_column(md):
    head = _block(md, "2")
    head = head[head.index("<thead>"):head.index("</thead>")]
    assert "estimations<br>No" not in head
    assert "Replication: prevalence estimations" in head


def test_significance_legends_keep_their_first_mark(md):
    assert not re.search(r"(?m)^\*\n", md)
    assert md.count("*p < .05. **p < .01. ***p < .001.") >= 3
