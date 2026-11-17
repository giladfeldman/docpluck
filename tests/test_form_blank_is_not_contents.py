"""A form blank is not a table of contents; a DOI's case or opener does not unlock a digit join.

T0 strips a blank-line paragraph as a table of contents when at least half its
lines are contents lines. Any line with "___" once counted, so a two-line form
("Participant name: ______" over "Date of birth: 12 May 1990") or a one-line
"Signature: ________" paragraph was deleted whole. A contents line is now an
entry that ends in its page number, a bare leader line, or a contents heading.

S6u keeps a bare-DOI line from swallowing the page-number lines below it; the
guard compared case-sensitively and with the opener attached, so an upper-case
DOI or one opened by "(" was still joined into "10.1037/A00286012772".
"""
from __future__ import annotations

import pytest

from docpluck.normalize import _rejoin_broken_urls, _strip_toc_dot_leader_block

_BODY = "\n\n".join(["Intro paragraph about the study and its aims."] * 3)


@pytest.mark.parametrize("para, kept", [
    ("Participant name: ______\nDate of birth: 12 May 1990", "Date of birth: 12 May 1990"),
    ("Signature: ________", "Signature: ________"),
    ("Name: ____\nDate: ____\nSignature: ____\nNotes:", "Notes:"),
], ids=["two_line_form", "signature_only", "four_line_form"])
def test_form_blank_paragraph_is_kept(para, kept):
    out = _strip_toc_dot_leader_block(f"{_BODY}\n\n{para}\n\n{_BODY}")
    assert kept in out


def test_real_contents_block_is_still_stripped():
    toc = "Contents\nBackground ____________ 17\nMethods ____________ 19\nResults ____________ 23"
    out = _strip_toc_dot_leader_block(f"{_BODY}\n\n{toc}\n\n{_BODY}")
    assert "Methods" not in out and out.count("Intro paragraph") == 6


@pytest.mark.parametrize("text", [
    "10.1037/A0028601\n277\n2",
    "(10.1037/a0028601\n277\n2",
    "<10.1037/A0028601\n277\n2",
], ids=["upper_case", "paren_opener", "angle_opener"])
def test_bare_doi_line_does_not_swallow_digit_lines(text):
    assert _rejoin_broken_urls(text) == text


def test_doi_cut_mid_suffix_still_joins():
    assert _rejoin_broken_urls("Appetite. doi:10.1093/ije/1234\n567\nNext") == (
        "Appetite. doi:10.1093/ije/1234567\nNext")
