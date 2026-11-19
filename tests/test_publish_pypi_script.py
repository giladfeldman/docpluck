"""scripts/publish_pypi.py reads the PyPI token from a gitignored .env.local and never from git."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("publish_pypi", _ROOT / "scripts" / "publish_pypi.py")
pp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pp)


@pytest.mark.parametrize("name", [".env.local", ".env"])
def test_token_files_are_ignored_by_git(name):
    assert pp.env_file_is_ignored(_ROOT / name)


def test_env_local_is_read_before_env():
    assert [f.name for f in pp.ENV_FILES] == [".env.local", ".env"]


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


@pytest.mark.parametrize("body", ["", "OTHER=1\n", "PYPI_TOKEN=notatoken-s3cr3t\n"])
def test_missing_or_malformed_token_stops(tmp_path, body):
    f = tmp_path / ".env.local"
    f.write_text(body, encoding="utf-8")
    with pytest.raises(SystemExit) as e:
        pp.read_token(f)
    assert "s3cr3t" not in str(e.value)  # the rejected value must never be echoed


def test_missing_file_stops(tmp_path):
    with pytest.raises(SystemExit):
        pp.read_token(tmp_path / ".env.local")


# --- main(): the order of operations, with PyPI and every subprocess faked ---------------

SECRET = "pypi-FAKE-s3cr3t-token"


def _fake_main(monkeypatch, tmp_path, *, on_pypi, ignored=True, write_token=True):
    """Run main() with PyPI answering `on_pypi` (list of filenames, or None for no such
    version) and every subprocess recorded instead of run. Returns (calls, envs, exit)."""
    env_file = tmp_path / ".env.local"
    if write_token:
        env_file.write_text(f"PYPI_TOKEN={SECRET}\n", encoding="utf-8")
    monkeypatch.setattr(pp, "ENV_FILES", (env_file,))
    monkeypatch.setattr(pp, "ENV_FILE", env_file)
    monkeypatch.setattr(pp, "env_file_is_ignored", lambda f: ignored)
    answers = iter([on_pypi] + [["docpluck-9.9.9.tar.gz", "docpluck-9.9.9-py3-none-any.whl"]] * 20)
    monkeypatch.setattr(pp, "pypi_files", lambda v: next(answers))
    monkeypatch.setattr(pp.time, "sleep", lambda s: None)

    def fake_export(tag, dest):
        (dest / "src").mkdir()
        (dest / "src" / "pyproject.toml").write_text('version = "9.9.9"\n', encoding="utf-8")
    monkeypatch.setattr(pp, "export_tag", fake_export)

    calls, envs = [], []

    def fake_run(argv, **kw):
        calls.append([str(a) for a in argv])
        envs.append(kw.get("env"))
        if "build" in argv:
            out = Path(argv[argv.index("--outdir") + 1])
            out.mkdir(parents=True, exist_ok=True)
            (out / "docpluck-9.9.9.tar.gz").write_text("x")
            (out / "docpluck-9.9.9-py3-none-any.whl").write_text("x")
        return type("R", (), {"returncode": 0})()
    monkeypatch.setattr(pp.subprocess, "run", fake_run)
    return calls, envs


def test_refuses_when_token_file_is_not_ignored(monkeypatch, tmp_path):
    calls, _ = _fake_main(monkeypatch, tmp_path, on_pypi=None, ignored=False)
    with pytest.raises(SystemExit) as e:
        pp.main(["v9.9.9"])
    assert "REFUSING" in str(e.value) and calls == []


def test_bad_tag_is_refused_before_anything_runs(monkeypatch, tmp_path):
    calls, _ = _fake_main(monkeypatch, tmp_path, on_pypi=None)
    with pytest.raises(SystemExit):
        pp.main(["9.9.9"])  # no leading "v": refused before git or PyPI is touched
    assert calls == []


def test_fully_published_version_needs_no_token(monkeypatch, tmp_path, capsys):
    calls, _ = _fake_main(monkeypatch, tmp_path, write_token=False,
                          on_pypi=["docpluck-9.9.9.tar.gz", "docpluck-9.9.9-py3-none-any.whl"])
    assert pp.main(["v9.9.9"]) == 0
    assert "nothing to do" in capsys.readouterr().out and calls == []


def test_half_published_version_uploads_the_missing_file(monkeypatch, tmp_path, capsys):
    calls, _ = _fake_main(monkeypatch, tmp_path, on_pypi=["docpluck-9.9.9.tar.gz"])
    assert pp.main(["v9.9.9"]) == 0
    out = capsys.readouterr().out
    assert "missing: wheel" in out and "nothing to do" not in out
    upload = [c for c in calls if "upload" in c]
    assert len(upload) == 1 and "--skip-existing" in upload[0]


def test_dry_run_reads_no_token_and_uploads_nothing(monkeypatch, tmp_path):
    calls, _ = _fake_main(monkeypatch, tmp_path, on_pypi=None, write_token=False)
    assert pp.main(["v9.9.9", "--dry-run"]) == 0
    assert not any("upload" in c for c in calls)


def test_token_reaches_only_the_upload_env(monkeypatch, tmp_path, capsys):
    calls, envs = _fake_main(monkeypatch, tmp_path, on_pypi=None)
    assert pp.main(["v9.9.9"]) == 0
    assert not any(SECRET in a for c in calls for a in c)            # never in argv
    assert SECRET not in capsys.readouterr().out                       # never printed
    with_token = [c for c, e in zip(calls, envs) if e and e.get("TWINE_PASSWORD") == SECRET]
    assert len(with_token) == 1 and "upload" in with_token[0]          # only the upload sees it


def test_poll_survives_a_network_error_after_upload(monkeypatch, tmp_path, capsys):
    calls, _ = _fake_main(monkeypatch, tmp_path, on_pypi=None)
    state = {"n": 0}

    def flaky(v):
        state["n"] += 1
        if state["n"] == 1:
            return None
        if state["n"] == 2:
            raise pp.urllib.error.URLError("down")
        return ["docpluck-9.9.9.tar.gz", "docpluck-9.9.9-py3-none-any.whl"]
    monkeypatch.setattr(pp, "pypi_files", flaky)
    assert pp.main(["v9.9.9"]) == 0
    assert "PUBLISHED" in capsys.readouterr().out
