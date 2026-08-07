"""v2.0 must not change extract_pdf() output for any fixture in MANIFEST.json.

The guarantee is byte-for-byte, and it is enforced against a **sha256 per
fixture** in ``tests/snapshots/checksums.json`` rather than against a stored
copy of each paper's text.

Why (2026-08-07): the stored copies were 984 KB of published article text —
title, authors, affiliations, full body — git-tracked and live on a PUBLIC
remote since 2026-05-07. ``apa_efendic_affect.txt`` carried SAGE's own reuse
notice verbatim. Plaintext is *more* scrapable than the PDFs this repo already
refuses to commit. A hash asserts exactly the same thing in ~1 KB and asserts
nothing about anyone's copyright.

What a hash cannot do is print a diff. ``pytest --snapshot-explain`` restores
that: on mismatch it writes the actual text to ``tmp/snapshots/`` (gitignored)
for local diffing. ``pytest --snapshot-update`` re-pins the checksums after an
intentional extraction change.
"""

import hashlib
import json
import os
from pathlib import Path

import pytest


_HERE = Path(__file__).parent
_MANIFEST = _HERE / "fixtures" / "structured" / "MANIFEST.json"
_SNAPSHOT_DIR = _HERE / "snapshots"
_CHECKSUMS = _SNAPSHOT_DIR / "checksums.json"

# The portfolio root. Resolution order per the ~/Vibe/CLAUDE.md hard rule
# ("Never hardcode the Vibe root — use VIBE_ROOT"): env var, then $HOME/Vibe.
#
# 2026-08-07: this was hardcoded to `$HOME/Dropbox/Vibe`. The portfolio moved
# OUT of Dropbox on 2026-08-03 (Dropbox syncing a live .git corrupts repos), so
# every fixture resolved to a path that no longer exists and **all 12 tests
# SKIPPED** — silently, for four days. That is the precise failure the hard
# rule warns about: "a discovery helper that returns empty when the root is
# wrong makes a broken run look like a clean one".
_VIBE = Path(os.environ.get("VIBE_ROOT") or (Path(os.path.expanduser("~")) / "Vibe"))


def _manifest() -> dict:
    if not _MANIFEST.is_file():
        return {}
    return json.loads(_MANIFEST.read_text(encoding="utf-8"))


def _entries():
    return _manifest().get("fixtures", [])


def _resolve(entry: dict) -> Path:
    base = _VIBE if _manifest().get("vibe_relative") else Path("/")
    return base / entry["source_path"]


# The tool-artifact family article-finder holds these texts under. The version
# is part of the view NAME on purpose: a new docpluck release registers a new
# view rather than overwriting this one, so the artifact a regression gate
# compares against can never be silently rewritten by the tool under test.
_ARTIFACT_FAMILY = "extract-text__docpluck"


def _captured_version() -> str:
    """The docpluck version these checksums were pinned from, or ''."""
    raw = _checksums().get("captured_from", "")
    return raw.split("v")[-1].strip() if raw else ""


def _checksums() -> dict:
    if not _CHECKSUMS.is_file():
        return {"version": 1, "algorithm": "sha256", "fixtures": {}}
    return json.loads(_CHECKSUMS.read_text(encoding="utf-8"))


def _digest(text: str) -> tuple[str, int]:
    """sha256 over UTF-8 bytes with canonical LF newlines.

    Hashing the decoded string rather than a file on disk makes the pin
    platform-independent: the old ``.txt`` snapshots were written in text mode,
    so they carried CRLF on Windows and LF elsewhere while comparing equal.
    """
    data = text.encode("utf-8")
    return hashlib.sha256(data).hexdigest(), len(data)


