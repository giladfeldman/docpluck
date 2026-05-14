"""Real-PDF regression tests for P1 front-matter metadata-leak strip.

Per /docpluck-iterate skill rule 0d: every fix ships with at least one
``*_real_pdf`` test that exercises the public library entry point on an
actual PDF fixture from ``../PDFextractor/test-pdfs/``.

The PDF fixtures live OUTSIDE this repo (gitignored — closed-access journal
content; see memory ``feedback_no_pdfs_in_repo``). Tests therefore use the
manifest-with-skip pattern: if the fixture is missing locally, the test
``pytest.skip``s with a clear message. CI runs in the docpluckapp repo
where the fixtures are present.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from docpluck.normalize import (
    NORMALIZATION_VERSION,
    _strip_frontmatter_metadata_leaks,
    _strip_page_footer_lines,
)
from docpluck.render import render_pdf_to_markdown


_PDF_ROOT = Path(__file__).resolve().parents[1] / ".." / "PDFextractor" / "test-pdfs"


def _maybe_render(rel: str) -> str:
    """Render a fixture PDF or skip if not present."""
    pdf = (_PDF_ROOT / rel).resolve()
    if not pdf.is_file():
        pytest.skip(f"fixture not available locally: {rel}")
    return render_pdf_to_markdown(pdf.read_bytes())


# ── Contract tests for the helper (synthetic strings — fast, exhaustive) ───


def test_p1_version_bumped_to_184():
    assert NORMALIZATION_VERSION.startswith("1.8.")


def test_p0_strips_supplemental_data_sidebar():
    # Promoted to P0 in v2.4.16 (globally safe — exact boilerplate).
    text = (
        "Intro paragraph one.\n\n"
        "Supplemental data for this article can be accessed here.\n\n"
        "Intro paragraph two."
    )
    out = _strip_page_footer_lines(text)
    assert "Supplemental data for this article" not in out
    assert "Intro paragraph one." in out
    assert "Intro paragraph two." in out


def test_p0_strips_truncated_department_affiliation():
    # Promoted to P0 in v2.4.16. Distinct from the legitimate full form
    # because the truncation pattern requires the line to END at
    # "University of" — full affiliations have a place name after.
    text = (
        "Body before.\n"
        "Department of Psychology, University of\n"
        "Body after."
    )
    out = _strip_page_footer_lines(text)
    assert "Department of Psychology, University of\n" not in out
    assert "Body before." in out
    assert "Body after." in out


def test_p0_preserves_full_affiliation_with_place():
    # P0 must NOT touch the full form "University of <Place>".
    text = (
        "Body.\n"
        "Department of Psychology, University of Minnesota\n"
        "Body 2."
    )
    out = _strip_page_footer_lines(text)
    assert "Department of Psychology, University of Minnesota" in out


def test_p1_strips_we_thank_acknowledgments_paragraph():
    text = (
        "Intro.\n\n"
        "We wish to thank our editor Jill Perry-Smith and three anonymous "
        "reviewers for their insightful and constructive feedback. We also "
        "thank Angelo DeNisi for helpful comments.\n\n"
        "Intro continues." + "\n\nbody. " * 200
    )
    out = _strip_frontmatter_metadata_leaks(text)
    assert "We wish to thank our editor" not in out
    assert "Intro." in out
    assert "Intro continues." in out


def test_p1_preserves_we_thank_body_prose_without_acknowledgment_keywords():
    # "We thank participants for completing the survey" appears in Methods
    # — it has no reviewers/editor/feedback/comments keyword, so the
    # acknowledgment guard rejects the match.
    text = (
        "Method body.\n\n"
        "We thank participants for completing the survey.\n\n"
        "More method." + "\n\nbody. " * 200
    )
    out = _strip_frontmatter_metadata_leaks(text)
    assert "We thank participants for completing the survey." in out


def test_p1_strips_previous_version_note():
    text = (
        "Intro.\n\n"
        "A previous version of this article was presented at the meetings "
        "of the Academy of Management.\n\n"
        "Body." + "\n\nbody. " * 200
    )
    out = _strip_frontmatter_metadata_leaks(text)
    assert "A previous version of this article was presented" not in out


def test_p1_strips_creative_commons_license_block():
    text = (
        "Abstract body.\n\n"
        "This work is licensed under a Creative Commons Attribution 4.0 "
        "License. For more information, see https://creativecommons.org/.\n\n"
        "Intro." + "\n\nbody. " * 200
    )
    out = _strip_frontmatter_metadata_leaks(text)
    assert "This work is licensed under a Creative Commons" not in out


def test_p1_strips_correspondence_concerning_block():
    text = (
        "Intro.\n\n"
        "Correspondence concerning this article should be addressed to "
        "Author Name, Department of X, University of Y.\n\n"
        "Body." + "\n\nbody. " * 200
    )
    out = _strip_frontmatter_metadata_leaks(text)
    assert "Correspondence concerning this article" not in out


def test_p0_strips_bare_uppercase_running_header():
    # Promoted to P0 in v2.4.16 (recurs at every page break — globally safe).
    text = (
        "Intro paragraph.\n"
        "RECKELL et al.\n"
        "More intro."
    )
    out = _strip_page_footer_lines(text)
    assert "RECKELL et al." not in out
    assert "Intro paragraph." in out
    assert "More intro." in out


def test_p1_position_gate_protects_late_acknowledgments():
    # The legitimate ## Acknowledgments section lives at the END of the
    # document. P1 must not touch it.
    # P1's cutoff is ``max(8000, len(text) // 6)`` so the synthetic body
    # must push the acknowledgments paragraph past 8000 chars.
    body = "Body sentence. " * 1200  # ~18,000 chars
    text = (
        "Front matter.\n\n"
        + body
        + "\n\n## Acknowledgments\n\n"
        + "We wish to thank our reviewers for insightful feedback.\n\n"
        + "End."
    )
    assert text.index("We wish to thank") > 8000, (
        "test fixture too short to exercise position gate"
    )
    out = _strip_frontmatter_metadata_leaks(text)
    # The acknowledgments paragraph is past the position cutoff — preserved.
    assert "We wish to thank our reviewers" in out


def test_p1_idempotent():
    text = (
        "Intro.\n\n"
        "Supplemental data for this article can be accessed here.\n\n"
        "Body." + "\n\nbody. " * 200
    )
    once = _strip_frontmatter_metadata_leaks(text)
    twice = _strip_frontmatter_metadata_leaks(once)
    assert once == twice


def test_p1_short_text_noop():
    # Documents under 200 chars get returned untouched.
    text = "Supplemental data for this article can be accessed here."
    out = _strip_frontmatter_metadata_leaks(text)
    assert out == text


# ── Real-PDF regression tests (rule 0d) ────────────────────────────────────


def test_xiao_2021_crsp_supplemental_and_truncated_affil_real_pdf():
    md = _maybe_render("apa/xiao_2021_crsp.pdf")
    # Front-matter leaks must be gone.
    assert "Supplemental data for this article can be accessed here" not in md
    # The truncated affiliation: line ends right after "University of".
    # The full form ("University of Hong Kong" or similar) may legitimately
    # appear elsewhere in the doc, so we only assert the truncation form
    # is absent.
    import re as _re
    assert not _re.search(
        r"(?m)^Department\s+of\s+\w+,\s*University\s+of\s*$", md
    ), "truncated 'Department of <X>, University of' still present"
    # Legitimate Acknowledgments section at the end must survive.
    assert "## Acknowledgments" in md or "## ACKNOWLEDGMENTS" in md


def test_amj_1_acknowledgments_leak_real_pdf():
    md = _maybe_render("aom/amj_1.pdf")
    # The "We wish to thank our editor Jill Perry-Smith..." line that
    # pdftotext inlines mid-Introduction must be stripped.
    assert "We wish to thank our editor Jill Perry-Smith" not in md
    # The body must still be there.
    assert "negative feedback" in md.lower()


def test_amle_1_acknowledgments_and_previous_version_real_pdf():
    md = _maybe_render("aom/amle_1.pdf")
    assert "We thank Steven Charlier" not in md
    assert "A previous version of this article was presented" not in md
    # Body integrity.
    assert "scholarly impact" in md.lower()


def test_ieee_access_2_license_and_running_header_real_pdf():
    md = _maybe_render("ieee/ieee_access_2.pdf")
    # License blob inlined between Abstract and Introduction.
    assert "This work is licensed under a Creative Commons" not in md
    # Bare "RECKELL et al." running header on its own line.
    # Use regex to avoid matching false hits (none expected) inside other
    # constructs.
    import re as _re
    assert not _re.search(r"(?m)^RECKELL\s+et\s+al\.?\s*$", md), (
        "bare 'RECKELL et al.' running header still present mid-body"
    )
    # Body integrity (the Petri-net Introduction must still be there).
    assert "Petri net" in md or "Petri Net" in md
