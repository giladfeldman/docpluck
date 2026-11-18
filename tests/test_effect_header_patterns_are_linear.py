"""Effect-type header patterns stay fast on a long header cell.

Two unbounded runs of the same class side by side ("\s*[_-]?\s*") backtrack
quadratically, three cubically: a header of 2,000 spaces after "eta" took 41 s
and one after "generalized" 17 s (2026-11-18). Every gap is now bounded.
"""
from __future__ import annotations

import re
import time

import pytest

from docpluck.tables import flatten as F

_PATTERNS = (
    [(f"type:{n}", p) for n, p in F._EFFECT_TYPE_PATTERNS]
    + [(f"vocab:{n}", p) for n, p in F._VOCAB_EFFECT_TYPE_PATTERNS]
    + [("generalized_eta", F._GENERALIZED_ETA_RE), ("cohens_d_name", re.compile(F._COHENS_D_NAME))]
)
_PREFIXES = ["", "eta", "eta squared", "\u03b7", "\u03b7\u00b2", "generalized", "partial",
             "cohen's d", "hedges"]
_FILLS = [" ", "_", "-", " _", "\x00BR\x00"]


@pytest.mark.parametrize("name, rx", _PATTERNS, ids=[n for n, _ in _PATTERNS])
def test_pattern_is_fast_on_a_long_header(name, rx):
    worst = 0.0
    for pre in _PREFIXES:
        for fill in _FILLS:
            s = pre + fill * (2000 // len(fill)) + "x"
            t0 = time.perf_counter()
            rx.search(s)
            worst = max(worst, time.perf_counter() - t0)
    assert worst < 0.25, f"{name}: {worst:.2f}s"


@pytest.mark.parametrize("header, kind", [
    ("\u03b7\u00b2p", "eta_squared_partial"), ("eta squared p", "eta_squared_partial"),
    ("partial eta", "eta_squared_partial"), ("Cohen's d", "cohens_d"), ("Cohen's dz", "cohens_d"),
    ("Hedges' g", "hedges_g"),
], ids=["greek_p", "latin_p", "partial", "cohen_d", "cohen_dz", "hedges"])
def test_bounded_patterns_still_name_the_printed_types(header, kind):
    assert any(n == kind and p.search(header) for n, p in F._EFFECT_TYPE_PATTERNS)
    if kind == "eta_squared_partial":
        assert not F._GENERALIZED_ETA_RE.search(header)
    assert F._GENERALIZED_ETA_RE.search("generalized eta") and F._GENERALIZED_ETA_RE.search("\u03b7\u00b2 G")
