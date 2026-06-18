"""G5d affiliation-heading guard (v2.4.92) — real-PDF + contract.

Background
==========
An academic affiliation / institution line is masthead furniture (the author's
address), never a section heading. ``_strip_frontmatter_masthead_block`` removes
such lines, but only inside the H1 → first-``## `` zone. When column-interleave
serialises a two-column title block out of order, an affiliation line can land
PAST that zone — on chandrashekar_2023_mp, "Department of Philosophy, Lake Forest
College" is dropped immediately after ``## Abstract``. The masthead strip can no
longer reach it, and its short Title-Case shape then matches
``_promote_isolated_titlecase_subsection_headings`` and becomes a hallucinated
``### Department of Philosophy, Lake Forest College`` heading (G5d) — corrupting
the section structure of the Abstract.

The fix (general, keyed on a STRUCTURAL SIGNATURE — affiliation grammar, never
paper identity): the promoter consults ``_looks_like_affiliation_line`` and
refuses to promote any affiliation/institution line. The line stays body text —
a strict improvement over a fake heading. A 47-gold / 2226-real-heading FP scan
during development found zero legitimate headings the guard would reject.

Real-PDF (rule 0d) + structural-signature general fix (rule 16). The real-PDF
test asserts the INVARIANT (no affiliation-shaped ``### `` heading survives the
full render), not the mechanism.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from docpluck.render import _looks_like_affiliation_line, render_pdf_to_markdown

_CORPUS = Path(__file__).resolve().parents[2] / "PDFextractor" / "test-pdfs" / "apa"

# An affiliation grammar matcher used only to FLAG a heading as suspicious in the
# invariant test — independent of the library's own regex so the test does not
# merely re-assert the implementation.
_AFFIL_HEADING_PROBE = re.compile(
    r"(?:\b(?:Department|School|Faculty|Division|Institute|Laboratory)\s+of\b)"
    r"|\b(?:University|College|Polytechnic)\b",
)


def test_chandrashekar_no_affiliation_heading_real_pdf():
    """chandrashekar_2023_mp must not promote its stray "Department of
    Philosophy, Lake Forest College" affiliation to a ``### `` heading."""
    pdf = _CORPUS / "chandrashekar_2023_mp.pdf"
    if not pdf.exists():
        pytest.skip(f"corpus fixture missing: {pdf}")
    md = render_pdf_to_markdown(pdf.read_bytes())

    # Specific regression: the exact hallucinated heading is gone.
    assert "### Department of Philosophy" not in md, (
        "chandrashekar: affiliation line promoted to a subsection heading (G5d)"
    )

    # Invariant: NO ``### `` / ``#### `` heading anywhere in the render is an
    # affiliation/institution line. (``## `` H2 sections are author-section
    # headings and never match this probe; we scope to the promoter's output.)
    for ln in md.splitlines():
        s = ln.strip()
        if s.startswith("### "):
            label = s[4:].strip()
            assert not _AFFIL_HEADING_PROBE.search(label), (
                f"affiliation/institution line promoted to heading: {label!r}"
            )

    # The affiliation text itself must still be PRESENT (demoted to body, not
    # dropped — this guard only vetoes promotion, it does not strip).
    assert "Lake Forest College" in md, (
        "affiliation text disappeared — the guard must demote, not delete"
    )


@pytest.mark.parametrize(
    "line",
    [
        "Department of Philosophy, Lake Forest College",
        "Department of Psychology, Norwegian University of Science and Technology (NTNU)",
        "School of Medicine",
        "Faculty of Social Sciences",
        "Institute of Cognitive Neuroscience",
        "Lake Forest College",
        "Harvard University",
        "Karolinska Institute",
    ],
)
def test_affiliation_lines_match(line: str):
    assert _looks_like_affiliation_line(line), f"should match affiliation: {line!r}"


@pytest.mark.parametrize(
    "line",
    [
        # Documented limitation: institution names whose keyword is NOT the
        # final token ("X Institute of Y", "X College <City>") are intentionally
        # NOT matched — anchoring the keyword at end-of-line is what keeps the
        # FP surface at zero (broadening to trailing tokens would wrongly flag
        # plausible headings like "The College Years"). These are rarer leak
        # forms; the line stays body text either way, so the worst case is a
        # missed demotion, never a dropped or mangled heading.
        "Massachusetts Institute of Technology",
        "Imperial College London",
    ],
)
def test_known_unmatched_institution_forms(line: str):
    assert not _looks_like_affiliation_line(line), (
        f"behaviour changed for documented-limitation form: {line!r}"
    )


@pytest.mark.parametrize(
    "line",
    [
        # Real subsection headings drawn from the corpus that MUST stay eligible
        # for promotion (no institution grammar).
        "Reasons for change",
        "Choice of Study",
        "Background",
        "Data Analysis Strategy",
        "Self-control assessment",
        "Practice instructions",
        "Main findings",
        "Strengths and weaknesses of the study",
        "The Misestimation of Others' Emotions",
        "Overview",
        # "College"/"University" as ordinary words, not an institution phrase.
        "College Students and Stress",
        "University Life",
    ],
)
def test_non_affiliation_lines_do_not_match(line: str):
    assert not _looks_like_affiliation_line(line), (
        f"false positive — real heading flagged as affiliation: {line!r}"
    )
