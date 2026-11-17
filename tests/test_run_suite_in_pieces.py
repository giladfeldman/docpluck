"""The piece runner never reads a stopped or silent run as a pass.

A suite stopped at the job queue's 60-minute limit printed dots and no summary;
read loosely, that looks like "no failures". Under -q pytest prints its summary
without "====" bars, which a first version of the runner missed (it reported a
clean run as NOT RUN, the safe direction, but still wrong).
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_spec = importlib.util.spec_from_file_location(
    "run_suite_in_pieces", Path(__file__).resolve().parents[1] / "scripts" / "run_suite_in_pieces.py")
rsp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rsp)


@pytest.mark.parametrize("log, code, verdict", [
    ("....loadq: task reached its 60-minute limit; stopping", 124, "NOT RUN"),
    ("..x....", 0, "NOT RUN"),                        # no summary at all
    ("3 passed, 1 failed in 2.0s", 1, "FAIL"),
    ("1 error in 1.1s", 1, "FAIL"),
    ("6 passed in 3.62s", 0, "PASS"),                 # -q form
    ("==== 5 passed, 2 skipped in 1.1s ====", 0, "PASS"),
    ("6 passed in 3.62s", 3, "NOT RUN"),              # summary but a bad exit
], ids=["stopped", "silent", "failed", "error", "q_form", "bar_form", "bad_exit"])
def test_verdict(log, code, verdict):
    assert rsp._verdict(log, code)[0].startswith(verdict)
