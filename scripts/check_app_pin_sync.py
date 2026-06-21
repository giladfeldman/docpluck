#!/usr/bin/env python3
"""Cross-repo version-sync gate: docpluck library <-> docpluckapp service pin.

The app (giladfeldman/docpluckapp) imports the library via a git pin in
``service/requirements.txt``::

    docpluck[all] @ git+https://github.com/giladfeldman/docpluck.git@v<VERSION>

That pin MUST always equal the latest *released* library tag, or production
silently keeps running the old library. A ``bump-app-pin.yml`` workflow in the
library repo auto-commits the bump on every ``v*.*.*`` tag push, but it is
*best-effort*: a token expiry, an Actions outage, or a regex drift can let it
miss silently. This script is the deterministic backstop that every
docpluck-* skill (qa / review / deploy) runs to VERIFY the bump actually landed.

Authoritative source of truth for the app pin is docpluckapp **origin/master**
(that is what Railway deploys), NOT the local working-tree file — a stale local
clone shows an old pin even when production is correctly synced. The script
fetches origin/master and reads the pin from there; it falls back to the local
working tree only when the remote is unreachable, and says so loudly.

Exit code 0 = in sync; 1 = mismatch (a release defect to fix now); 2 = could
not determine (treat as FAIL in CI/skills, never as PASS).

Usage::

    python scripts/check_app_pin_sync.py            # normal gate
    python scripts/check_app_pin_sync.py --app-repo /path/to/PDFextractor
    python scripts/check_app_pin_sync.py --allow-local-fallback   # offline dev
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

# docpluckapp service/requirements.txt pin line, e.g.
#   docpluck[all] @ git+https://github.com/giladfeldman/docpluck.git@v2.4.95
_PIN_RE = re.compile(
    r"docpluck\[all\]\s*@\s*git\+https://github\.com/giladfeldman/docpluck\.git@v?(\d+\.\d+\.\d+)"
)
_VERSION_RE = re.compile(r"""^__version__\s*=\s*["'](\d+\.\d+\.\d+)["']""", re.M)
_TAG_RE = re.compile(r"^v(\d+\.\d+\.\d+)$")


def compare(latest_tag: str | None, app_pin: str | None, lib_version: str | None) -> tuple[bool, str]:
    """Pure decision core (kept import-friendly so both branches are unit-testable).

    Returns ``(ok, message)``. ``ok`` is True only when the app pin equals the
    latest released library tag. An unreleased working-tree ``__version__``
    (ahead of the latest tag) is reported but does NOT fail the gate — the pin
    legitimately tracks the latest *release* until that version is tagged.
    """
    if not latest_tag:
        return False, "could not determine the library's latest v* tag"
    if not app_pin:
        return False, "could not parse the docpluck pin from app service/requirements.txt"

    if app_pin != latest_tag:
        return False, (
            f"MISMATCH: app pin v{app_pin} != latest library tag v{latest_tag}. "
            f"The bump-app-pin workflow did not land v{latest_tag} on docpluckapp "
            f"origin/master. Recover by re-pushing the tag (re-fires the workflow) "
            f"or hand-bump service/requirements.txt to @v{latest_tag} and push to master."
        )

    msg = f"in sync: app pin v{app_pin} == latest library tag v{latest_tag}"
    if lib_version and lib_version != latest_tag:
        msg += (
            f"  [note: working-tree __version__ {lib_version} is ahead of the latest "
            f"tag v{latest_tag} -- UNRELEASED. Tag + push v{lib_version} so the app "
            f"auto-bumps to it.]"
        )
    return True, msg


def _git(cwd: Path, *args: str) -> str | None:
    try:
        out = subprocess.run(
            ["git", "-C", str(cwd), *args],
            capture_output=True, text=True, timeout=60,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    return out.stdout.strip()


def _latest_tag(repo: Path) -> str | None:
    out = _git(repo, "tag", "--sort=-v:refname")
    if not out:
        return None
    for line in out.splitlines():
        m = _TAG_RE.match(line.strip())
        if m:
            return m.group(1)
    return None


def _lib_version(repo: Path) -> str | None:
    init = repo / "docpluck" / "__init__.py"
    try:
        m = _VERSION_RE.search(init.read_text(encoding="utf-8"))
    except OSError:
        return None
    return m.group(1) if m else None


def _app_pin(app_repo: Path, allow_local_fallback: bool) -> tuple[str | None, str]:
    """Return (pin_version, source_description). Prefers origin/master."""
    rel = "service/requirements.txt"
    # Authoritative: docpluckapp origin/master (what Railway deploys).
    _git(app_repo, "fetch", "origin", "--quiet")
    remote = _git(app_repo, "show", f"origin/master:{rel}")
    if remote:
        m = _PIN_RE.search(remote)
        if m:
            return m.group(1), "docpluckapp origin/master (production-authoritative)"

    # Fallback: local working tree — may be stale; only with explicit opt-in.
    local_file = app_repo / "service" / "requirements.txt"
    try:
        text = local_file.read_text(encoding="utf-8")
    except OSError:
        return None, f"unreadable: {local_file}"
    m = _PIN_RE.search(text)
    if not m:
        return None, f"no docpluck pin found in {local_file}"
    if not allow_local_fallback:
        return None, (
            "could not read origin/master (offline?) and --allow-local-fallback "
            "not set; refusing to trust a possibly-stale local clone"
        )
    return m.group(1), f"LOCAL WORKING TREE {local_file} (may be stale -- could not reach origin/master)"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--app-repo",
        type=Path,
        default=None,
        help="Path to the docpluckapp (PDFextractor) checkout. "
        "Default: sibling ../PDFextractor of this library repo.",
    )
    parser.add_argument(
        "--allow-local-fallback",
        action="store_true",
        help="If origin/master is unreachable, fall back to the local "
        "working-tree pin (offline dev only; prints a stale-clone warning).",
    )
    args = parser.parse_args(argv)

    lib_repo = Path(__file__).resolve().parent.parent
    app_repo = args.app_repo or (lib_repo.parent / "PDFextractor")

    if not (app_repo / "service" / "requirements.txt").exists() and not (app_repo / ".git").exists():
        print(f"FAIL: app repo not found at {app_repo} (use --app-repo)")
        return 2

    lib_version = _lib_version(lib_repo)
    latest_tag = _latest_tag(lib_repo)
    app_pin, pin_source = _app_pin(app_repo, args.allow_local_fallback)

    print(f"library __version__ (working tree): {lib_version or '?'}")
    print(f"library latest released tag:        v{latest_tag or '?'}")
    print(f"app pin:                            v{app_pin or '?'}  [{pin_source}]")

    if app_pin is None:
        print(f"INCONCLUSIVE: {pin_source}")
        return 2

    ok, message = compare(latest_tag, app_pin, lib_version)
    print(("PASS: " if ok else "FAIL: ") + message)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
