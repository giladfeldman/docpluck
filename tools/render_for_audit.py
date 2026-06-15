"""Stable CLI for rendering a single docpluck canary paper at current library HEAD.

Used by `~/.claude/skills/_shared/iterate-loop/canary-audit.sh` to produce the
artifact the audit subagent compares against the AI gold.

This file is the STABLE entry point. The ad-hoc tmp/render_canary_cycle1.py is
deprecated; do not use it from new scripts (it hard-codes a 5-paper DOI list
and a cycle-N output dir, neither of which generalize).

Locates the PDF via article-finder ONLY (per memory feedback_paper_locating_via_article_finder
+ iterate-loop rule I9). Never reads PDFs from project-local test-pdfs/ or any
filesystem path other than what article-finder returns.

Usage:
    python tools/render_for_audit.py --key <DOI> --out <output-path>

Exit codes:
    0  - rendered successfully
    1  - article-finder cache-check failed (PDF not in repository)
    2  - docpluck render raised an exception
    3  - usage error
    4  - input-feed provenance mismatch (rec R-0003: located PDF sha != pinned/expected)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

# --- argparse first so --help works even if docpluck import fails ----------

parser = argparse.ArgumentParser(
    description="Render a single canary paper for audit (stable entry point)."
)
parser.add_argument("--key", required=True, help="Canonical key (DOI for docpluck papers)")
parser.add_argument("--out", required=True, help="Output .md path (will be created/overwritten)")
parser.add_argument(
    "--manifest",
    default=None,
    help="Optional path to write a per-render manifest JSON (pdf_sha, rendered_sha, elapsed_s, library_version)",
)
parser.add_argument(
    "--quiet",
    action="store_true",
    help="Suppress per-step stdout (errors still go to stderr)",
)
parser.add_argument(
    "--expected-sha",
    default=None,
    help=(
        "Expected sha256 of the input PDF (input-feed provenance gate, rec "
        "R-0003). If omitted, falls back to canary.json's expected_pdf_sha for "
        "--key. On mismatch the render aborts with exit 4 BEFORE scoring, so a "
        "drifted input PDF can never be silently scored against a gold made "
        "from the original."
    ),
)
args = parser.parse_args()


def _log(msg: str) -> None:
    if not args.quiet:
        print(msg)


# --- locate PDF via article-finder (I9 compliance) -------------------------

AF_CACHE_CHECK = Path.home() / ".claude" / "skills" / "article-finder" / "cache-check.py"

if not AF_CACHE_CHECK.exists():
    print(
        f"ERROR: article-finder not found at {AF_CACHE_CHECK}. "
        "Cannot locate PDF — direct filesystem reads forbidden by I9.",
        file=sys.stderr,
    )
    sys.exit(1)


def locate_pdf_via_article_finder(key: str) -> Path:
    """Locate the PDF for a given key via article-finder cache-check. Never direct filesystem."""
    proc = subprocess.run(
        [sys.executable, str(AF_CACHE_CHECK), key],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"article-finder cache-check exited {proc.returncode} for {key}: "
            f"stderr={proc.stderr.strip()}"
        )
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        raise RuntimeError(
            f"article-finder cache-check produced non-JSON output for {key}: "
            f"{proc.stdout[:200]!r} (err: {e})"
        )
    if not data.get("found"):
        raise RuntimeError(
            f"article-finder cache-check says NOT FOUND for {key}: {data}. "
            "Paper may not be onboarded yet."
        )
    path = Path(data["path"])
    if not path.exists():
        raise RuntimeError(
            f"article-finder returned path {path} but the file does not exist on disk."
        )
    return path


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


# --- render through docpluck HEAD -----------------------------------------

try:
    import docpluck  # noqa: E402
    from docpluck.render import render_pdf_to_markdown  # noqa: E402
except ImportError as e:
    print(
        f"ERROR: cannot import docpluck. Is the library installed in the current Python env? {e}",
        file=sys.stderr,
    )
    sys.exit(2)

t0 = time.time()
try:
    pdf_path = locate_pdf_via_article_finder(args.key)
except RuntimeError as e:
    print(f"ERROR locating PDF: {e}", file=sys.stderr)
    sys.exit(1)

_log(f"docpluck version: {docpluck.__version__}")
_log(f"PDF located via article-finder: {pdf_path}")

pdf_bytes = pdf_path.read_bytes()
pdf_sha = sha256_bytes(pdf_bytes)
_log(f"PDF sha256: {pdf_sha}")

# --- input-feed provenance gate (rec R-0003) ------------------------------
# The verification substrate (the PDF we are about to render + score) must be
# byte-equal to the canonical production input feed. The expected sha comes
# from --expected-sha, or failing that from canary.json's expected_pdf_sha for
# this key. Un-pinned keys are a no-op (additive guard). On mismatch we abort
# with exit 4 BEFORE rendering, so a drifted PDF is never silently scored
# against a gold generated from the original input.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from canary_provenance import check_provenance, load_expected_sha  # noqa: E402

_canary_json = (
    Path(__file__).resolve().parents[1] / ".claude" / "skills" / "_project" / "canary.json"
)
expected_sha = args.expected_sha or load_expected_sha(str(_canary_json), args.key)
_prov_ok, _prov_msg = check_provenance(args.key, pdf_sha, expected_sha)
if not _prov_ok:
    print(_prov_msg, file=sys.stderr)
    sys.exit(4)
if expected_sha:
    _log(f"provenance OK: input PDF matches pinned sha for {args.key}")

try:
    md = render_pdf_to_markdown(pdf_bytes)
except Exception as e:  # noqa: BLE001 - we want to surface everything the library raises
    print(f"ERROR docpluck.render raised {type(e).__name__}: {e}", file=sys.stderr)
    sys.exit(2)

out_path = Path(args.out)
out_path.parent.mkdir(parents=True, exist_ok=True)
out_path.write_text(md, encoding="utf-8")
rendered_sha = sha256_bytes(md.encode("utf-8"))
elapsed = round(time.time() - t0, 2)

_log(f"rendered {len(md):,} chars in {elapsed:.2f}s -> {out_path}")
_log(f"rendered sha256: {rendered_sha}")

# --- manifest -------------------------------------------------------------

manifest = {
    "key": args.key,
    "library_version": docpluck.__version__,
    "pdf_path": str(pdf_path),
    "pdf_sha": pdf_sha,
    "expected_pdf_sha": expected_sha or "",
    "provenance_ok": True,
    "rendered_path": str(out_path),
    "rendered_sha": rendered_sha,
    "rendered_bytes": len(md.encode("utf-8")),
    "elapsed_s": elapsed,
    "locator_via": "cache-check",
    "rendered_at_unix": int(time.time()),
}

if args.manifest:
    manifest_path = Path(args.manifest)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    _log(f"manifest: {manifest_path}")

# Always echo the manifest as the last stdout line so callers can capture it.
# (The orchestrator script reads stdout's last JSON line to get rendered_sha etc.)
print(json.dumps(manifest))
