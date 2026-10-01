"""Regression test for G5c-1 — orphan multi-level section numbers.

The APA Phase-5d sweep found that pdftotext sometimes splits a numbered
subsection heading such as ``5.4. Discussion`` into a bare ``5.4.`` line and
a separate ``Discussion`` line. The section partitioner then promotes the
lone title word to a generic ``## Discussion`` and strands the number::

    5.4.
    <blank>
    ## Discussion

Fix (G5c-1): ``_fold_orphan_multilevel_numerals_into_headings`` (render.py
post-process) — the multi-level analogue of
``_fold_orphan_arabic_numerals_into_headings`` — folds an orphan ``N.N.``
number into the immediately-following generic ``##``/``###`` heading and
emits it at subsection level: ``## Discussion`` → ``### 5.4. Discussion``.

Scope: only the immediately-adjacent case is folded. An orphan number
separated from its heading by a figure block, or one whose title word the
partitioner consumed elsewhere (leaving body prose below the number), is
partitioner-level work (G5c-2) and is intentionally left untouched.
"""

from __future__ import annotations

import re


# Camelot is not needed by this module's tests; skipping it keeps them fast.
# Declarative on purpose: this was `os.environ.setdefault(...)` at module scope,
# which executes during COLLECTION and was never undone, so importing this file
# disabled Camelot for the WHOLE pytest process and every real-PDF table test
# collected afterwards found no tables. `conftest._camelot_disabled_per_module`
# reads this flag and restores the prior value when the module finishes.
DISABLE_CAMELOT = True

from docpluck.render import (
    _fold_orphan_multilevel_numerals_into_headings,
    render_pdf_to_markdown,
)

from docpluck.testing import require_corpus_pdf


# An orphan multi-level number line immediately followed by a generic
# (non-numbered, non-Figure/Table) `##`/`###` heading.
_ORPHAN_MULTILEVEL_BEFORE_HEADING_RE = re.compile(
    r"(?m)^\d+(?:\.\d+){1,3}\.?[ \t]*\n(?:[ \t]*\n)+#{2,3} (?!\d)(?!Figure\b)(?!Table\b)"
)


# ── Unit tests on the helper ────────────────────────────────────────────

def test_folds_orphan_multilevel_with_dot():
    assert (
        _fold_orphan_multilevel_numerals_into_headings("5.4.\n\n## Discussion")
        == "### 5.4. Discussion"
    )


def test_folds_orphan_multilevel_without_dot():
    assert (
        _fold_orphan_multilevel_numerals_into_headings("5.4\n\n## Discussion")
        == "### 5.4. Discussion"
    )


def test_folds_deeper_numbering_into_h3_heading():
    assert (
        _fold_orphan_multilevel_numerals_into_headings("6.1.2.\n\n### Methods")
        == "### 6.1.2. Methods"
    )


def test_demotes_h2_target_to_subsection_level():
    # A multi-level number denotes a subsection regardless of the level the
    # partitioner gave the stranded title — the `##` target becomes `###`.
    out = _fold_orphan_multilevel_numerals_into_headings("5.4.\n\n## Discussion")
    assert out.startswith("### ")


def test_idempotent_on_already_folded_heading():
    src = "### 5.4. Discussion"
    assert _fold_orphan_multilevel_numerals_into_headings(src) == src


def test_does_not_fold_before_body_prose():
    # The non-foldable G5c-2 case: title word consumed elsewhere, body prose
    # follows the orphan number. Must be left untouched.
    src = "6.3.\n\nWe performed one-way ANOVAs to test H1a."
    assert _fold_orphan_multilevel_numerals_into_headings(src) == src


def test_does_not_fold_into_figure_heading():
    # `### Figure N` is a library-emitted structural marker, never a section.
    src = "5.3.\n\n### Figure 1"
    assert _fold_orphan_multilevel_numerals_into_headings(src) == src


