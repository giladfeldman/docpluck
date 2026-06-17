"""Real-PDF regression tests for the 2026-06-17 single-column subsection-
heading promotion relaxation (docpluck-iterate cycle 2).

JESP / Elsevier single-column papers emit subsection headings ("Overview",
"Practice instructions", "Self-control assessment") on their own line with NO
blank padding on EITHER side — glued directly between the prior subsection's
sentence-terminated body and their own body::

    ...recruited through newspaper ads ... smoking cessation.
    Overview
    Participants undertook a 2 week training program ...

Every existing promoter requires ``blank_before AND blank_after`` (or the
PSPB no-blank-after relaxation, which still requires ``blank_before``), so
these stay demoted to body text.

``_promote_isolated_titlecase_subsection_headings`` now admits a no-blank-
before candidate **only when the document is single-column** (a width-derived
signal computed from the raw pdftotext text — see ``_raw_text_is_single_column``)
AND the immediately-preceding line is a sentence-terminated prose line. On a
two-column layout the identical shape is a narrow table-cell / measures-list
label, and admitting it re-opens the G5d hallucinated-heading trap — so the
relaxation is gated OFF there.

These tests drive the public ``render_pdf_to_markdown`` entry point against
real-PDF fixtures, per CLAUDE.md hard rule 0d.

See ``_project/lessons.md`` 2026-06-17 for the trap (line-width signal is
destroyed by the time the render pipeline reaches the promoter, so it must be
precomputed from the raw text).
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from docpluck.render import (
    _is_single_col_relaxation_fragment,
    _raw_text_is_single_column,
    render_pdf_to_markdown,
)

os.environ.setdefault("DOCPLUCK_DISABLE_CAMELOT", "1")

TEST_PDFS = Path(__file__).resolve().parents[1].parent / "PDFextractor" / "test-pdfs"


def _headings(md: str) -> list[str]:
    return [m.group() for m in re.finditer(r"^#{1,6} .+", md, re.MULTILINE)]


# ---- Contract tests (cheap, pure helper) ----------------------------------


class TestRawTextIsSingleColumn:
    def test_wide_body_prose_is_single_column(self):
        # 30 lines of full-page-width body prose (~80 chars each).
        raw = "\n".join(
            "This is a full page width single column body line of academic prose text."
            for _ in range(30)
        )
        assert _raw_text_is_single_column(raw)

    def test_narrow_two_column_lines_are_not_single_column(self):
        # 30 lines of narrow column-width text (~30 chars each) — the shape
        # pdftotext emits when serialising a two-column layout column-by-column.
        raw = "\n".join("a narrow two column line ok" for _ in range(30))
        assert not _raw_text_is_single_column(raw)

    def test_too_few_lines_is_conservative_false(self):
        # Below the 20-line floor we cannot judge layout — stay conservative.
        raw = "\n".join(
            "a very wide single column body prose line well past sixty five chars long"
            for _ in range(5)
        )
        assert not _raw_text_is_single_column(raw)

    def test_empty_text_is_false(self):
        assert not _raw_text_is_single_column("")


class TestSingleColRelaxationFragment:
    """The fragment guard that keeps the single-column no-blank-before relaxation
    from re-opening the false-positive shapes the hard blank_before reject used
    to filter. Each shape was a real corpus false-positive."""

    @pytest.mark.parametrize("frag", [
        "(Continued )",                                       # bjps_1 table-continuation marker
        "[Note]",                                             # bracket furniture
        "From Cornell University undergraduates to American",  # korbmacher wrapped sentence (leading prep)
        "To the editor and reviewers",                        # leading preposition
        "Meaning These findings suggest that",                # jama_open_1 dangling tail connector
        "Anesthesiologists; CI, confidence interval; DSMB,",  # plos_med_1 abbreviation glossary (semicolon + trailing comma)
        "Control variables, covariates,",                     # trailing comma list fragment
    ])
    def test_rejects_fragment_shapes(self, frag):
        assert _is_single_col_relaxation_fragment(frag), frag

    @pytest.mark.parametrize("heading", [
        "Overview",
        "Practice instructions",
        "Self-control assessment",
        "The current study",                                  # leading article is fine
        "Applied implications: limitations and possibilities",  # colon subtitle is fine
        "Inclusion and Exclusion",
        "Modeling Strategy",
        "Differences by National Ancestry",                   # "by" mid-heading is fine
    ])
    def test_admits_real_headings(self, heading):
        assert not _is_single_col_relaxation_fragment(heading), heading


# ---- Real-PDF regression tests (rule 0d) ----------------------------------

_AR_APA = TEST_PDFS / "apa" / "ar_apa_j_jesp_2009_12_011.pdf"
_IP_FELDMAN = TEST_PDFS / "apa" / "ip_feldman_2025_pspb.pdf"


@pytest.mark.skipif(not _AR_APA.exists(), reason="ar_apa_j_jesp_2009_12_011.pdf fixture not present")
def test_ar_apa_single_column_promotes_glued_subsection_headings():
    """JESP single-column paper: the three glued Method subsection headings
    must promote to ``### `` (they rendered as body text before the
    single-column relaxation)."""
    md = render_pdf_to_markdown(_AR_APA.read_bytes())
    headings = _headings(md)
    for h in ("### Overview", "### Practice instructions", "### Self-control assessment"):
        assert h in headings, f"missing {h!r} in {headings!r}"


@pytest.mark.skipif(not _AR_APA.exists(), reason="ar_apa_j_jesp_2009_12_011.pdf fixture not present")
def test_ar_apa_is_detected_single_column():
    from docpluck.extract import extract_pdf

    raw, _ = extract_pdf(_AR_APA.read_bytes())
    assert _raw_text_is_single_column(raw)


@pytest.mark.skipif(not _IP_FELDMAN.exists(), reason="ip_feldman_2025_pspb.pdf fixture not present")
def test_ip_feldman_two_column_does_not_over_promote_cell_labels():
    """PSPB two-column paper: the single-column relaxation must stay OFF so the
    narrow table-cell / measures-list labels do NOT get promoted to headings
    (the G5d trap). These three labels were the over-promotions that blocked
    the naive fix."""
    md = render_pdf_to_markdown(_IP_FELDMAN.read_bytes())
    headings = _headings(md)
    for bad in ("### Others ratings", "### Address order effects"):
        assert bad not in headings, f"G5d over-promotion: {bad!r} present in {headings!r}"
    # The "Prevalence Estimation Error: ..." cell label was promoted with a
    # colon-bearing tail — assert no heading starts with it.
    assert not any(
        h.startswith("### Prevalence Estimation Error") for h in headings
    ), f"G5d over-promotion: 'Prevalence Estimation Error' heading in {headings!r}"


@pytest.mark.skipif(not _IP_FELDMAN.exists(), reason="ip_feldman_2025_pspb.pdf fixture not present")
def test_ip_feldman_is_detected_two_column():
    from docpluck.extract import extract_pdf

    raw, _ = extract_pdf(_IP_FELDMAN.read_bytes())
    assert not _raw_text_is_single_column(raw)
