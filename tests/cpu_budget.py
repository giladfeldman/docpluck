"""CPU-time budgets for the suite's performance checks -- one rule, one place.

Two tests failed on 2026-09-25 while ~20 sessions shared the machine and process
creation was failing: ``test_docx_extraction_under_1s`` ("2.08s (limit 1.0s)",
then "7.41s (limit 5.0s)" under xdist) and ``test_structured_flag_outputs_json``
(a ``python -m docpluck`` subprocess killed at 120s, then at 480s). Both failed
identically on an untouched ce7414d, so neither was a regression. Both budgets
were WALL-CLOCK, and wall time is a measurement of the machine: a process that
is waiting for a CPU, or for a page to come back from disk, accrues wall time
while doing none of the work the budget is about.

Measured the same day at 100% CPU load, serial, on this tree. To re-measure,
time ``extract_docx`` on ``_build_docx_fixture(GROUND_TRUTH_PASSAGES)`` with
``time.process_time`` beside ``time.perf_counter``, and read the ``cpu_seconds``
this module attaches to a ``python -m docpluck extract <pdf> --structured`` run:

* ``extract_docx`` on the benchmark fixture: CPU 0.31s median, wall up to 0.91s;
  cProfile puts ~99% of it inside mammoth's XML parse of python-docx's template.
* the structured CLI on the 24-page chan_feldman fixture: CPU 32-34s, wall
  55-58s (1.7x), peak working set 474 MB.

CPU time does not stop the clock for waiting, so it measures the WORK, which is
what a regression changes. It is not perfectly load-proof -- a shared physical
core runs slower -- which is why ``cpu_seconds`` takes the MINIMUM of several
runs (contention only ever adds; the minimum is the run that was least
disturbed, the estimator ``timeit`` recommends for the same reason).

What a CPU budget cannot see: a regression that makes the code WAIT (sleep, a
lock, blocking I/O) rather than compute. Neither guarded path waits on anything
but its own pdftotext child, so that is recorded rather than covered; the
subprocess runner below also fails a child that stops accruing CPU altogether.
"""

from __future__ import annotations

import gc
import os
import subprocess
import sys
import time
from collections.abc import Callable

# --- in-process work ----------------------------------------------------------


def cpu_seconds(fn: Callable[[], object], *, repeat: int = 5) -> float:
    """Minimum process CPU time of ``fn()`` over ``repeat`` runs.

    ``time.process_time`` counts every thread of this process, so a call that
    hands work to a native thread pool is still charged for it.

    The garbage collector is run before each timing and paused during it, as
    ``timeit`` does: otherwise a collection of garbage left by EARLIER calls
    lands inside whichever call happens to trip the threshold.
    """
    best = float("inf")
    was_enabled = gc.isenabled()
    for _ in range(repeat):
        gc.collect()
        gc.disable()
        try:
            start = time.process_time()
            fn()
            best = min(best, time.process_time() - start)
        finally:
            if was_enabled:
                gc.enable()
    return best


# --- a child process ----------------------------------------------------------


def _child_cpu_seconds(proc: subprocess.Popen) -> float | None:
    """User + kernel CPU seconds of ``proc`` itself, or None if unreadable here.

    Grandchildren (docpluck's own pdftotext calls) are not included; they are
    bounded separately by the library's pdftotext timeout.
    """
    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes

        handle = getattr(proc, "_handle", None)
        if handle is None:
            return None
        ft = [wintypes.FILETIME() for _ in range(4)]
        k32 = ctypes.windll.kernel32
        k32.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4
        if not k32.GetProcessTimes(int(handle), *(ctypes.byref(f) for f in ft)):
            return None

        def secs(f: wintypes.FILETIME) -> float:
            return ((f.dwHighDateTime << 32) | f.dwLowDateTime) / 1e7  # 100 ns units

        return secs(ft[2]) + secs(ft[3])  # kernel + user
    try:
        with open(f"/proc/{proc.pid}/stat", encoding="ascii") as fh:
            fields = fh.read().rsplit(")", 1)[1].split()
        # fields[0] is state (field 3); utime/stime are fields 14/15.
        return (int(fields[11]) + int(fields[12])) / os.sysconf("SC_CLK_TCK")
    except (OSError, ValueError, IndexError):
        return None


class BudgetExceeded(AssertionError):
    """The child was stopped by a budget; the message says which one and why."""


def run_with_cpu_budget(
    cmd: list[str],
    *,
    cpu_budget_s: float,
    fallback_wall_s: float,
    stall_s: float = 600.0,
    wall_backstop_s: float = 3600.0,
    poll_s: float = 1.0,
    **popen_kwargs,
) -> subprocess.CompletedProcess:
    """Run ``cmd`` to completion, failing it on WORK done, not on time waited.

    * ``cpu_budget_s``: the regression guard -- the child is killed once its
      own CPU time passes this, and a finished child over it fails too.
    * ``stall_s``: a child whose CPU time has not moved for this long is hung
      (a deadlock burns no CPU, so the CPU budget alone would never fire). It
      is long on purpose: a starved child can go a minute on under a second of
      CPU (measured: 54s wall, 0.5s CPU for one import probe at 100% load),
      and the CLI's own longest legitimate wait is a pdftotext child that the
      library already bounds at 120s.
    * ``wall_backstop_s``: bounds the suite if a child crawls forward forever.
    * ``fallback_wall_s``: where the child's CPU time cannot be read (neither
      Windows nor Linux), the old wall-clock timeout applies unchanged, so no
      platform ends up with a weaker check than before.

    The returned ``CompletedProcess`` carries ``cpu_seconds`` (None when the
    platform could not report it) so a caller can print what it measured.
    """
    start = time.monotonic()
    popen_kwargs.setdefault("text", True)
    popen_kwargs.setdefault("encoding", "utf-8")
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, **popen_kwargs)
    last_cpu = -1.0
    last_progress = start
    reason = None
    while True:
        try:
            # communicate() keeps draining both pipes, so a child writing more
            # than a pipe buffer (the structured JSON is ~200 KB) cannot block.
            out, err = proc.communicate(timeout=poll_s)
            break
        except subprocess.TimeoutExpired:
            pass
        now = time.monotonic()
        cpu = _child_cpu_seconds(proc)
        if cpu is None:
            if now - start > fallback_wall_s:
                reason = f"wall {now - start:.0f}s > {fallback_wall_s:.0f}s (CPU time unreadable here)"
        elif cpu > cpu_budget_s:
            reason = f"CPU {cpu:.1f}s > budget {cpu_budget_s:.0f}s"
        elif cpu > last_cpu:
            last_cpu, last_progress = cpu, now
        elif now - last_progress > stall_s:
            reason = f"no CPU progress for {now - last_progress:.0f}s at {cpu:.1f}s CPU (hung)"
        if reason is None and now - start > wall_backstop_s:
            reason = f"wall {now - start:.0f}s > backstop {wall_backstop_s:.0f}s"
        if reason is not None:
            proc.kill()
            out, err = proc.communicate()
            raise BudgetExceeded(f"{' '.join(cmd)}: stopped -- {reason}\nstderr tail:\n{(err or '')[-2000:]}")

    cpu = _child_cpu_seconds(proc)
    if cpu is not None and cpu > cpu_budget_s:
        raise BudgetExceeded(f"{' '.join(cmd)}: finished over budget -- CPU {cpu:.1f}s > {cpu_budget_s:.0f}s")
    result = subprocess.CompletedProcess(cmd, proc.returncode, out, err)
    result.cpu_seconds = cpu  # type: ignore[attr-defined]
    return result
