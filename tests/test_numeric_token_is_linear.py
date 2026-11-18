"""The numeric-word pattern that counts a table's number rows is linear in a long digit run.

"\\d*\\.?\\d+" retries every split of a digit run before failing, so one long
digit word that is not a number (here followed by a letter) took 15 s at
20,000 digits. The pattern is now "\\d+(\\.\\d+)?|\\.\\d+", which accepts the
same words: "12", "12.5", ".5", never "12.".
"""
from __future__ import annotations

import time

import pytest

from docpluck.tables.detect import _NUMERIC_TOKEN_RE


def test_long_digit_run_is_linear():
    times = []
    for n in (20000, 40000):
        s = "0" * n + "x"
        t0 = time.perf_counter()
        assert _NUMERIC_TOKEN_RE.match(s) is None
        times.append(time.perf_counter() - t0)
    assert times[1] < 0.5, times


@pytest.mark.parametrize("word, ok", [
    ("12", True), ("12.5", True), (".5", True), ("12.", False),
    ("(−.05)*", True), ("<.001", True), ("[3.2]", True), ("a12", False), ("1.2.3", False),
])
def test_number_words_still_match(word, ok):
    assert bool(_NUMERIC_TOKEN_RE.match(word)) is ok
