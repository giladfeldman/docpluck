"""Real-PDF regression tests for the WRAPPED contact-footer strip (run 6, cycle 1).

Defect (reproduced at HEAD on ``xiao_2021_crsp``, 2026-08-05): the Taylor &
Francis correspondence footer leaked into body prose and **split a real
sentence in half**::

    ... The option superior to the decoy is commonly referred to as the
    target, whereas the other option is referred to as the competitor.
    The target and the
    CONTACT Gilad Feldman            <-- LEAKED publisher furniture
    Hong Kong, Hong Kong SAR         <-- LEAKED publisher furniture
    competitor form a core choice set. With a decoy added ...

Root cause: the v2.4.6 pattern requires ``CONTACT``, the author name AND the
email address to sit on ONE line. When the source PDF column-wraps the
correspondence block, pdftotext serialises it across several lines, so the
one-line pattern misses every one of them. Four of the block's six lines were
already dropped by *other* P0 patterns (the email line, the supplemental-data
sidebar, the copyright line, the truncated affiliation) — which is why only the
opener and the region tail survived, landing mid-sentence.

The fix is keyed on the STRUCTURAL SIGNATURE (a line-initial all-caps
``CONTACT`` followed only by a personal name), never on paper identity, and the
region tail is removed only when ADJACENT to such an opener — a bare
``<City>, <Region>`` line is an ordinary prose fragment and must never be
stripped on its own shape.

Per /docpluck-iterate rule 0d: ships with a ``*_real_pdf`` test exercising the
public library entry point on an actual PDF fixture.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from docpluck.normalize import (
    _CONTACT_NON_NAME_WORDS,
    _CONTACT_REGION_TAIL,
    _WRAPPED_CONTACT_OPENER,
    _strip_page_footer_lines,
)
from docpluck.render import render_pdf_to_markdown


_PDF_ROOT = Path(__file__).resolve().parents[1] / ".." / "PDFextractor" / "test-pdfs"


def _maybe_render(rel: str) -> str:
    pdf = (_PDF_ROOT / rel).resolve()
    if not pdf.is_file():
        pytest.skip(f"fixture not available locally: {rel}")
    return render_pdf_to_markdown(pdf.read_bytes())


# ── Contract tests (synthetic strings, fast) ───────────────────────────────


def test_wrapped_contact_block_is_removed_and_sentence_rejoins():
    """The whole wrapped block goes, and the split sentence becomes contiguous."""
    raw = "\n".join(
        [
            "target, whereas the other option is referred to as the competitor.",
            "The target and the",
            "CONTACT Gilad Feldman",
            "gfeldman@hku.hk; giladfel@gmail.com",
            "Hong Kong, Hong Kong SAR",
            "Supplemental data for this article can be accessed here.",
            "© 2021 European Association of Social Psychology",
            "",
            "competitor form a core choice set. With a decoy added to the set,",
        ]
    )
    out = _strip_page_footer_lines(raw)
    assert "CONTACT Gilad Feldman" not in out
    assert "Hong Kong, Hong Kong SAR" not in out
    assert "gfeldman@hku.hk" not in out
    # the two halves of the real sentence must now be adjacent
    assert "The target and the\ncompetitor form a core choice set." in out


@pytest.mark.parametrize(
    "line",
    [
        "CONTACT Gilad Feldman",
        "CONTACT Qinyu Xiao",
        "CONTACT Anna-Maria O’Brien",
        "CONTACT John R Smith",
        "CONTACT John R. Smith",
        "CONTACT Mary-Jane Watson",
        "CONTACT José Álvarez",
        "CONTACT Ian McDonald",
    ],
)
def test_wrapped_contact_openers_are_stripped(line):
    assert _WRAPPED_CONTACT_OPENER.match(line)
    assert not _CONTACT_NON_NAME_WORDS.search(line)
    assert _strip_page_footer_lines(line).strip() == ""


@pytest.mark.parametrize(
    "line",
    [
        # nav / heading furniture — matches the name shape but is not a name
        "CONTACT Details Below",
        "CONTACT Author Details",
        "CONTACT Support Team",
        "CONTACT Page Two",
        # not the wrapped shape at all
        "CONTACT US",
        "CONTACT INFORMATION",
        "CONTACT",
        "CONTACT the corresponding author for data",
        "Contact Gilad Feldman",
        "We CONTACT Participants Twice",
    ],
)
def test_non_correspondence_contact_lines_survive(line):
    """The veto must keep ordinary prose / navigation text."""
    assert _strip_page_footer_lines(line).strip() == line.strip()


def test_region_tail_alone_is_never_stripped():
    """A bare '<City>, <Region>' line is prose — only adjacency to an opener
    licenses removing it. This is the false-positive guard that makes the
    tail sweep safe."""
    prose = "\n".join(
        [
            "Participants were recruited in two waves.",
            "Hong Kong, Hong Kong SAR",
            "All gave informed consent.",
        ]
    )
    out = _strip_page_footer_lines(prose)
    assert "Hong Kong, Hong Kong SAR" in out
    # the shape does match the tail pattern — proving the guard is adjacency,
    # not the pattern alone
    assert _CONTACT_REGION_TAIL.match("Hong Kong, Hong Kong SAR")


def test_tail_sweep_stops_at_the_first_body_line():
    """Only the furniture run is consumed; the next prose line survives even
    when it happens to look like a '<Word>, <Word>' tail."""
    raw = "\n".join(
        [
            "CONTACT Gilad Feldman",
            "Hong Kong, Hong Kong SAR",
            "Sadly, participants withdrew.",
            "Berlin, Germany",
        ]
    )
    out = _strip_page_footer_lines(raw)
    assert "CONTACT Gilad Feldman" not in out
    assert "Hong Kong, Hong Kong SAR" not in out
    assert "Sadly, participants withdrew." in out
    # past the body line the sweep is off, so this stays
    assert "Berlin, Germany" in out


# ── Real-PDF tests (the rule-0d gate) ──────────────────────────────────────


def test_xiao_2021_crsp_contact_block_absent_from_body_real_pdf():
    md = _maybe_render("apa/xiao_2021_crsp.pdf")
    assert "CONTACT Gilad Feldman" not in md
    assert "Hong Kong, Hong Kong SAR" not in md


def test_xiao_2021_crsp_split_sentence_is_contiguous_real_pdf():
    """The defect's user-visible harm: a real sentence cut in half by
    publisher furniture. Both halves must now sit in one paragraph."""
    md = _maybe_render("apa/xiao_2021_crsp.pdf")
    assert "The target and the" in md
    assert "competitor form a core choice set" in md
    head = md.index("The target and the")
    tail = md.index("competitor form a core choice set")
    between = md[head:tail]
    # nothing but the wrap whitespace may separate the two halves
    assert "CONTACT" not in between
    assert len(between) < 120, f"furniture still between the halves: {between!r}"


def test_xiao_2021_crsp_body_text_not_over_stripped_real_pdf():
    """Sanity: the strip must not have eaten surrounding body prose."""
    md = _maybe_render("apa/xiao_2021_crsp.pdf")
    assert "The option superior to the decoy is commonly referred to as the" in md
    assert "asymmetrically dominated decoy" in md
