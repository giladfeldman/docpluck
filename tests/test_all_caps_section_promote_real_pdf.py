"""Real-PDF regression tests for v2.4.26 ALL-CAPS section heading
promotion (cycle 11, deferred item B from the cycle-9 handoff).

The section detector in :mod:`docpluck.sections.annotators.text`
rejects ALL-CAPS multi-word headings when pdftotext flattens the
paragraph breaks around them (no blank line before AND no blank line
after). This breaks AOM-style structure where major section headings
sit directly below the prior paragraph's last sentence and directly
above a sub-section label::

    ...last paragraph sentence.
    STUDY 1: QUASI-FIELD EXPERIMENT
    Procedure
    We conducted the study...

Cycle 11 added a render-layer post-processor
(:func:`docpluck.render._promote_study_subsection_headings`) that
promotes ALL-CAPS standalone-line headings to ``## {heading}`` when
they sit between a sentence-terminator and a heading-like next line.

These tests exercise the public render entry point
(``render_pdf_to_markdown``) against the actual library code and four
real-PDF fixtures, per CLAUDE.md hard rule 0d.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from docpluck.render import (
    _ALL_CAPS_SECTION_HEADING_RE,
    _is_safe_all_caps_promote,
    render_pdf_to_markdown,
)


os.environ.setdefault("DOCPLUCK_DISABLE_CAMELOT", "1")


TEST_PDFS = Path(__file__).resolve().parents[1].parent / "PDFextractor" / "test-pdfs"


# ---- Contract tests (cheap, pure helpers) ---------------------------------


class TestAllCapsSectionRegex:
    @pytest.mark.parametrize("line", [
        "THEORETICAL DEVELOPMENT",
        "OVERVIEW OF THE STUDIES",
        "STUDY 1: QUASI-FIELD EXPERIMENT",
        "STUDY 2: LABORATORY EXPERIMENT",
        "GENERAL DISCUSSION",
        "MANIPULATION AND MEASURES",
        "LIMITATIONS AND FUTURE RESEARCH DIRECTIONS",
        "PRESENT STUDY AND RESEARCH QUESTIONS",
        "SCHOLARLY IMPACT AND KNOWLEDGE TRANSFER",
    ])
    def test_admits_real_section_headings(self, line):
        assert _ALL_CAPS_SECTION_HEADING_RE.match(line), line

    @pytest.mark.parametrize("line", [
        "USA",                        # too short
        "this is body text",          # lowercase
        "Mixed Case Heading",         # not ALL-CAPS
        "ABC",                        # too short
        "PARTICIPANTS were 225",      # contains lowercase
    ])
    def test_rejects_non_headings(self, line):
        m = _ALL_CAPS_SECTION_HEADING_RE.match(line)
        assert not m or m.group(0) != line, line


class TestIsSafeAllCapsPromote:
    def test_safe_when_prev_ends_with_period_and_next_is_subheading(self):
        lines = [
            "...end of the prior paragraph sentence.",
            "STUDY 1: QUASI-FIELD EXPERIMENT",
            "Procedure",
        ]
        assert _is_safe_all_caps_promote(lines, 1, lines[1])

    def test_unsafe_when_prev_does_not_terminate(self):
        lines = [
            "trailing fragment with no period",
            "STUDY 1: QUASI-FIELD EXPERIMENT",
            "Procedure",
        ]
        assert not _is_safe_all_caps_promote(lines, 1, lines[1])

    def test_unsafe_when_next_line_is_lowercase(self):
        lines = [
            "prior sentence ends here.",
            "STUDY 1: QUASI-FIELD EXPERIMENT",
            "we conducted the study",
        ]
        assert not _is_safe_all_caps_promote(lines, 1, lines[1])

    def test_unsafe_when_next_is_another_all_caps(self):
        # Multi-line title page — don't promote here.
        lines = [
            "prior.",
            "STUDY 1: QUASI-FIELD",
            "EXPERIMENT IN A KOREAN COMPANY",
            "Procedure",
        ]
        assert not _is_safe_all_caps_promote(lines, 1, lines[1])


# ---- Real-PDF regression tests (rule 0d) ----------------------------------


def _headings(md: str) -> list[str]:
    return [m.group() for m in re.finditer(r"^#{1,6} .+", md, re.MULTILINE)]


@pytest.mark.skipif(
    not (TEST_PDFS / "aom" / "amj_1.pdf").exists(),
    reason="amj_1.pdf fixture not present",
)
def test_amj_1_promotes_all_caps_headings():
    """amj_1.pdf has 4 ALL-CAPS major section headings that v2.4.25
    failed to promote because the section detector's strict
    blank-before/blank-after constraints rejected them."""
    pdf = TEST_PDFS / "aom" / "amj_1.pdf"
    md = render_pdf_to_markdown(pdf.read_bytes())
    headings = _headings(md)
    expected = [
        "## THEORETICAL DEVELOPMENT",
        "## OVERVIEW OF THE STUDIES",
        "## STUDY 1: QUASI-FIELD EXPERIMENT",
        "## STUDY 2: LABORATORY EXPERIMENT",
    ]
    for h in expected:
        assert h in headings, f"missing {h!r} in {headings!r}"


@pytest.mark.skipif(
    not (TEST_PDFS / "aom" / "amle_1.pdf").exists(),
    reason="amle_1.pdf fixture not present",
)
def test_amle_1_promotes_all_caps_headings():
    """amle_1.pdf has several ALL-CAPS section headings (METHOD,
    RESULTS, DISCUSSION, etc.) that v2.4.25 left as inline bold."""
    pdf = TEST_PDFS / "aom" / "amle_1.pdf"
    md = render_pdf_to_markdown(pdf.read_bytes())
    headings = _headings(md)
    for h in ("## METHOD", "## RESULTS", "## DISCUSSION"):
        assert h in headings, f"missing {h!r} in {headings!r}"


@pytest.mark.skipif(
    not (TEST_PDFS / "ieee" / "ieee_access_2.pdf").exists(),
    reason="ieee_access_2.pdf fixture not present",
)
def test_ieee_access_2_promotes_all_caps_headings():
    """ieee_access_2.pdf has INTRODUCTION, METHODOLOGY, RESULTS,
    DISCUSSION AND CONCLUSION, etc. that v2.4.25 left as inline bold."""
    pdf = TEST_PDFS / "ieee" / "ieee_access_2.pdf"
    md = render_pdf_to_markdown(pdf.read_bytes())
    headings = _headings(md)
    for h in ("## INTRODUCTION", "## METHODOLOGY", "## RESULTS"):
        assert h in headings, f"missing {h!r} in {headings!r}"


@pytest.mark.skipif(
    not (TEST_PDFS / "apa" / "xiao_2021_crsp.pdf").exists(),
    reason="xiao_2021_crsp.pdf fixture not present",
)
def test_xiao_no_false_positive_promotion():
    """xiao_2021_crsp.pdf uses Title Case for its section headings —
    the ALL-CAPS post-processor should NOT promote any line that isn't
    already a real ALL-CAPS heading."""
    pdf = TEST_PDFS / "apa" / "xiao_2021_crsp.pdf"
    md = render_pdf_to_markdown(pdf.read_bytes())
    # xiao has known ALL-CAPS frontmatter labels (ABSTRACT, KEYWORDS)
    # which legitimately get `##`. Verify they're present but no
    # surprise additions show up.
    headings = _headings(md)
    h2_caps = [h for h in headings if h.startswith("## ") and h[3:].isupper()]
    # Expect only ABSTRACT + KEYWORDS, no body-prose fragments.
    assert h2_caps == ["## ABSTRACT", "## KEYWORDS"], h2_caps
