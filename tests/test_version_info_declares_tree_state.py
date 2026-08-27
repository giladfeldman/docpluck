"""`git_sha` alone is a FALSE IDENTITY under an editable install.

Most of this portfolio consumes docpluck through `pip install -e`. That
executes whatever sits in the working tree, while `git rev-parse HEAD` reports
the last commit — so every uncommitted edit ships under a SHA that does not
contain it, and two runs of materially different code produce identical
receipts.

**Measured 2026-08-27, in this checkout**: HEAD was `9504ad9` with twelve paths
modified, `normalize.py` among them — a file whose changes alter extraction
output. A consumer on the editable install would have been running that
normalization and recording `git_sha: 9504ad9` for it. `dirty` appeared **zero
times anywhere under `docpluck/`**, so nothing in the receipt could have said
so.

The `PDFextractor` service had already had to solve this at its own boundary
(`service/app/identity.py`, `state = "dirty" if porcelain else "clean"`)
*because the library did not offer it*. `git_state` uses that same vocabulary
rather than a second spelling — one concept, one table, or the two receipts
eventually disagree.

Raised by CONDUCTOR #4 (2026-08-27) alongside the `flatten.py` eta fabrication,
on the grounds that an output-changing fix landing in an unnameable tree is the
part that makes a fabrication untraceable. Verified before implementing:
`grep -c dirty docpluck/**/*.py` was 0.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from docpluck.version import get_version_info

_REPO_ROOT = Path(__file__).resolve().parent.parent


def test_version_info_carries_the_tree_state():
    info = get_version_info()
    assert "git_state" in info, (
        "the receipt names a SHA but not whether the tree matches it — under an "
        "editable install that is a false identity"
    )
    assert info["git_state"] in {"clean", "dirty", "unknown"}


def test_the_state_matches_what_git_actually_reports():
    """Two-sided: the value must track reality, not be a constant."""
    info = get_version_info()
    if info["git_sha"] == "unknown":
        assert info["git_state"] == "unknown", (
            "no checkout means no tree to be dirty; a confident clean/dirty here "
            "would be manufactured"
        )
        return
    porcelain = subprocess.run(
        ["git", "-C", str(_REPO_ROOT), "status", "--porcelain"],
        capture_output=True, text=True, timeout=10,
    )
    expected = "dirty" if porcelain.stdout.strip() else "clean"
    assert info["git_state"] == expected, (
        f"git says {expected!r}, the receipt says {info['git_state']!r}"
    )


def test_state_and_sha_are_both_present_or_both_unknown():
    """They are read as a pair; one without the other is the defect restated."""
    info = get_version_info()
    assert ("unknown" == info["git_sha"]) == ("unknown" == info["git_state"]), (
        "a known SHA beside an unknown state (or the reverse) leaves the reader "
        "exactly where they started"
    )


def test_the_value_does_not_change_with_when_you_ask():
    """A provenance value must be stable within a process.

    `git_sha` is `@lru_cache`d; a freshly-probed state beside a cached SHA
    would let the two halves of one receipt describe different moments.
    """
    assert get_version_info()["git_state"] == get_version_info()["git_state"]


def test_the_receipt_is_a_fresh_dict_so_a_caller_cannot_poison_the_cache():
    first = get_version_info()
    first["git_state"] = "tampered"
    assert get_version_info()["git_state"] != "tampered"
