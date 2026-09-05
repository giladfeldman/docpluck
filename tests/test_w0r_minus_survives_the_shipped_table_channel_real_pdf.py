r"""W0r end to end: the minus sign must survive the PIPELINE, not just the repair function.

Written 2026-09-05. Watched fail by neutralising the repair in-process (see
`test_the_guard_actually_bites_end_to_end`), which is the only honest red for a test
added after its fix.

WHY THIS FILE EXISTS, AND WHY THE EXISTING 14 TESTS CANNOT REPLACE IT.
`tests/test_table_channel_minus_sign_destruction.py` pins W0r with 14 tests. Every one
of them calls `clean_cell_text` / `recover_unmapped_glyph_minus` on a hand-built string.
None opens a PDF.

That matters more here than it usually would, because of what the original defect WAS.
The repair was not wrong. `cell_cleaning` held a correct rule, keyed on the literal
`(cid:0)` that pdfminer.six emits for an unmappable glyph. Camelot 2.0.0 stopped using
pdfminer.six -- it reads text through `playa.miner`, whose `Font.decode` falls back to an
identity map, so the same character code arrives as a raw NUL. **The rule kept passing
its unit tests while the pipeline stopped delivering the input it was keyed on**, and
`10.1016/j.joep.2020.102350` p2 shipped `Cramer's V = 0.067 [\x00 0.108, 0.218]` -- an
interval every consumer reads as EXCLUDING zero where the page prints one that SPANS it.

A unit test on the repair function is structurally incapable of catching that. It is the
same class as the two `A3a`/`_column_runs` incidents this repo already records: the
instrument stayed green because it never touched the thing that broke. So the pin has to
run the shipped path -- Camelot backend, `clean_cell_text`, `cells[]`, `raw_text` -- and
assert on what a consumer actually receives.

COST: ~17 s per extraction here, two extractions.
Source page rasterized and read on 2026-09-02 (W-0015); the values below are what the
page prints, not what another parser reports.
"""

from __future__ import annotations

import pytest

from tests.conftest import pdf_available, pdf_path

_PAPER = "10.1016__j.joep.2020.102350.pdf"

pytestmark = pytest.mark.skipif(
    not pdf_available("articlerepo", _PAPER),
    reason=(
        f"SKIPPED, NOT PASSED: {_PAPER} is not in the article repository. "
        "Fetch it through article-finder; never copy it into this repo."
    ),
)


def _shipped_table_text(raw: bytes) -> tuple[str, int]:
    """(everything a consumer reads out of the table channel, table count)."""
    from docpluck import extract_pdf_structured

    tables = extract_pdf_structured(raw)["tables"]
    parts = []
    for t in tables:
        parts.extend((c.get("text") or "") for c in (t.get("cells") or []))
        parts.append(t.get("raw_text") or "")
    return "\n".join(parts), len(tables)


@pytest.fixture(scope="module")
def shipped() -> tuple[str, int]:
    raw = open(pdf_path("articlerepo", _PAPER), "rb").read()
    text, n = _shipped_table_text(raw)
    # INPUT CONTROL. Camelot returning nothing would satisfy every "no corrupt marker
    # survives" assertion below while proving nothing at all -- a green from an empty
    # input is the false green this repo's rules single out by name.
    assert n > 0, "no tables extracted -- this run cannot speak to the table channel"
    assert len(text) > 2000, f"table channel yielded only {len(text)} chars -- too thin to trust"
    return text, n


def test_the_published_interval_spans_zero_in_the_shipped_cells(shipped):
    """p2 Table 1 prints `Cramer's V = 0.067 [-0.108, 0.218]`."""
    text, _ = shipped
    assert "[-0.108," in text, (
        "the lower bound lost its minus in the shipped table channel: an interval the "
        "page prints as SPANNING zero now reads as EXCLUDING it."
    )


def test_no_unmapped_glyph_marker_reaches_a_consumer(shipped):
    """Both spellings. A rule keyed on one library's spelling dies at the next bump."""
    text, _ = shipped
    assert text.count("\x00") == 0, f"{text.count(chr(0))} raw NULs (playa spelling) reached cells[]"
    assert "(cid:" not in text, "a `(cid:N)` marker (pdfminer spelling) reached cells[]"


def test_the_signed_row_keeps_its_signs(shipped):
    """p4 Table 2 prints `199 -1 -31 -30 213 14 31 17` -- its own two-sided control.

    The row carries three signed and three unsigned values, so a run that destroyed
    signs wholesale and one that merely failed to find this table look different.
    """
    text, _ = shipped
    negatives = sum(1 for tok in text.split() if tok.startswith("-") and tok[1:2].isdigit())
    assert negatives >= 10, (
        f"only {negatives} negative numbers survived the table channel; before the fix "
        "this whole class was destroyed."
    )


def test_the_guard_actually_bites_end_to_end():
    """MUTATION CHECK -- the red this file was watched fail on.

    Neutralising `recover_unmapped_glyph_minus` to the identity must break
    `test_the_published_interval_spans_zero_in_the_shipped_cells`. If it does not, the
    repair is not what is keeping that assertion green and this file is measuring
    something else.
    """
    import docpluck.tables.cell_cleaning as CC

    raw = open(pdf_path("articlerepo", _PAPER), "rb").read()
    original = CC.recover_unmapped_glyph_minus
    try:
        CC.recover_unmapped_glyph_minus = lambda s, *a, **k: s
        text, n = _shipped_table_text(raw)
    finally:
        CC.recover_unmapped_glyph_minus = original

    assert n > 0, "mutation run extracted no tables -- it proves nothing"
    assert "[-0.108," not in text, (
        "the interval kept its minus with the repair disabled, so this file's green is "
        "not evidence that the repair works. Find what is really producing it."
    )
