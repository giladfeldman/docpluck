"""Pagination is decided on the raw text; table integers and row labels survive.

F3 (2026-09-03, re-measured 2026-09-27): the line-space page-number rule UNIONED
every +1 run 20+ lines apart, so table columns of small integers chained like
pages and were blanked -- 1,840 lines over 120 PDFs, 36 papers blanking more
lines than they have pages. F1: the repeated-line strip's once-per-page arm
took table row labels repeated once per page. Both now read one verdict
(`normalize._pagination_verdict`), taken while the page breaks still exist.

Real papers only, by DOI, from the article custodian; a missing file FAILS.
"""
from __future__ import annotations

import pytest

from docpluck.extract import extract_pdf
from docpluck.normalize import (
    PAGE_BREAK,
    NormalizationLevel,
    _pagination_verdict,
    _strip_standalone_page_numbers,
    normalize_text,
)
from docpluck.testing.corpus import custody_path


def _raw(name: str) -> str:
    p = custody_path("fulltext", name)
    if not p.is_file():
        pytest.fail(f"custodian copy missing: {p}")
    return extract_pdf(p.read_bytes())[0]


def test_jesp_2010_page_numbers_are_exactly_the_printed_ones():
    """10.1016/j.jesp.2010.02.007, printed pages 685-690 (page-verified p3)."""
    raw = _raw("10.1016__j.jesp.2010.02.007.pdf")
    verdict = _pagination_verdict(raw)
    assert verdict is not None
    assert sorted(verdict.members) == [685, 686, 687, 688]


def test_jesp_2010_table_raw_data_is_not_blanked():
    """p3 Table 1 prints raw ratings 6 1 7 8 9 / 2 3 2 1 1; the old rule blanked
    46 such lines on pages 3-4 (50 blanked for a 6-page paper)."""
    raw = _raw("10.1016__j.jesp.2010.02.007.pdf")
    before = raw.split("\n")
    after = _strip_standalone_page_numbers(raw, _pagination_verdict(raw)).split("\n")
    assert len(before) == len(after)
    blanked = [b.strip(PAGE_BREAK + " ") for b, a in zip(before, after) if b != a]
    assert sorted(blanked) == ["685", "686", "687", "688"], blanked


def test_pone_row_labels_repeated_once_per_page_keep_every_copy():
    """10.1371/journal.pone.0285199: each row label precedes its value on every
    page of a long table; deleting copies 2..N orphans those values."""
    raw = _raw("10.1371__journal.pone.0285199.pdf")
    out, report = normalize_text(raw, NormalizationLevel.academic)
    for label in ("Family income at age 10", "Household income (Per £1000)"):
        n_raw = sum(ln.strip() == label for ln in raw.split("\n"))
        n_out = sum(ln.strip() == label for ln in out.split("\n"))
        assert n_raw >= 5 and n_out == n_raw, (label, n_raw, n_out)
        assert label in report.fallback_details["repeated_line_kept_value_followed"]


def test_unpaginated_text_keeps_the_legacy_rule():
    assert _pagination_verdict("no page breaks here\n12\n") is None


def test_a_second_pass_elects_no_offset_from_table_integers():
    raw = _raw("10.1016__j.jesp.2010.02.007.pdf")
    once, _ = normalize_text(raw, NormalizationLevel.academic)
    twice, _ = normalize_text(once, NormalizationLevel.academic)
    assert once == twice


# Consult round 2026-10-08 (Sonnet, tier 2), findings 1 and 3, reproduced here.
def test_a_row_label_followed_by_a_value_equal_to_a_page_token_is_still_value_followed():
    """F1 guard: a verified page-number TOKEN must be skipped only where it sits
    like a page number (set off by a blank line), never when it is glued under
    a row label as that label's value."""
    from docpluck.normalize import _value_followed_fraction

    lines = ["Number of participants", "4", "Mean age", "", "Collabra: Psychology", "", "4", "", "Body."]
    assert _value_followed_fraction(lines, [0], ignore=frozenset({"4"})) == 1.0
    # ...while a running header followed (after a blank line) by its page number is not.
    assert _value_followed_fraction(lines, [4], ignore=frozenset({"4"})) == 0.0


def test_years_are_not_elected_as_four_digit_page_numbers():
    """Finding 3: 2019 / 2020 / 2021 each as its own block on consecutive pages
    (a year axis) satisfy the arithmetic; the later 4-digit rule already excludes
    1900-2100 as years, and so does the verdict."""
    body = "".join(f"Body sentence {i}.\n" for i in range(30))
    raw = "".join(f"{body}\n{y}\n\n{body}\f" for y in (2019, 2020, 2021, 2022))
    verdict = _pagination_verdict(raw)
    assert verdict is not None and not verdict.members, verdict
