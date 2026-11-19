"""scripts/publish_pypi.py reads the PyPI token from a gitignored .env.local and never from git."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("publish_pypi", _ROOT / "scripts" / "publish_pypi.py")
pp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pp)


def test_env_local_is_ignored_by_git():
    assert pp.env_file_is_ignored(_ROOT / ".env.local")


def test_a_tracked_path_is_not_ignored():
    # Control: the check must be able to say "not ignored".
    assert not pp.env_file_is_ignored(_ROOT / "pyproject.toml")


@pytest.mark.parametrize("body", [
    "PYPI_TOKEN=pypi-abc123\n",
    "# my token\n\nPYPI_TOKEN = \"pypi-abc123\"\n",
    "﻿OTHER=1\nPYPI_TOKEN='pypi-abc123'\n",
])
def test_token_is_read(tmp_path, body):
    f = tmp_path / ".env.local"
    f.write_text(body, encoding="utf-8")
    assert pp.read_token(f) == "pypi-abc123"


@pytest.mark.parametrize("body", ["", "OTHER=1\n", "PYPI_TOKEN=notatoken\n"])
def test_missing_or_malformed_token_stops(tmp_path, body):
    f = tmp_path / ".env.local"
    f.write_text(body, encoding="utf-8")
    with pytest.raises(SystemExit) as e:
        pp.read_token(f)
    assert "pypi-abc" not in str(e.value)


def test_missing_file_stops(tmp_path):
    with pytest.raises(SystemExit):
        pp.read_token(tmp_path / ".env.local")
