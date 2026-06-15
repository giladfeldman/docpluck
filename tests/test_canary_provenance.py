"""
Input-feed provenance gate for the docpluck-iterate canary (rec R-0003, 2026-06-15).

Cross-project lesson transfer (CitationGuard => docpluck): the verification
substrate must be byte-equal to the production input feed BEFORE scoring. A
CitationGuard run once scored its tool output against raw PyMuPDF for a whole
run, producing a misleading score.

docpluck already scores render-vs-AI-gold (never vs a deterministic extractor --
see CLAUDE.md hard rule "GROUND TRUTH ... NEVER pdftotext/PyMuPDF"), so the
residual gap that lesson maps to here is INPUT provenance: the PDF rendered for
audit must be byte-identical to the canonical input pinned for that canary
paper. If the cached PDF for a DOI ever drifts (re-download, re-encode, a stray
Dropbox conflicted-copy), the canary would silently score a render of a
different input than the gold was made from -- the same "wrong substrate" bug
class.

These tests pin each canary paper's expected input-PDF sha256 in canary.json and
assert the located PDF is byte-equal, plus exercise the tools/canary_provenance
helper that render_for_audit uses to enforce this before rendering/scoring.
"""
import hashlib
import json
import os
import subprocess
import sys

import pytest

_HERE = os.path.dirname(__file__)
_REPO = os.path.dirname(_HERE)
_TOOLS = os.path.join(_REPO, "tools")
if _TOOLS not in sys.path:
    sys.path.insert(0, _TOOLS)

import canary_provenance as cp  # noqa: E402

CANARY_JSON = os.path.join(_REPO, ".claude", "skills", "_project", "canary.json")
CACHE_CHECK = os.path.join(
    os.path.expanduser("~"), ".claude", "skills", "article-finder", "cache-check.py"
)


def _canary_papers():
    with open(CANARY_JSON, encoding="utf-8") as f:
        c = json.load(f)
    papers = list(c.get("canary", {}).get("fixed", []) or [])
    papers += list(c.get("canary", {}).get("rotating_pool", []) or [])
    return papers


# --- unit tests of the provenance helper ----------------------------------


def test_check_provenance_passes_on_match():
    ok, msg = cp.check_provenance("10.x/abc", "a" * 64, "a" * 64)
    assert ok is True
    assert msg == ""


def test_check_provenance_fails_on_mismatch():
    ok, msg = cp.check_provenance("10.x/abc", "a" * 64, "b" * 64)
    assert ok is False
    # Message must name the key and both shas so a failure is self-diagnosing.
    assert "10.x/abc" in msg
    assert "a" * 64 in msg
    assert "b" * 64 in msg


def test_no_expected_sha_is_not_enforced():
    # When nothing is pinned, provenance is a no-op (zero behaviour change for
    # un-pinned keys -- the guard only fires where a canonical sha is pinned).
    ok, msg = cp.check_provenance("10.x/abc", "a" * 64, None)
    assert ok is True
    assert msg == ""


def test_every_canary_paper_has_pinned_sha():
    papers = _canary_papers()
    assert papers, "canary.json declares no canary papers"
    for p in papers:
        expected = cp.load_expected_sha(CANARY_JSON, p["key"])
        assert expected is not None, f"canary paper {p['key']} missing expected_pdf_sha pin"
        assert len(expected) == 64, f"{p['key']} expected_pdf_sha is not a sha256 hex digest"


# --- integration: pinned shas match the real cached PDFs -------------------


def _cache_check(doi):
    if not os.path.isfile(CACHE_CHECK):
        return None
    proc = subprocess.run(
        [sys.executable, CACHE_CHECK, doi], capture_output=True, text=True, check=False
    )
    if proc.returncode != 0:
        return None
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        return None


def _sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(65536), b""):
            h.update(b)
    return h.hexdigest()


@pytest.mark.parametrize(
    "paper", _canary_papers(), ids=lambda p: p.get("stem", p.get("key", "?"))
)
def test_canary_pdf_is_byte_equal_to_pin(paper):
    """The canonical input PDF for each canary paper must equal its pinned sha."""
    info = _cache_check(paper["key"])
    if not info or not info.get("found"):
        pytest.skip(f"{paper['key']} not in article-finder cache (cannot verify here)")
    path = info.get("path", "")
    if not path or not os.path.isfile(path):
        pytest.skip(f"{paper['key']} cache path missing on disk: {path!r}")
    expected = cp.load_expected_sha(CANARY_JSON, paper["key"])
    assert expected is not None, f"{paper['key']} missing expected_pdf_sha pin in canary.json"
    actual = _sha256_file(path)
    assert actual == expected, (
        f"INPUT-FEED DRIFT for {paper['key']}: located PDF sha {actual} != pinned {expected}. "
        "Verification substrate is NOT byte-equal to the pinned production input feed."
    )


# --- render_for_audit enforces provenance BEFORE rendering/scoring ----------

RENDER_FOR_AUDIT = os.path.join(_TOOLS, "render_for_audit.py")
EXIT_PROVENANCE_MISMATCH = 4


@pytest.fixture(scope="module")
def cached_canary_key():
    """A canary key whose PDF is in cache, else skip the render-path tests."""
    for p in _canary_papers():
        info = _cache_check(p["key"])
        if info and info.get("found") and os.path.isfile(info.get("path", "")):
            return p["key"]
    pytest.skip("no canary PDF available in cache to exercise render_for_audit")


def test_render_for_audit_aborts_on_provenance_mismatch(tmp_path, cached_canary_key):
    """A wrong --expected-sha must abort with exit 4 and write no artifact --
    the provenance guard fires BEFORE the (expensive) render and before scoring."""
    out = tmp_path / "out.md"
    proc = subprocess.run(
        [
            sys.executable, RENDER_FOR_AUDIT,
            "--key", cached_canary_key,
            "--out", str(out),
            "--expected-sha", "0" * 64,
            "--quiet",
        ],
        capture_output=True, text=True, check=False,
    )
    assert proc.returncode == EXIT_PROVENANCE_MISMATCH, (
        f"expected exit {EXIT_PROVENANCE_MISMATCH} on provenance mismatch, got "
        f"{proc.returncode}. stdout={proc.stdout[-400:]!r} stderr={proc.stderr[-400:]!r}"
    )
    assert "PROVENANCE MISMATCH" in (proc.stdout + proc.stderr)
    assert not out.exists(), "render_for_audit wrote output despite a provenance mismatch"
