"""Build a released tag and upload it to PyPI, reading the upload token from .env.local.

Usage (from the repo root):
    python scripts/publish_pypi.py v2.4.161            # build, check, upload
    python scripts/publish_pypi.py v2.4.161 --dry-run  # build and check only

The token lives in a gitignored file at the repo root, .env.local (read first) or .env, one line:
    PYPI_TOKEN=pypi-...
The script never prints it. It is passed to twine through the environment of the
upload process only.

What it does, in order, and stops at the first failure:
1. Refuses if the token file is not ignored by git (a token must never be committable).
2. Exports the TAG (git archive), not the working folder, into a temporary
   directory, so uncommitted edits can never reach PyPI.
3. Checks that the version inside the tag equals the tag name.
4. Refuses if PyPI already has that version (PyPI never accepts a re-upload).
5. Builds the sdist and wheel, runs `twine check`.
6. Uploads, then reads PyPI back until it lists the version.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENV_FILES = (ROOT / ".env.local", ROOT / ".env")
ENV_FILE = ENV_FILES[0]
TOKEN_KEY = "PYPI_TOKEN"
PYPI_JSON = "https://pypi.org/pypi/docpluck/json"


def read_token(env_file: Path = ENV_FILE) -> str:
    """Return PYPI_TOKEN from env_file; raise SystemExit with a plain message if absent."""
    if not env_file.is_file():
        raise SystemExit(
            f"No {env_file.name} found at {env_file}. Create it with one line:\n"
            f"    {TOKEN_KEY}=pypi-...   (your PyPI API token)")
    for raw in env_file.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.strip() == TOKEN_KEY:
            value = value.strip().strip('"').strip("'")
            if not value.startswith("pypi-"):
                raise SystemExit(f"{TOKEN_KEY} in {env_file.name} does not start with 'pypi-'.")
            return value
    raise SystemExit(f"{env_file.name} has no {TOKEN_KEY}=... line.")


def env_file_is_ignored(env_file: Path = ENV_FILE) -> bool:
    r = subprocess.run(["git", "check-ignore", "-q", str(env_file)], cwd=ROOT)
    return r.returncode == 0


def pypi_versions() -> set[str]:
    with urllib.request.urlopen(PYPI_JSON, timeout=30) as resp:
        return set(json.load(resp)["releases"])


def export_tag(tag: str, dest: Path) -> None:
    archive = dest / "src.tar"
    subprocess.run(["git", "archive", "--format=tar", "-o", str(archive), tag], cwd=ROOT, check=True)
    src = dest / "src"
    src.mkdir()
    with tarfile.open(archive) as tf:
        tf.extractall(src, filter="data")


def version_in(src: Path) -> str:
    text = (src / "pyproject.toml").read_text(encoding="utf-8")
    m = re.search(r'^version\s*=\s*"([^"]+)"', text, re.M)
    if not m:
        raise SystemExit("No version line in the tag's pyproject.toml.")
    return m.group(1)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("tag", help="the release tag, e.g. v2.4.161")
    ap.add_argument("--dry-run", action="store_true", help="build and check only; no upload")
    args = ap.parse_args(argv)

    env_file = next((f for f in ENV_FILES if f.is_file()), ENV_FILE)
    if not env_file_is_ignored(env_file):
        raise SystemExit(f"REFUSING: {env_file.name} is not ignored by git. Add it to .gitignore first.")
    token = None if args.dry_run else read_token(env_file)

    want = args.tag.lstrip("v")
    if want in pypi_versions():
        print(f"PyPI already has docpluck {want}; nothing to do.")
        return 0

    with tempfile.TemporaryDirectory(prefix="docpluck-publish-") as tmp:
        tmpd = Path(tmp)
        export_tag(args.tag, tmpd)
        src, dist = tmpd / "src", tmpd / "dist"
        got = version_in(src)
        if got != want:
            raise SystemExit(f"Tag {args.tag} holds version {got}, not {want}.")
        subprocess.run([sys.executable, "-m", "build", "--outdir", str(dist)], cwd=src, check=True)
        files = sorted(str(p) for p in dist.iterdir())
        subprocess.run([sys.executable, "-m", "twine", "check", *files], check=True)
        if args.dry_run:
            print(f"DRY RUN OK: built and checked {len(files)} file(s) for {want}; nothing uploaded.")
            return 0
        env = {**os.environ, "TWINE_USERNAME": "__token__", "TWINE_PASSWORD": token,
               "TWINE_NON_INTERACTIVE": "1"}
        subprocess.run([sys.executable, "-m", "twine", "upload", *files], env=env, check=True)

    for _ in range(12):
        if want in pypi_versions():
            print(f"PUBLISHED: PyPI lists docpluck {want}.")
            return 0
        time.sleep(10)
    print(f"Uploaded, but PyPI does not list {want} yet after 2 minutes; check {PYPI_JSON}.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
