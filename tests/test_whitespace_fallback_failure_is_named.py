"""A crash in the caption-anchored whitespace fallback must NAME itself in the artifact.

Why this file exists (rule 40, v2.4.144 review, 2026-09-24). `extract_structured`'s
§A R1 block runs `whitespace_cells` for every caption Camelot left unmatched, and
catches two kinds of exception so a working extraction is never lost:

* setup -- the lazy imports / layout parse fail: ``whitespace_setup_failed:<Exc>``
  in ``method`` plus the ``whitespace_cells_setup_exception`` fallback;
* per region -- ``_region_for_caption`` or ``whitespace_cells`` raises on one
  caption: ``whitespace_region_failed:<Exc>`` plus
  ``whitespace_cells_region_exception``.

Both tokens were recorded and NOTHING asserted them. The loss they name is
invisible otherwise: the caption still falls through to the cell-less isolated
table, so the table COUNT is unchanged and only these tokens distinguish "the
fallback ran and found no grid" from "the fallback crashed".

`rule-40-scan.py` flags exactly that: a recorded failure no test asserts.

THE CONTROL IS A SPY, NOT THE METHOD STRING. On this paper the fallback runs and
recovers no cells (the region over-capture defect pinned xfail in
``tests/test_r1_whitespace_cells_wiring_real_pdf.py``), so ``whitespace_cells``
never appears in ``method`` on the healthy path. The only proof the block is
reached is counting calls into the helper. Measured 2026-09-25 on
apa/chan_feldman_2025_cogemo.pdf: 2 calls on the default path.
"""

import os

import pytest

import docpluck.tables.whitespace as ws
from docpluck.extract_structured import extract_pdf_structured
from docpluck.testing import require_corpus_pdf

pytest.importorskip("camelot", reason="camelot not installed (pip install docpluck[all])")

# Two captions reach the whitespace fallback on the default path.
_PAPER = "apa/chan_feldman_2025_cogemo.pdf"


@pytest.fixture(scope="module")
def paper_bytes() -> bytes:
    # require_, not corpus_pdf: a paper this gate needs and cannot read is a FAILURE.
    return require_corpus_pdf(_PAPER).read_bytes()


@pytest.fixture(autouse=True)
def _camelot_must_be_enabled(monkeypatch):
    """With Camelot disabled every caption is unmatched and the reach changes."""
    monkeypatch.delenv("DOCPLUCK_DISABLE_CAMELOT", raising=False)
    assert os.environ.get("DOCPLUCK_DISABLE_CAMELOT", "0") != "1"


def test_control_the_fallback_is_reached_and_records_nothing(paper_bytes, monkeypatch):
    real = ws.whitespace_cells
    calls = []

    def _spy(*a, **k):
        calls.append(1)
        return real(*a, **k)

    monkeypatch.setattr(ws, "whitespace_cells", _spy)
    result = extract_pdf_structured(paper_bytes)
    method = result["method"]

    assert calls, (
        "whitespace_cells was never called: the fallback block was not reached, so "
        f"the failure tests below would pass vacuously. method={method}"
    )
    assert "whitespace_setup_failed:" not in method, method
    assert "whitespace_region_failed:" not in method, method
    assert "whitespace_cells_setup_exception" not in result["fallbacks"]
    assert "whitespace_cells_region_exception" not in result["fallbacks"]


def test_a_setup_failure_is_named_in_method_and_fallbacks(paper_bytes, monkeypatch):
    """The lazy ``from .tables.whitespace import whitespace_cells`` raises ImportError.

    Deleting the attribute is what makes that one import fail without patching
    ``builtins.__import__``; `whitespace_cells` has no other caller in the
    library, so nothing else on the path is perturbed.
    """
    monkeypatch.delattr(ws, "whitespace_cells")
    result = extract_pdf_structured(paper_bytes)
    method = result["method"]

    assert "whitespace_setup_failed:ImportError" in method, (
        "the whitespace fallback could not start and the method string reads like a "
        f"run where it found nothing. method={method}"
    )
    assert "whitespace_cells_setup_exception" in result["fallbacks"], (
        f"setup failure not recorded. fallbacks={result['fallbacks']}"
    )
    assert "whitespace_region_failed:" not in method, (
        f"setup failed, so no region should have been attempted. method={method}"
    )


def test_a_region_failure_is_named_in_method_and_fallbacks(paper_bytes, monkeypatch):
    def _boom(*_a, **_kw):
        raise RuntimeError("injected: whitespace_cells crashed")

    monkeypatch.setattr(ws, "whitespace_cells", _boom)
    result = extract_pdf_structured(paper_bytes)
    method = result["method"]

    assert "whitespace_region_failed:RuntimeError" in method, (
        "the whitespace fallback crashed on a caption and the method string does not "
        f"say so. method={method}"
    )
    assert "whitespace_cells_region_exception" in result["fallbacks"], (
        f"region failure not recorded. fallbacks={result['fallbacks']}"
    )
    assert result["tables"], "a crashed fallback must still leave the Camelot tables"
