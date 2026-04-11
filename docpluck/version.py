"""
Version introspection helper.

Exposes :func:`get_version_info` which returns a machine-readable dict of
``{version, normalize_version, git_sha}`` for batch runners that record an
immutable "bundle receipt" alongside their outputs. See MetaESCI request D3.
"""

from __future__ import annotations

import subprocess
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def _resolve_git_sha() -> str:
    """Best-effort resolution of the docpluck git SHA.

    Returns ``"unknown"`` if docpluck was installed from a wheel, from PyPI,
    or from a directory that is not a git checkout. Never raises.
    """
    pkg_dir = Path(__file__).resolve().parent
    repo_root = pkg_dir.parent
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        if result.returncode == 0:
            return result.stdout.strip() or "unknown"
    except Exception:
        pass
    return "unknown"


def get_version_info() -> dict:
    """Return a dict with docpluck version metadata.

    Keys:
        version:           PEP 440 library version (matches ``pyproject.toml``).
        normalize_version: ``NORMALIZATION_VERSION`` from ``normalize.py``.
        git_sha:           Git SHA of the docpluck checkout, or ``"unknown"``.

    The git SHA resolution is cached (shells out to ``git rev-parse`` at most
    once per process). A fresh dict is returned on every call, so callers may
    mutate the result without corrupting the cache.
    """
    from . import __version__
    from .normalize import NORMALIZATION_VERSION

    return {
        "version": __version__,
        "normalize_version": NORMALIZATION_VERSION,
        "git_sha": _resolve_git_sha(),
    }
