"""The version the package reports must be findable in the changelog.

Written 2026-09-05. Watched fail against a real historical tree -- see below.

WHAT HAPPENED. Commit `59604df` (2026-09-05) bumped `docpluck/__init__.py` and
`pyproject.toml` from 2.4.139 to 2.4.140 and did not write a changelog section for it.
Every sub-heading under `[Unreleased]` still said 2.4.139, so the newest work was
attributed to the previous version and a consumer looking up 2.4.140 found nothing.
Reproduce the historical red with:

    git show 59604df:docpluck/__init__.py | grep -m1 __version__   ->  2.4.140
    git show 59604df:CHANGELOG.md | grep -c '2\.4\.140'           ->  0

`tests/test_docs_consistency_gate.py` was green across that commit and correctly so: it
checks that `__version__`, `pyproject.toml` and the version examples in the docs agree
with each other. All three said 2.4.140. Nothing in it looks at CHANGELOG.md, so the one
document a consumer reads to find out what changed was the one nothing checked.

This is a cheap check and it is deliberately weak: it asks only that the version string
appear SOMEWHERE in the changelog -- under a released `## [x.y.z]` heading, or inside the
`[Unreleased]` block while the version is still unreleased. It is not a review of whether
the entry is any good. It catches the specific, silent, recurring failure of bumping a
number and forgetting to say what it was for.
"""

from __future__ import annotations

import re
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]


def _declared_version() -> str:
    src = (_REPO / "docpluck" / "__init__.py").read_text(encoding="utf-8", errors="replace")
    m = re.search(r'^__version__ = "([^"]+)"', src, re.MULTILINE)
    assert m, "could not read __version__ from docpluck/__init__.py -- the check cannot run"
    return m.group(1)


def _version_is_documented(version: str, changelog: str) -> bool:
    """The whole rule, as one function, so it can be tested in both directions."""
    return re.search(rf"(?<![\d.]){re.escape(version)}(?![\d.])", changelog) is not None


def test_the_rule_rejects_a_changelog_that_never_names_the_version():
    """Two-sided control, negative side. Modelled on the real 59604df text."""
    historical = (
        "# Changelog\n\n## [Unreleased] - table extraction 2.4.13\n\n"
        "### DOCX tables reach the consumer (2.4.139)\n"
    )
    assert not _version_is_documented("2.4.140", historical), (
        "the rule accepted a changelog that names only 2.4.139 while the package says "
        "2.4.140 -- it would have passed the commit it was written for."
    )


def test_the_rule_accepts_a_changelog_that_does_name_it():
    """Two-sided control, positive side. A rule that rejects everything is not a rule."""
    assert _version_is_documented("2.4.140", "## [Unreleased]\n\n### Something (2.4.140)\n")
    assert _version_is_documented("2.4.138", "## [2.4.138] - 2026-09-02\n")
    # And it must not match a longer version that merely contains this one as a prefix.
    assert not _version_is_documented("2.4.14", "### Something (2.4.140)\n")


def test_the_declared_version_appears_in_the_changelog():
    version = _declared_version()
    changelog = (_REPO / "CHANGELOG.md").read_text(encoding="utf-8", errors="replace")
    assert len(changelog) > 1000, "CHANGELOG.md is missing or trivially short -- a pass here means nothing"
    assert _version_is_documented(version, changelog), (
        f"docpluck reports version {version} and CHANGELOG.md never names it. A consumer "
        f"looking up what changed in {version} finds the previous version's entry instead. "
        "Add the section before tagging."
    )
