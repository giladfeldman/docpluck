"""CLI: docpluck extract --structured ..."""

import json
import os
import subprocess
import sys

import pytest

from tests.cpu_budget import run_with_cpu_budget
from tests.structured_fixtures import resolve_fixture as _resolve_fixture

# Each test here spawns a REAL `python -m docpluck` subprocess against a real
# PDF, so its wall time is a function of how loaded the machine is -- not of
# whether the code is correct. Under `pytest -n auto` on 14 workers the whole
# box is saturated and a 120s budget expires: measured 2026-09-16, the full
# parallel suite reported `test_figures_only_omits_tables` and
# `test_html_tables_to_writes_html_files` as FAILED on
# `subprocess.TimeoutExpired`, and the same file run serially passed 7/7 in
# 192s. That is a false RED in the release gate, which costs more than a false
# green because it sends someone hunting a regression that does not exist.
#
# The fix that followed -- 120s serial, 480s under xdist -- still failed on an
# unchanged tree on 2026-09-25 (120s serial, then 480s), with the machine out of
# memory and failing to create processes. Scaling a WALL-clock budget chases
# the load and never catches it. So the budget is now the child's own CPU time
# (see `tests/cpu_budget.py`): measured at 100% machine load the same day, the
# `--structured` run used 32-34s CPU against 55-58s wall. 120 CPU-seconds is
# the old serial number, now held in every run mode -- tighter under xdist than
# the 480s it replaces. A child that stops accruing CPU for 600s is failed as
# hung: longer than the probes' 180s because this child legitimately waits on
# pdftotext, which the library itself bounds at 120s per call.
_CPU_BUDGET_S = 120
_FALLBACK_WALL_S = 480 if os.environ.get("PYTEST_XDIST_WORKER") else 120


def _run(*args: str) -> subprocess.CompletedProcess:
    return run_with_cpu_budget(
        [sys.executable, "-m", "docpluck", *args],
        cpu_budget_s=_CPU_BUDGET_S,
        fallback_wall_s=_FALLBACK_WALL_S,
    )


def test_structured_flag_outputs_json():
    pdf = _resolve_fixture("apa_chan_feldman_lineless")
    result = _run("extract", str(pdf), "--structured")
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert "tables" in data
    assert "figures" in data
    assert "text" in data
    assert "method" in data
    assert "page_count" in data


def test_thorough_flag():
    pdf = _resolve_fixture("apa_chan_feldman_lineless")
    result = _run("extract", str(pdf), "--structured", "--thorough")
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert "thorough" in data["method"]


def test_text_mode_placeholder_flag():
    pdf = _resolve_fixture("apa_chan_feldman_lineless")
    result = _run("extract", str(pdf), "--structured", "--text-mode", "placeholder")
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    if data["tables"] or data["figures"]:
        assert "[Table" in data["text"] or "[Figure" in data["text"]


def test_tables_only_omits_figures():
    pdf = _resolve_fixture("apa_chan_feldman_lineless")
    result = _run("extract", str(pdf), "--structured", "--tables-only")
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert data["figures"] == []


def test_figures_only_omits_tables():
    pdf = _resolve_fixture("apa_chan_feldman_lineless")
    result = _run("extract", str(pdf), "--structured", "--figures-only")
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert data["tables"] == []


def test_existing_extract_no_flags_unchanged():
    """extract <file> without --structured emits plain text, not JSON."""
    pdf = _resolve_fixture("apa_chan_feldman_lineless")
    result = _run("extract", str(pdf))
    assert result.returncode == 0, result.stderr
    # First non-whitespace char should NOT be { (which would indicate JSON)
    stripped = result.stdout.lstrip()
    assert not stripped.startswith("{"), "plain extract should not emit JSON"


def test_html_tables_to_writes_html_files(tmp_path):
    pdf = _resolve_fixture("apa_chan_feldman_lineless")
    out_dir = tmp_path / "html_out"
    result = _run(
        "extract", str(pdf), "--structured", "--html-tables-to", str(out_dir)
    )
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    structured_tables = [t for t in data["tables"] if t["kind"] == "structured"]
    if not structured_tables:
        pytest.skip("no structured tables in this fixture")
    # Each structured table should have a corresponding .html file
    for t in structured_tables:
        out_file = out_dir / f"{t['id']}.html"
        assert out_file.is_file(), f"missing {out_file}"
        contents = out_file.read_text(encoding="utf-8")
        assert "<table>" in contents
