"""Regression test for the math-italic Greek corruption (cycle 2, v2.4.34).

The APA Phase-5d sweep found that effect-size symbols were corrupted: an
"η² = 0.34" rendered as "n2 = 0.34", a coefficient "β" as "b". Diagnosis:
the source PDFs encode Greek as Mathematical-Italic codepoints (U+1D6FD 𝛽,
U+1D702 𝜂, …), and normalize.py's S0 step transliterated math-italic Greek
to ASCII Latin (𝜂→"n", 𝛽→"b", 𝛼→"a"). This is a docpluck-introduced
corruption — pdftotext extracts the math-italic glyph faithfully; docpluck
then mangled it.

Fix (v2.4.34): `destyle_math_alphanumeric` NFKC-normalises the whole
Mathematical Alphanumeric Symbols block (U+1D400-U+1D7FF), stripping the
styling to the plain base letter — Greek stays Greek. Applied in S0 (body
channel) and in tables/cell_cleaning `_html_escape` (Camelot layout channel,
which bypasses S0).
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

os.environ.setdefault("DOCPLUCK_DISABLE_CAMELOT", "1")

from docpluck.normalize import destyle_math_alphanumeric
from docpluck.render import render_pdf_to_markdown

TEST_PDFS = Path(__file__).resolve().parents[1].parent / "PDFextractor" / "test-pdfs"

# Any Mathematical Alphanumeric Symbol (styled Latin/Greek/digit).
_MATH_ALNUM_RE = re.compile(r"[\U0001D400-\U0001D7FF]")


# ── Unit tests on the helper ────────────────────────────────────────────

def test_mathitalic_greek_becomes_real_greek():
    # 𝜂 U+1D702, 𝛽 U+1D6FD, 𝛼 U+1D6FC
    assert destyle_math_alphanumeric("\U0001D702") == "η"  # η
    assert destyle_math_alphanumeric("\U0001D6FD") == "β"  # β
    assert destyle_math_alphanumeric("\U0001D6FC") == "α"  # α


def test_mathitalic_greek_not_transliterated_to_latin():
    # The pre-v2.4.34 bug mapped 𝜂→"n", 𝛽→"b". Must NOT happen.
    out = destyle_math_alphanumeric("\U0001D702\U0001D6FD = 0.34")
    assert "n" not in out and "b" not in out
    assert out == "ηβ = 0.34"


def test_mathitalic_latin_becomes_ascii_latin():
    # 𝐴 U+1D434 (math italic capital A), 𝑥 U+1D465 (small x)
    assert destyle_math_alphanumeric("\U0001D434") == "A"
    assert destyle_math_alphanumeric("\U0001D465") == "x"


def test_math_bold_and_sans_variants_also_destyled():
    # 𝐀 bold A U+1D400, 𝟎 bold digit 0 U+1D7CE, 𝝰 sans-bold alpha U+1D770
    assert destyle_math_alphanumeric("\U0001D400") == "A"
    assert destyle_math_alphanumeric("\U0001D7CE") == "0"
    assert destyle_math_alphanumeric("\U0001D770") == "α"  # α


def test_plain_text_untouched():
    plain = "Cronbach's alpha was .89, eta-squared = .34."
    assert destyle_math_alphanumeric(plain) == plain


# ── Real-PDF regression test ────────────────────────────────────────────

def test_korbmacher_greek_recovered_not_transliterated():
    pdf = TEST_PDFS / "apa" / "korbmacher_2022_kruger.pdf"
    if not pdf.exists():
        pytest.skip(f"fixture missing: {pdf}")
    md = render_pdf_to_markdown(pdf.read_bytes())
    # The PDF prints H(2) = 237, p < .001, η² = 0.34 — Greek eta must survive.
    assert "η" in md, "Greek eta (η) not present — math-italic Greek lost"
    # The corruption signature must be gone.
    assert "n2 = 0.34" not in md, "math-italic eta still transliterated to 'n'"
    assert "n2 = 0.014" not in md
    # No raw math-alphanumeric codepoint may leak into the rendered output
    # (body OR table cells — the Camelot channel must be covered too).
    leaks = _MATH_ALNUM_RE.findall(md)
    assert not leaks, f"math-alphanumeric chars leaked into render: {leaks!r}"
