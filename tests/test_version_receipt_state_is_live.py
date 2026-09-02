"""``git_state`` is probed per receipt, never frozen for the process lifetime.

Fleet ask ``2026-08-22T102300Z`` amendment_1 predicted this defect in writing
before the feature existed: "A git_dirty flag computed INSIDE the cached
function inherits the same permanent staleness, so the fix would pass its own
test and still report a frozen answer in production" — and prescribed the fix:
"move the dirty check outside the lru_cache (or drop the cache on the git
resolution entirely — it is one subprocess call per receipt, not per
document)." The shipped implementation cached it anyway, arguing pair-coherence
with the cached SHA. Measured 2026-09-02 in a single process at eb3e84d:
clean -> tree dirtied -> ``get_version_info()["git_state"]`` still ``"clean"``.
That is the HTTP consumption mode: a server process left running while the
tree is edited reports ``clean`` forever.

The SHA stays cached BY DESIGN and these tests do not touch it: it names the
identity the process loaded, and its staleness class (``stale``) is handled at
the app boundary (``PDFextractor`` ``service/app/identity.py``), a recorded
decision in ``_resolve_git_state``'s docstring. A frozen SHA beside a live
``dirty`` says exactly the true thing: the tree no longer matches the identity
this process loaded.

Written RED against 2b14d62 (both tests fail: the resolver carries an
``lru_cache`` wrapper and the second probe returns the frozen value), then the
cache was removed.
"""

import subprocess

from docpluck import version as version_mod


def test_git_state_resolver_is_not_process_cached():
    """The defect WAS the cache: the resolver must not carry one."""
    assert not hasattr(version_mod._resolve_git_state, "cache_info"), (
        "_resolve_git_state is lru_cached — a long-lived process can never "
        "notice the tree changed under it (ask 2026-08-22T102300Z amendment_1)"
    )


def test_git_state_tracks_the_tree_within_one_process(monkeypatch):
    """Two receipts in one process straddling a tree edit must disagree."""
    real_run = subprocess.run
    state = {"porcelain": ""}

    def fake_run(cmd, *args, **kwargs):
        if "status" in cmd and "--porcelain" in cmd:
            return subprocess.CompletedProcess(cmd, 0, stdout=state["porcelain"], stderr="")
        return real_run(cmd, *args, **kwargs)

    monkeypatch.setattr(subprocess, "run", fake_run)
    first = version_mod._resolve_git_state()
    state["porcelain"] = " M docpluck/normalize.py\n"
    second = version_mod._resolve_git_state()
    assert (first, second) == ("clean", "dirty"), (
        f"one process, tree edited between receipts: {first!r} -> {second!r}; "
        "a frozen answer here is the false receipt the ask measured"
    )
