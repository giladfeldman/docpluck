"""maier Table 7 TEXT-LOSS: a prose grid outranks the correct data (2026-08-04).

`_pick_better_table` chooses between a caption's region-driven and auto-detected
candidates on STRUCTURAL SHAPE alone — column count, then populated-cell count. Nothing
checks whether the winning grid's CONTENT is plausibly the caption's table.

maier Table 7 ("Perceived Impact (Extension): Descriptives") is a 3x5 descriptives grid
in the AI gold. With `DOCPLUCK_DISABLE_CAMELOT=1` the raw_text channel captures it
gold-exact (all 15 values: 3.47 [1.23] (170) … 3.12 [1.34] (1004)). With Camelot
enabled, a 4x2 grid of DISCUSSION PROSE ("Following the analyses conducted in Study 1 of
Small / et al. (2007), we carried out a 2 (Explicit Learning) × 2 …") wins the shape
comparison and replaces it, so the rendered .md shows `### Table 7` with its caption and
ZERO data values.

Traced: the winning grid is `camelot_t18` — the LEGACY AUTO-DETECT path. The
content-plausibility guard is applied only to region-path grids
(`if id_prefix.startswith("region")` in camelot_extract), and feeding this exact grid to
`_whitespace_grid_is_clean` returns False — the guard WOULD have caught it, auto-detect
just never consults it. Widening that gate wholesale was already tried and rejected
(it discarded legitimate-but-imperfect auto-detect grids, cog_emo T5/6/7), so the fix
belongs at SELECTION time as a relative judgement between candidates.

Full analysis + candidate fix directions:
``docs/FINDINGS_2026-08-04_pick_better_table_ignores_content.md``.

This test is `xfail(strict)`: it pins REAL, gold-verified TEXT-LOSS that is not yet
safely fixable (the fix is a pairing-class change, and this project's history shows
global pairing changes are net-harmful unless gated by a guard-diff + AI-gold sweep).
**Do NOT weaken the assertion to make it pass**, and do not delete it — a correct fix
XPASSes loudly and should become a plain assert then.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from docpluck.extract_structured import extract_pdf_structured

TEST_PDFS = Path(__file__).resolve().parents[1].parent / "PDFextractor" / "test-pdfs"

# Values straight from the AI gold (article-finder `reading` view) — the ground truth.
# Row 1 of the grid; enough to prove the table's data reached the output at all.
_GOLD_T7_VALUES = ["3.47", "2.91", "2.94", "3.11"]


@pytest.mark.skipif(
    os.environ.get("DOCPLUCK_DISABLE_CAMELOT", "0") == "1",
    reason="The defect only manifests with Camelot enabled (auto-detect supplies the "
    "prose grid that outranks the correct raw_text data).",
)
@pytest.mark.xfail(
    strict=True,
    reason=(
        "REAL gold-verified TEXT-LOSS (2026-08-04). maier Table 7's 3x5 descriptives "
        "grid is captured correctly by raw_text but replaced by a 4x2 Discussion-prose "
        "grid from the auto-detect path, because _pick_better_table selects on shape "
        "only and never checks content plausibility. Fix is a pairing-class change "
        "requiring a 101-PDF guard-diff + AI-gold canary sweep — see "
        "docs/FINDINGS_2026-08-04_pick_better_table_ignores_content.md. Do NOT weaken "
        "this assertion. strict=True: a correct fix XPASSes loudly."
    ),
)
def test_maier_table7_keeps_its_data():
    """Table 7 must carry its own descriptives, not Discussion prose."""
    pdf = TEST_PDFS / "apa" / "maier_2023_collabra.pdf"
    if not pdf.exists():
        pytest.skip(f"fixture missing: {pdf}")

    result = extract_pdf_structured(pdf.read_bytes())
    t7 = next((t for t in result["tables"] if t.get("label") == "Table 7"), None)
    assert t7 is not None, "Table 7 caption not detected at all"

    haystack = (t7.get("raw_text") or "") + " ".join(
        (c.get("text") or "") for c in (t7.get("cells") or [])
    )
    missing = [v for v in _GOLD_T7_VALUES if v not in haystack]
    assert not missing, (
        f"Table 7 lost gold values {missing}. Content is: {haystack[:200]!r}"
    )


def test_maier_table7_data_is_recoverable_without_camelot():
    """Control: the raw_text channel DOES capture Table 7 correctly.

    This is what makes the defect a genuine selection bug rather than a capture
    failure — the correct data exists and is thrown away. Plain assert (not xfail):
    if this ever breaks, the underlying capture regressed and the diagnosis above
    no longer holds.
    """
    pdf = TEST_PDFS / "apa" / "maier_2023_collabra.pdf"
    if not pdf.exists():
        pytest.skip(f"fixture missing: {pdf}")

    prior = os.environ.get("DOCPLUCK_DISABLE_CAMELOT")
    os.environ["DOCPLUCK_DISABLE_CAMELOT"] = "1"
    try:
        result = extract_pdf_structured(pdf.read_bytes())
    finally:
        if prior is None:
            os.environ.pop("DOCPLUCK_DISABLE_CAMELOT", None)
        else:
            os.environ["DOCPLUCK_DISABLE_CAMELOT"] = prior

    t7 = next((t for t in result["tables"] if t.get("label") == "Table 7"), None)
    assert t7 is not None, "Table 7 caption not detected"
    raw = t7.get("raw_text") or ""
    missing = [v for v in _GOLD_T7_VALUES if v not in raw]
    assert not missing, f"raw_text channel no longer captures Table 7: missing {missing}"
