"""Unit tests for scripts/check_app_pin_sync.py::compare (the pure decision core).

Regression guard for the 2026-06-25 direction-bug: the working-tree note said
"__version__ X is ahead of latest tag Y -- UNRELEASED. Tag + push X" for ANY
inequality, so a checkout BEHIND its own latest release tag (e.g. a stale
2.4.95 working copy while v2.4.97 is live) was wrongly told it was "ahead" and
advised to tag an OLDER version. The fix makes the note direction-aware via an
ordered version-tuple comparison.

This is a pure version-string comparator (NOT extraction logic), so a non-PDF
unit test is the correct shape here — rule 0d's real-PDF requirement scopes to
extraction/render fixes.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

# Load the script as a module (it lives in scripts/, not an importable package).
_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "check_app_pin_sync.py"
_spec = importlib.util.spec_from_file_location("check_app_pin_sync", _SCRIPT)
assert _spec and _spec.loader
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

compare = _mod.compare
_vtuple = _mod._vtuple


class TestVTuple:
    def test_basic_ordering(self):
        assert _vtuple("2.4.97") > _vtuple("2.4.95")
        assert _vtuple("2.4.95") < _vtuple("2.4.97")
        assert _vtuple("2.5.0") > _vtuple("2.4.99")
        assert _vtuple("3.0.0") > _vtuple("2.99.99")

    def test_equal(self):
        assert _vtuple("2.4.97") == _vtuple("2.4.97")

    def test_malformed_component_never_sorts_high(self):
        # A garbage component sorts as -1 so it never silently beats a real one.
        assert _vtuple("2.x.0") < _vtuple("2.0.0")


class TestCompareSynced:
    def test_in_sync_no_note_when_version_equals_tag(self):
        ok, msg = compare(latest_tag="2.4.97", app_pin="2.4.97", lib_version="2.4.97")
        assert ok is True
        assert "in sync" in msg
        assert "note" not in msg.lower()
        assert "WARNING" not in msg

    def test_ahead_says_unreleased_tag_hint(self):
        # Working tree ahead of latest tag — legitimate UNRELEASED state.
        ok, msg = compare(latest_tag="2.4.97", app_pin="2.4.97", lib_version="2.4.98")
        assert ok is True
        assert "ahead" in msg
        assert "UNRELEASED" in msg
        assert "Tag + push v2.4.98" in msg

    def test_behind_says_stale_warning_not_ahead(self):
        # THE REGRESSION: working tree BEHIND latest tag must NOT say "ahead".
        ok, msg = compare(latest_tag="2.4.97", app_pin="2.4.97", lib_version="2.4.95")
        assert ok is True  # pin still tracks the release correctly -> gate PASS
        assert "ahead" not in msg
        assert "UNRELEASED" not in msg
        assert "Tag + push v2.4.95" not in msg  # never advise tagging an OLDER version
        assert "BEHIND" in msg
        assert "stale" in msg.lower()

    def test_no_note_when_lib_version_unknown(self):
        ok, msg = compare(latest_tag="2.4.97", app_pin="2.4.97", lib_version=None)
        assert ok is True
        assert "note" not in msg.lower()
        assert "WARNING" not in msg


class TestCompareFailures:
    def test_mismatch_pin_behind_tag(self):
        ok, msg = compare(latest_tag="2.4.97", app_pin="2.4.95", lib_version="2.4.97")
        assert ok is False
        assert "MISMATCH" in msg
        assert "v2.4.95" in msg and "v2.4.97" in msg

    def test_no_tag_is_failure(self):
        ok, msg = compare(latest_tag=None, app_pin="2.4.97", lib_version="2.4.97")
        assert ok is False
        assert "latest v* tag" in msg

    def test_no_pin_is_failure(self):
        ok, msg = compare(latest_tag="2.4.97", app_pin=None, lib_version="2.4.97")
        assert ok is False
        assert "pin" in msg.lower()


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
