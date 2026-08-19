"""The corpus pipeline must run the symbol-font scan, not just the structured one.

## The defect, found by an external consult on 2026-08-19

`docs/OVERHAUL_REGISTER.md` §H4 states, of the α-as-`a` / `=`-as-`5` corruption class:

    every affected document now reports `symbol_font_greek_corruption_detected` to its
    consumer instead of shipping `a5(.93)` in silence

That was **false for `batch.py`**, which owns the corpus pipeline and writes the per-file `.json`
sidecar. `detect_symbol_font_corruption` was called from exactly one place —
`extract_structured.extract_pdf_structured` — and `grep -c detect_symbol_font_corruption
docpluck/batch.py` returned **0**. A document run through the corpus pipeline shipped `a5(.93)` in
exactly the silence the register said had been eliminated.

**This is the same shape as the v2.4.134 telemetry defect one release earlier** (see
`test_batch_sidecar_carries_fallbacks.py`): a capability wired into one caller and claimed for all
of them. The layout was ALREADY materialised in `batch.py` for `dropped_minus_layout=`, so the scan
cost nothing extra — it had simply never been connected.

## Why this test patches the detector rather than using a corrupt paper

The defect was **"never called"**, not "detector broken". A test that needs a specific corrupt PDF
would skip on any machine without it, and a skipped test is a coverage hole wearing a green tick
(L-045). Patching the detector to return a known result proves the thing that was actually missing:
that `batch.py` invokes it and that the result reaches the consumer's sidecar.

The detector's own correctness is pinned separately by
`tests/test_symbol_font_detector_false_positives.py`.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from docpluck import batch as B


@pytest.fixture
def fake_pdf(tmp_path: Path) -> Path:
    """A file the pipeline will attempt; extraction is patched, so bytes are inert."""
    p = tmp_path / "paper.pdf"
    p.write_bytes(b"%PDF-1.4\n%fake\n")
    return p


def test_batch_calls_the_symbol_font_scan_and_the_key_reaches_the_sidecar(
    fake_pdf: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    calls: list[object] = []

    class _FakeLayout:
        pages = ()
        raw_text = "Cronbach a5(.93) for the scale."
        page_offsets = ()

    def _fake_extract_pdf_file(path, **kwargs):
        return "Cronbach a5(.93) for the scale.", "pdftotext"

    def _fake_layout(_bytes):
        return _FakeLayout()

    def _fake_detect(layout):
        calls.append(layout)
        return {"AdvPS7DA6": 13}

    monkeypatch.setattr(B, "extract_pdf_file", _fake_extract_pdf_file)
    monkeypatch.setattr(
        "docpluck.extract_layout.extract_pdf_layout", _fake_layout, raising=True
    )
    monkeypatch.setattr(
        "docpluck.extract_layout.detect_symbol_font_corruption", _fake_detect,
        raising=True,
    )

    out = tmp_path / "out"
    report = B.extract_to_dir(pdf_paths=[fake_pdf], out_dir=out)

    assert calls, (
        "batch.py never called detect_symbol_font_corruption — the corpus pipeline "
        "is shipping a5(.93) in the silence register H4 says was eliminated"
    )

    result = report.results[0]
    assert result.fallbacks.get("symbol_font_greek_corruption_detected") == 13, (
        f"the scan ran but its result did not reach the file result: {result.fallbacks}"
    )
    assert (
        result.fallback_details.get("symbol_font_greek_corruption_detected", {}).get(
            "AdvPS7DA6"
        )
        == 13
    ), "the FONT NAME is what tells a consumer which document to distrust"

    # And on disk — a field the sidecar filters out is invisible to a consumer.
    sidecars = list(out.glob("*.json"))
    assert sidecars, "no sidecar written"
    payload = json.loads(sidecars[0].read_text(encoding="utf-8"))
    blob = json.dumps(payload)
    assert "symbol_font_greek_corruption_detected" in blob, (
        "the scan result never reached the artifact a consumer reads"
    )


def test_the_two_channels_agree_on_the_COUNT_not_merely_the_key(
    fake_pdf: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """`extract_pdf_structured` records once per corrupt glyph. So must batch.

    A channel that records the key once while the other records it thirteen times
    gives two consumers two different answers about the same document, which is the
    ONE CONCEPT, ONE TABLE rule stated for telemetry.
    """

    class _FakeLayout:
        pages = ()
        raw_text = ""
        page_offsets = ()

    monkeypatch.setattr(
        B, "extract_pdf_file", lambda path, **kw: ("text", "pdftotext")
    )
    monkeypatch.setattr(
        "docpluck.extract_layout.extract_pdf_layout", lambda _b: _FakeLayout(),
        raising=True,
    )
    monkeypatch.setattr(
        "docpluck.extract_layout.detect_symbol_font_corruption",
        lambda layout: {"AdvPS7DA6": 3, "AdvP4C4E74": 2},
        raising=True,
    )

    report = B.extract_to_dir(pdf_paths=[fake_pdf], out_dir=tmp_path / "o")
    fb = report.results[0].fallbacks
    assert fb.get("symbol_font_greek_corruption_detected") == 5, (
        f"expected 3 + 2 glyph events, got {fb}"
    )
