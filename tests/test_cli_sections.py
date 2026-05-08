"""CLI: `docpluck sections <file>` and `docpluck extract --sections=...`."""

import io
import json
import os
import subprocess
import sys
import tempfile

import pytest

pytest.importorskip("reportlab")
pytest.importorskip("pdfplumber")


def _make_pdf_file(tmp: str) -> str:
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import letter
    p = os.path.join(tmp, "x.pdf")
    c = canvas.Canvas(p, pagesize=letter)
    c.setFont("Helvetica-Bold", 14); c.drawString(72, 720, "Abstract")
    c.setFont("Helvetica", 11); c.drawString(72, 700, "Abstract body.")
    c.setFont("Helvetica-Bold", 14); c.drawString(72, 660, "References")
    c.setFont("Helvetica", 11); c.drawString(72, 640, "[1] Doe.")
    c.showPage(); c.save()
    return p


def _run(*args) -> tuple[int, str, str]:
    proc = subprocess.run(
        [sys.executable, "-m", "docpluck.cli", *args],
        capture_output=True, text=True,
    )
    return proc.returncode, proc.stdout, proc.stderr


def test_cli_sections_json_output():
    with tempfile.TemporaryDirectory() as tmp:
        path = _make_pdf_file(tmp)
        code, out, err = _run("sections", path, "--format", "json")
        assert code == 0, err
        payload = json.loads(out)
        assert "sections" in payload
        assert payload["sectioning_version"] == "1.2.0"
        assert any(s["canonical_label"] == "abstract" for s in payload["sections"])


def test_cli_extract_sections_filter():
    with tempfile.TemporaryDirectory() as tmp:
        path = _make_pdf_file(tmp)
        code, out, err = _run("extract", path, "--sections", "abstract,references")
        assert code == 0, err
        assert "Abstract body" in out
        assert "[1] Doe" in out


def test_cli_version_still_works():
    code, out, _ = _run("--version")
    assert code == 0
    payload = json.loads(out)
    assert "version" in payload
