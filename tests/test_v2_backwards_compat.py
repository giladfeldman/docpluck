"""v2.0 must not change extract_pdf() output for any fixture in MANIFEST.json."""

import json
import os
from pathlib import Path

import pytest


_HERE = Path(__file__).parent
_MANIFEST = _HERE / "fixtures" / "structured" / "MANIFEST.json"
_SNAPSHOT_DIR = _HERE / "snapshots"
_VIBE = Path(os.path.expanduser("~")) / "Dropbox" / "Vibe"


def _entries():
    if not _MANIFEST.is_file():
        return []
    return json.loads(_MANIFEST.read_text(encoding="utf-8"))["fixtures"]


def _resolve(entry: dict) -> Path:
    data = json.loads(_MANIFEST.read_text(encoding="utf-8"))
    base = _VIBE if data.get("vibe_relative") else Path("/")
    return base / entry["source_path"]


@pytest.mark.parametrize("entry", _entries(), ids=lambda e: e.get("id", "?"))
def test_extract_pdf_byte_identical(entry):
    """extract_pdf() output must match its committed snapshot byte-for-byte.

    On first run for a new fixture, the snapshot is captured and the test SKIPs
    with a message indicating capture. On subsequent runs, drift fails the test.
    """
    pdf_path = _resolve(entry)
    if not pdf_path.is_file():
        pytest.skip(f"Fixture not available: {entry['id']}")

    snapshot = _SNAPSHOT_DIR / f"{entry['id']}.txt"

    from docpluck import extract_pdf
    text, method = extract_pdf(pdf_path.read_bytes())

    if not snapshot.exists():
        snapshot.parent.mkdir(parents=True, exist_ok=True)
        snapshot.write_text(text, encoding="utf-8")
        pytest.skip(f"Snapshot captured: {snapshot.relative_to(_HERE.parent)}")

    expected = snapshot.read_text(encoding="utf-8")
    if text != expected:
        # Provide a useful failure message — first 200 chars of diff context.
        import difflib
        diff = list(difflib.unified_diff(
            expected.splitlines(keepends=True)[:50],
            text.splitlines(keepends=True)[:50],
            fromfile="expected", tofile="actual", n=2,
        ))
        diff_preview = "".join(diff[:80])
        pytest.fail(
            f"extract_pdf() drift on {entry['id']}\n{diff_preview}\n"
            f"To accept new output, delete {snapshot} and re-run."
        )


@pytest.mark.parametrize("entry", _entries(), ids=lambda e: e.get("id", "?"))
def test_method_value_uses_known_strings(entry):
    """method must be one of the documented values (or 'error' on malformed PDFs).

    v2.4.76 (R4 column-aware re-extraction) extends the documented set with a
    ``+column_corrected:N,M,...`` suffix when R4 fires on flagged interleave
    pages. The base prefix still matches one of the v2.4.74 known strings.
    """
    pdf_path = _resolve(entry)
    if not pdf_path.is_file():
        pytest.skip(f"Fixture not available: {entry['id']}")
    from docpluck import extract_pdf
    _, method = extract_pdf(pdf_path.read_bytes())
    known_bases = {
        "pdftotext_default",
        "pdftotext_default+pdfplumber_recovery",
        "error",
    }
    # Strip the optional R4 suffix `+column_corrected:N,M,...` before checking.
    base = method.split("+column_corrected:")[0]
    assert base in known_bases, f"unexpected method base: {base!r} (full: {method!r})"
