"""Regression test for D6 — orphan arabic section numbers (cycle 3, v2.4.35).

The APA Phase-5d sweep found that JDM / Cambridge-style papers, which number
their sections "1. Introduction", "2. Method", etc., rendered the section
number stranded on its own line, separated from the heading the section
partitioner had promoted to `## `:

    1.
    <blank>
    ## Introduction

Fix (v2.4.35): `_fold_orphan_arabic_numerals_into_headings` (render.py
post-process) — arabic analogue of `_fold_orphan_roman_numerals_into_headings`
— folds an orphan 1-2 digit number into the `## ` heading immediately below
it: `## Introduction` → `## 1. Introduction`.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

os.environ.setdefault("DOCPLUCK_DISABLE_CAMELOT", "1")

from docpluck.render import _fold_orphan_arabic_numerals_into_headings, render_pdf_to_markdown

TEST_PDFS = Path(__file__).resolve().parents[1].parent / "PDFextractor" / "test-pdfs"

# A bare 1-2 digit line (optional dot) immediately followed by a `## ` heading.
_ORPHAN_BEFORE_HEADING_RE = re.compile(r"(?m)^\d{1,2}\.?[ \t]*\n(?:[ \t]*\n)+## ")


# ── Unit tests on the helper ────────────────────────────────────────────

def test_folds_orphan_number_with_dot():
    assert (
        _fold_orphan_arabic_numerals_into_headings("1.\n\n## Introduction")
        == "## 1. Introduction"
    )


def test_folds_orphan_number_without_dot():
    # korbmacher prints a bare "1" (no dot) before its Introduction heading.
    assert (
        _fold_orphan_arabic_numerals_into_headings("1\n\n## Introduction")
        == "## 1. Introduction"
    )


def test_idempotent_on_already_numbered_heading():
    src = "## 1. Introduction"
    assert _fold_orphan_arabic_numerals_into_headings(src) == src


def test_does_not_fold_number_before_body_prose():
    # A bare number followed by ordinary prose (page number, list item) is
    # NOT a section number — must be left untouched.
    src = "3.\n\nThe participants were recruited online."
    assert _fold_orphan_arabic_numerals_into_headings(src) == src


def test_does_not_double_number_a_numbered_heading():
    # If the heading already starts with a number, don't fold another in.
    src = "2.\n\n## 1. Introduction"
    assert _fold_orphan_arabic_numerals_into_headings(src) == src


def test_folds_multiple_independent_occurrences():
    src = "1.\n\n## Introduction\n\nbody\n\n2.\n\n## Methods"
    out = _fold_orphan_arabic_numerals_into_headings(src)
    assert "## 1. Introduction" in out
    assert "## 2. Methods" in out


# ── Real-PDF regression test ────────────────────────────────────────────

@pytest.mark.parametrize("stem", ["korbmacher_2022_kruger", "jdm_.2023.15"])
def test_no_orphan_number_before_heading_in_render(stem):
    pdf = TEST_PDFS / "apa" / f"{stem}.pdf"
    if not pdf.exists():
        pytest.skip(f"fixture missing: {pdf}")
    md = render_pdf_to_markdown(pdf.read_bytes())
    leak = _ORPHAN_BEFORE_HEADING_RE.search(md)
    assert leak is None, (
        f"{stem}: orphan section number still stranded before a heading: "
        f"{md[leak.start():leak.start()+40]!r}"
    )
    # The Introduction heading must carry its section number.
    assert "## 1. Introduction" in md, f"{stem}: Introduction heading not numbered"
