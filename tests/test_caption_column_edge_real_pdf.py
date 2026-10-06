"""Two capture defects that left a table's values under no label, or under the wrong one.

1. A CAPTION IN ONE TEXT COLUMN SHARES ITS y-ROW WITH THE NEIGHBOURING COLUMN.
   `_bbox_of_caption_line` took the row's whole x-extent, so on a two-column page a
   left-column caption's box ran to the right margin. 10.1177/01461672251327169 p15,
   Table 10 (8 coefficient rows x 3 values, page-verified): the region swallowed the
   right column's prose, the grid was rejected as body prose, and the table shipped
   only the word "Measure" -- every value lost. The box now stops where the second
   text block of the row begins (`_neighbour_block_edge`), which is NOT the end of
   the caption's own wrapped line (that crop cost a stat column in 2026-08, J14).
"""

from __future__ import annotations


from docpluck.extract_structured import extract_pdf_structured
from docpluck.tables.detect import _neighbour_block_edge
from docpluck.testing import require_corpus_pdf


def _row(text: str, x0: float, *, size: float = 5.0) -> list[dict]:
    """x-sorted glyph dicts for one printed run, `size` pt wide each, no gaps."""
    return [
        {"text": ch, "x0": x0 + i * size, "x1": x0 + (i + 1) * size}
        for i, ch in enumerate(text)
    ]


def test_neighbour_edge_found_across_a_central_gutter():
    left = _row("Table 10 caption", 60.0)            # ends at x=140
    right = _row("next column prose", 330.0)         # starts at x=330 (page 612 wide)
    assert _neighbour_block_edge(left + right, 0, 612.0) == 330.0


def test_neighbour_edge_ignores_a_gap_outside_the_central_band():
    # A wide gap near the left margin is a tab stop, not a column gutter.
    row = _row("Table 1", 60.0) + _row("Results", 140.0)
    assert _neighbour_block_edge(row, 0, 612.0) is None


def test_neighbour_edge_ignores_a_narrow_word_gap_in_the_centre():
    row = _row("a caption running across the middle of", 150.0)
    assert _neighbour_block_edge(row, 0, 612.0) is None


_IP_T10_ROWS = {
    "Loneliness": [".29***", "−.21***", ".07"],
    "Rumination/brooding": [".22***", "−.10*", ".04"],
    "Depressive symptoms": [".29***", "−.20***", ".07"],
    "Satisfaction with life": ["−.18***", ".24***", ".05"],
    "Subjective happiness": ["−.28***", ".34***", ".10"],
    "Number of confidants": ["−.07", ".15**", ".02"],
}


def _rows_of(table) -> dict[str, list[str]]:
    by_row: dict[int, list] = {}
    for c in table.get("cells") or []:
        by_row.setdefault(c["r"], []).append(c)
    out = {}
    for cells in by_row.values():
        cells.sort(key=lambda c: c["c"])
        texts = [c["text"] for c in cells]
        out[texts[0]] = texts[1:]
    return out


def test_ip_feldman_table10_keeps_its_coefficients():
    """Values read off the printed page (p15, 300 dpi), minus signs included."""
    pdf = require_corpus_pdf("apa/ip_feldman_2025_pspb.pdf")
    result = extract_pdf_structured(pdf.read_bytes())
    t10 = next((t for t in result["tables"] if t.get("label") == "Table 10"), None)
    assert t10 is not None, "Table 10 caption not detected"
    rows = _rows_of(t10)
    for measure, values in _IP_T10_ROWS.items():
        assert rows.get(measure) == values, (
            f"Table 10 row {measure!r}: got {rows.get(measure)!r}, printed {values!r}"
        )