def _record(fixture_id: str, sha: str, size: int, method: str) -> None:
    """Merge one fixture's pin into checksums.json, preserving the rest.

    Read-modify-write per fixture so that a partially available corpus (some
    PDFs missing) updates what it can without dropping pins it cannot verify.
    """
    data = _checksums()
    from docpluck import __version__ as _dp_version
    # Keep this current, or `--snapshot-explain` fetches the baseline for a
    # version these pins were not captured from.
    data["captured_from"] = f"docpluck v{_dp_version}"
    data.setdefault("fixtures", {})[fixture_id] = {
        "sha256": sha, "bytes": size, "method": method,
    }
    data["fixtures"] = dict(sorted(data["fixtures"].items()))
    _CHECKSUMS.parent.mkdir(parents=True, exist_ok=True)
    _CHECKSUMS.write_text(
        json.dumps(data, indent=2) + "\n", encoding="utf-8")


def _explain_against_custodian(entry: dict, actual: str, out_dir: Path) -> list[str]:
    """Diff the actual text against the custodian's copy, if it holds one.

    The expected text is not in this repo — it is a versioned tool artifact in
    article-finder (``extract-text__docpluck@<version>``), keyed by the paper's
    DOI. Fetching it here restores the one thing a sha256 cannot do, without
    putting a single byte of anybody's article back into a public tree.

    Best-effort by design: article-finder may not be installed, and a fixture
    may predate its registration. Missing context degrades the failure message;
    it must never mask the drift, which the sha256 has already established.
    """
    key = entry.get("canonical_key")
    if not key:
        return ["  (no canonical_key in MANIFEST.json — cannot fetch the "
                "expected text from article-finder)"]

    finder = Path(os.path.expanduser("~")) / ".claude" / "skills" / "article-finder"
    if not finder.is_dir():
        return [f"  (article-finder not installed at {finder} — actual text only)"]

    import subprocess
    import sys as _sys
    proc = subprocess.run(
        [_sys.executable, str(finder / "ai-gold.py"), "views", key],
        capture_output=True, text=True,
    )
    # `views` prints a header row then "CORPUS VIEW FORMAT PRODUCER STORED_AT".
    candidates = sorted({
        parts[1] for parts in (ln.split() for ln in proc.stdout.splitlines())
        if len(parts) >= 2 and parts[1].startswith(f"{_ARTIFACT_FAMILY}@")
    })
    if not candidates:
        return [f"  (article-finder holds no {_ARTIFACT_FAMILY} baseline for {key})"]
    # Prefer the version these checksums were captured from; else the newest.
    pinned = f"{_ARTIFACT_FAMILY}@{_captured_version()}" if _captured_version() else ""
    chosen = pinned if pinned in candidates else candidates[-1]

    # `ai-gold.py get` prints the PATH of the stored view, not its contents.
    got = subprocess.run(
        [_sys.executable, str(finder / "ai-gold.py"), "get", key, "--view", chosen],
        capture_output=True, text=True,
    )
    stored = Path(got.stdout.strip()) if got.stdout.strip() else None
    if got.returncode != 0 or stored is None or not stored.is_file():
        return [f"  (could not read {chosen} for {key} from article-finder)"]
    expected = stored.read_text(encoding="utf-8", errors="replace")

    import difflib
    diff = list(difflib.unified_diff(
        expected.splitlines(keepends=True)[:400],
        actual.splitlines(keepends=True)[:400],
        fromfile=f"{chosen} (custodian)", tofile="actual", n=2,
    ))
    (out_dir / f"{entry['id']}.diff").write_text("".join(diff), encoding="utf-8")
    return [
        f"  diffed against {chosen} -> {out_dir / (entry['id'] + '.diff')}",
        "".join(diff[:40]),
    ]


def test_fixture_root_exists():
    """Fail loudly when the corpus root is wrong, instead of skipping 12 tests.

    Without this, a relocated portfolio turns the whole snapshot suite into a
    silent no-op and the run still reports green. A missing *individual* PDF is
    a legitimate skip (not everyone has the closed-access corpus); a missing
    *root* is a broken configuration and must be visible.
    """
    data = _manifest()
    if not data.get("vibe_relative"):
        pytest.skip("manifest is not vibe-relative")
    assert _VIBE.is_dir(), (
        f"corpus root {_VIBE} does not exist — every fixture would skip and the "
        "suite would report green. Set VIBE_ROOT, or check whether the portfolio "
        "moved (it left ~/Dropbox/Vibe on 2026-08-03)."
    )


