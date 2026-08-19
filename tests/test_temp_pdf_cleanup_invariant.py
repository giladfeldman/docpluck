"""Every path that writes a temp PDF must delete it, and must never fail loudly.

## Why this file replaces the directory-counting version

The previous test asserted ``after <= before`` where both are
``len(glob(tempfile.gettempdir() + "/tmp*.pdf"))`` -- a count of a directory
EVERY process on this machine shares. Measured 2026-08-19, both directions wrong:

    run alone                      -> delta +1, FAIL, while docpluck's own
                                      telemetry reported 0 cleanup failures
    run with a concurrent extractor-> delta  0, PASS

The +1 was another process's temp file existing at the instant of the count --
it does not even need to LEAK, only to be mid-extraction. A second full pytest
run was live on this machine at the time (the previous session's, per its
handoff). So the gate is red when nothing is wrong and can be green when
something is: it cannot see the property it names.

The property is process-local, so the instrument must be too. These tests spy on
``tempfile.NamedTemporaryFile`` and check the paths THIS process created.

## The invariant, and how many sites held it

    A temp-PDF cleanup failure must never propagate out of an extraction entry
    point, and must never be silent.

There are five ``NamedTemporaryFile(suffix=".pdf", delete=False)`` sites in
``docpluck/``. Before this change:

    camelot_extract.py:834  ``_unlink_temp_pdf``   retried + recorded
    camelot_extract.py:947  ``_unlink_temp_pdf``   retried + recorded
    extract.py:249          bare ``os.unlink``     RAISES out of extract_pdf
    extract_columns.py:292  ``except: pass``       silent
    extract_columns.py:965  ``except: pass``       silent

-- under a comment at the camelot sites reading "BOTH call sites, because a fix
applied to one of two is not fixed, and this module has a documented history of
exactly that". It was a fix applied to two of five.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

_CORPUS = Path(__file__).resolve().parents[2] / "PDFextractor" / "test-pdfs" / "apa"
_PDF = _CORPUS / "efendic_2022_affect.pdf"

pytestmark = pytest.mark.skipif(not _PDF.is_file(), reason=f"fixture not available: {_PDF}")


class _Spy:
    """Record every temp PDF path THIS process creates."""

    def __init__(self, monkeypatch):
        self.created: list[str] = []
        real = tempfile.NamedTemporaryFile

        def spy(*args, **kwargs):
            handle = real(*args, **kwargs)
            if str(kwargs.get("suffix", "")).endswith(".pdf"):
                self.created.append(handle.name)
            return handle

        monkeypatch.setattr(tempfile, "NamedTemporaryFile", spy)

    @property
    def left_behind(self) -> list[str]:
        return [p for p in self.created if os.path.exists(p)]


def _entry_points():
    from docpluck.extract import extract_pdf
    from docpluck.extract_structured import extract_pdf_structured
    from docpluck.render import render_pdf_to_markdown
    from docpluck.tables.camelot_extract import (
        extract_tables_camelot,
        extract_tables_camelot_by_region,
    )

    region_spec = [{"key": "t1", "page": 1, "area": "50,750,560,80",
                    "area_bu": (50.0, 750.0, 560.0, 80.0)}]
    return [
        ("extract_pdf", lambda d: extract_pdf(d)),
        ("extract_tables_camelot", lambda d: extract_tables_camelot(d)),
        ("extract_tables_camelot_by_region",
         lambda d: extract_tables_camelot_by_region(d, region_spec)),
        ("extract_pdf_structured", lambda d: extract_pdf_structured(d)),
        ("render_pdf_to_markdown", lambda d: render_pdf_to_markdown(d)),
    ]


@pytest.mark.parametrize("name,call", _entry_points(), ids=lambda v: v if isinstance(v, str) else "")
def test_no_entry_point_leaves_its_own_temp_pdf_behind(monkeypatch, name, call):
    spy = _Spy(monkeypatch)
    call(_PDF.read_bytes())
    assert spy.created, f"{name} wrote no temp PDF — this assertion would be vacuous"
    assert not spy.left_behind, (
        f"{name} left {len(spy.left_behind)} of {len(spy.created)} temp PDF(s) behind; "
        f"each is a full copy of the input document"
    )


@pytest.mark.parametrize("name,call", _entry_points(), ids=lambda v: v if isinstance(v, str) else "")
def test_a_cleanup_failure_never_propagates_out_of_an_entry_point(monkeypatch, name, call):
    """The invariant two of five sites held.

    A locked temp file is a CLEANUP problem. Letting it escape turns it into an
    extraction failure: `extract_structured`'s broad `except` reads a raised
    PermissionError as "camelot failed" and zeroes every table (incident
    2026-06-13), and `extract_pdf` has no such net at all — it simply raises,
    from the library's primary text entry point, after the text was already
    extracted successfully.
    """
    def boom(*args, **kwargs):
        raise PermissionError(32, "The process cannot access the file")

    monkeypatch.setattr(os, "unlink", boom)
    monkeypatch.setattr(Path, "unlink", boom)

    try:
        call(_PDF.read_bytes())
    except PermissionError as exc:
        pytest.fail(
            f"{name} let a temp-cleanup PermissionError escape: {exc}. Cleanup is "
            f"best-effort; the extraction had already succeeded."
        )


def test_a_cleanup_failure_is_recorded_rather_than_swallowed(monkeypatch):
    """Silence is what let 1,469 files accumulate unnoticed. Two of the five
    sites swallowed the error with a bare ``except: pass``."""
    from docpluck.extract import extract_pdf
    from docpluck.telemetry import fallback_scope

    def boom(*args, **kwargs):
        raise PermissionError(32, "The process cannot access the file")

    monkeypatch.setattr(os, "unlink", boom)
    monkeypatch.setattr(Path, "unlink", boom)

    with fallback_scope() as fb:
        extract_pdf(_PDF.read_bytes())

    assert any(k.endswith("temp_pdf_not_deleted") for k in fb.counters), (
        f"a cleanup failure was swallowed with no record; counters={sorted(fb.counters)}"
    )


def test_extraction_still_works_so_the_assertions_above_are_not_vacuous():
    from docpluck.tables.camelot_extract import extract_tables_camelot

    assert extract_tables_camelot(_PDF.read_bytes()), "no tables — the leak tests are vacuous"
