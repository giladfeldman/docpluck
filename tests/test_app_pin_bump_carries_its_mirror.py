"""The pin and its frontend mirror move together, or the bump is not done.

WHY THIS EXISTS. `scripts/check_app_pin_sync.py --fix` rewrote
`service/requirements.txt` and then staged that ONE path. `frontend/` also
carries `docpluck-pin.json`, a committed mirror of the same pin, because the
documented CLI deploy is `cd frontend && vercel --prod`, which uploads only
`frontend/` and therefore cannot read `../service/requirements.txt`. Without a
fresh mirror that build falls back to the hand-maintained `DOCPLUCK_VERSION`
env var -- the 50-day-stale failure the derivation was built to remove.

IT HAD ALREADY HAPPENED, WHICH IS WHY THIS IS A TEST AND NOT A COMMENT: commit
`54c9a31` bumped the pin to v2.4.138 and stranded the mirror at 2.4.137, and
nobody noticed until a QA session went looking an hour before the 2.4.141
release. The failure is silent in the library repo and lands as two red tests on
the APP's master (`frontend/src/lib/errors/docpluck-pin.test.ts`) -- a repo whose
suite this project does not run.

Reported 2026-09-08 by two peer sessions, verified
here at the source before acting, and watched RED against the unpatched
`apply_fix` before the fix was written.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import check_app_pin_sync as pin  # noqa: E402

# Resolved through the script's own helper rather than restated here -- this
# test exists because two copies of one fact drifted, so it must not add a third.
REAL_GENERATOR = pin.default_app_repo() / "frontend" / "scripts" / "sync-docpluck-pin.mjs"


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=str(cwd), check=True,
                   capture_output=True, text=True)


@pytest.fixture()
def app_repo(tmp_path: Path) -> Path:
    """A minimal stand-in for the app repo, holding both halves of the pin."""
    if shutil.which("node") is None:
        pytest.skip("node is required: the fix calls the real mirror generator")
    if not REAL_GENERATOR.exists():
        pytest.skip(f"mirror generator not present at {REAL_GENERATOR}")

    repo = tmp_path / "app"
    (repo / "service").mkdir(parents=True)
    (repo / "frontend" / "scripts").mkdir(parents=True)

    (repo / "service" / "requirements.txt").write_text(
        "fastapi\n"
        "docpluck[all] @ git+https://github.com/giladfeldman/docpluck.git@v2.4.138\n",
        encoding="utf-8",
    )
    # THE REAL GENERATOR, not a reimplementation of it. One concept, one
    # implementation: a second copy of the mirror format written for this test
    # would pass while the shipped pair drifted.
    shutil.copy2(REAL_GENERATOR, repo / "frontend" / "scripts" / "sync-docpluck-pin.mjs")
    (repo / "frontend" / "docpluck-pin.json").write_text(
        json.dumps({"pin": "2.4.138"}, indent=2) + "\n", encoding="utf-8")

    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@example.invalid")
    _git(repo, "config", "user.name", "t")
    _git(repo, "config", "commit.gpgsign", "false")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "base")
    return repo


def _head_sha(repo: Path) -> str:
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(repo),
                          check=True, capture_output=True, text=True).stdout.strip()


def _files_in_head(repo: Path) -> set[str]:
    out = subprocess.run(
        ["git", "show", "--pretty=format:", "--name-only", "HEAD"],
        cwd=str(repo), check=True, capture_output=True, text=True).stdout
    return {line.strip().replace("\\", "/") for line in out.splitlines() if line.strip()}


def test_the_bump_commit_carries_BOTH_the_pin_and_its_mirror(app_repo: Path):
    rc = pin.apply_fix(app_repo, "2.4.141", "2.4.138", push=False)
    assert rc == 0, "apply_fix reported failure"

    changed = _files_in_head(app_repo)
    # Positive control first: if requirements.txt is absent the fixture is
    # broken and a missing mirror would mean nothing.
    assert "service/requirements.txt" in changed, (
        "the fixture did not exercise the bump at all -- this assertion is the "
        "control that stops the mirror check below from passing vacuously")
    assert "frontend/docpluck-pin.json" in changed, (
        "the bump commit staged requirements.txt alone and left the mirror "
        "behind. A `cd frontend && vercel --prod` build reads the mirror, not "
        "requirements.txt, so production would deploy against the OLD pin while "
        "the library repo reported the bump as done.")


def test_the_mirror_actually_holds_the_new_version_not_just_a_staged_file(app_repo: Path):
    """Staging the path is not the same as refreshing its contents."""
    assert pin.apply_fix(app_repo, "2.4.141", "2.4.138", push=False) == 0
    mirror = json.loads((app_repo / "frontend" / "docpluck-pin.json").read_text(encoding="utf-8"))
    assert mirror["pin"] == "2.4.141", (
        f"mirror says {mirror['pin']!r}; requirements.txt was bumped to 2.4.141. "
        "A committed-but-stale mirror is worse than an uncommitted one: it looks "
        "synchronised to every later reader.")


def test_a_missing_generator_FAILS_rather_than_skipping_the_mirror(app_repo: Path):
    """The mirror is not optional, so its absence must be loud.

    A silent skip is the original defect wearing a green tick: the commit would
    land, the library repo would print success, and the app's own suite would go
    red on a branch this project never runs.
    """
    before = _head_sha(app_repo)
    (app_repo / "frontend" / "scripts" / "sync-docpluck-pin.mjs").unlink()
    rc = pin.apply_fix(app_repo, "2.4.141", "2.4.138", push=False)
    assert rc != 0, "a missing mirror generator was treated as success"
    # AND NO COMMIT MAY EXIST. The first draft of this assertion asked whether
    # the mirror path appeared in HEAD's file list, which is true of the
    # FIXTURE'S OWN base commit -- it failed against the correct code and would
    # have been "fixed" by weakening the check. Comparing the sha asks the
    # question that was meant: did this call create a commit at all?
    assert _head_sha(app_repo) == before, (
        "a failed bump still wrote a commit -- a half-applied pin is worse than "
        "an unapplied one, because the next reader sees a bump that happened")


# ---------------------------------------------------------------------------
# The resolver itself. It became load-bearing when the hardcoded sibling NAME
# was removed (this repo is public, and a name would publish the private
# consumer's layout), so it needs its own two-sided coverage: a wrong answer
# here sends the whole gate at the wrong tree, and "not found" must be
# distinguishable from "found something empty".
# ---------------------------------------------------------------------------

def test_the_resolver_finds_the_checkout_by_ITS_PIN_not_by_its_name(tmp_path, monkeypatch):
    monkeypatch.delenv("DOCPLUCK_APP_REPO", raising=False)
    root = tmp_path / "portfolio"
    (root / "lib" / "scripts").mkdir(parents=True)
    # A decoy that has the right SHAPE but no docpluck pin, sorted first so a
    # resolver that simply took the first sibling would pick it.
    (root / "aaa-decoy" / "service").mkdir(parents=True)
    (root / "aaa-decoy" / "service" / "requirements.txt").write_text(
        "fastapi\nuvicorn\n", encoding="utf-8")
    wanted = root / "zzz-consumer"
    (wanted / "service").mkdir(parents=True)
    (wanted / "service" / "requirements.txt").write_text(
        "docpluck[all] @ git+https://github.com/giladfeldman/docpluck.git@v2.4.138\n",
        encoding="utf-8")

    monkeypatch.setattr(pin, "__file__", str(root / "lib" / "scripts" / "x.py"))
    assert pin.default_app_repo() == wanted, (
        "resolved by position or by name rather than by the pin it carries")


def test_the_resolver_says_NOT_FOUND_rather_than_guessing(tmp_path, monkeypatch):
    monkeypatch.delenv("DOCPLUCK_APP_REPO", raising=False)
    root = tmp_path / "portfolio"
    (root / "lib" / "scripts").mkdir(parents=True)
    (root / "unrelated").mkdir(parents=True)
    monkeypatch.setattr(pin, "__file__", str(root / "lib" / "scripts" / "x.py"))
    assert pin.default_app_repo() is None, (
        "returned a path when nothing matched -- the caller would then report "
        "'app repo not found at <plausible path>', which reads as a moved "
        "checkout rather than as a resolver that found nothing")


def test_the_env_override_wins(tmp_path, monkeypatch):
    target = tmp_path / "elsewhere"
    target.mkdir()
    monkeypatch.setenv("DOCPLUCK_APP_REPO", str(target))
    assert pin.default_app_repo() == target.resolve()
