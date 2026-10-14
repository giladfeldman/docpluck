"""A caption region of exactly four lines still stops at its header lines (d-5410ed).

10.1001/jamanetworkopen.2023.39337 p6 (checked 2026-10-14): pdftotext gives
"Table 1. Baseline Characteristics of the Study Participantsa" then the header lines
"Participant group" / "Characteristic" / "Age, y" and a blank line. The title-line rule
(title of 4+ words, then three header-like lines -> cut) existed, but a guard skipped
every region with fewer than five non-blank lines, so the caption shipped as
"... Participantsa Participant group Characteristic Age, y".
"""
from __future__ import annotations

from docpluck.extract_structured import _trim_table_caption_at_cell_region as trim


def test_four_line_region_is_cut_at_the_header_run():
    region = ("Table 1. Baseline Characteristics of the Study Participantsa\n"
              "Participant group\nCharacteristic\nAge, y")
    assert trim(region) == "Table 1. Baseline Characteristics of the Study Participantsa"


def test_four_line_region_with_a_wrapped_title_is_kept():
    # a lowercase wrap line is a title continuation, never a header
    region = "Table 2. Means and Standard Deviations of the\nkey variables by\nCondition\nStudy"
    assert trim(region) == region


def test_three_line_region_is_left_alone():
    region = "Table 3. Descriptive Statistics\nMean\nSD"
    assert trim(region) == region
