"""Cluster A-ter (2026-05-26): subsection-chain promotion regression tests.

The Cluster A `_promote_isolated_titlecase_subsection_headings` correctly
rejects single-candidate cell-region / sibling-label shapes, but stacked
subsection chains (multiple consecutive blank-separated titlecase labels
under a ``## `` parent) were collateral damage — every chain member was
individually rejected by either the cell-region or sibling-label gates.

The Cluster A-ter `_is_subsection_chain_member` walks back to confirm a
``## `` parent and forward to confirm body-prose terminus, then bypasses
the per-candidate rejects. This file regression-tests the chain-detection
helper and its integration into the main promoter.

Per rule 0d: every fix ships with at least one ``*_real_pdf`` test that
exercises the public library entry point on an actual PDF fixture.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from docpluck.render import (
    _is_subsection_chain_member,
    _promote_isolated_titlecase_subsection_headings,
    render_pdf_to_markdown,
)


_PDF_ROOT = Path(__file__).resolve().parents[1] / ".." / "PDFextractor" / "test-pdfs"


def _maybe_render(rel: str) -> str:
    pdf = (_PDF_ROOT / rel).resolve()
    if not pdf.is_file():
        pytest.skip(f"fixture not available locally: {rel}")
    return render_pdf_to_markdown(pdf.read_bytes())


# ── Chain detection helper — synthetic ─────────────────────────────────────


def test_chain_detects_three_member_chain_under_h2_parent():
    """Standard PSPB-style stacked Method subsections."""
    text = (
        "Body paragraph before.\n\n"
        "## Method\n\n"
        "Design and Procedure\n\n"
        "Power Analysis and Sensitivity Test\n\n"
        "Measures\n\n"
        "We summarized the experimental design and all measures in a "
        "preregistered protocol described below.\n"
    )
    lines = text.split("\n")
    # Find each chain member's index
    for label in ("Design and Procedure", "Power Analysis and Sensitivity Test", "Measures"):
        i = next(j for j, l in enumerate(lines) if l.strip() == label)
        assert _is_subsection_chain_member(lines, i), (
            f"{label!r} should be detected as chain member"
        )


def test_chain_rejects_when_no_h2_parent():
    """Candidate stack without ``## `` parent above is NOT a chain."""
    text = (
        "Body paragraph before.\n\n"
        "Design and Procedure\n\n"
        "Power Analysis and Sensitivity Test\n\n"
        "We summarized the experimental design and all measures.\n"
    )
    lines = text.split("\n")
    i = next(j for j, l in enumerate(lines) if l.strip() == "Design and Procedure")
    assert not _is_subsection_chain_member(lines, i), (
        "no ## parent: should not be chain"
    )


def test_chain_rejects_when_no_body_terminus():
    """Candidate stack that never terminates in body prose is NOT a chain."""
    text = (
        "## Glossary\n\n"
        "Term One\n\n"
        "Term Two\n\n"
        "Term Three\n"
    )
    lines = text.split("\n")
    i = next(j for j, l in enumerate(lines) if l.strip() == "Term One")
    assert not _is_subsection_chain_member(lines, i), (
        "chain never reaches body — should not promote"
    )


def test_chain_rejects_when_h3_intervenes():
    """A ``### `` heading between candidates breaks the chain (not a stack)."""
    text = (
        "## Method\n\n"
        "Design and Procedure\n\n"
        "### Existing Subsection\n\n"
        "Power Analysis\n\n"
        "Body paragraph here that is long enough to qualify as body prose.\n"
    )
    lines = text.split("\n")
    # "Power Analysis" should NOT be a chain member — there's a ### between
    # it and the ## Method parent.
    i = next(j for j, l in enumerate(lines) if l.strip() == "Power Analysis")
    assert not _is_subsection_chain_member(lines, i)


