"""Real-PDF regression tests for v2.4.17 body-integer corruption fixes.

Two related defects, same defect family (academic-mode body-integer
corruption):

1. **A3 thousands-separator widening** — `_N_PROTECT_PATTERNS` was too narrow
   (only protected `N =`, `df =`, "sample size of", "total of N
   participants"). Generic body integers like `1,001 participants`,
   `4,200 followers`, `7,445 sources`, `3,000 hours` fell through to A3 and
   got corrupted into `1.001`, `4.200`, etc. — silently destroying sample
   sizes.

2. **R2 noun-exception list** — R2 (page-number scrub in references span)
   uses ``_raw_page_numbers`` (digits that appear as standalone lines ≥ 2
   times). On PDFs with many cell-value standalone digits (e.g. amle_1
   has "20" and "40" as Yes/No table cell values appearing 4+ times each),
   R2 falsely strips body-phrase digits like `first 20 years` →
   `first years`.

Per /docpluck-iterate skill rule 0d: every fix ships with at least one
``*_real_pdf`` test that exercises the public library entry point on an
actual PDF fixture from ``../PDFextractor/test-pdfs/``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from docpluck.normalize import (
    NORMALIZATION_VERSION,
    NormalizationLevel,
    normalize_text,
    _R2_BODY_NOUN_PATTERN,
    _r2_is_body_phrase,
)
from docpluck.render import render_pdf_to_markdown


_PDF_ROOT = Path(__file__).resolve().parents[1] / ".." / "PDFextractor" / "test-pdfs"


def _maybe_render(rel: str) -> str:
    pdf = (_PDF_ROOT / rel).resolve()
    if not pdf.is_file():
        pytest.skip(f"fixture not available locally: {rel}")
    return render_pdf_to_markdown(pdf.read_bytes())


# ── Contract tests (synthetic strings, fast) ───────────────────────────────


def test_v185_version_bump():
    # v2.4.29 bumped 1.8.x → 1.9.0 for `preserve_math_glyphs`. The A3
    # widening this test exercises remains in place; the bump only
    # gates the A3 step on the new flag, which defaults to False
    # (back-compat). Accept both families.
    assert NORMALIZATION_VERSION.startswith(("1.8.", "1.9."))


def test_a3_widening_preserves_sample_size_1001():
    # "1,001 participants" must not become "1.001 participants".
    text = "Our final sample consisted of 1,001 participants who completed the survey."
    out, _ = normalize_text(text, NormalizationLevel.academic)
    assert "1,001 participants" in out or "1001 participants" in out
    assert "1.001 participants" not in out


def test_a3_widening_preserves_followers_4200():
    text = "He has approximately 4,200 followers on Twitter."
    out, _ = normalize_text(text, NormalizationLevel.academic)
    assert "1.200" not in out
    assert "4.200" not in out
    assert "4,200" in out or "4200" in out


def test_a3_widening_preserves_seven_thousand_sources():
    text = (
        "Our database includes 7,445 sources, 33,719 articles and book "
        "chapters, and 32,981 authors cited at least once."
    )
    out, _ = normalize_text(text, NormalizationLevel.academic)
    for bad in ["7.445", "33.719", "32.981"]:
        assert bad not in out, f"A3 corrupted {bad} in body integer"


def test_a3_widening_preserves_three_thousand_hours():
    text = "Participants spent approximately 3,000 hours coding."
    out, _ = normalize_text(text, NormalizationLevel.academic)
    assert "3.000 hours" not in out


def test_a3_still_normalizes_european_decimal():
    # European decimal `0,05` should still be normalized to `0.05` by A3.
    text = "We rejected the null hypothesis (p = 0,05) and tested d = 0,87."
    out, _ = normalize_text(text, NormalizationLevel.academic)
    assert "0.05" in out
    assert "0.87" in out


def test_a3_still_normalizes_one_digit_decimal_comma():
    # `1,5` (German for 1.5) must still convert.
    text = "The mean was 1,5 and SD 0,3."
    out, _ = normalize_text(text, NormalizationLevel.academic)
    assert "1.5" in out
    assert "0.3" in out


def test_r2_body_phrase_helper_matches_years():
    # The helper should recognize " 20 years" as a body phrase.
    refs_text = "The first 20 years of Organizational Research Methods."
    pos = refs_text.find("20")
    assert _r2_is_body_phrase("20", refs_text, pos) is True


def test_r2_body_phrase_helper_matches_participants():
    refs_text = "We recruited 1675 participants from the lab."
    pos = refs_text.find("1675")
    assert _r2_is_body_phrase("1675", refs_text, pos) is True


def test_r2_body_phrase_helper_rejects_page_number_leak():
    # "psychological 41 science" is the classic page-number leak.
    # 'science' is not in the body-noun list, so no body-phrase match.
    refs_text = "Their study published in psychological 41 science."
    pos = refs_text.find("41")
    assert _r2_is_body_phrase("41", refs_text, pos) is False


def test_r2_body_noun_pattern_covers_common_units():
    for noun in [
        "years", "year", "days", "hours", "participants", "subjects",
        "followers", "sources", "authors", "articles", "people", "students",
        "patients", "managers", "items", "trials", "studies",
        "instruments", "measures", "scales", "factors",
    ]:
        assert _R2_BODY_NOUN_PATTERN.search(noun), f"missing noun: {noun}"


# ── v2.4.84 quantifier-head pre-context guard (general, closed-class) ────────


def test_r2_quantifier_head_preserves_of_three_instruments():
    # "of 3 instruments" — "of" is a function word heading a noun phrase, so
    # the digit is a quantifier and must be preserved even though the prior
    # noun list never enumerated "instruments". This is the plos_med_1
    # Clinimetric defect (citationguard-iterate 2026-06-10) root signature.
    refs_text = "Clinimetric properties of 3 instruments measuring recovery."
    pos = refs_text.find("3")
    assert _r2_is_body_phrase("3", refs_text, pos) is True


def test_r2_quantifier_head_preserves_the_five_factors():
    refs_text = "Validation of the 5 factors underlying the construct."
    pos = refs_text.find("5")
    assert _r2_is_body_phrase("5", refs_text, pos) is True


def test_r2_quantifier_head_does_not_rescue_content_word_leak():
    # The preceding word "psychological" is a CONTENT word, so the
    # quantifier-head guard must NOT preserve — the page-number leak still
    # strips (no false rescue). Mirrors the original strip-test.
    refs_text = "Their study published in psychological 41 science."
    pos = refs_text.find("41")
    assert _r2_is_body_phrase("41", refs_text, pos) is False


# ── Real-PDF regression tests (rule 0d) ────────────────────────────────────


def test_amle_1_first_20_years_preserved_real_pdf():
    md = _maybe_render("aom/amle_1.pdf")
    # The reference title "The first 20 years of Organizational Research
    # Methods" must keep the "20" — was lost at v2.4.16 because R2 saw "20"
    # as a recurring standalone-line value (cell value in tables) and
    # stripped it.
    assert "first 20 years" in md, "R2 still strips '20' from 'first 20 years'"
    assert "first 40 years" in md, "R2 still strips '40' from 'first 40 years'"


def test_xiao_2021_crsp_sample_size_1001_not_corrupted_real_pdf():
    md = _maybe_render("apa/xiao_2021_crsp.pdf")
    # Sample size "1,001 participants" must NOT be corrupted to "1.001".
    # Either "1,001" or "1001" is acceptable (comma stripped by A3a).
    assert "1.001 participants" not in md, "A3 corrupts sample size 1,001 → 1.001"
    assert "1,001" in md or "1001" in md


def test_amle_1_sample_counts_not_corrupted_real_pdf():
    md = _maybe_render("aom/amle_1.pdf")
    # Database counts: "7,445 sources, 33,719 articles, 32,981 authors".
    # A3 corruption would produce "7.445", "33.719", "32.981".
    for bad in ["7.445", "33.719", "32.981"]:
        assert bad not in md, f"A3 still corrupts {bad}"


def test_plos_med_1_three_instruments_preserved_real_pdf():
    # plos_med_1 reference: "Clinimetric properties of 3 instruments measuring
    # postoperative recovery in a gynecologic surgical population." R2 saw "3"
    # as a recurring standalone-line page number and stripped it from the
    # title → "… properties of instruments measuring …", silently corrupting
    # the citation citationguard consumed (filed 2026-06-10). The v2.4.84
    # quantifier-head guard preserves it because "of" precedes the digit.
    md = _maybe_render("vancouver/plos_med_1.pdf")
    assert "of 3 instruments" in md, "R2 still strips the quantifier '3' from the title"
    assert "of instruments measuring" not in md
