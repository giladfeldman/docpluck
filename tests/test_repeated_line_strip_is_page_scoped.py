"""A repeated line is furniture because of WHERE ON THE PAGE it sits.

The repeated-line strip (`P0q_repeated_line_strip`) decided with
``min(gaps) >= 20`` — the minimum LINE-INDEX distance between consecutive
occurrences, used as a proxy for "appears once per page". The proxy is not
stable under line removal, and the rule's own comment predicted the failure it
caused: *"causing idempotence drift when pass 2 has a shorter input."*

## What it actually did, measured on `ieee_access_5.pdf`

``Performance metric`` is a table COLUMN HEADER. On pass 1 it appears NINE
times, at line positions::

    [521, 545, 582, 651, 682, 972, 978, 1032, 1040]
                                 ^^^^^^^^  ^^^^^^^^   two tight pairs

so ``min(gaps)`` is 6 and the line is KEPT. Other steps then delete those four
tail occurrences. Pass 2 sees five well-spaced ones, ``min(gaps)`` is 22, and
all five are DELETED — leaving a column of anonymous numbers with nothing
saying what they measure.

No threshold fixes this. Min-gap over a *shrinking* occurrence set is not
monotone, so every threshold has an input that crosses it in one direction or
the other.

## The metric that survives line removal

Which PAGE each occurrence sits on. A line's page is a property of the
document; deleting other lines cannot move it. Over the 21-paper strided
sample the classes separate with no overlap:

============================  ==============================  ==========
class                         signature                       count
============================  ==============================  ==========
running header / footer       5–21 pages, ≤1 per page             16
watermark                     on EVERY page, 4–5 per page          4
**table content**             1–4 pages, 2–26 per page            13
============================  ==============================  ==========

All thirteen in the third row were being DELETED — `Number of trained
architectures`, the values `100`/`200`/`0.18`/`2`/`3`/`4`/`8`, `Total`,
`Other`, demography_3's 21 `***` significance markers (19 of them on ONE page,
taken by the `count >= 20` path) and maier_2023_collabra's 26 `X` table marks
(ALL on one page). So this was never only an idempotency bug.

## Two prerequisites, both of which are also fixes

1. **The page boundaries had to come back.** Five steps dropped whole lines
   with a bare ``continue``, taking the form feed glued to each — 371 raw form
   feeds became 85, with 11 of 21 papers left at ZERO page boundaries. A gate
   that asks "which page?" cannot run on that. See
   `test_page_boundaries_survive_furniture_removal` below.
2. **`_carries_statistical_content` had to be consulted** (CLAUDE.md rule 0g,
   "delete furniture, never data" — this deleting step never called it). With
   the page gate in, `j_health_soc_behav_1`'s figure note sits once under each
   of five figures on five pages and is indistinguishable from a running footer
   BY POSITION. It is unmistakable by CONTENT: it carries ``N = 136,739``.

Written 2026-08-25 against the unfixed code and watched fail.
"""

from __future__ import annotations

import pytest

from docpluck.extract import extract_pdf
from docpluck.normalize import (
    NormalizationLevel,
    PAGE_BREAK,
    keep_page_break,
    normalize_text,
    page_break_residue,
)

from .conftest import pdf_available, pdf_path

_IEEE5 = ("docpluck", "ieee", "ieee_access_5.pdf")
_JHSB = ("docpluck", "asa", "j_health_soc_behav_1.pdf")


def _normalized(parts) -> str:
    raw, _method = extract_pdf(open(pdf_path(*parts), "rb").read())
    assert len(raw) > 10_000, (
        "extraction returned almost nothing — assert the input before the "
        "output, or an empty corpus reads as a clean result"
    )
    text, _report = normalize_text(raw, NormalizationLevel("academic"))
    return text


# ---------------------------------------------------------------------------
# The shared page-boundary helper
# ---------------------------------------------------------------------------

def test_keep_page_break_preserves_the_boundary_of_a_deleted_line():
    out: list[str] = []
    keep_page_break(PAGE_BREAK + "Smith et al.", out)
    assert out == [PAGE_BREAK], "the furniture goes, the page boundary stays"


def test_keep_page_break_emits_nothing_for_an_ordinary_line():
    out: list[str] = []
    keep_page_break("Smith et al.", out)
    assert out == [], "a line with no boundary must not manufacture one"


