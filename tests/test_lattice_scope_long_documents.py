"""Long documents get Camelot's lattice pass on their caption pages only -- and say so.

Why this file exists (2026-09-25). ``/api/analyze`` with tables requested ran past
the 200 s upstream abort on the 72-page 10.1098/rsos.250979. Counted, not timed
(this machine's wall clock is unusable under load): 18 ``camelot.read_pdf`` calls
and 160 page-parses -- stream 88 (72 whole-document + 16 region re-reads), lattice
72. In the same run one lattice page-parse cost ~7.7x one stream page-parse, so
the lattice pass was ~83% of Camelot's time. Lattice rasterises every page at
300 dpi; nothing about that is redundant work that could be skipped for free.

So the bound is on the INPUT: above ``LATTICE_FULL_SCAN_MAX_PAGES`` lattice reads
only the pages carrying a "Table N" caption. The same PDF always gets the same
cut, on any machine under any load, and the cut is announced in ``method`` and
``fallbacks`` -- a page never scanned for ruled tables must not look like a page
scanned and found empty.

Also here: the "every flavor failed" label. It used to fire whenever both flavors
returned nothing, so an image-only PDF on which Camelot ran cleanly was labelled
``camelot_failed:camelot_all_flavors_failed``, the same as a broken Camelot.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from docpluck import extract_structured as es
from docpluck.tables import camelot_extract as ce
from docpluck.telemetry import fallback_scope

camelot = pytest.importorskip("camelot", reason="camelot not installed (pip install docpluck[all])")


def _cap(page: int, kind: str = "table") -> SimpleNamespace:
    return SimpleNamespace(page=page, kind=kind)


# ── the scope decision ──────────────────────────────────────────────────────

def test_at_or_below_the_threshold_nothing_changes():
    pieces: list[str] = []
    with fallback_scope() as fb:
        scope = es._lattice_scope(es.LATTICE_FULL_SCAN_MAX_PAGES, [_cap(3)], pieces)
    assert scope is None, "a document at the threshold must be scanned in full"
    assert pieces == [] and dict(fb.counters) == {}, (
        f"an unchanged scan announced a cut: method={pieces} fallbacks={dict(fb.counters)}"
    )


def test_above_the_threshold_lattice_reads_caption_pages_and_says_so():
    pieces: list[str] = ["pdftotext_default"]
    caps = [_cap(9), _cap(4), _cap(9), _cap(12, kind="figure"), _cap(30)]
    n = es.LATTICE_FULL_SCAN_MAX_PAGES + 1
    with fallback_scope() as fb:
        scope = es._lattice_scope(n, caps, pieces)
    # Table captions only, de-duplicated, ascending; a figure caption is not
    # evidence of a table.
    assert scope == [4, 9, 30]
    assert pieces[-1] == f"lattice_scope:3/{n}"
    assert fb.counters["camelot_lattice_limited_to_caption_pages"] == 1
    assert fb.details["camelot_lattice_limited_to_caption_pages"] == {f"3/{n}": 1}


def test_a_long_document_with_no_table_caption_is_still_announced():
    """Zero caption pages means lattice reads NOTHING -- the loudest case, so
    it must be announced like any other cut, not treated as a no-op."""
    pieces: list[str] = []
    with fallback_scope() as fb:
        scope = es._lattice_scope(72, [_cap(5, kind="figure")], pieces)
    assert scope == []
    assert pieces == ["lattice_scope:0/72"]
    assert fb.counters["camelot_lattice_limited_to_caption_pages"] == 1


# ── what extract_tables_camelot does with the scope ─────────────────────────

class _FakeCamelot:
    """Records every ``read_pdf`` call; returns no tables unless told to raise."""

    def __init__(self, raise_for: set[str] = frozenset()):
        self.calls: list[tuple[str, str]] = []
        self.raise_for = raise_for

    def read_pdf(self, _path, *, pages, flavor, **_kw):
        self.calls.append((flavor, pages))
        if flavor in self.raise_for:
            raise RuntimeError(f"injected {flavor} failure")
        return []


@pytest.fixture
def fake(monkeypatch):
    def make(raise_for=frozenset()):
        f = _FakeCamelot(set(raise_for))
        monkeypatch.setattr(camelot, "read_pdf", f.read_pdf)
        return f
    return make


def test_no_scope_reads_every_page_with_both_flavors(fake):
    f = fake()
    ce.extract_tables_camelot(b"%PDF-1.4 fake")
    assert f.calls == [("stream", "all"), ("lattice", "all")]


def test_a_scope_limits_lattice_only(fake):
    f = fake()
    ce.extract_tables_camelot(b"%PDF-1.4 fake", lattice_pages=[9, 4, 9])
    assert f.calls == [("stream", "all"), ("lattice", "4,9")], (
        "stream must still read every page; lattice only the scoped pages, sorted, once each"
    )


def test_an_empty_scope_makes_no_lattice_call(fake):
    """``pages=""`` is not "no pages" to Camelot; the call must not be made at all."""
    f = fake()
    ce.extract_tables_camelot(b"%PDF-1.4 fake", lattice_pages=[])
    assert f.calls == [("stream", "all")]


def test_a_clean_empty_result_is_not_labelled_a_failure(fake):
    """Two-sided control, side 1: both flavors RAN and found nothing."""
    fake()
    with fallback_scope() as fb:
        assert ce.extract_tables_camelot(b"%PDF-1.4 fake") == []
    assert not (ce.CAMELOT_UNAVAILABLE_EVENTS & fb.counters.keys()), (
        f"a clean empty run was labelled as Camelot failing: {dict(fb.counters)}"
    )


@pytest.mark.parametrize("raise_for,scope", [
    ({"stream", "lattice"}, None),   # both raised
    ({"stream"}, []),                # the only flavor that ran raised
    ({"stream"}, None),              # stream raised, lattice ran clean and empty
])
def test_an_empty_result_behind_an_exception_is_still_named(fake, raise_for, scope):
    """Two-sided control, side 2: the loss the label exists for still fires."""
    fake(raise_for)
    with fallback_scope() as fb:
        assert ce.extract_tables_camelot(b"%PDF-1.4 fake", lattice_pages=scope) == []
    assert "camelot_all_flavors_failed" in fb.counters, dict(fb.counters)


def test_an_image_only_pdf_is_not_labelled_a_camelot_failure(tmp_path, monkeypatch):
    """The real case that exposed the label: no text layer, nothing raised."""
    reportlab = pytest.importorskip("reportlab")  # noqa: F841
    pil = pytest.importorskip("PIL.Image")
    from reportlab.pdfgen import canvas

    png = tmp_path / "scan.png"
    pil.new("RGB", (600, 300), "white").save(png)
    pdf = tmp_path / "scan.pdf"
    c = canvas.Canvas(str(pdf))
    c.drawImage(str(png), 50, 400, 500, 250)
    c.save()

    monkeypatch.delenv("DOCPLUCK_DISABLE_CAMELOT", raising=False)
    result = es.extract_pdf_structured(pdf.read_bytes())
    assert "camelot_failed" not in result["method"], result["method"]
    assert "camelot_all_flavors_failed" not in result["fallbacks"], result["fallbacks"]
