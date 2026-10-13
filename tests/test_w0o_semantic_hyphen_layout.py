"""W0o: a compound hyphen that pdftotext's dehyphenation removed is restored.

ip_feldman (10.1177/01461672251327169, p10) prints the heading ``Well-`` /
``Being`` across a line end; pdftotext joins it to ``WellBeing``. The same paper
prints ``well-being`` inline 61 times and never prints ``wellbeing`` glued.

The gate is document-level word counting (no line pairing, which merges the two
columns of a two-column page): restore ``AB`` -> ``A-B`` iff the text prints
``A-B`` inline, the LAYOUT channel never holds ``AB`` as a word, the layout holds
a line-end ``A-`` fragment for every glued copy, and the copy is not in a URL/DOI.
"""
from __future__ import annotations

import re
from types import SimpleNamespace

from docpluck.normalize import (
    NormalizationLevel,
    normalize_text,
    recover_semantic_hyphens_via_layout,
)
from docpluck.testing import require_corpus_pdf


def _layout(*words):
    page = SimpleNamespace(words=tuple({"text": w} for w in words))
    return SimpleNamespace(pages=(page,))


def test_glued_compound_with_inline_attestation_is_restored():
    text = "Our well-being scale. Later the WellBeing heading and wellbeing again."
    lay = _layout("Our", "well-being", "scale.", "Well-", "Being", "well-", "being")
    n = [0]
    out = recover_semantic_hyphens_via_layout(text, lay, n)
    assert "Well-Being heading" in out
    assert "well-being again" in out
    assert n[0] == 2


def test_a_word_the_paper_prints_glued_is_never_touched():
    # The document prints `preregistration` glued on a line: the glued copies
    # in the text may be genuine, so none is rewritten.
    text = "A pre-registration was filed. The preregistration and preregistration."
    lay = _layout("pre-registration", "preregistration", "pre-", "registration")
    out = recover_semantic_hyphens_via_layout(text, lay, None)
    assert out == text


def test_no_inline_attestation_no_rewrite():
    text = "The experiences were coded."
    lay = _layout("experi-", "ences")
    assert recover_semantic_hyphens_via_layout(text, lay, None) == text


def test_more_glued_copies_than_line_end_fragments_is_refused():
    text = "self-report items; selfreport and selfreport."
    lay = _layout("self-report", "self-", "report")  # one fragment, two glued
    assert recover_semantic_hyphens_via_layout(text, lay, None) == text


def test_a_glued_word_inside_a_longer_layout_token_is_never_touched():
    # 10.1016/j.jesp.2020.103977 p9 prints the reference "derive from nonmoral"
    # (rasterized 2026-10-13); its PDF has no space glyphs there, so pdfplumber
    # returns one token `...derivefromnonmoral`, never `nonmoral` alone. The
    # paper also prints `non-moral` inline and has unrelated `non-` line ends.
    # Consult round 2 (Sonnet, 2026-10-13) finding 2.
    text = "a non-moral view. Patterns of moral judgment derive from nonmoral ones"
    lay = _layout("non-moral", "Patternsofmoraljudgmentderivefromnonmoral", "non-", "verbal")
    assert recover_semantic_hyphens_via_layout(text, lay, None) == text


def test_one_line_end_fragment_licenses_one_site_across_compounds():
    # 10.5465/amj.2016.1196: self-concept (2 glued) and self-regulation (1 glued)
    # against 2 `self-` line ends. A fragment cannot license two sites, so the
    # prefix is refused as a whole. Consult round 2 (Sonnet, 2026-10-13) finding 1.
    text = ("self-concept and self-regulation inline; selfconcept, selfconcept "
            "and selfregulation glued")
    lay = _layout("self-concept", "self-regulation", "self-", "concept", "self-", "regulation")
    assert recover_semantic_hyphens_via_layout(text, lay, None) == text


def test_a_doi_is_never_hyphenated():
    # 10.5465/annals.2018.0057 cites `10.1109/ROMAN.2016.7745155` and elsewhere
    # prints the conference name RO-MAN; the DOI itself has no hyphen.
    text = "At RO-MAN 2016. https://doi.org/ 10.1109/ROMAN.2016.7745155."
    lay = _layout("RO-MAN", "10.1109/RO-", "MAN.2016.7745155.")
    assert recover_semantic_hyphens_via_layout(text, lay, None) == text


def test_no_layout_is_a_no_op():
    text = "well-being and wellbeing"
    assert recover_semantic_hyphens_via_layout(text, None, None) == text


def test_ip_feldman_well_being_real_pdf():
    from docpluck.extract import extract_pdf
    from docpluck.extract_layout import extract_pdf_layout

    pdf = require_corpus_pdf("apa/ip_feldman_2025_pspb.pdf").read_bytes()
    raw, _ = extract_pdf(pdf)
    layout = extract_pdf_layout(pdf)
    plain, _ = normalize_text(raw, NormalizationLevel.academic)
    fixed, report = normalize_text(
        raw, NormalizationLevel.academic, dropped_minus_layout=layout
    )
    # Known positive: the defect is present without the layout channel.
    assert len(re.findall(r"(?i)\bwellbeing\b", plain)) == 8
    assert re.findall(r"(?i)\bwellbeing\b", fixed) == []
    assert "Well-Being" in fixed
    # Correct value, not just absence: the restored count is exact.
    assert report.changes_made["semantic_hyphens_restored"] == 11
    # The paper prints `preregistration` glued; it stays glued.
    assert "preregistration" in fixed.lower()
