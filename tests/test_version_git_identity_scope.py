"""git_sha / git_state describe docpluck's OWN checkout or nothing (d-5bf4ee, d-fcb3d3).

A wheel inside a consumer's repository used to report the consumer's HEAD and
cleanliness as docpluck's: ``git -C`` walks up to the enclosing repository.
"""
from __future__ import annotations

import subprocess

import pytest

from docpluck import version


def _git(*a, cwd):
    subprocess.run(["git", *a], cwd=cwd, check=True, capture_output=True)


@pytest.fixture
def consumer_repo(tmp_path, monkeypatch):
    repo = tmp_path / "consumer"
    pkg = repo / ".venv" / "Lib" / "site-packages" / "docpluck"
    pkg.mkdir(parents=True)
    (repo / "app.py").write_text("x = 1\n")
    _git("init", "-q", cwd=repo)
    _git("-c", "user.email=t@t", "-c", "user.name=t", "add", "app.py", cwd=repo)
    _git("-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "c", cwd=repo)
    monkeypatch.setattr(version, "_pkg_dir", lambda: pkg)
    version._resolve_git_sha.cache_clear()
    yield repo
    version._resolve_git_sha.cache_clear()


def test_wheel_inside_a_consumer_repo_reports_unknown(consumer_repo):
    # Control: the walk-up really does find the consumer's repository.
    head = subprocess.run(["git", "-C", str(version._pkg_dir().parent), "rev-parse", "HEAD"],
                          capture_output=True, text=True).stdout.strip()
    assert len(head) == 40
    assert version._resolve_git_sha() == version.UNKNOWN
    assert version._resolve_git_state() == version.UNKNOWN


def test_own_checkout_still_reports_its_sha():
    version._resolve_git_sha.cache_clear()
    root = version._own_repo_root()
    if root is None:
        pytest.skip("docpluck not imported from a git checkout")
    head = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"],
                          capture_output=True, text=True).stdout.strip()
    assert version._resolve_git_sha() == head
    assert version._resolve_git_state() in ("clean", "dirty")


def test_source_edited_after_load_reports_stale(tmp_path, monkeypatch):
    """ESCImate 2026-10-30: a long-running process said `clean` for code it did not run."""
    root = version._own_repo_root()
    if root is None:
        pytest.skip("docpluck not imported from a git checkout")
    assert version._resolve_git_state() in ("clean", "dirty")   # control
    monkeypatch.setattr(version, "_LOADED_AT", 0.0)              # every file is "newer"
    assert version._resolve_git_state() == "stale"
