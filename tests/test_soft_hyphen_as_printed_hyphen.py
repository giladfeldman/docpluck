"""A document whose font maps its printed hyphen glyph to U+00AD keeps its hyphens.

10.1126/science.aac4716 (the OpenPDF export of the reproducibility-project
manuscript) prints ``1359-1366``, ``high-powered``, ``meta-analysis``, R's
``<-`` and negative table values ``-0.327`` (p30, p2, p67, p13; rasterized
2026-10-27), and its text layer gives every one of those glyphs as U+00AD.
pdftotext reports 315 U+00AD between two word characters and not one U+002D
there. S6 stripped U+00AD as an invisible soft hyphen, so the text said
``13591366``, ``highpowered``, ``metaanalysis`` and ``0.327``.

Elsewhere U+00AD really is invisible: 10.1177/00221465251343322 p2 prints
``American`` and the text layer holds ``Amer<U+00AD>ican``; that paper prints
U+002D in ``well-being`` throughout. So the call is made per DOCUMENT: U+00AD is
the hyphen glyph only when it is the document's intra-word hyphen character
(several word-internal U+00AD, and U+002D almost never there).
"""
from __future__ import annotations

from docpluck.normalize import NormalizationLevel, normalize_text

SHY = "\u00ad"


def _doc(body: str) -> str:
    return body.replace("~", SHY)


def test_shy_is_the_hyphen_when_the_document_has_no_other():
    text = _doc(
        "We ran high~powered designs. Ninety~seven percent; a meta~analysis "
        "of the to~be~replicated set. Psychol. Sci. 22, 1359~1366 (2011). "
        "Nature 483, 531~533 (2012). Original r: ~0.327 and ~0.057.\n"
    ) * 3
    out, report = normalize_text(text, NormalizationLevel.academic)
    assert "1359-1366" in out
    assert "531-533" in out
    assert "high-powered" in out
    assert "meta-analysis" in out
    assert "to-be-replicated" in out
    assert "-0.327" in out
    assert SHY not in out
    assert "S0h_soft_hyphen_is_hyphen_glyph" in report.steps_changed


def test_invisible_soft_hyphen_beside_real_hyphens_is_still_dropped():
    text = _doc(
        "the well-being of young Amer~ican citizens; a cross-sectional, "
        "two-wave, face-to-face, self-report study of long-term health.\n"
    )
    out, _ = normalize_text(text, NormalizationLevel.academic)
    assert "American" in out
    assert "Amer-ican" not in out


def test_hyphens_set_as_u2010_count_as_the_documents_hyphen():
    # S0h runs before S5 folds U+2010 into `-`: a paper printing its hyphens as
    # U+2010 with invisible soft hyphens must not read as a U+00AD-hyphen paper.
    text = _doc(
        "signifi~cant experi~ment rela~tion partici~pants analy~sis condi~tion; "
        + " ".join(["well\u2010being"] * 6)
        + " and long\u2010term.\n"
    )
    out, _ = normalize_text(text, NormalizationLevel.academic)
    assert "significant" in out and "participants" in out and "condition" in out


def test_hyphenation_hints_inside_words_only_are_not_the_hyphen_glyph():
    # An HTML/CMS text with an `&shy;` break hint in every long word: many
    # word-internal U+00AD, few hyphens, but never one between two digits or
    # before a number -- a hyphenation hint never splits a number. (Second-model
    # consult, 2026-10-27.)
    text = _doc(
        "The signifi~cant experi~mental condi~tions were analy~sed. Partici~pants "
        "(N = 120) com~pleted the ques~tion~naire in 2019; effects were small "
        "(d = 0.21, 95% CI [0.05, 0.37]) and mood rose.\n"
    )
    out, _ = normalize_text(text, NormalizationLevel.academic)
    assert "significant" in out and "questionnaire" in out
    assert "signifi-cant" not in out


def test_a_short_text_with_split_numbers_is_not_enough():
    # Second-model consult (2026-10-27): 3 hinted words plus 2 hint-split
    # numbers and no hyphen passed a 5-site gate. A short text is too little
    # evidence to call the glyph.
    text = _doc("signifi~cant experi~ment rela~tion; ISBN 978~0~19 and 12~34.\n")
    out, _ = normalize_text(text, NormalizationLevel.academic)
    assert "significant" in out and "signifi-cant" not in out


def test_a_few_soft_hyphens_alone_are_not_enough():
    # Four word-internal U+00AD and no U+002D: too little to call the glyph.
    text = _doc("signifi~cant, experi~ment, rela~tion, partici~pants.\n")
    out, _ = normalize_text(text, NormalizationLevel.academic)
    assert "significant" in out and "participants" in out


def test_science_aac4716_page_ranges_and_hyphens_survive_extract_and_normalize():
    from docpluck.extract import extract_pdf
    from docpluck.testing.corpus import custody_path

    p = custody_path("fulltext", "10.1126__science.aac4716.pdf")
    raw, _ = extract_pdf(p.read_bytes())
    out, _ = normalize_text(raw, NormalizationLevel.academic)
    assert "1359-1366" in out
    assert "531-533" in out
    assert "13591366" not in out
    assert "high-powered" in out
