"""
jama-open-1 defect cluster regression tests (v2.4.74, 2026-05-25).

Five defects surfaced by the Haiku-orchestration pretest on
jama_open_1.pdf (`HANDOFF_2026-05-25_pretest-followups.md` Issue 1).
This file covers four of five (defect 4 / MISSING_SECTION / Key Points
sidebar is left for R4 column-aware re-extraction):

  D1 RUNNING_HEADER_LEAK — `Downloaded from jamanetwork.com …` and
     standalone date footers (`October 27, 2023`) leaking into body.
  D2 HALLUC_HEAD — Table 2 / 4 cells promoted to `### N. Mean glucose
     level` / `### Control` / `### Body weight, kg` / `### Total
     cholesterol`.
  D3 ABSTRACT_LEVEL_MISMATCH — `## RESULTS` / `## CONCLUSIONS AND
     RELEVANCE` / `## Findings` promoted from structured-abstract
     inline labels and Key Points sidebar items.
  D5 TABLE_STRUCTURE_CORRUPT — Table 3 emitted with
     `<th>JAMA Network Open | …</th>` (masthead) and
     `<td>Discussion</td>` (next section name).

Real-PDF (rule 0d) + structural-signature general fix (rule 16).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from docpluck.render import render_pdf_to_markdown


_PDF = Path(__file__).resolve().parents[2] / "PDFextractor" / "test-pdfs" / "ama" / "jama_open_1.pdf"


@pytest.fixture(scope="module")
def rendered_md() -> str:
    if not _PDF.exists():
        pytest.skip(f"corpus fixture missing: {_PDF}")
    return render_pdf_to_markdown(_PDF.read_bytes())


def test_d1_downloaded_jamanetwork_footer_stripped(rendered_md: str):
    """D1: every `Downloaded from jamanetwork.com … on MM/DD/YYYY` page
    footer is stripped from the body."""
    assert "Downloaded from jamanetwork" not in rendered_md, (
        "JAMA Open page footer ('Downloaded from jamanetwork.com by … user on …') "
        "still leaks into the rendered body. Check _WATERMARK_PATTERNS in "
        "docpluck/normalize.py for the bare-domain + MM/DD/YYYY variant added "
        "in v2.4.74."
    )


def test_d1_standalone_date_line_stripped(rendered_md: str):
    """D1: a bare `October 27, 2023` page-footer line (no surrounding
    metadata) is stripped. The legitimate `Published: October 27, 2023.
    doi:…` metadata line must survive."""
    lines = rendered_md.split("\n")
    standalone_date_leaks = sum(
        1 for ln in lines if ln.strip() == "October 27, 2023"
    )
    assert standalone_date_leaks == 0, (
        f"{standalone_date_leaks} standalone 'October 27, 2023' lines still leak. "
        f"Check _PAGE_FOOTER_LINE_PATTERNS bare-date pattern in normalize.py."
    )
    published_line_present = any(
        "Published: October 27, 2023" in ln for ln in lines
    )
    assert published_line_present, (
        "The legitimate 'Published: October 27, 2023. doi:…' metadata line "
        "was accidentally stripped — the bare-date pattern over-matched."
    )


def test_d2_table_cell_headings_demoted(rendered_md: str):
    """D2: no `### {table-cell-shape}` lines remain in the body. Specifically
    the four shapes surfaced in the pretest:
      - `### 1.0. Mean glucose level` (numeric-prefix shape)
      - `### Control` (single-Title-Case-word column-header-stranded)
      - `### Body weight, kg` (data-unit-suffix shape)
      - `### Total cholesterol` (next-line-is-data-unit-label)
    """
    suspect_headings = [
        "### 1.0. Mean glucose level",
        "### Control",
        "### Body weight, kg",
        "### Total cholesterol",
    ]
    lines = rendered_md.split("\n")
    leaks = [h for h in suspect_headings if any(ln == h for ln in lines)]
    assert not leaks, (
        f"jama-open-1 HALLUC_HEAD leaks not demoted: {leaks}. Check "
        f"_demote_isolated_table_cell_headings in render.py."
    )


def test_d3_abstract_zone_no_intermediate_h2(rendered_md: str):
    """D3: between `## Abstract` and the next body-section h2 (Introduction /
    Methods / Background / etc.), NO `## X` heading remains. JAMA structured-
    abstract inline labels (RESULTS / CONCLUSIONS / IMPORTANCE / OBJECTIVE)
    and Key Points sidebar labels (Findings / Meaning / Question) all get
    promoted by upstream rules when column-interleave drops them on their
    own lines — demoted by _demote_abstract_zone_inline_labels."""
    lines = rendered_md.split("\n")
    abstract_idx = next(
        (i for i, ln in enumerate(lines) if ln.strip() == "## Abstract"),
        None,
    )
    assert abstract_idx is not None, "## Abstract heading missing"
    # Find next body-section h2.
    end_labels = {
        "Introduction", "Background", "Methods", "Method", "Materials",
    }
    end_idx = None
    for j in range(abstract_idx + 1, len(lines)):
        ln = lines[j].strip()
        if ln.startswith("## "):
            label = ln[3:].strip()
            if label in end_labels:
                end_idx = j
                break
    assert end_idx is not None, "no body-section h2 follows Abstract"
    intermediate_h2 = [
        lines[j] for j in range(abstract_idx + 1, end_idx)
        if lines[j].startswith("## ")
    ]
    assert not intermediate_h2, (
        f"ABSTRACT_LEVEL_MISMATCH — these h2 headings remain between "
        f"`## Abstract` and `## {lines[end_idx][3:].strip()}`: {intermediate_h2}. "
        f"Check _demote_abstract_zone_inline_labels in render.py."
    )


def test_d5_phantom_table_3_masthead_stripped(rendered_md: str):
    """D5: no `<th>JAMA Network Open | …` masthead leaks into table headers,
    and no `<td>Discussion</td>` next-section leaks into table bodies."""
    assert "<th>JAMA Network Open" not in rendered_md, (
        "JAMA masthead still leaks into a <th> cell. Check "
        "_strip_phantom_camelot_tables in render.py."
    )
    assert "<td>Discussion</td>" not in rendered_md, (
        "Section name 'Discussion' still leaks into a <td> cell. Check "
        "_strip_phantom_camelot_tables phantom detection rules."
    )
