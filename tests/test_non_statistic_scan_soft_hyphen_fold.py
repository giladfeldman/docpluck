"""The non-statistic corpus scan must fold a soft hyphen to NOTHING.

S6 deletes U+00AD (soft hyphen) outright, so a URL such as
``publi\u00adca\u00adtions`` correctly becomes ``publications``. The scan used to
fold U+00AD to ``-``, which made that correct strip look like a rewritten URL
and turned the release gate red on a healthy tree (two corpus papers).
"""
from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path

import pytest

from docpluck import NormalizationLevel, normalize_text

URL = "http://www.example.org/pub\u00adlica\u00adtions/"
_DIAG = str(Path(__file__).resolve().parents[1] / "tools" / "diag")


@pytest.fixture(scope="module")
def scan():
    """Import the diagnostic script without leaking its import-time env changes."""
    before = {k: v for k, v in os.environ.items() if k.startswith("DOCPLUCK_")}
    sys.path.insert(0, _DIAG)
    try:
        mod = importlib.import_module("non_statistic_corpus_scan")
    finally:
        sys.path.remove(_DIAG)
        for k in [k for k in os.environ if k.startswith("DOCPLUCK_")]:
            if k not in before:
                del os.environ[k]
        os.environ.update(before)
    return mod


def test_soft_hyphen_folds_to_nothing(scan):
    assert scan.notation_fold(URL) == "http://www.example.org/publications/"


def test_a_stripped_soft_hyphen_is_not_reported_as_a_rewrite(scan):
    out, _ = normalize_text("can be found at " + URL, NormalizationLevel.academic)
    assert "publications" in out  # control: S6 really did strip it
    assert scan.notation_fold(URL) in scan.notation_fold(out)


def test_a_real_dash_still_folds_to_ascii_hyphen(scan):
    # Control: the dash fold must still work, or the tests above prove nothing.
    assert scan.notation_fold("a\u2013b") == "a-b"
