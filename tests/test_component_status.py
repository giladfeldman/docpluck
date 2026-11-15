"""`tables_status` / `figures_status`: an empty list must say WHY it is empty.

Owner decision 2026-11-13: keep `tables == []`, add a status beside it. These tests
pin (1) the classification is total -- every `*_exception` event the package can
record is sorted into the table channel, the text channel or diagnostic-only, so
a new catch site cannot read as "tables ok" by omission; (2) each status value is
reachable through the REAL wrapper, not only the helper.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

import docpluck
from docpluck import extract_structured as es
from docpluck.resources import (
    DIAGNOSTIC_ONLY_EVENTS,
    TABLE_CHANNEL_EXCEPTION_EVENTS,
    TEXT_CHANNEL_EXCEPTION_EVENTS,
    component_status,
)

PKG = Path(docpluck.__file__).parent
_EVENT = re.compile(r'record_fallback\(\s*"([a-z0-9_]+_exception)"')


def _recorded_exception_events() -> set[str]:
    found: set[str] = set()
    for py in PKG.rglob("*.py"):
        found |= set(_EVENT.findall(py.read_text(encoding="utf-8")))
    return found


def test_every_exception_event_is_classified_exactly_once():
    events = _recorded_exception_events()
    # A zero here would mean the grep broke, not that the package is clean.
    assert len(events) >= 30, f"only {len(events)} events found -- broken scan?"
    classes = (TABLE_CHANNEL_EXCEPTION_EVENTS, TEXT_CHANNEL_EXCEPTION_EVENTS,
               DIAGNOSTIC_ONLY_EVENTS)
    unclassified = sorted(e for e in events if not any(e in c for c in classes))
    assert not unclassified, (
        "new *_exception event(s) with no channel: add each to "
        "TABLE_CHANNEL_EXCEPTION_EVENTS or TEXT_CHANNEL_EXCEPTION_EVENTS in "
        f"docpluck/resources.py: {unclassified}")
    overlap = TABLE_CHANNEL_EXCEPTION_EVENTS & TEXT_CHANNEL_EXCEPTION_EVENTS
    assert not overlap
    stale = sorted((TABLE_CHANNEL_EXCEPTION_EVENTS | TEXT_CHANNEL_EXCEPTION_EVENTS)
                   - events)
    assert not stale, f"classified events no code records any more: {stale}"


@pytest.mark.parametrize("counters, expected", [
    ({}, "ok"),
    ({"column_correction_exception": 1}, "ok"),            # text-only loss
    ({"camelot_lattice_exception": 2}, "partial:camelot_lattice_exception"),
    ({"camelot_all_flavors_failed": 1, "camelot_lattice_exception": 1},
     "failed:camelot_all_flavors_failed"),
    ({"camelot_extract_exception": 0}, "ok"),                # zero count = did not fire
])
def test_component_status_values(counters, expected):
    assert component_status(counters) == expected


def test_failed_becomes_partial_when_a_backup_path_built_a_grid():
    assert component_status({"camelot_extract_exception": 1}, grids_shipped=2) == (
        "partial:camelot_extract_exception")


def test_not_run_reason_wins():
    assert component_status({"camelot_extract_exception": 1},
                            not_run_reason="camelot_disabled") == "not_run:camelot_disabled"


def test_crashing_table_pass_reports_failed_through_the_real_wrapper(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("synthetic camelot crash")
    monkeypatch.delenv("DOCPLUCK_DISABLE_CAMELOT", raising=False)
    monkeypatch.setattr(es, "extract_tables_camelot", boom)
    pdf = _reportlab_pdf()
    r = es.extract_pdf_structured(pdf)
    # Camelot never ran. A backup path (whitespace cells) may still build a
    # grid, and then the honest word is "partial", never "ok"; with no grid at
    # all it is "failed".
    grids = [t for t in r["tables"] if t.get("cells")]
    expected = ("partial:" if grids else "failed:") + "camelot_extract_exception"
    assert r["tables_status"] == expected
    assert r["figures_status"] == "ok"


def test_disabled_camelot_reports_not_run(monkeypatch):
    monkeypatch.setenv("DOCPLUCK_DISABLE_CAMELOT", "1")
    r = es.extract_pdf_structured(_reportlab_pdf())
    assert r["tables_status"] == "not_run:camelot_disabled"


def test_healthy_run_reports_ok(monkeypatch):
    monkeypatch.delenv("DOCPLUCK_DISABLE_CAMELOT", raising=False)
    r = es.extract_pdf_structured(_reportlab_pdf())
    assert r["tables_status"] == "ok", r["fallbacks"]


def test_docx_figures_say_not_extracted():
    docx = pytest.importorskip("docx")
    import io
    d = docx.Document()
    d.add_paragraph("Hello world.")
    buf = io.BytesIO()
    d.save(buf)
    r = docpluck.extract_docx_structured(buf.getvalue())
    assert r["tables_status"] == "ok"
    assert r["figures_status"] == "not_run:docx_figures_not_extracted"


def _reportlab_pdf() -> bytes:
    canvas = pytest.importorskip("reportlab.pdfgen.canvas")
    import io
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    c.drawString(72, 720, "A short paragraph of body text for the test.")
    c.drawString(72, 700, "Table 1 Means by condition")
    c.drawString(72, 680, "Group   M     SD")
    c.drawString(72, 665, "A       1.20  0.30")
    c.drawString(72, 650, "B       2.40  0.50")
    c.showPage()
    c.save()
    return buf.getvalue()
