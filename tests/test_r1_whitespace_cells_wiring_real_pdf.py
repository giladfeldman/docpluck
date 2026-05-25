"""
R1 / B1 wiring regression test (post-v2.4.72 repair, 2026-05-25).

The v2.4.72 cycle wired `docpluck.tables.whitespace.whitespace_cells` as the
caption-anchored fallback when Camelot returns no cells (see
`docpluck/extract_structured.py` §A R1 block). A subsequent AI-gold sweep
(R1 verification, 2026-05-25) discovered the wiring was structurally dead:
`_region_for_caption` returned None in 100% of B1 unmatched-caption cases
because `_bbox_of_caption_line` used first-20-char prefix matching against
joined layout chars — but joined layout chars drop inter-word whitespace
and preserve raw PDF ligatures (e.g. `'Table5.Reﬂection…'`), so the prefix
`'Table 5. Reflection'` never matched.

This regression test asserts the wiring is now LIVE end-to-end: the
helper resolves a region AND `whitespace_cells` yields a non-empty cell
grid on at least one well-behaved fixture from the B1 corpus.

Real-PDF (rule 0d) + structural-signature general fix (rule 16): the test
fails if the wiring goes dead again for any reason (ligature changes,
caption-line shape regression, region-detect false-empty), not just on
this specific paper.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from docpluck.extract_layout import extract_pdf_layout
from docpluck.tables.captions import find_caption_matches
from docpluck.tables.detect import _region_for_caption
from docpluck.tables.whitespace import whitespace_cells


# Fixtures live in the (private) PDFextractor sibling repo; tests skip
# gracefully when the corpus isn't mounted.
_CORPUS = Path(__file__).resolve().parents[2] / "PDFextractor" / "test-pdfs" / "apa"

# The two papers the R1 sweep confirmed should yield ≥1 cell post-repair:
# chan_feldman (8 caps → 72 cells) and maier (11 caps → 100 cells).
B1_LIVE_FIXTURES = [
    ("chan_feldman_2025_cogemo.pdf", 8, 50),  # min 50 cells (actual: 72)
    ("maier_2023_collabra.pdf", 11, 50),      # min 50 cells (actual: 100)
]


@pytest.mark.parametrize("filename, min_regions, min_cells", B1_LIVE_FIXTURES)
def test_b1_whitespace_cells_wiring_live(filename: str, min_regions: int, min_cells: int):
    """The R1/B1 fallback must yield ≥1 region and ≥min_cells cells on each B1 fixture.

    If this test starts failing with `regions=0`, _bbox_of_caption_line has
    regressed — likely a ligature/whitespace normalization change. If
    `regions > 0` but `cells=0`, the whitespace_cells thresholds have shifted
    or _region_for_caption is yielding too-narrow bboxes.
    """
    pdf = _CORPUS / filename
    if not pdf.exists():
        pytest.skip(f"corpus fixture missing: {pdf}")

    layout = extract_pdf_layout(pdf.read_bytes())
    caps = [c for c in find_caption_matches(layout.raw_text, list(layout.page_offsets)) if c.kind == "table"]
    assert len(caps) >= min_regions, (
        f"expected ≥{min_regions} table captions in {filename}, got {len(caps)}"
    )

    regions_resolved = 0
    cells_total = 0
    for cap in caps:
        region = _region_for_caption(layout, cap)
        if region is None:
            continue
        regions_resolved += 1
        cells = whitespace_cells(layout, region=region)
        cells_total += len(cells)

    assert regions_resolved >= min_regions, (
        f"R1 dead-wiring regression: only {regions_resolved}/{len(caps)} captions "
        f"resolved to a region in {filename} (expected ≥{min_regions}). "
        f"Check docpluck/tables/detect.py::_bbox_of_caption_line."
    )
    assert cells_total >= min_cells, (
        f"R1 fallback yielded only {cells_total} cells across {regions_resolved} "
        f"regions in {filename} (expected ≥{min_cells}). Check "
        f"whitespace_cells thresholds or region bbox sizing."
    )


def test_bbox_of_caption_line_normalizes_ligatures_and_whitespace():
    """Unit test for the normalization fix that made _bbox_of_caption_line robust.

    Synthetic fixture: a single y-row containing 'Table1.Reﬂection' (raw PDF
    ligature, no inter-word space) must match a caption with line_text
    'Table 1. Reflection of...' (de-ligatured, space-preserving text channel).
    """
    from docpluck.tables.captions import CaptionMatch
    from docpluck.tables.detect import _bbox_of_caption_line

    # Construct one row of "chars" objects (mirroring pdfplumber char dicts).
    row_text = "Table1.Reﬂectionpromptsthatparticipants"
    x = 56.0
    row_chars: list[dict] = []
    for ch in row_text:
        row_chars.append({"text": ch, "x0": x, "x1": x + 5, "top": 56.0, "bottom": 66.0})
        x += 5

    class FakePage:
        pass

    FakePage.chars = tuple(row_chars)
    FakePage.width = 612.0

    cap = CaptionMatch(
        kind="table",
        number=1,
        label="Table 1",
        page=5,
        char_start=0,
        char_end=40,
        line_text="Table 1. Reflection prompts that participants",
    )

    bbox = _bbox_of_caption_line(FakePage(), cap)
    assert bbox is not None, "normalized match should succeed despite ligature + space mismatch"
    # Bbox should span the row.
    x0, top, x1, bottom = bbox
    assert top == 56.0
    assert bottom == 66.0
    assert x0 == 56.0
    assert x1 > x0
