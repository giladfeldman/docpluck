"""Regression: extract_tables_camelot must not let a temp-file cleanup error
propagate (Windows WinError 32).

Incident 2026-06-13: on Windows, camelot (>=2.0) can still hold the temp PDF
handle open when ``extract_tables_camelot`` reaches its ``finally`` block, so
``Path(tmp_path).unlink()`` raised ``PermissionError [WinError 32]``. That
exception propagated out of the function and was swallowed by
``extract_structured``'s broad ``except`` (→ ``camelot_failed``), silently
dropping EVERY table on Windows even when extraction had succeeded. POSIX allows
unlinking an open file, so prod/Linux never saw it. The fix makes the temp
cleanup best-effort (swallow ``OSError``).
"""
from __future__ import annotations

import io

import pytest


def _tiny_pdf() -> bytes:
    rl = pytest.importorskip("reportlab")
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import letter
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    c.setFont("Helvetica", 11)
    # A little tabular-looking content so camelot has something to chew on.
    for i, y in enumerate(range(700, 600, -20)):
        c.drawString(72, y, f"Row{i}   {i*1.5:.2f}   {i*2.5:.2f}")
    c.showPage()
    c.save()
    return buf.getvalue()


def test_cleanup_oserror_does_not_propagate(monkeypatch):
    """If the temp-file unlink raises (Windows lock), the function still returns
    a list rather than raising — so extract_structured does not see a spurious
    camelot failure and zero out all tables."""
    pytest.importorskip("camelot")
    from docpluck.tables import camelot_extract

    real_unlink = camelot_extract.Path.unlink

    def boom(self, *args, **kwargs):
        raise PermissionError(32, "The process cannot access the file")

    monkeypatch.setattr(camelot_extract.Path, "unlink", boom)
    # Must NOT raise PermissionError out of the finally block.
    result = camelot_extract.extract_tables_camelot(_tiny_pdf())
    assert isinstance(result, list)
    # restore (monkeypatch auto-undoes, but be explicit for clarity)
    monkeypatch.setattr(camelot_extract.Path, "unlink", real_unlink)
