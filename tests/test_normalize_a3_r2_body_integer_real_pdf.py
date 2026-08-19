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


def test_a3_no_longer_normalizes_a_european_decimal():
    """RE-FIXTURED 2026-08-14. A3 is DELETED under the scope directive.

    Measured over 297 English papers before removal: A3 fired 9 times in 2
    papers and NOT ONCE correctly. A European decimal now reaches the consumer
    verbatim, so the source token is intact and the consumer can still decide.
    """
    text = "We rejected the null hypothesis (p = 0,05) and tested d = 0,87."
    out, _ = normalize_text(text, NormalizationLevel.academic)
    assert out.strip() == text
    assert "0.05" not in out
    assert "0.87" not in out


def test_bare_prose_decimal_comma_is_PRESERVED_not_guessed(_decision="D1"):
    """Re-fixtured in v2.4.128 (decision D1). The old expectation was wrong.

    This test used to assert that `The mean was 1,5` converts to `1.5`. The
    reason it no longer does is not an oversight — it is the whole point of
    v2.4.127's A3 rewrite, and the REASON matters more than the value:

    **Nothing in that sentence decides it.** `1,5` is one-point-five under a
    German convention and "items 1 and 5" under an English one. The old rule
    guessed, using a lookbehind that enumerated what may not precede the number
    — and measured over 101 papers it fired 29 times in 13 of them with **~27
    of those not decimals at all**: Vancouver citation runs, affiliation
    markers, enumerations, flattened df pairs. A3 now converts only in the
    VALUE POSITION (an operator immediately before the number), which is a
    positive structural signature rather than a growing denylist.

    ESCImate's own shared conformance corpus contains this exact token shape
    TWICE with OPPOSITE expectations, two cases apart:

        'decimal-single-digit-fraction' : "The ratio was 1,5 times higher."  -> 1.5
        'list-items'                    : "items 1,5 and 7 were reversed"    -> 1,5

    Only the surrounding words differ, and their own lesson says a word
    vocabulary "can never be complete and must not be the primary mechanism".

    Preserving the token is not the same as getting it wrong: the source form
    is intact and BOTH readings stay recoverable, where a wrong conversion is
    irreversible. Resolving it needs document-level evidence, which as of
    v2.4.128 docpluck computes and publishes (`NormalizationReport
    .numeric_locale`) but deliberately does not yet act on — see
    `tests/test_numeric_locale_inference.py` for why the aggressive form was
    refuted before implementation.

    `SD 0,3` is unchanged too, and for a different reason worth stating: A3c
    handles the leading-zero form `0,XX` only from two digits, because `[0,5]`
    is far more often the range "0 to 5" than the decimal 0.5.
    """
    text = "The mean was 1,5 and SD 0,3."
    out, _ = normalize_text(text, NormalizationLevel.academic)
    assert "1,5" in out, "an ambiguous prose token must be preserved verbatim"
    assert "1.5" not in out
    assert "0,3" in out


def test_the_same_token_ALSO_passes_through_in_the_value_position():
    """RE-FIXTURED 2026-08-14 — and this one records a genuine simplification.

    Its companion above (`test_bare_prose_decimal_comma_is_PRESERVED_not_guessed`)
    pinned v2.4.127's decision that A3 was a POSITION rule: outside the value
    position the token was ambiguous and preserved; inside it, an operator made
    it a value and it converted. This test was the "and then it converts" half.

    The position distinction is gone with the rule, and the outcome is that
    docpluck now gives ONE answer for `1,5` instead of two that depended on
    whether an operator happened to precede it. A library that converts one
    input two ways has no contract at all (LESSONS.md L-024).
    """
    out, _ = normalize_text("The mean was M = 1,5", NormalizationLevel.academic)
    assert "M = 1,5" in out
    assert "M = 1.5" not in out


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
