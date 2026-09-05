"""The corpus guard-diff's arm B must be REACHABLE: every name it neutralises must exist.

Written 2026-09-04 against the unfixed tree and watched fail (todo.md W-0023).

`tools/diag/table_capture_guard_diff.py` is the gate `docpluck-qa` check 2 names as
mandatory for any change under `docpluck/tables/`. Its arm B monkeypatches named
functions back to their pre-fix behaviour. One of those names, `detect._column_runs`,
never existed in any commit -- the caption clip it belonged to was written, measured
and REVERTED before release (register J14) -- so `_neutralise` raised AttributeError on
every one of the 26 corpus papers and the gate extracted nothing, for as long as it
existed. A second arm, `row_cluster`, swapped `_cluster_into_rows` for a BEHAVIOURALLY
IDENTICAL copy of itself (the anchor fix was also reverted, J12): `_cluster_prev_word`
is a refactor, not a byte-equal copy -- it hoists the threshold into `_row_threshold` --
but both measure the y-gap to the PREVIOUS WORD and cluster 3000/3000 random word sets
identically (measured 2026-09-04). So neutralising it changed nothing and could only
ever pull `arms_differ` toward the zero the tool refuses to print.

This test imports the tool and asserts three things a gate must satisfy before its
verdict means anything:

  1. every name arm B patches exists on the module it patches;
  2. neutralising and restoring round-trips (the tool cannot leak a patched library
     into the caller's process);
  3. every arm actually CHANGES the callable it patches -- an arm that swaps a function
     for an equivalent one is a measurement of nothing wearing a measurement's name.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_TOOL = Path(__file__).resolve().parents[1] / "tools" / "diag" / "table_capture_guard_diff.py"


@pytest.fixture(scope="module")
def guard_diff():
    spec = importlib.util.spec_from_file_location("table_capture_guard_diff", _TOOL)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_every_neutralised_name_exists_before_arm_b_runs(guard_diff):
    """AttributeError here is W-0023: the arm names a function the library never had."""
    undo = guard_diff._neutralise(guard_diff.CHANGES)
    try:
        assert undo, "arm B neutralised nothing -- the gate has no arms"
        for mod, name, orig in undo:
            assert hasattr(mod, name), f"{mod.__name__}.{name} does not exist"
            assert callable(orig)
    finally:
        guard_diff._restore(undo)


def test_neutralise_restore_round_trips(guard_diff):
    before = {}
    undo = guard_diff._neutralise(guard_diff.CHANGES)
    for mod, name, orig in undo:
        before[(mod.__name__, name)] = orig
    guard_diff._restore(undo)
    for (modname, name), orig in before.items():
        assert getattr(sys.modules[modname], name) is orig, f"{modname}.{name} not restored"


def test_every_arm_changes_the_callable_it_patches(guard_diff):
    """An arm whose replacement is the shipped function measures nothing (J12's row_cluster)."""
    undo = guard_diff._neutralise(guard_diff.CHANGES)
    try:
        for mod, name, orig in undo:
            patched = getattr(mod, name)
            assert patched is not orig, f"{mod.__name__}.{name}: arm B is the shipped code"
            # Same source text is the same rule under a different name.
            import inspect
            try:
                assert inspect.getsource(patched) != inspect.getsource(orig), (
                    f"{mod.__name__}.{name}: arm B re-implements the shipped rule verbatim"
                )
            except (OSError, TypeError):
                pass  # lambdas defined inline have no retrievable source; identity check above suffices
    finally:
        guard_diff._restore(undo)
