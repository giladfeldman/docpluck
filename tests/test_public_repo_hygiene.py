"""This repo is PUBLIC. Assert it, on every test run.

Found by /docpluck-cleanup on 2026-08-20: `tests/test_docx_omml_statistics_survive.py`
carried an absolute `<home>/Vibe/MetaScienceTools/CitationGuard/...` path, twice.
That is three defects braided into one string literal:

  1. an absolute local user path in a PUBLIC repo — the exact class the
     2026-08-06 purge of 259 files existed to remove;
  2. the name and internal directory layout of a DIFFERENT, PRIVATE project;
  3. a path that resolves on exactly one machine, so everywhere else the tests
     it gated SKIPPED SILENTLY and the suite read as green. ("A skipped test is
     a coverage hole wearing a green tick.")

It survived because the check for it lived only in a cleanup SKILL — a grep a
human runs when they remember to run it. Section 0.3 of `/docpluck-cleanup` had
in fact passed over this file before.

So the check lives here now, where it runs on every `pytest`. A rule enforced by
a checklist is enforced whenever someone reads the checklist; a rule enforced by
a test is enforced always.

Watched RED before the fix: with the two literals restored, both tests below
name the file.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent

# An absolute path into a real user's home directory. `~/...` and `<home>/...`
# are fine — they are portable, and the comments that explain WHY not to
# hardcode a root are worth keeping.
ABSOLUTE_USER_PATH = re.compile(
    r"""(?x)
    [A-Za-z]:[/\\]{1,2}Users[/\\]{1,2}[A-Za-z0-9._-]+   # C:/Users/<name>
  | /home/[a-z][a-z0-9._-]*/                            # /home/<name>/
  | /Users/[A-Za-z0-9._-]+/                             # macOS /Users/<name>/
    """
)

# Files where a historical absolute path is part of the record, not a live
# instruction. Each is a deliberate exemption, not a convenience.
EXEMPT = {
    # The incident log and the rules file quote old paths when explaining what
    # went wrong; removing the quote removes the reason.
    "LESSONS.md",
    "CLAUDE.md",
    # A historical changelog entry describing a path that WAS wrong and was
    # fixed. Rewriting shipped history to look tidier is its own defect.
    "CHANGELOG.md",
}


def _tracked_text_files() -> list[Path]:
    out = subprocess.run(
        ["git", "ls-files"], cwd=REPO, capture_output=True, text=True, check=True
    ).stdout.splitlines()
    files = []
    for rel in out:
        if rel in EXEMPT:
            continue
        p = REPO / rel
        if not p.is_file():
            continue
        if p.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".pdf", ".ico", ".zip"}:
            continue
        files.append(p)
    return files


def test_no_absolute_user_path_in_any_tracked_file():
    """A public repo must not print a real person's home directory."""
    offenders: list[str] = []
    for path in _tracked_text_files():
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for lineno, line in enumerate(text.splitlines(), 1):
            m = ABSOLUTE_USER_PATH.search(line)
            if m:
                rel = path.relative_to(REPO).as_posix()
                offenders.append(f"{rel}:{lineno}: {m.group(0)}")

    assert not offenders, (
        "absolute local paths in a PUBLIC repo — resolve the root instead "
        "(`os.environ.get('VIBE_ROOT') or Path.home() / 'Vibe'`), per the "
        "portfolio rule 'never hardcode the Vibe root':\n  "
        + "\n  ".join(offenders)
    )


def test_no_sibling_private_project_paths_in_tracked_source():
    """Naming a sibling PRIVATE project's internal layout is its own leak.

    Referring to a sibling corpus is legitimate — tests do it to find fixtures.
    Hardcoding *where it lives on one machine* is not.
    """
    offenders: list[str] = []
    pattern = re.compile(
        r"""(?x)
        [A-Za-z]:[/\\]{1,2}Users .* (CitationGuard|ESCIcheck|MetaESCI|ScienceArena|PDFextractor)
      | /home/[a-z]+/ .* (CitationGuard|ESCIcheck|MetaESCI|ScienceArena|PDFextractor)
        """
    )
    for path in _tracked_text_files():
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for lineno, line in enumerate(text.splitlines(), 1):
            if pattern.search(line):
                offenders.append(f"{path.relative_to(REPO).as_posix()}:{lineno}")

    assert not offenders, (
        "a PUBLIC file hardcodes the on-disk location of a PRIVATE sibling "
        "project:\n  " + "\n  ".join(offenders)
    )


