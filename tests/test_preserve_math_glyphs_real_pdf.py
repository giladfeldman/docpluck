"""Regression test for the preserve_math_glyphs flag (TRIAGE 2026-05-14 G2/G7/G12/G21).

The render path (`render_pdf_to_markdown`) MUST preserve source PDF glyphs:
- Greek letters (β, δ, γ, σ, μ, τ, ε, ω, π, α, χ, η, φ) — never transliterate to "beta" / "delta" / etc.
- Math operators (×, ≥, ≤, ÷, ±, ·) — never substitute with ASCII (x, >=, <=, etc.)
- Superscripts (²/³/etc.) and subscripts (₀/₁/etc.) — preserve Unicode chars
- The ONLY documented Unicode→ASCII conversion is U+2212 → "-" (CLAUDE.md L004)

The stat-extraction path (`normalize_text` default) keeps the old ASCII transliteration
behavior so D5 stat-regex tests + downstream consumers continue to work.

Real-PDF fixtures: the ieee_access_2 paper contains heavy Greek/math content
(SIRS model: β/γ/δ ODEs, ², ≥/≤). The xiao paper has η²_p / χ² statistical content.
"""

import pytest
from pathlib import Path

from docpluck.render import render_pdf_to_markdown
from docpluck.normalize import normalize_text, NormalizationLevel
from docpluck.sections import extract_sections


# Fixture paths
APP_REPO = Path(__file__).parent.parent.parent / "PDFextractor" / "test-pdfs"
IEEE_PDF = APP_REPO / "ieee" / "ieee_access_2.pdf"
XIAO_PDF = APP_REPO / "apa" / "xiao_2021_crsp.pdf"


def _require_pdf(p: Path) -> None:
    if not p.exists():
        pytest.skip(f"Fixture not available: {p}")


def test_render_preserves_beta_glyph_in_body():
    """ieee_access_2 has β in body equations (~61 occurrences). Render must keep them as β."""
    _require_pdf(IEEE_PDF)
    md = render_pdf_to_markdown(IEEE_PDF.read_bytes())
    assert "β" in md, "Render dropped β (Greek beta) — preserve_math_glyphs not active"
    # Body should NOT have the transliterated form (as a standalone word)
    # Allow "beta" inside reference URLs / DOIs that legitimately contain "beta"
    # but the body text "beta" / "betaSI" / "delta" patterns must be absent
    assert "betaSI" not in md, "Render transliterated βSI to 'betaSI'"
    assert "deltaR" not in md, "Render transliterated δR to 'deltaR'"


def test_render_preserves_delta_glyph_in_body():
    """ieee_access_2 has δ in body (~32 occurrences). Render must keep them as δ."""
    _require_pdf(IEEE_PDF)
    md = render_pdf_to_markdown(IEEE_PDF.read_bytes())
    assert "δ" in md, "Render dropped δ (Greek delta) — preserve_math_glyphs not active"


def test_render_preserves_greek_inconsistency_fix():
    """Prior bug: β/δ transliterated, γ/τ kept (inconsistent). Now: all preserved."""
    _require_pdf(IEEE_PDF)
    md = render_pdf_to_markdown(IEEE_PDF.read_bytes())
    # γ and τ were always preserved; β and δ used to be transliterated. After
    # the fix, all four are preserved together — the inconsistency is gone.
    assert "γ" in md
    assert "β" in md
    assert "δ" in md


def test_render_preserves_superscript_squared_when_upstream_provides_it():
    """If pdftotext preserves ² in its output, render must NOT transliterate it
    to plain '2' via A5. (For some PDFs poppler drops ² upstream — Cycle 15g
    addresses that separately. This test verifies the in-library preserve path,
    not the upstream recovery.)"""
    _require_pdf(IEEE_PDF)
    # Build the raw-text channel the way render does
    from docpluck.extract import extract_pdf
    raw, _ = extract_pdf(IEEE_PDF.read_bytes())
    if "²" not in raw:
        pytest.skip("pdftotext dropped ² upstream for this PDF (Cycle 15g)")
    md = render_pdf_to_markdown(IEEE_PDF.read_bytes())
    assert "²" in md, "Render dropped ² superscript — preserve_math_glyphs not active"


def test_render_preserves_comparison_operators():
    """ieee_access_2 figure captions use ≤ (e.g. 'RRMSE ≤ 44%'). Render must keep ≤."""
    _require_pdf(IEEE_PDF)
    md = render_pdf_to_markdown(IEEE_PDF.read_bytes())
    # ≤ appears in figure captions
    assert "≤" in md, "Render substituted ≤ with '<=' — preserve_math_glyphs not active"


def test_render_preserves_chi_squared_for_xiao():
    """xiao_2021_crsp has η²_p / χ² in statistical results. Render must keep glyphs."""
    _require_pdf(XIAO_PDF)
    md = render_pdf_to_markdown(XIAO_PDF.read_bytes())
    # At least one of the Greek stat glyphs should survive (the paper has η_p², χ², φ)
    has_greek = any(g in md for g in ("η", "χ", "φ", "α"))
    assert has_greek, "Render stripped all Greek stat letters from xiao — preserve_math_glyphs not active"


def test_normalize_text_default_still_transliterates():
    """Backward compat: D5 stat-extraction tests expect 'chi2' / 'eta2' / 'beta' in
    the default normalize_text output. The flag is OPT-IN; default behavior preserved."""
    sample = "We found χ²(1) = 4.5, p < .05, η²_p = .12, β = 0.34, σ = 2.1."
    normalized, _ = normalize_text(sample, NormalizationLevel.academic)
    # Default behavior (preserve_math_glyphs=False) transliterates
    assert "chi" in normalized.lower() or "chi2" in normalized.lower()
    assert "beta" in normalized
    assert "sigma" in normalized


