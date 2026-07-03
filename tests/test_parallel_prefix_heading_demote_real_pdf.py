"""Regression test for C3: demote a Results-subsection heading over-promoted to
`## ` back to `### `, keyed on a parallel-prefix `### ` sibling (v2.4.110).

The 2026-07-03 canary AI-verify found ip_feldman_2025_pspb rendering
`## Prevalence Estimates Associations with WellBeing (Replication)` as a
top-level `## ` when the gold has it as `### ` — a Results subsection SIBLING to
`### Prevalence Estimate Errors` and `### Intensity Estimate Errors`. It is 7
words, above the ≤6-word `### ` promoter's window, so the 5-12-word `## `
major-section promoter picked it up one level too high.

Fix (v2.4.110): `_demote_parallel_prefix_subsection_headings` demotes a `## `
back to `### ` ONLY when a `### ` heading earlier in the same section shares a
≥2-word stemmed prefix AND then diverges. This keys on parallel-prefix structure
(not "nearest `##` parent is Results", which would wrongly demote `## Discussion`),
and the divergence guard prevents demoting a `## ` whose `### ` "sibling" is
actually a duplicate of the same title.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("DOCPLUCK_DISABLE_CAMELOT", "1")

from docpluck.render import render_pdf_to_markdown

TEST_PDFS = Path(__file__).resolve().parents[1].parent / "PDFextractor" / "test-pdfs"


def test_ip_feldman_results_subsection_demoted_to_h3():
    """The over-promoted Results subsection renders `### `, and its siblings +
    the following `## Discussion` are unchanged."""
    pdf = TEST_PDFS / "apa" / "ip_feldman_2025_pspb.pdf"
    if not pdf.exists():
        pytest.skip(f"fixture missing: {pdf}")
    md = render_pdf_to_markdown(pdf.read_bytes())
    # The target is now a subsection.
    assert "### Prevalence Estimates Associations with WellBeing" in md
    assert "## Prevalence Estimates Associations with WellBeing" not in md.replace(
        "### Prevalence Estimates Associations with WellBeing", ""
    )
    # Its parallel siblings stay `### `.
    assert "### Prevalence Estimate Errors" in md
    assert "### Intensity Estimate Errors" in md
    # `## Discussion` (nearest `##` parent is also Results, but no shared prefix)
    # is NOT demoted.
    assert "## Discussion" in md


def test_demote_helper_parallel_prefix_only():
    """Unit contract: only a divergent parallel-prefix pair demotes; a duplicate
    or a `## ` with no shared-prefix `### ` sibling is left alone."""
    from docpluck.render import _demote_parallel_prefix_subsection_headings as D

    # Parallel pair → demote.
    parallel = (
        "## Results\n\n"
        "### Prevalence Estimate Errors (Replication)\n\nbody body body here.\n\n"
        "## Prevalence Estimates Associations with Well-Being (Replication)\n\nbody.\n"
    )
    out = D(parallel)
    assert "### Prevalence Estimates Associations with Well-Being (Replication)" in out

    # Duplicate title (identical) → do NOT demote the `## ` (collabra pattern).
    dup = (
        "## Results\n\n"
        "### Extension: Perceived Impact of Donation\n\nx.\n\n"
        "## Extension: Perceived Impact of Donation\n\ny.\n"
    )
    assert "## Extension: Perceived Impact of Donation" in D(dup)

    # No shared prefix → `## Discussion` untouched.
    disc = (
        "## Results\n\n### Primary Outcome Analysis\n\nx.\n\n## Discussion\n\ny.\n"
    )
    assert "## Discussion" in D(disc)

    # Different major section after a `### ` → not demoted (no shared prefix).
    method = (
        "## Results\n\n### Emotional Experiences\n\nx.\n\n## Method\n\ny.\n"
    )
    assert "## Method" in D(method)


def test_demote_helper_does_not_cross_section_boundary():
    """A `### ` in a PRIOR major section must not license a demotion across the
    intervening `## ` body-section boundary."""
    from docpluck.render import _demote_parallel_prefix_subsection_headings as D

    text = (
        "## Results\n\n### Prevalence Estimate Errors\n\nx.\n\n"
        "## Method\n\ny.\n\n"  # boundary
        "## Prevalence Estimates Overview\n\nz.\n"  # different section
    )
    # The scan stops at `## Method`, so the Overview `## ` is NOT demoted.
    assert "## Prevalence Estimates Overview" in D(text)
