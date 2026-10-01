"""A table pass that fails must change ``method``, and a failed page render is retried.

Measured 2026-10-01. ESCImate ran the same 27 papers twice through a local service
at v2.4.147; 6 papers returned different table sets with NO ``incomplete:`` label
in ``method``. Locally:

* the library alone, serial, and the service (3 runs, 2 concurrent requests) all
  gave one output per paper -- the one ESCImate got in its SECOND run;
* a per-process memory cap reproduced ESCImate's FIRST run exactly
  (10.1038/s41598-023-50401-z 124 -> 125 rows, 10.1371/journal.pmed.1004323
  114 -> 103, 10.1525/collabra.122515 56 -> 82, collabra.77859
  ``region_pick:0+1`` -> ``1+0``): the lattice pass was lost;
* there it was labelled, because the failing allocation was OpenCV's. When the
  failing allocation is pdfium's page bitmap instead, pypdfium2 raises a plain
  ``PdfiumError`` -- not a memory error -- and Camelot either re-renders the page
  with another program (Ghostscript/Poppler: a different raster, so possibly
  different ruled tables) or raises ``ImageConversionError``. Injecting that
  failure on 10.1038/s41598-023-50401-z gave 125 rows under a ``method``
  byte-identical to the healthy run's 124.

The fix, pinned here two-sided:

* every ``*_exception`` event recorded during structured extraction is named in
  ``method`` as ``+incomplete:<event>``, whatever its cause;
* a failed lattice page render is retried, so a transient failure yields the
  quiet-machine output;
* the lattice raster always comes from pdfium; Camelot never silently swaps the
  renderer.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from docpluck import resources
from docpluck.resources import incomplete_method_pieces

from .conftest import pdf_available, pdf_path, requires_pdftotext


@pytest.fixture(autouse=True)
def _no_backoff(monkeypatch):
    monkeypatch.setattr(resources, "RETRY_BACKOFF_S", 0.0)


# ── the label ───────────────────────────────────────────────────────────────


def test_every_exception_event_is_named():
    pieces = incomplete_method_pieces({
        "camelot_lattice_exception": 1, "camelot_region_exception": 2,
        "camelot_table_too_small": 6,
    })
    assert pieces == ["incomplete:camelot_lattice_exception,camelot_region_exception"]


def test_resource_label_keeps_its_own_piece():
    # ESCImate matches `+incomplete:resource_exhausted` literally.
    pieces = incomplete_method_pieces({"resource_exhausted": 1, "camelot_lattice_exception": 1})
    assert pieces == ["incomplete:resource_exhausted", "incomplete:camelot_lattice_exception"]


def test_a_healthy_run_has_no_label():
    assert incomplete_method_pieces({"camelot_table_too_small": 6, "resource_retry": 1}) == []


# ── the real paper ──────────────────────────────────────────────────────────

_PAPER = "10.1038__s41598-023-50401-z.pdf"
_needs_paper = pytest.mark.skipif(
    not pdf_available("articlerepo", _PAPER),
    reason="closed-access fixture not present in the article repository",
)


def _run():
    from docpluck import extract_pdf_structured, flatten_tables_for_paper

    r = extract_pdf_structured(Path(pdf_path("articlerepo", _PAPER)).read_bytes())
    rows = flatten_tables_for_paper(r["tables"])
    sha = hashlib.sha1(json.dumps(rows, sort_keys=True, default=str).encode()).hexdigest()
    return r, len(rows), sha


def _pdfium_fails(monkeypatch, *, times):
    """Make pdfium's page render raise like an allocation failure, `times` times
    (None = always). Returns the call counter and the other renderers' counter."""
    from camelot.backends import ghostscript_backend, pdfium_backend, poppler_backend
    from pypdfium2 import PdfiumError

    calls = {"pdfium": 0, "other": 0}
    real_to_array = pdfium_backend.PdfiumBackend.to_array
    real_convert = pdfium_backend.PdfiumBackend.convert

    def fail_or(real):
        def f(self, *a, **k):
            calls["pdfium"] += 1
            if times is None or calls["pdfium"] <= times:
                raise PdfiumError("Failed to get bitmap buffer (null pointer returned)")
            return real(self, *a, **k)
        return f

    def other(self, *a, **k):
        calls["other"] += 1
        raise AssertionError("Camelot swapped the lattice renderer")

    monkeypatch.setattr(pdfium_backend.PdfiumBackend, "to_array", fail_or(real_to_array))
    monkeypatch.setattr(pdfium_backend.PdfiumBackend, "convert", fail_or(real_convert))
    monkeypatch.setattr(poppler_backend.PopplerBackend, "convert", other)
    monkeypatch.setattr(ghostscript_backend.GhostscriptBackend, "convert", other)
    return calls


@requires_pdftotext
@_needs_paper
def test_a_lost_lattice_pass_is_named_in_method(monkeypatch):
    healthy, n_ok, _ = _run()
    assert "incomplete:" not in healthy["method"]

    calls = _pdfium_fails(monkeypatch, times=None)
    r, n, _ = _run()
    assert calls["pdfium"] > 0, "the injection never reached the lattice render"
    assert calls["other"] == 0, "a different renderer was used for the lattice raster"
    assert n != n_ok, "losing the lattice pass no longer changes this paper; pick another"
    assert "incomplete:camelot_lattice_exception" in r["method"], r["method"]


@requires_pdftotext
@_needs_paper
def test_a_transient_render_failure_gives_the_healthy_output(monkeypatch):
    healthy, n_ok, sha_ok = _run()
    calls = _pdfium_fails(monkeypatch, times=1)
    r, n, sha = _run()
    assert calls["pdfium"] > 1, "the render was not retried"
    assert (n, sha) == (n_ok, sha_ok)
    assert r["method"] == healthy["method"]
    assert r["fallbacks"].get("camelot_render_retry", 0) >= 1