@pytest.mark.parametrize(
    "secret_pattern",
    [
        r"dp_[A-Za-z0-9]{12,}",
        r"ghp_[A-Za-z0-9]{20,}",
        r"sk-[A-Za-z0-9]{16,}",
        r"AKIA[0-9A-Z]{16}",
        r"postgres(ql)?://[^\s\"']*:[^\s\"']*@",
    ],
)
def test_no_secret_values_in_tracked_files(secret_pattern: str):
    """An env-var NAME in a runbook is fine. A VALUE is a rotate-everything event."""
    rx = re.compile(secret_pattern)
    offenders: list[str] = []
    for path in _tracked_text_files():
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for lineno, line in enumerate(text.splitlines(), 1):
            if rx.search(line):
                offenders.append(f"{path.relative_to(REPO).as_posix()}:{lineno}")
    assert not offenders, (
        f"possible secret VALUE matching {secret_pattern!r} — if real, ROTATE it; "
        "a history purge does not un-leak a key that was public:\n  "
        + "\n  ".join(offenders)
    )


# ── The allowlist, inverted — the actual guard ────────────────────────────
#
# A DENYLIST of internal filename prefixes can only ever cover the naming
# conventions someone already thought of. It has now failed three times:
#
#   2026-08-06  259 internal files public — three cleanup passes had walked by
#   2026-08-07  INBOX_*/OUTBOX_* were missing from the prefix list
#   2026-08-20  INVENTORY_* and *_REGISTER.md were missing from the prefix list
#
# Each time the remedy was "add the prefix we just learned about", and each time
# the next new name walked straight through. So this test asks the INVERSE
# question — what is ALLOWED to be public? — and fails on anything else,
# whatever it is called.
#
# The allowlist below is the same one `/docpluck-cleanup` Section 0 carries. The
# difference that matters: a skill's grep runs when a human remembers to run it,
# and this runs on every `pytest`.

ALLOWED_DIRECTORY_PREFIXES = (
    "docpluck/",          # the library
    "tests/",             # its tests
    "scripts/",           # supporting tooling
    "tools/",             # diagnostics
    ".github/workflows/", # CI
)

ALLOWED_ROOT_FILES = {
    "README.md",
    "LICENSE",
    "CHANGELOG.md",
    "pyproject.toml",
    ".gitignore",
    # Public by explicit owner decision, 2026-08-06.
    "CLAUDE.md",
    "LESSONS.md",
}

ALLOWED_DOCS = {
    "docs/README.md",
    "docs/DESIGN.md",
    "docs/NORMALIZATION.md",
    # Consumer contracts — public BY MANDATE. CLAUDE.md requires the scope
    # statement to be stated in docs/SCOPE.md, and SYMBOL_CONTRACT.md opens
    # "If you maintain a tool that parses docpluck's output, this page is your
    # interface." Removing either breaks a published promise.
    "docs/SCOPE.md",
    "docs/SYMBOL_CONTRACT.md",
}

# `docs/BENCHMARKS*.md` — a family, because benchmark runs are dated.
ALLOWED_DOCS_PATTERN = re.compile(r"^docs/BENCHMARKS[A-Za-z0-9_.-]*\.md$")


def _is_allowed_public(rel: str) -> bool:
    if rel.startswith(ALLOWED_DIRECTORY_PREFIXES):
        return True
    if rel in ALLOWED_ROOT_FILES or rel in ALLOWED_DOCS:
        return True
    return bool(ALLOWED_DOCS_PATTERN.match(rel))


def test_every_tracked_file_is_on_the_public_allowlist():
    """This repo is PUBLIC. Anything tracked is served to the world, forever.

    Adding a genuinely-public file is allowed — it is a deliberate act that
    also updates the allowlist above. Adding one WITHOUT updating the allowlist
    is the defect this test exists to make impossible.

    Watched RED 2026-08-20: it named `docs/OVERHAUL_REGISTER.md` and
    `docs/INVENTORY_2026-08-14_notation_vs_repair.md`.
    """
    tracked = subprocess.run(
        ["git", "ls-files"], cwd=REPO, capture_output=True, text=True, check=True
    ).stdout.splitlines()

    outside = sorted(rel for rel in tracked if rel and not _is_allowed_public(rel))

    assert not outside, (
        "tracked in a PUBLIC repo but not on the allowlist. Either it is "
        "internal — untrack it, add its CATEGORY to .gitignore, and remember "
        "that untracking alone leaves it readable at every past commit and tag "
        "on GitHub — or it is genuinely public, in which case add it to "
        "ALLOWED_DOCS above with the reason:\n  " + "\n  ".join(outside)
    )


def test_the_allowlist_names_only_files_that_exist():
    """A stale allowlist entry silently exempts the next file created at that path."""
    tracked = set(
        subprocess.run(
            ["git", "ls-files"], cwd=REPO, capture_output=True, text=True, check=True
        ).stdout.splitlines()
    )
    stale = sorted(
        p for p in (ALLOWED_ROOT_FILES | ALLOWED_DOCS) if p not in tracked
    )
    assert not stale, f"allowlist entries for files that no longer exist: {stale}"