def test_does_not_fold_into_table_heading():
    src = "5.3.\n\n### Table 1"
    assert _fold_orphan_multilevel_numerals_into_headings(src) == src


def test_does_not_fold_into_already_numbered_heading():
    src = "5.4.\n\n## 6. Study 2"
    assert _fold_orphan_multilevel_numerals_into_headings(src) == src


def test_leaves_single_level_number_to_the_arabic_folder():
    # A bare single-level `1.` carries no dot group — the multi-level folder
    # must not touch it (that is `_fold_orphan_arabic_numerals_into_headings`).
    src = "1.\n\n## Introduction"
    assert _fold_orphan_multilevel_numerals_into_headings(src) == src


def test_folds_multiple_independent_occurrences():
    src = "5.4.\n\n## Discussion\n\nbody\n\n6.1.\n\n### Methods"
    out = _fold_orphan_multilevel_numerals_into_headings(src)
    assert "### 5.4. Discussion" in out
    assert "### 6.1. Methods" in out


# ── Real-PDF regression test ────────────────────────────────────────────

def test_orphan_multilevel_number_folded_in_render():
    pdf = require_corpus_pdf("apa/jdm_m.2022.2.pdf")
    md = render_pdf_to_markdown(pdf.read_bytes())
    # The foldable case: `5.4.` immediately above the generic `## Discussion`.
    assert "### 5.4. Discussion" in md, "5.4. Discussion subsection not folded"
    # No orphan multi-level number may sit immediately above a generic heading.
    leak = _ORPHAN_MULTILEVEL_BEFORE_HEADING_RE.search(md)
    assert leak is None, (
        "orphan multi-level number still stranded before a generic heading: "
        f"{md[leak.start():leak.start() + 48]!r}"
    )


# ── The trailing-number move must not manufacture single-level headings ──
#
# `_render_sections_to_markdown` moves a section body's trailing bare number
# after the floats it appends, so the multi-level folder can rejoin it with the
# next heading. On single-level `N.` that move promoted text that is NOT a
# section number into a heading (census 2026-10-01, 125 papers, every case
# checked against the page):
#   10.5334/irsp.945 p43       -- running page number `43` -> `## 43. Discussion`
#   10.5334/irsp.946 p44       -- page number `31`         -> `## 31. References`
#   10.1525/collabra.57785 p9  -- `... is in Table` / `8.` -> `## 8. Discussion`,
#                                 pulling the digit out of its sentence
#   10.1177/19485506211056761  -- a stray `4.`             -> `## 4. Author Contributions`
# Every multi-level number the move rejoined was printed with its heading.

def test_trailing_move_never_makes_a_page_number_a_heading():
    for rel, bad, real in (
        ("escicheck/xiao_2024_irsp.pdf", "## 43. Discussion", "## Discussion"),
        ("escicheck/chandrashekar_2024_irsp.pdf", "## 31. References", "## References"),
        ("escicheck/chen_2023_collabra.pdf", "## 8. Discussion", "## Discussion"),
        ("apa/efendic_2022_affect.pdf", "## 4. Author Contributions", "## Author Contributions"),
    ):
        md = render_pdf_to_markdown(require_corpus_pdf(rel).read_bytes())
        assert bad not in md, f"{rel}: {bad!r} manufactured from a non-section number"
        # Presence, so the absence above cannot be satisfied by losing the section.
        assert re.search(r"(?m)^" + re.escape(real) + r"$", md), f"{rel}: {real!r} heading lost"


def test_trailing_single_level_number_kept_when_the_paper_numbers_its_sections():
    # 10.1017/jdm.2023.15 prints `3. Results` (with `3.1.` ... subsections);
    # once Table 1 is placed at its caption it sits between `3.` and `Results`.
    md = render_pdf_to_markdown(require_corpus_pdf("apa/jdm_.2023.15.pdf").read_bytes())
    assert "## 3. Results" in md
