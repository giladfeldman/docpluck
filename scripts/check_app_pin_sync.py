#!/usr/bin/env python3
"""Cross-repo version-sync gate: docpluck library <-> docpluckapp service pin.

The app (giladfeldman/docpluckapp) imports the library via a git pin in
``service/requirements.txt``::

    docpluck[all] @ git+https://github.com/giladfeldman/docpluck.git@v<VERSION>

That pin MUST always equal the latest *released* library tag, or production
silently keeps running the old library.

**This script is now the ONLY mechanism that maintains the pin.** The
``bump-app-pin.yml`` GitHub Actions workflow that used to do it was DELETED on
2026-08-20 — the owner does not and will not pay for GitHub Actions, and the
workflow had just proved its own fragility: a history purge force-pushed tags
v2.4.134 and v2.4.135 together, both runs fired, the OLDER one finished one
second later and won, and production was silently downgraded.

So the bump is local, explicit and ordered:

* ``--check`` (default) VERIFIES the pin — the gate every docpluck-* skill runs.
* ``--fix`` PERFORMS the bump, commits it to the app repo, and refuses to move
  the pin BACKWARDS. Run it after tagging a release.

A local script beats a workflow here for the reason the incident showed: it runs
in a known order, on demand, with the result visible immediately — rather than
in a race between two runners whose finish order nobody controls.

Authoritative source of truth for the app pin is docpluckapp **origin/master**
(that is what Railway deploys), NOT the local working-tree file — a stale local
clone shows an old pin even when production is correctly synced. The script
fetches origin/master and reads the pin from there; it falls back to the local
working tree only when the remote is unreachable, and says so loudly.

Exit code 0 = in sync; 1 = mismatch (a release defect to fix now); 2 = could
not determine (treat as FAIL in CI/skills, never as PASS).

Usage::

    python scripts/check_app_pin_sync.py            # normal gate (verify only)
    python scripts/check_app_pin_sync.py --fix     # bump + commit the app pin
    python scripts/check_app_pin_sync.py --fix --push   # ...and push to master
    python scripts/check_app_pin_sync.py --app-repo /path/to/PDFextractor
    python scripts/check_app_pin_sync.py --allow-local-fallback   # offline dev
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
from pathlib import Path

# docpluckapp service/requirements.txt pin line, e.g.
#   docpluck[all] @ git+https://github.com/giladfeldman/docpluck.git@v2.4.95
_PIN_RE = re.compile(
    r"docpluck\[all\]\s*@\s*git\+https://github\.com/giladfeldman/docpluck\.git@v?(\d+\.\d+\.\d+)"
)
_VERSION_RE = re.compile(r"""^__version__\s*=\s*["'](\d+\.\d+\.\d+)["']""", re.M)
_TAG_RE = re.compile(r"^v(\d+\.\d+\.\d+)$")


def _vtuple(v: str) -> tuple[int, ...]:
    """Parse a dotted version string into an int tuple for ordered comparison.

    Non-numeric / malformed components sort as ``-1`` so a garbage version never
    silently compares *higher* than a real one.
    """
    parts: list[int] = []
    for p in (v or "").split("."):
        try:
            parts.append(int(p))
        except ValueError:
            parts.append(-1)
    return tuple(parts)


def compare(latest_tag: str | None, app_pin: str | None, lib_version: str | None) -> tuple[bool, str]:
    """Pure decision core (kept import-friendly so both branches are unit-testable).

    Returns ``(ok, message)``. ``ok`` is True only when the app pin equals the
    latest released library tag. An unreleased working-tree ``__version__``
    (ahead of the latest tag) is reported but does NOT fail the gate — the pin
    legitimately tracks the latest *release* until that version is tagged.

    The working-tree note is DIRECTION-AWARE (fixed 2026-06-25): it must compare
    versions as ordered tuples, not merely ``!=``. The pre-fix code said
    "working-tree X is ahead of latest tag Y -- UNRELEASED. Tag + push X" for
    *any* inequality, so a tree that is BEHIND its own latest tag (e.g. a stale
    2.4.95 working copy while v2.4.97 is the latest release — a real state hit
    during a branch-reconciliation) got told it was "ahead" and advised to tag an
    OLDER version. That advice is actively harmful. Now: ahead → UNRELEASED-tag
    hint; behind → loud stale-working-tree warning; equal → no note.
    """
    if not latest_tag:
        return False, "could not determine the library's latest v* tag"
    if not app_pin:
        return False, "could not parse the docpluck pin from app service/requirements.txt"

    if app_pin != latest_tag:
        return False, (
            f"MISMATCH: app pin v{app_pin} != latest library tag v{latest_tag}. "
            "Nothing bumps this automatically (there is no CI). Fix it with:\n"
            "    python scripts/check_app_pin_sync.py --fix --push"
        )

    msg = f"in sync: app pin v{app_pin} == latest library tag v{latest_tag}"
    if lib_version and lib_version != latest_tag:
        if _vtuple(lib_version) > _vtuple(latest_tag):
            msg += (
                f"  [note: working-tree __version__ {lib_version} is ahead of the latest "
                f"tag v{latest_tag} -- UNRELEASED. Tag + push v{lib_version} so the app "
                f"auto-bumps to it.]"
            )
        else:
            msg += (
                f"  [WARNING: working-tree __version__ {lib_version} is BEHIND the latest "
                f"tag v{latest_tag} -- the checkout is stale relative to the release. The "
                f"app pin (v{app_pin}) correctly tracks the release; fast-forward / checkout "
                f"v{latest_tag} before iterating so you don't re-do or collide with shipped work.]"
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


def default_app_repo() -> Path | None:
    """Locate the consumer application checkout STRUCTURALLY, never by name.

    Resolved in ONE place and shared by this script's `main` and by the mirror
    regression test, so a path convention cannot drift between two copies of it.

    It looks for a sibling directory of this repo that holds a
    ``service/requirements.txt`` carrying a docpluck pin -- a property of the
    thing we need, not a directory name. That is deliberate on two counts. This
    repo is PUBLIC, so a hardcoded sibling name would publish the private
    consumer's layout; and a name is the more fragile key anyway, since renaming
    or relocating the checkout would silently send this gate somewhere that does
    not exist. ``$DOCPLUCK_APP_REPO`` overrides, and ``--app-repo`` beats both.

    Returns None when nothing matches, so the caller can say so rather than
    proceed against a path that is merely absent.
    """
    override = os.environ.get("DOCPLUCK_APP_REPO")
    if override:
        return Path(override).expanduser().resolve()

    lib_repo = Path(__file__).resolve().parent.parent
    for sibling in sorted(lib_repo.parent.iterdir()):
        if sibling == lib_repo or not sibling.is_dir():
            continue
        req = sibling / "service" / "requirements.txt"
        try:
            if req.is_file() and _PIN_RE.search(req.read_text(encoding="utf-8")):
                return sibling
        except OSError:
            continue
    return None


def apply_fix(app_repo: Path, latest_tag: str, current_pin: str | None, push: bool) -> int:
    """Bump the app pin to ``latest_tag``, commit it, optionally push.

    REFUSES TO MOVE THE PIN BACKWARDS. This is the guard the deleted
    ``bump-app-pin.yml`` never had: on 2026-08-20 a history purge force-pushed
    v2.4.134 and v2.4.135 together, both workflow runs fired, and the OLDER tag
    finished one second later (14:56:57 vs 14:56:56) and won — silently
    downgrading production. Nothing failed; only this script noticed.
    """
    req = app_repo / "service" / "requirements.txt"
    if not req.exists():
        print(f"FAIL: {req} not found")
        return 2

    if current_pin and _vtuple(latest_tag) < _vtuple(current_pin):
        print(
            f"REFUSING to bump BACKWARDS: pin is v{current_pin}, latest tag is "
            f"v{latest_tag}. If you really mean to downgrade, edit the pin by hand "
            "and say why in the commit message."
        )
        return 1
    if current_pin and _vtuple(latest_tag) == _vtuple(current_pin):
        print(f"already pinned to v{latest_tag} — nothing to do")
        return 0

    text = req.read_text(encoding="utf-8")
    new_text, n = _PIN_RE.subn(
        f"docpluck[all] @ git+https://github.com/giladfeldman/docpluck.git@v{latest_tag}",
        text,
    )
    if n == 0:
        print(f"FAIL: no docpluck pin line found in {req}")
        return 2
    req.write_text(new_text, encoding="utf-8")
    print(f"bumped v{current_pin or '?'} -> v{latest_tag} in {req}")

    # THE MIRROR IS PART OF THE PIN, NOT A SEPARATE CHORE. `cd frontend &&
    # vercel --prod` uploads ONLY frontend/, so that build cannot read
    # ../service/requirements.txt and falls back to frontend/docpluck-pin.json;
    # without it, it falls back further to the hand-maintained DOCPLUCK_VERSION
    # env var -- the 50-day-stale failure the derivation was built to remove.
    # Until 2026-09-08 this function staged requirements.txt ALONE, so every
    # --fix run left the mirror behind and pushed a red master: that is exactly
    # how 54c9a31 bumped to v2.4.138 and stranded the mirror at 2.4.137, a drift
    # nobody noticed until a QA session went looking an hour before the 2.4.141
    # release. Reported by the peer session and VERIFIED HERE at the
    # source before acting on it.
    #
    # It calls the EXISTING generator rather than writing the JSON here: one
    # concept, one implementation. A second copy of the mirror format in Python
    # would drift from the Node one silently, which is the failure this repo's
    # "ONE CONCEPT, ONE TABLE" rule exists to prevent.
    #
    # A missing `node` is a HARD FAILURE, never a skip. Skipping is precisely
    # the current defect wearing a green tick, and the commit would then push a
    # master whose own tests fail.
    mirror_rel = "frontend/docpluck-pin.json"
    gen = app_repo / "frontend" / "scripts" / "sync-docpluck-pin.mjs"
    if not gen.exists():
        print(f"FAIL: {gen} not found — cannot refresh {mirror_rel}")
        return 2
    try:
        r = subprocess.run(
            ["node", str(gen)],
            cwd=str(app_repo / "frontend"),
            capture_output=True, text=True,
        )
    except FileNotFoundError:
        print(f"FAIL: `node` not on PATH — cannot refresh {mirror_rel}. The pin "
              "and its mirror move together or not at all; requirements.txt has "
              "been rewritten but NOTHING was committed.")
        return 2
    if r.returncode != 0:
        print(f"FAIL: {gen.name} exited {r.returncode}: {(r.stderr or r.stdout).strip()}")
        return 2
    print((r.stdout or "").strip() or f"refreshed {mirror_rel}")

    if _git(app_repo, "add", "service/requirements.txt", mirror_rel) is None:
        print("FAIL: git add failed")
        return 2
    msg = "\n".join(
        [
            f"pin: bump docpluck library to v{latest_tag}",
            "",
            "service/requirements.txt AND frontend/docpluck-pin.json, together --",
            "a frontend-only `vercel --prod` build cannot read requirements.txt and",
            "falls back to the mirror. Staging only requirements.txt is what left",
            "the mirror at 2.4.137 against a v2.4.138 pin.",
            "",
            "Applied by scripts/check_app_pin_sync.py --fix in the library repo.",
            "This replaces the deleted bump-app-pin.yml GitHub Actions workflow —",
            "the owner does not pay for Actions, and the workflow had no",
            "newer-than-current guard, so a re-pushed old tag could (and did)",
            "downgrade production.",
        ]
    )
    if _git(app_repo, "commit", "-m", msg) is None:
        print("FAIL: git commit failed (nothing staged?)")
        return 2
    print("committed to the app repo")

    if push:
        if _git(app_repo, "push", "origin", "HEAD:master") is None:
            print("FAIL: git push failed — commit is local; push it yourself")
            return 1
        print("pushed to docpluckapp master (Railway will redeploy)")
    else:
        print("NOT pushed (use --push, or push from the app repo yourself)")
    return 0


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
    parser.add_argument(
        "--fix",
        action="store_true",
        help="Bump the app pin to the latest released tag and commit it. "
        "Refuses to move the pin backwards.",
    )
    parser.add_argument(
        "--push",
        action="store_true",
        help="With --fix, also push the app repo to origin/master.",
    )
    args = parser.parse_args(argv)

    lib_repo = Path(__file__).resolve().parent.parent
    app_repo = args.app_repo or default_app_repo()

    if app_repo is None:
        print("FAIL: no sibling checkout carries a service/requirements.txt with a "
              "docpluck pin. Point at it with --app-repo or $DOCPLUCK_APP_REPO.")
        return 2
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

    if ok or not args.fix:
        return 0 if ok else 1

    if not latest_tag:
        print("FAIL: no released tag to bump to")
        return 2
    print()
    return apply_fix(app_repo, latest_tag, app_pin, args.push)


if __name__ == "__main__":
    raise SystemExit(main())
