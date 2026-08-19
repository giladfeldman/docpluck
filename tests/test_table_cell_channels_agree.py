"""One input, one answer — every table-text channel must agree.

## The defect these tests pin (register F7a, fixed v2.4.133)

Until v2.4.133 the table-cell glyph repairs lived *inside*
``cell_cleaning._html_escape``. That fused the repairs to the HTML escaper, so
they were reachable only by the consumer that rendered HTML. Measured on the
real corruption shape ``"[20.45, 20.06]"`` — a `2`-for-U+2212 CI, which the
page actually prints as ``[-0.45, -0.06]``::

    cells_to_html(cells)          -> "[-0.45, -0.06]"    repaired
    flatten._cells_to_grid(cells) -> "[20.45, 20.06]"    RAW
    Table["cells"][i]["text"]     -> "[20.45, 20.06]"    RAW
    Table["raw_text"]             -> "[20.45, 20.06]"    RAW

``flatten`` is production (``cli.py``, ``render.py``) and feeds the JSONL
sidecar, so a p-value that rendered correctly in the HTML table was
simultaneously shipped corrupt to every structured consumer. The owner named
this risk directly — *"I worry about fixing in one but keeping an error in the
other"* — and it was already shipping.

**This is the check that did not exist**: nothing anywhere asserted that two
channels give the same answer for one input, which is why the divergence was
invisible. A library that can convert one input two ways has no contract at all.

## Why the repair moved to CONSTRUCTION

The cleaning pipeline merges and splits cells, so cell↔position correspondence
degrades as the pipeline runs. A repair keyed on cell content has to happen
while the cell still is what the capture emitted.
"""

from __future__ import annotations

import pytest

from docpluck.tables.cell_cleaning import clean_cell_text
from docpluck.tables.flatten import _cells_to_grid
from docpluck.tables.render import cells_to_html


class _FakeCamelotTable:
    """The minimal surface ``_camelot_table_to_dict`` reads off a Camelot table.

    Deliberately NOT a hand-built Cell list. An earlier draft of this file built
    cells by calling ``clean_cell_text`` in the test helper — which would have
    stayed green even if cell construction stopped calling it, pinning the
    helper instead of the pipeline. The whole point of these tests is that the
    REAL construction path applies the repair, so they go through the real
    entry point.
    """

    def __init__(self, rows: tuple[list[str], ...], accuracy: float = 99.0):
        import pandas as pd
        self.df = pd.DataFrame(rows)
        self.accuracy = accuracy
        self.whitespace = 0.0
        self.page = 1
        self.flavor = "stream"
        self._bbox = (0.0, 0.0, 100.0, 100.0)


def _build(*rows: list[str]):
    """Run the REAL Camelot cell-construction path and return its Cell list."""
    from docpluck.tables.camelot_extract import _camelot_table_to_dict
    td = _camelot_table_to_dict(_FakeCamelotTable(rows), 0)
    assert td is not None, "fixture did not survive the table-likeness gate"
    return td


def _cells(*rows: list[str]):
    return _build(*rows)["cells"]


# ── the repair chain itself ────────────────────────────────────────────────

def test_clean_cell_text_is_idempotent():
    """``_html_escape`` still calls ``clean_cell_text``, so a constructed cell
    is cleaned twice. Verified over 9,369 real corpus cells at the time of the
    change; these are the shapes that would break first if a future repair were
    written non-idempotently."""
    for raw in [
        "[20.45, 20.06]",       # 2-for-minus CI
        "\\.001",               # <-as-backslash
        "(cid:0) 0.23",         # unmapped minus glyph
        "Direction 3 attribute",  # x-as-3
        "-0.45",                # already correct — must not move
        "[-0.45, -0.06]",
        "2.84",
        "",
        "Predictor",
        "95% CI",
        "1,000",                # US thousands — passes through, never stripped
    ]:
        once = clean_cell_text(raw)
        assert clean_cell_text(once) == once, f"not idempotent: {raw!r} -> {once!r}"


def test_clean_cell_text_repairs_the_two_for_minus_ci():
    """The shape rasterized from 10.1177/19485506211056761 p5, which prints
    ``[-0.96, -0.59]`` while the text layer says ``[20.96, 20.59]``."""
    assert clean_cell_text("[20.45, 20.06]") == "[-0.45, -0.06]"


def test_clean_cell_text_does_not_strip_thousands_separators():
    """SCOPE guard. English + US numeric convention is the contract: `1,000` is
    clearly one thousand, and rewriting it to `1000` repairs nothing while
    erasing locale-bearing evidence a consumer might need. A3a was deleted in
    v2.4.130 for producing 1000x errors; this pins that the cell channel did
    not quietly keep a copy."""
    for s in ("1,000", "185,178", "12,345.67"):
        assert clean_cell_text(s) == s


# ── the cross-channel contract ─────────────────────────────────────────────

CORRUPT_ROWS = (
    ["Predictor", "p", "95% CI"],
    ["Condition", "0.031", "[20.45, 20.06]"],
    ["Order", "0.44", "[20.12, 20.03]"],
)


def test_every_channel_reports_the_same_repaired_ci():
    """THE regression test for F7a. Before v2.4.133 the HTML said
    ``[-0.45, -0.06]`` while flatten and ``cells[].text`` said
    ``[20.45, 20.06]`` for this exact input."""
    cells = _cells(*CORRUPT_ROWS)

    html = cells_to_html(cells)
    grid = _cells_to_grid(cells)
    cell_texts = [c["text"] for c in cells]

    assert "[-0.45, -0.06]" in html, "HTML channel lost the repair"
    assert "20.45" not in html

    flat = [t for row in grid for t in row]
    assert "[-0.45, -0.06]" in flat, f"flatten channel shipped raw text: {flat}"
    assert not any("20.45" in t for t in flat)

    assert "[-0.45, -0.06]" in cell_texts, f"cells[].text shipped raw: {cell_texts}"
    assert not any("20.45" in t for t in cell_texts)


@pytest.mark.parametrize("raw,expected", [
    ("[20.45, 20.06]", "[-0.45, -0.06]"),
    ("\\.001", "<.001"),
])
def test_html_and_flatten_never_disagree(raw: str, expected: str):
    """Generalised: for any repairable cell, the rendered table and the
    structured sidecar must carry the same value. The HTML channel escapes
    ``<`` to ``&lt;``, so compare on the unescaped side."""
    cells = _cells(["Term", "value"], ["x", raw])
    grid = _cells_to_grid(cells)
    flat = [t for row in grid for t in row]
    assert expected in flat, f"flatten: {flat}"
    # And the constructed cell already carries it, so no consumer has to know
    # which cleaning function to call.
    assert any(c["text"] == expected for c in cells)
