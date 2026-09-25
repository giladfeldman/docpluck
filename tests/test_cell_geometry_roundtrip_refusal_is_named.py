"""A cell-geometry round-trip refusal must reach the artifact BY NAME.

Why this file exists (rule 40, v2.4.144 review, 2026-09-24).
`camelot_cell_bboxes` refuses a table whose sampled cells do not contain their
own text, returning ``roundtrip_failed:<score><<threshold>``. That reason lands
in two places a consumer reads: the table's ``cell_geometry`` field, and the
``camelot_cell_geometry_refused`` fallback's detail. Nothing asserted either.
``tests/test_cell_geometry_roundtrip.py`` proves the guard REFUSES under a broken
transform, but only at the function boundary and without looking at the reason --
so a refusal that stopped being named, or stopped reaching the artifact, would
leave every cell at ``ZERO_BBOX`` with no explanation.

This is a refusal, not an exception, so the forced failure is a broken transform
rather than a raise: `_recovered_text` returns nothing, as it would if every cell
box pointed at empty page. Every table must then refuse with this token.

THE CONTROL IS PAPER-SPECIFIC ON PURPOSE. A round-trip refusal is a legitimate
outcome on a real paper (measured 2026-09-25: apa/chan_feldman_2025_cogemo.pdf
refuses one candidate with ``roundtrip_failed:0.50<0.60`` on the healthy path),
so "the healthy path never emits it" is not a general law. On
apa/efendic_2022_affect.pdf all 5 tables verify and nothing is refused; if that
changes, a table on a paper whose geometry was fully verified has started
refusing, which is worth a look before relaxing the control.
"""

import os

import pytest

import docpluck.tables.cell_geometry as cg
from docpluck.extract_structured import extract_pdf_structured
from docpluck.testing import require_corpus_pdf

pytest.importorskip("camelot", reason="camelot not installed (pip install docpluck[all])")

_PAPER = "apa/efendic_2022_affect.pdf"


@pytest.fixture(scope="module")
def paper_bytes() -> bytes:
    # require_, not corpus_pdf: a paper this gate needs and cannot read is a FAILURE.
    return require_corpus_pdf(_PAPER).read_bytes()


@pytest.fixture(autouse=True)
def _camelot_must_be_enabled(monkeypatch):
    """Without Camelot there is no cell geometry and every assertion is vacuous."""
    monkeypatch.delenv("DOCPLUCK_DISABLE_CAMELOT", raising=False)
    assert os.environ.get("DOCPLUCK_DISABLE_CAMELOT", "0") != "1"


def _camelot_geometry(result) -> list[str]:
    # `no_cells` / `whitespace_native` tables never went through the round-trip.
    return [
        str(t.get("cell_geometry"))
        for t in result["tables"]
        if t.get("camelot_flavor") is not None
    ]


def test_control_real_geometry_verifies_and_nothing_is_refused(paper_bytes):
    result = extract_pdf_structured(paper_bytes)
    geo = _camelot_geometry(result)
    assert geo, "no Camelot tables: the round-trip was never reached"
    assert all(g.startswith("verified:") for g in geo), geo
    assert "roundtrip_failed:" not in " ".join(geo), geo
    assert "camelot_cell_geometry_refused" not in result["fallbacks"], result["fallbacks"]


def test_a_failed_roundtrip_is_named_on_the_table_and_in_fallbacks(paper_bytes, monkeypatch):
    monkeypatch.setattr(cg, "_recovered_text", lambda _layout, _page, _bbox: "")
    result = extract_pdf_structured(paper_bytes)
    geo = _camelot_geometry(result)

    assert geo, "no Camelot tables: the round-trip was never reached"
    unnamed = [g for g in geo if not g.startswith("roundtrip_failed:")]
    assert not unnamed, (
        "geometry that cannot be recovered from the page was not refused by name; "
        f"a consumer sees zero boxes with no reason. cell_geometry={geo}"
    )
    details = result["fallback_details"].get("camelot_cell_geometry_refused") or {}
    assert any(k.startswith("roundtrip_failed:") for k in details), (
        "the refusal did not reach the fallback record. "
        f"fallback_details={result['fallback_details']}"
    )
    for t in result["tables"]:
        if t.get("camelot_flavor") is not None:
            assert all(c["bbox"] == cg.ZERO_BBOX for c in t.get("cells") or []), (
                "a refused table still shipped non-zero cell boxes"
            )