def test_a_double_form_feed_survives_intact():
    """`\\f\\f` is the footnote-appendix marker, not an accident."""
    assert page_break_residue(PAGE_BREAK * 2 + "junk") == PAGE_BREAK * 2


# ---------------------------------------------------------------------------
# The defect: a table column header deleted on the second pass
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not pdf_available(*_IEEE5), reason="test corpus not available")
def test_a_repeated_table_column_header_is_not_deleted():
    """`Performance metric` labels a column; deleting it orphans the numbers."""
    text = _normalized(_IEEE5)
    assert text.count("Performance metric") >= 5, (
        "the repeated-line strip deleted a table COLUMN HEADER — the numbers "
        "underneath it are now anonymous"
    )


@pytest.mark.skipif(not pdf_available(*_IEEE5), reason="test corpus not available")
def test_a_repeated_table_row_label_is_not_deleted():
    text = _normalized(_IEEE5)
    assert "Number of trained architectures" in text


@pytest.mark.skipif(not pdf_available(*_IEEE5), reason="test corpus not available")
def test_normalization_reaches_a_fixed_point_on_ieee_access_5():
    """The corpus idempotency ratchet was at 1, and this paper was the 1."""
    raw, _ = extract_pdf(open(pdf_path(*_IEEE5), "rb").read())
    L = NormalizationLevel("academic")
    once, _ = normalize_text(raw, L)
    twice, _ = normalize_text(once, L)
    assert once == twice, (
        "a second normalization pass changed the text — the page-index gate is "
        "back, or something upstream is moving occurrences between passes"
    )


@pytest.mark.skipif(not pdf_available(*_IEEE5), reason="test corpus not available")
def test_the_genuine_running_header_is_still_removed():
    """The other side of the gate. Without this, "keeps more" is not a fix.

    `SeqNAS: Neural Architecture Search for Event Sequence Classification` is
    the article title printed on 16 of 17 pages, once each.
    """
    text = _normalized(_IEEE5)
    assert text.count("SeqNAS: Neural Architecture Search for Event Sequence") <= 2, (
        "the running header survived — the gate has stopped removing furniture, "
        "which is the mirror failure of removing data"
    )


@pytest.mark.skipif(not pdf_available(*_IEEE5), reason="test corpus not available")
def test_page_boundaries_survive_furniture_removal():
    """16 of this paper's 17 form feeds arrive glued to a repeated header."""
    raw, _ = extract_pdf(open(pdf_path(*_IEEE5), "rb").read())
    text, _ = normalize_text(raw, NormalizationLevel("academic"))
    raw_breaks = raw.count(PAGE_BREAK)
    kept = text.count(PAGE_BREAK)
    assert raw_breaks >= 15, f"fixture changed: only {raw_breaks} raw page breaks"
    assert kept >= 10, (
        f"only {kept} of {raw_breaks} page boundaries survived. Stripping the "
        "furniture took the structure with it — and the page-distribution gate "
        "is built on that structure, so this is not a cosmetic loss"
    )


# ---------------------------------------------------------------------------
# Rule 0g: delete furniture, never data
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not pdf_available(*_JHSB), reason="test corpus not available")
def test_a_figure_note_carrying_a_sample_size_is_never_furniture():
    """Five figures, five pages, once each — a running footer by POSITION only.

    This case exists because the page-distribution gate INTRODUCED it: the note
    scores exactly like a running footer and is saved only by its content.
    """
    text = _normalized(_JHSB)
    assert "N = 136,739" in text, (
        "a figure note carrying the study's sample size was deleted as "
        "furniture — rule 0g: consult _carries_statistical_content before "
        "removing any line"
    )


@pytest.mark.skipif(not pdf_available(*_JHSB), reason="test corpus not available")
def test_a_wrapped_data_source_caption_survives_with_its_second_line():
    """The note wraps; its second line carries the survey and the year range.

    Guard (b) cannot see it — a wrapped line ends mid-sentence, so the
    terminal-punctuation test fails. The data-source-caption marker catches it
    once the year is allowed to sit anywhere inside the parenthesis group.
    """
    text = _normalized(_JHSB)
    assert "Household, Income and Labour Dynamics in Australia Survey" in text
    assert "Release 22, years 2001-2023" in text
