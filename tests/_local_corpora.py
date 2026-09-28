"""Machine-local corpora that live inside PRIVATE sibling repos.

THE ONE DEFINITION. Some tests read document corpora held in sibling repos that
are private. Their directory layout is not this PUBLIC repo's to publish, so it
is not written down in tracked source: it comes from ``tests/corpora.local.json``
(gitignored, written once per machine) or from ``$DOCPLUCK_LOCAL_CORPORA``.

Added 2026-09-22. Before that, three tests carried paths into a private sibling
repo, assembled from quoted segments -- and **every gate missed them**, because both
``tests/test_public_repo_hygiene.py`` and ``public-repo-guard.py`` match a
project name followed by a SLASH, and a split path has none. The whole-tree
audit reported the code clean while 20 such paths were live.

A missing key means "not on this machine" and the caller SKIPS, exactly as the
hardcoded paths did: a private corpus being absent is the normal state for any
clone of a public repo. Values must be ABSOLUTE paths (``~`` is expanded). A
relative value RAISES: it used to be joined onto a fixed portfolio root, which
published that layout here, and guessing a base would turn a configuration error
into a silent skip.

WHAT MAY STILL LIVE HERE (2026-09-25). Only documents that can never enter the
article custodian by DOI: the DOCX sources, which are unsubmitted manuscripts.
They are never published, so they have no DOI, and they are never named by
filename in this public repo (tests locate them by content hash or by a key the
machine-local config supplies). Published papers do NOT belong here -- they
resolve by DOI through ``docpluck.testing``, where a miss FAILS. The retired
``escicheck_pdfs`` key was exactly that mistake: its folder was deleted when its
papers went into custody, and every test reading it skipped silently from then
on.

``require_local_corpus`` is the stricter form for tests: a key that is not
configured skips (by design, on any machine without the manuscripts), but a key
that IS configured and points at nothing FAILS. The second case is a machine
that claims to hold the corpus and does not, which is the silent-skip hole in a
new place.

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
    except OSError:
        return None
    except ValueError as exc:
        # Malformed config is a configuration ERROR, not "not on this machine".
        # Returning None here turned a mistyped Windows path (an unescaped
        # backslash in the env JSON) into a silent skip -- measured 2026-09-28.
        raise ValueError(
            "machine-local corpus config is not valid JSON "
            "($DOCPLUCK_LOCAL_CORPORA or tests/corpora.local.json)"
        ) from exc
    val = data.get(key)
    if not val:
        return None
    p = os.path.expanduser(val)
    if not os.path.isabs(p):
        raise ValueError(
            f"local corpus {key!r} is configured as the relative path {val!r}; "
            "give an absolute path in tests/corpora.local.json or "
            "$DOCPLUCK_LOCAL_CORPORA."
        )
    return p


def require_local_corpus(key: str) -> str:
    """The directory for ``key``: skip if unconfigured, FAIL if configured but absent.

    Call inside a test body (it uses ``pytest.skip`` / ``pytest.fail``).
    """
    import pytest

    path = local_corpus(key)
    if path is None:
        pytest.skip(
            f"machine-local corpus {key!r} is not configured on this machine "
            "(unsubmitted manuscripts; never in this public repo)"
        )
    if not os.path.isdir(path):
        pytest.fail(
            f"machine-local corpus {key!r} is configured as {path}, which does not "
            "exist. Either restore it or remove the key from tests/corpora.local.json "
            "-- a configured corpus that is missing must not read as a skip."
        )
    return path