def test_chain_accepts_method_subsection_labels_member():
    """Single-word _METHOD_SUBSECTION_LABELS members (e.g. "Measures") can
    be chain members."""
    text = (
        "## Method\n\n"
        "Design and Procedure\n\n"
        "Measures\n\n"
        "Participants completed measures of well-being and other traits "
        "in random order.\n"
    )
    lines = text.split("\n")
    i = next(j for j, l in enumerate(lines) if l.strip() == "Measures")
    assert _is_subsection_chain_member(lines, i), (
        "_METHOD_SUBSECTION_LABELS members must be chain-eligible"
    )


def test_chain_promoter_promotes_all_stacked_members():
    """Integration: the promoter actually emits ``### `` for every chain
    member."""
    text = (
        "Body sentence.\n\n"
        "## Method\n\n"
        "Design and Procedure\n\n"
        "Power Analysis and Sensitivity Test\n\n"
        "Measures\n\n"
        "We summarized the experimental design and all measures in a "
        "preregistered protocol described below.\n"
    )
    out = _promote_isolated_titlecase_subsection_headings(text)
    assert "### Design and Procedure" in out
    assert "### Power Analysis and Sensitivity Test" in out
    assert "### Measures" in out


def test_chain_promoter_preserves_glossary_sidebar():
    """Negative-integration: glossary-style stacked labels (no ##  parent OR
    no body terminus) are NOT promoted."""
    # No ## parent
    text = (
        "Body sentence one.\n\n"
        "Term One\n\n"
        "Term Two\n\n"
        "Term Three\n\n"
        "More body.\n"
    )
    out = _promote_isolated_titlecase_subsection_headings(text)
    assert "### Term One" not in out
    assert "### Term Two" not in out


# ── Real-PDF regression (rule 0d) ──────────────────────────────────────────


def test_ip_feldman_method_subsections_promoted_real_pdf():
    """ip_feldman_2025_pspb cycle 2 audit findings: Method subsections
    were rendered as plain body text — chain detection promotes the
    STACKED-adjacent ones (Design and Procedure + Power Analysis and
    Sensitivity Test, opening the section) and B2c-skip + PSPB
    relaxation promotes solo single-word labels (Measures).

    Known limitation: "Data Analysis Strategy" appears mid-Method
    AFTER body paragraphs (not stacked-adjacent to ``## Method``),
    so strict-adjacent chain detection rejects it.  The through-body
    parent walk was tried but over-promotes Table 4 row labels (the
    same shape signature is ambiguous when seen from deep inside the
    section).  Tracked for a follow-up cycle with a different
    disambiguation signal.
    """
    md = _maybe_render("apa/ip_feldman_2025_pspb.pdf")
    # Adjacent stack at the head of ## Method:
    assert "### Design and Procedure" in md, (
        "Method subsection 'Design and Procedure' not promoted"
    )
    assert "### Power Analysis and Sensitivity Test" in md, (
        "Method subsection 'Power Analysis and Sensitivity Test' not promoted"
    )
    # Solo subsection caught by B2c-skip relaxation + PSPB:
    assert "### Measures" in md, (
        "Method subsection 'Measures' (in _METHOD_SUBSECTION_LABELS) not promoted"
    )
    # Known limitation: "Data Analysis Strategy" mid-Method with body
    # before — not yet promoted by strict-adjacent chain logic.  When a
    # safer through-body disambiguator lands, restore this assertion.
    # assert "### Data Analysis Strategy" in md


def test_ip_feldman_no_table4_cell_overpromotion_real_pdf():
    """Negative regression: Table 4 row labels MUST NOT be promoted to
    ``### `` headings.  When Camelot fails to extract Table 4, its row
    labels ("Exploratory open-ended", "Well-being measures and traits",
    "IV1: estimation of negative emotional events", etc.) leak out as
    plain text inside the Method section.  Through-body chain detection
    would falsely promote them; strict-adjacent backward-walk avoids
    this trap.
    """
    md = _maybe_render("apa/ip_feldman_2025_pspb.pdf")
    for label in (
        "Exploratory open-ended",
        "Well-being measures and traits",
        "IV1: estimation of negative emotional events",
        "IV1: estimation of positive emotional events",
    ):
        assert f"### {label}" not in md, (
            f"Table 4 row label {label!r} was falsely promoted to ### heading"
        )
