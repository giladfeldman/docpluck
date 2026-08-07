"""v2.0 must not change extract_pdf() output for any fixture in MANIFEST.json."""

import json
import os
from pathlib import Path

import pytest


_HERE = Path(__file__).parent
_MANIFEST = _HERE / "fixtures" / "structured" / "MANIFEST.json"
_SNAPSHOT_DIR = _HERE / "snapshots"

# The portfolio root. Resolution order per the ~/Vibe/CLAUDE.md hard rule
# ("Never hardcode the Vibe root — use VIBE_ROOT"): env var, then $HOME/Vibe.
#
# 2026-08-07: this was hardcoded to `$HOME/Dropbox/Vibe`. The portfolio moved
# OUT of Dropbox on 2026-08-03 (Dropbox syncing a live .git corrupts repos), so
# every fixture resolved to a path that no longer exists and **all 12 tests
# SKIPPED** — silently, for four days. That is the precise failure the hard
# rule warns about: "a discovery helper that returns empty when the root is
# wrong makes a broken run look like a clean one". Worse here than usual,
# because these tests are the reason 984 KB of published article text sits in
# `tests/snapshots/` — all of the exposure, none of the protection.
_VIBE = Path(os.environ.get("VIBE_ROOT") or (Path(os.path.expanduser("~")) / "Vibe"))


def _entries():
    if not _MANIFEST.is_file():
        return []
    return json.loads(_MANIFEST.read_text(encoding="utf-8"))["fixtures"]


def _resolve(entry: dict) -> Path:
    data = json.loads(_MANIFEST.read_text(encoding="utf-8"))
    base = _VIBE if data.get("vibe_relative") else Path("/")
    return base / entry["source_path"]


def test_fixture_root_exists():
    """Fail loudly when the corpus root is wrong, instead of skipping 12 tests.

    Without this, a relocated portfolio turns the whole snapshot suite into a
    silent no-op and the run still reports green. A missing *individual* PDF is
    a legitimate skip (not everyone has the closed-access corpus); a missing
    *root* is a broken configuration and must be visible.
    """
    data = json.loads(_MANIFEST.read_text(encoding="utf-8")) if _MANIFEST.is_file() else {}
    if not data.get("vibe_relative"):
        pytest.skip("manifest is not vibe-relative")
    assert _VIBE.is_dir(), (
        f"corpus root {_VIBE} does not exist — every fixture would skip and the "
        "suite would report green. Set VIBE_ROOT, or check whether the portfolio "
        "moved (it left ~/Dropbox/Vibe on 2026-08-03)."
    )


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
