"""Machine-local corpora that live inside PRIVATE sibling repos.

THE ONE DEFINITION. Some tests read document corpora held in sibling repos that
are private. Their directory layout is not this PUBLIC repo's to publish, so it
is not written down in tracked source: it comes from ``tests/corpora.local.json``
(gitignored, written once per machine) or from ``$DOCPLUCK_LOCAL_CORPORA``.

Added 2026-09-22. Before that, three tests carried paths like
``_VIBE / "<group>" / "<private repo>" / "apps" / "worker" / ...`` assembled from
quoted segments -- and **every gate missed them**, because both
``tests/test_public_repo_hygiene.py`` and ``public-repo-guard.py`` match a
project name followed by a SLASH, and a split path has none. The whole-tree
audit reported the code clean while 20 such paths were live.

A missing key means "not on this machine" and the caller SKIPS, exactly as the
hardcoded paths did. It never raises: a private corpus being absent is the
normal state for any clone of a public repo.

This is a standalone module rather than a ``conftest`` helper because ``tests/``
is not a package and ``from conftest import ...`` does not resolve under this
project's pytest import mode -- measured 2026-09-22, it raised
``ModuleNotFoundError`` at collection.
"""

from __future__ import annotations

import json
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
_CONFIG = os.path.join(_HERE, "corpora.local.json")
_VIBE = os.environ.get("VIBE_ROOT") or os.path.join(os.path.expanduser("~"), "Vibe")


def local_corpus(key: str) -> str | None:
    """Absolute path for a machine-local corpus key, or None when unconfigured."""
    spec = os.environ.get("DOCPLUCK_LOCAL_CORPORA")
    data: dict = {}
    try:
        if spec:
            data = json.loads(spec)
        elif os.path.isfile(_CONFIG):
            with open(_CONFIG, encoding="utf-8") as fh:
                data = json.load(fh)
    except (OSError, ValueError):
        return None
    val = data.get(key)
    if not val:
        return None
    p = os.path.expanduser(val)
    return p if os.path.isabs(p) else os.path.join(_VIBE, p)