def test_normalize_text_preserve_flag_keeps_greek():
    """Explicit preserve_math_glyphs=True keeps Unicode."""
    sample = "We found χ²(1) = 4.5, η²_p = .12, β = 0.34, σ = 2.1, μ = 5.0."
    normalized, _ = normalize_text(
        sample, NormalizationLevel.academic, preserve_math_glyphs=True
    )
    assert "χ" in normalized
    assert "β" in normalized
    assert "σ" in normalized
    assert "μ" in normalized
    # And the transliterated forms should NOT appear
    assert "chi2" not in normalized
    assert "beta" not in normalized
    assert "sigma" not in normalized


def test_extract_sections_preserve_flag_forwards_to_normalize():
    """extract_sections plumbs preserve_math_glyphs through to normalize_text."""
    _require_pdf(IEEE_PDF)
    doc = extract_sections(
        IEEE_PDF.read_bytes(),
        source_format="pdf",
        preserve_math_glyphs=True,
    )
    assert "β" in doc.normalized_text
    assert "δ" in doc.normalized_text


def test_extract_sections_default_still_transliterates():
    """Without the flag, extract_sections preserves backward-compat behavior."""
    _require_pdf(IEEE_PDF)
    doc = extract_sections(IEEE_PDF.read_bytes(), source_format="pdf")
    # Greek letters should be transliterated in the default path (back-compat)
    # The presence of "beta" or "delta" in normalized_text confirms A5 ran
    assert "beta" in doc.normalized_text or "delta" in doc.normalized_text


# ───────────────────────────────────────────────────────────────────────────
# Cycle 15b: G17 — comma-thousands preservation (amle_1 fix)
# ───────────────────────────────────────────────────────────────────────────


AMLE_PDF = APP_REPO / "aom" / "amle_1.pdf"


def test_render_preserves_comma_thousands_in_body_prose():
    """amle_1 abstract has '7,445 sources, 33,719 articles ... 32,981 authors'.
    Render must keep the commas — they're thousands separators, not decimals."""
    _require_pdf(AMLE_PDF)
    md = render_pdf_to_markdown(AMLE_PDF.read_bytes())
    # The three abstract counts must appear with their commas intact
    assert "7,445" in md, "Render stripped comma from 7,445 (thousands separator)"
    assert "33,719" in md, "Render stripped comma from 33,719 (thousands separator)"
    assert "32,981" in md, "Render stripped comma from 32,981 (thousands separator)"
    # And the comma-stripped forms (read as years!) must NOT be present alone
    # (Use word boundaries so we don't false-positive on '7445' inside a longer string)
    import re
    assert not re.search(r"\b7445\b", md), "Render emitted '7445' — comma-stripped"
    assert not re.search(r"\b33719\b", md), "Render emitted '33719' — comma-stripped"


def test_render_preserves_european_decimal_in_render_path():
    """Synthetic check: in preserve mode, '0,87' should NOT be converted to '0.87'.
    Downstream stat-extraction (which uses preserve_math_glyphs=False) still gets
    the dot form."""
    from docpluck.normalize import normalize_text, NormalizationLevel
    sample = "Effect size d = 0,87 was found. Sample size N = 1,675."
    # Default behavior: A3 + A3a strip and normalize
    normalized_default, _ = normalize_text(sample, NormalizationLevel.academic)
    assert "0.87" in normalized_default  # A3 converted
    assert "1675" in normalized_default  # A3a stripped
    # Preserve behavior: both kept as-is
    normalized_preserve, _ = normalize_text(
        sample, NormalizationLevel.academic, preserve_math_glyphs=True
    )
    assert "0,87" in normalized_preserve  # A3 skipped
    assert "1,675" in normalized_preserve  # A3a skipped


# ───────────────────────────────────────────────────────────────────────────
# Cycle 15c: G15 — NFC composition fixes combining-char splits (amj_1 fix)
# ───────────────────────────────────────────────────────────────────────────


def test_normalize_recomposes_combining_diacritics():
    """amj_1 PDF emits 'Förster' as NFD decomposed (F + o + combining diaeresis)
    OR with a stray space (Fö rster → Fö rster). NFC composition + the
    space-before-combining-mark squash must yield 'Förster' (precomposed)."""
    from docpluck.normalize import normalize_text, NormalizationLevel
    # NFD form (F + o + combining diaeresis U+0308)
    nfd_sample = "Author: Förster, Friedman, 2004"
    normalized, _ = normalize_text(nfd_sample, NormalizationLevel.academic)
    assert "Förster" in normalized, "NFC composition didn't recompose o + combining diaeresis"

    # Space-before-combining-mark form (pdftotext bug pattern)
    spaced_sample = "Author: Fö ̈rster"  # implausible but trace pattern
    # The simpler real-world case: a stray space between letter and a combining mark
    spaced_real = "Author: o ̈rster"  # 'o' + space + combining-diaeresis + 'rster'
    normalized_spaced, _ = normalize_text(spaced_real, NormalizationLevel.academic)
    # After the squash + NFC, the space should be removed and ö composed
    assert " ̈" not in normalized_spaced, "stray space before combining mark not squashed"


def test_normalize_potocnik_recomposes():
    """amj_1 has 'Potočnik' (ASCII 'c' + combining caron). NFC must recompose
    to single Unicode code point 'č' (U+010D)."""
    from docpluck.normalize import normalize_text, NormalizationLevel
    nfd_sample = "Author: Potočnik, 2024"
    normalized, _ = normalize_text(nfd_sample, NormalizationLevel.academic)
    assert "Potočnik" in normalized
    # The decomposed form should be gone
    assert "č" not in normalized
