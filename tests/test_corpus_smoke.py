"""End-to-end corpus smoke test for v2.3.0.

Skips cleanly when the spike-output baselines or test PDFs are not on
disk (so the suite passes on CI / fresh clones without the sister app
repo). When the corpus IS available, runs ``render_pdf_to_markdown``
against a handful of representative papers and asserts the health
metrics produced by ``scripts/verify_corpus.py``.

The full corpus run takes 8–10 minutes. This test runs 3 representative
papers from different journal styles (~30s total) to catch the worst
regressions cheaply. Use ``python scripts/verify_corpus.py`` for the
exhaustive run.

Representative picks:
  - **efendic_2022_affect** (APA) — exercises Bug 3 figure positioning
    (5 figures, 1 table) and the abstract synthesis path.
  - **jama_open_1** (AMA) — exercises ``_pick_best_per_page`` lattice
    artifact filter; 3 tables must render with HTML.
  - **korbmacher_2022_kruger** (APA/JESP) — exercises the appendix
    fallback for unlocated tables (15 tables, none find-able in body).
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parent.parent
APP_PDFS = REPO_ROOT.parent / "PDFextractor" / "test-pdfs"

REPRESENTATIVE_PAPERS = [
    # (basename, min_section_count, min_table_html_count, max_figs_above_abstract)
    ("efendic_2022_affect", 8, 1, 0),
    ("jama_open_1", 8, 2, 0),
    ("korbmacher_2022_kruger", 6, 0, 0),  # tables go to appendix; 0 in body is fine
]


def _find_pdf(name: str):
    for p in APP_PDFS.rglob(f"{name}.pdf"):
        return p
    return None


_TITLE_RE = re.compile(r"^#\s+", re.MULTILINE)
_H2_RE = re.compile(r"^##\s+([^\n]+)", re.MULTILINE)
_FIG_HEADING_RE = re.compile(r"^###\s+Figure\s+\d+", re.MULTILINE)
_TABLE_HEADING_RE = re.compile(r"^###\s+Table\s+\d+", re.MULTILINE | re.IGNORECASE)


@pytest.mark.parametrize(
    "name,min_sections,min_table_html,max_figs_above_abstract",
    REPRESENTATIVE_PAPERS,
)
def test_corpus_paper_renders(name, min_sections, min_table_html, max_figs_above_abstract):
    """Smoke-test render quality on a representative paper."""
    pdf_path = _find_pdf(name)
    if pdf_path is None:
        pytest.skip(f"PDF not on disk: {name}.pdf")

    from docpluck import render_pdf_to_markdown
    md = render_pdf_to_markdown(pdf_path.read_bytes())

    # 1. Title present.
    assert _TITLE_RE.search(md), f"{name}: no '# Title' found"

    # 2. Section count.
    sections = _H2_RE.findall(md)
    assert len(sections) >= min_sections, (
        f"{name}: only {len(sections)} sections "
        f"(expected ≥ {min_sections}); got {sections}"
    )

    # 3. Table HTML count (body-spliced only — appendix tables are
    #    inherently isolated and not a render-bug signal). Skipped
    #    under DOCPLUCK_DISABLE_CAMELOT=1: without Camelot, structured
    #    tables aren't extracted so there is no body-spliced HTML to
    #    count; the metric is only meaningful with Camelot enabled.
    if os.environ.get("DOCPLUCK_DISABLE_CAMELOT", "0") != "1":
        appendix_idx = md.find("## Tables (unlocated in body)")
        body_section = md if appendix_idx < 0 else md[:appendix_idx]
        html_count = body_section.count("<table>")
        assert html_count >= min_table_html, (
            f"{name}: only {html_count} body-spliced HTML tables "
            f"(expected ≥ {min_table_html})"
        )

    # 4. Bug 3 check — figures must NOT appear before the first ## heading.
    first_h2 = _H2_RE.search(md)
    if first_h2:
        figs_above = _FIG_HEADING_RE.findall(md[:first_h2.start()])
        assert len(figs_above) <= max_figs_above_abstract, (
            f"{name}: {len(figs_above)} figures appear before the first "
            f"section heading (Bug 3 regression — figures spliced at top)"
        )

    # 5. No soft hyphens anywhere in the rendered output (caption fix).
    assert "­" not in md, (
        f"{name}: rendered output contains U+00AD soft hyphen "
        f"(caption normalization regression)"
    )


def test_corpus_papers_exist_or_skip_cleanly():
    """If APP_PDFS isn't on disk, the parametrized test above skips
    individually. This sanity-check confirms the path resolves to either
    a real directory or no-test."""
    if not APP_PDFS.exists():
        pytest.skip(f"sister test-pdfs directory not on disk: {APP_PDFS}")
    assert APP_PDFS.is_dir()
