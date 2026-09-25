"""A right-column caption's region must start at the caption, not at the page's
left column -- or the wrong grid is delivered under the caption's label.

``10.1002/pon.2046`` (McLean et al. 2013, Psycho-Oncology 22:28-38), PDF page 8,
rasterized and read (``pdftoppm -png -r 150 -f 8 -l 8``): Table 4, a 6-row
ANCOVA table, sits at the top of the RIGHT column; Figure 2's bar chart, with a
four-entry legend drawn as ruled boxes, sits at the bottom of the LEFT column.

The caption's first line shares its y-row with the left column's first body line
("groups differed on any of the outcome variables at"), 18pt of gutter apart.
``detect._bbox_of_caption_line`` took the whole row, so the caption box ran from
x=58 and the caption-anchored region became the entire page. No region grid
survived, and the only Camelot grid on the page -- the legend, ``EFT PT | EFT CG
| SC PT | SC CG`` -- was paired to the page's only caption and shipped as
"Table 4" (v2.4.144 and 2.4.145-candidate alike). Every printed statistic of the
real table was lost. Reported by a downstream consumer 2026-09-25.

Values are asserted on the STRUCTURED table through ``extract_pdf_structured``,
the shipped path; the same numbers are in the body text, so a whole-document
substring check would pass while the table is still the legend.
"""

from __future__ import annotations

import functools

import pytest

from docpluck.testing.corpus import require_corpus_pdf

PAPER = "vancouver/psychooncology_1.pdf"  # 10.1002/pon.2046


@functools.lru_cache(maxsize=None)
def _tables() -> dict:
    pytest.importorskip("camelot")
    from docpluck.extract_structured import extract_pdf_structured

    tables = extract_pdf_structured(require_corpus_pdf(PAPER).read_bytes())["tables"]
    return {t.get("label"): t for t in tables}


def _rows(table) -> list[list[str]]:
    by_r: dict[int, list[tuple[int, str]]] = {}
    for c in table.get("cells") or []:
        by_r.setdefault(c["r"], []).append((c["c"], (c.get("text") or "").strip()))
    return [[t for _, t in sorted(v)] for _, v in sorted(by_r.items())]


# The six printed rows: F and p for Treatment, F and p for the T1 covariate,
# then Patient status and Sex. Read off the rasterized page.
PRINTED = {
    "RDAS total score": ["0.11", "0.74", "91.08", "<0.0001", "ns", "ns"],
    "BDI prorated": ["0.17", "0.68", "33.62", "<0.0001", "ns", "ns"],
    "BHS prorated": ["0.11", "0.75", "78.35", "<0.0001", "ns", "ns"],
    "RFCS total score": ["0.09", "0.76", "65.41", "<0.0001", "ns", "ns"],
    "CBS1": ["1.48", "0.23", "48.55", "<0.0001", "ns", "ns"],
    "CBS2": ["0.02", "0.87", "12.00", "0.0015", "ns", "ns"],
}


def test_table_4_is_the_ancova_table_not_the_figure_legend():
    t4 = _tables().get("Table 4")
    assert t4 is not None, "Table 4 missing entirely"
    assert t4.get("page") == 8
    rows = {r[0]: r[1:] for r in _rows(t4) if r}
    for label, values in PRINTED.items():
        assert rows.get(label) == values, (label, rows.get(label))


def test_the_figure_legend_is_not_delivered_as_table_4():
    t4 = _tables().get("Table 4")
    assert t4 is not None
    texts = {(c.get("text") or "").strip() for c in t4.get("cells") or []}
    assert not texts & {"EFT PT", "EFT CG", "SC PT", "SC CG"}, texts
