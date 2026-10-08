"""H0's banner strip refuses to delete a line that carries a labelled statistic.

Promised to ESCImate on 2026-08-22 (their §3, U+0008 narrowing): the guard sits
on H0's LINE deletion, not on the control-character strip. Measured over the
125-paper manifest before shipping: H0 dropped 313 lines and none carried a
labelled statistic, so these are mechanism tests plus a two-sided control on
real masthead lines that must still be dropped.
"""
from __future__ import annotations

from docpluck.normalize import (
    _banner_line_carries_statistic,
    _strip_document_header_banners,
)

# Real header-zone furniture H0 drops today (10.1177/00031224241252079,
# 10.48550/arxiv.2406.11713). Their identifiers are digit runs and dates; the
# broad `_carries_statistical_content` would have vetoed both.
REAL_FURNITURE = [
    "ASRXXX10.1177/00031224241252079American Sociological ReviewJaspers et al.",
    "arXiv:2406.11713v1 [cs.CV] 17 Jun 2024",
]


def test_real_masthead_lines_are_not_mistaken_for_statistics():
    for line in REAL_FURNITURE:
        assert not _banner_line_carries_statistic(line), line


def test_a_labelled_statistic_is_recognised_outside_the_identifier():
    assert _banner_line_carries_statistic("https://doi.org/10.1/abc t(28) = 2.10, p = .045")
    assert _banner_line_carries_statistic("www.example.org β = .48")
    assert not _banner_line_carries_statistic("https://doi.org/10.1037/xge0001234")


def test_h0_keeps_a_banner_shaped_line_that_carries_a_statistic():
    text = (
        "A Title Line\n"
        "Published in final edited form as: the effect held, F(1, 28) = 5.10, p = .031\n"
        "Body.\n"
    )
    assert _strip_document_header_banners(text) == text


def test_h0_still_drops_the_same_banner_without_one():
    text = "A Title Line\nPublished in final edited form as: J Exp Psychol. 2020\nBody.\n"
    out = _strip_document_header_banners(text)
    assert "Published in final edited form" not in out
    assert "A Title Line" in out and "Body." in out
