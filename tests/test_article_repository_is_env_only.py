"""The article repository is found through ``$ARTICLE_REPOSITORY`` only.

Owner decision 2026-09-25 (option B of the public-repo follow-ups). The shipped
package used to fall back to a fixed directory under the home directory, which
published one machine's layout to PyPI and
let the suite find its papers without anyone configuring where they were.
Fourteen tests and tools each rebuilt that path again, two of them by counting
parent directories up from the test file.
"""

from __future__ import annotations

import pytest

from docpluck.testing import (
    article_finder_home,
    custody_path,
    project_skills_dir,
    repository_root,
    root_problem,
    tool_problem,
)


def test_unset_variable_resolves_to_nothing_even_where_the_old_default_exists(
    monkeypatch, tmp_path
):
    """Two-sided: point the home directory at a tree that HAS a repository-shaped
    folder, then unset the variable. The old resolver found such a folder under
    a fixed home-relative path; this one must return None and say why. (The old
    folder name is itself forbidden in tracked files -- see
    tests/test_public_repo_hygiene.py -- so it is not spelled here.)"""
    (tmp_path / "article-repository" / "fulltext").mkdir(parents=True)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.delenv("ARTICLE_REPOSITORY", raising=False)

    assert repository_root() is None
    assert "not set" in root_problem()
    assert not custody_path("fulltext", "x.pdf").exists()


def test_the_variable_is_honoured(monkeypatch, tmp_path):
    monkeypatch.setenv("ARTICLE_REPOSITORY", str(tmp_path))
    assert repository_root() == tmp_path
    assert root_problem() is None
    assert custody_path("fulltext", "x.pdf") == tmp_path / "fulltext" / "x.pdf"


def test_a_variable_naming_no_directory_is_reported_not_trusted(monkeypatch, tmp_path):
    missing = tmp_path / "nope"
    monkeypatch.setenv("ARTICLE_REPOSITORY", str(missing))
    assert repository_root() is None
    assert "not a directory" in root_problem()


@pytest.mark.parametrize(
    ("var", "resolver"),
    [("ARTICLE_FINDER_HOME", article_finder_home), ("DOCPLUCK_SKILLS_DIR", project_skills_dir)],
)
def test_tool_locations_are_env_only(monkeypatch, tmp_path, var, resolver):
    """The two tool directories follow the same rule: the variable, or nothing.

    Two-sided: a planted home directory holding the kind of tree the old
    fallbacks looked in resolves to None when the variable is unset, and to the
    variable's directory when it is set.
    """
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.delenv(var, raising=False)
    assert resolver() is None
    assert "not set" in tool_problem(var)

    monkeypatch.setenv(var, str(tmp_path))
    assert resolver() == tmp_path

    monkeypatch.setenv(var, str(tmp_path / "nope"))
    assert resolver() is None
    assert "not a directory" in tool_problem(var)


# The "no tracked code rebuilds the path" guard moved to
# tests/test_public_repo_hygiene.py::test_no_internal_reference_in_tracked_files,
# which covers every internal-layout word, not only this one.
