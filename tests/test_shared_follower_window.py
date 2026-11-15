"""The block-repeat vote reads as far as the value vote (consult round 2,
Haiku seat, 2026-11-13). `_shared_follower` looked 2 lines ahead while
`_value_followed_fraction` looks 4, so a repeated caption whose continuation
sat under two blank lines cast no vote. Text is invented. Failed on v2.4.160.
"""
from __future__ import annotations

from docpluck.normalize import _shared_follower, _value_followed_fraction


def test_follower_found_past_two_blank_lines():
    lines = ["Mean ratings by condition for each panel with", "", "",
             "the error bars showing one standard error", "body text here",
             "Mean ratings by condition for each panel with", "", "",
             "the error bars showing one standard error", "other body"]
    key, share = _shared_follower(lines, [0, 5])
    assert share == 1.0 and key.startswith("the error bars")


def test_both_votes_use_one_window():
    lines = ["Label", "", "", ".35"]
    assert _value_followed_fraction(lines, [0]) == 1.0
    lines2 = ["Label", "", "", "continuation words"]
    assert _shared_follower(lines2, [0])[1] == 1.0


def test_beyond_window_casts_no_vote():
    lines = ["Label", "", "", "", "", "far away"]
    assert _shared_follower(lines, [0]) == ("", 0.0)
