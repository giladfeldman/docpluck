"""The CPU-budget helpers must fire on work, stay silent on waiting, and say which.

``tests/cpu_budget.py`` replaced four wall-clock timeouts. A budget helper that
never fires is a green check on nothing, so each branch is exercised here with a
child whose behaviour is known: one that only computes, one that only waits.
"""

from __future__ import annotations

import subprocess
import sys
import time

import pytest

from tests import cpu_budget
from tests.cpu_budget import BudgetExceeded, cpu_seconds, run_with_cpu_budget

_BUSY = [sys.executable, "-c", "while True: pass"]


def _sleeper(seconds: float) -> list[str]:
    return [sys.executable, "-c", f"import time; time.sleep({seconds})"]


def test_child_cpu_is_readable_and_moves_on_this_platform():
    """A reader that always returned 0 or None would disable every budget."""
    if sys.platform != "win32" and not sys.platform.startswith("linux"):
        pytest.skip("CPU time is read on Windows and Linux; elsewhere the wall fallback applies")
    proc = subprocess.Popen(_BUSY)
    try:
        time.sleep(1.5)
        cpu = cpu_budget._child_cpu_seconds(proc)
    finally:
        proc.kill()
        proc.wait()
    assert cpu is not None and cpu > 0.2, f"child CPU read as {cpu!r} after 1.5s of spinning"


def test_a_computing_child_is_stopped_by_the_cpu_budget():
    with pytest.raises(BudgetExceeded, match=r"CPU [\d.]+s > budget"):
        run_with_cpu_budget(
            _BUSY, cpu_budget_s=1.0, fallback_wall_s=60, stall_s=30, wall_backstop_s=60, poll_s=0.2
        )


def test_a_child_that_finishes_between_polls_is_still_held_to_the_budget():
    """The last poll can miss the overrun; the exit check must not."""
    if sys.platform != "win32" and not sys.platform.startswith("linux"):
        pytest.skip("needs a readable CPU time")
    spin = [
        sys.executable,
        "-c",
        "import time\nend = time.process_time() + 1.5\nwhile time.process_time() < end: pass",
    ]
    with pytest.raises(BudgetExceeded, match="finished over budget"):
        run_with_cpu_budget(spin, cpu_budget_s=0.5, fallback_wall_s=600, poll_s=300)


def test_a_waiting_child_is_not_charged_for_the_wait():
    """The property the whole module exists for: wall time past the budget is fine."""
    result = run_with_cpu_budget(
        _sleeper(3), cpu_budget_s=1.0, fallback_wall_s=60, stall_s=60, poll_s=0.2
    )
    assert result.returncode == 0
    assert result.cpu_seconds is None or result.cpu_seconds < 1.0


def test_a_child_that_stops_accruing_cpu_is_failed_as_hung():
    if sys.platform != "win32" and not sys.platform.startswith("linux"):
        pytest.skip("stall detection needs a readable CPU time")
    with pytest.raises(BudgetExceeded, match="no CPU progress"):
        run_with_cpu_budget(
            _sleeper(60), cpu_budget_s=30, fallback_wall_s=120, stall_s=2, poll_s=0.2
        )


def test_the_wall_fallback_applies_where_cpu_is_unreadable(monkeypatch):
    monkeypatch.setattr(cpu_budget, "_child_cpu_seconds", lambda proc: None)
    with pytest.raises(BudgetExceeded, match="CPU time unreadable"):
        run_with_cpu_budget(_sleeper(60), cpu_budget_s=30, fallback_wall_s=1, poll_s=0.2)


def test_output_larger_than_a_pipe_buffer_is_drained():
    """The structured CLI writes ~200 KB; an undrained pipe would hang the child."""
    cmd = [sys.executable, "-c", "import sys; sys.stdout.write('x' * 500_000)"]
    result = run_with_cpu_budget(cmd, cpu_budget_s=30, fallback_wall_s=120, poll_s=0.2)
    assert result.returncode == 0 and len(result.stdout) == 500_000


def test_cpu_seconds_counts_work_and_not_sleep():
    def spin() -> None:
        end = time.process_time() + 0.2
        while time.process_time() < end:
            pass

    assert cpu_seconds(spin, repeat=2) >= 0.15
    assert cpu_seconds(lambda: time.sleep(0.3), repeat=2) < 0.1