def test_no_article_text_in_snapshot_dir():
    """``tests/snapshots/`` holds pins, never publication text.

    This is the guard that did not exist when 12 papers' worth of body text was
    committed here. It is deliberately a shape check on the directory rather
    than a filename denylist: the leaked files were named exactly like ordinary
    fixtures, which is why three filename-based cleanup passes walked past them.
    """
    stray = sorted(
        p.name for p in _SNAPSHOT_DIR.glob("*")
        if p.is_file() and p.name != "checksums.json"
    )
    assert not stray, (
        f"unexpected files in tests/snapshots/: {stray}. This directory holds "
        "checksums.json and nothing else — publication text belongs to "
        "article-finder, never to a project repo (and never to a public one)."
    )


def test_checksums_cover_every_manifest_fixture():
    """Every manifest fixture is pinned, and no pin is orphaned.

    Coverage has to be asserted, not counted at runtime. A gate that verifies
    "whatever it happens to find" reports N/N and passes while N silently
    shrinks — the same defect class as the 24-skipped run this suite shipped
    for four days, and as verify_corpus.py's ``13/13 PASS``.
    """
    ids = {e["id"] for e in _entries()}
    pinned = set(_checksums().get("fixtures", {}))
    assert ids, "MANIFEST.json declares no fixtures"
    missing = sorted(ids - pinned)
    orphan = sorted(pinned - ids)
    assert not missing, (
        f"fixtures with no checksum pin: {missing}. Run "
        "`pytest tests/test_v2_backwards_compat.py --snapshot-update`."
    )
    assert not orphan, (
        f"checksum pins with no manifest fixture: {orphan}. Remove them from "
        "tests/snapshots/checksums.json."
    )


@pytest.mark.parametrize("entry", _entries(), ids=lambda e: e.get("id", "?"))
def test_extract_pdf_byte_identical(entry, request):
    """extract_pdf() output must match its pinned sha256 byte-for-byte."""
    pdf_path = _resolve(entry)
    if not pdf_path.is_file():
        pytest.skip(f"Fixture not available: {entry['id']}")

    from docpluck import extract_pdf
    text, method = extract_pdf(pdf_path.read_bytes())
    sha, size = _digest(text)

    if request.config.getoption("--snapshot-update"):
        _record(entry["id"], sha, size, method)
        pytest.skip(f"Checksum re-pinned: {entry['id']} -> {sha[:12]}…")

    pinned = _checksums().get("fixtures", {}).get(entry["id"])
    assert pinned is not None, (
        f"no checksum pinned for {entry['id']} — run with --snapshot-update "
        "to capture it. (Auto-capturing silently would let a new fixture join "
        "the suite without ever having been verified.)"
    )

    if sha == pinned["sha256"] and method == pinned.get("method", method):
        return

    detail = [f"extract_pdf() drift on {entry['id']}"]
    if sha != pinned["sha256"]:
        detail.append(
            f"  sha256   expected {pinned['sha256']}\n"
            f"           actual   {sha}"
        )
        detail.append(
            f"  bytes    expected {pinned['bytes']}, actual {size} "
            f"(delta {size - pinned['bytes']:+d})"
        )
    if method != pinned.get("method", method):
        detail.append(
            f"  method   expected {pinned.get('method')!r}, actual {method!r}"
        )

    if request.config.getoption("--snapshot-explain"):
        out_dir = _HERE.parent / "tmp" / "snapshots"
        out_dir.mkdir(parents=True, exist_ok=True)
        dump = out_dir / f"{entry['id']}.actual.txt"
        dump.write_text(text, encoding="utf-8")
        detail.append(f"  actual text written to {dump} (gitignored)")
        detail.extend(_explain_against_custodian(entry, text, out_dir))
    else:
        detail.append(
            "  re-run with --snapshot-explain to dump the actual text for a "
            "local diff; --snapshot-update to accept the new output."
        )
    pytest.fail("\n".join(detail))


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
