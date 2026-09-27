"""Where the article repository is: ``$ARTICLE_REPOSITORY``, and nothing else.

ONE resolver for ``corpus.py`` and ``regenerate.py``. It lives in its own module
because ``regenerate.py`` rewrites ``corpus_manifest.py`` and must not depend on
importing it.

There is deliberately NO default location. Until 2026-09-25 an unset variable
fell back to a fixed directory under the home directory. That
fallback published one machine's directory layout in a package that ships to
PyPI, and it meant the suite found its papers on that one machine without
anyone having said where they were. Owner decision, 2026-09-25: the variable is
required. An unset variable is not a silent miss, though:
``tests/test_corpus_manifest.py::test_the_custodian_is_reachable`` FAILS and
prints :func:`root_problem`.
"""

from __future__ import annotations

import os
from pathlib import Path

ENV_REPO = "ARTICLE_REPOSITORY"


def repository_root() -> Path | None:
    """The article repository root, or None when it is not configured or not here."""
    explicit = os.environ.get(ENV_REPO)
    if not explicit:
        return None
    p = Path(explicit)
    return p if p.is_dir() else None


def root_problem() -> str | None:
    """Why :func:`repository_root` returned None, in words -- or None if it did not."""
    explicit = os.environ.get(ENV_REPO)
    if not explicit:
        return (
            f"{ENV_REPO} is not set. Set it to the article repository's directory; "
            "there is no default location."
        )
    if not Path(explicit).is_dir():
        return f"{ENV_REPO} is set to {explicit!r}, which is not a directory."
    return None


# ---------------------------------------------------------------------------
# The two TOOL locations the test and gate code needs, resolved the same way:
# an environment variable and NO default. Until 2026-09-27 each had a fallback
# under the home directory or inside this checkout, spelled out in eleven places;
# that published one machine's private tooling layout in a public repo. With the
# variable unset these return None and the callers skip, naming the variable.
# ---------------------------------------------------------------------------

ENV_ARTICLE_FINDER = "ARTICLE_FINDER_HOME"
ENV_SKILLS = "DOCPLUCK_SKILLS_DIR"


def _env_dir(name: str) -> Path | None:
    val = os.environ.get(name)
    if not val:
        return None
    p = Path(os.path.expanduser(val))
    return p if p.is_dir() else None


def article_finder_home() -> Path | None:
    """The article-finder tool directory (``$ARTICLE_FINDER_HOME``), or None."""
    return _env_dir(ENV_ARTICLE_FINDER)


def project_skills_dir() -> Path | None:
    """docpluck's own gate-skill directory (``$DOCPLUCK_SKILLS_DIR``), or None.

    It holds the gate skills and the canary configuration. It is never tracked in
    this public repo, so on a clone it is simply absent.
    """
    return _env_dir(ENV_SKILLS)


def tool_problem(name: str) -> str:
    """Why the tool location ``name`` (an ENV_* constant) did not resolve."""
    val = os.environ.get(name)
    if not val:
        return f"{name} is not set; there is no default location."
    return f"{name} is set to {val!r}, which is not a directory."
