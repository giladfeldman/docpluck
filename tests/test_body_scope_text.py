"""Body-scope text: the document text without its reference list.

`extract_pdf` + `normalize_text` return the whole document, bibliography
included. On a 30-paper held-out text benchmark that cost docpluck precision
(.811, against .991 for a tool that emits only the body). `docpluck.body`
removes the reference list and nothing else, and keeps body paragraphs that the
linearised text happens to place after the bibliography heading.
"""

from pathlib import Path

import pytest

from docpluck.body import BodyScopeReport, body_scope_text, reference_list_end

_BODY = (
    "Title of the paper\n\n"
    "Abstract\n\nWe studied a thing and found a result.\n\n"
    "Introduction\n\nThe thing matters for many reasons (Smith & Jones, 2019).\n\n"
    "Methods\n\nWe measured the thing in 40 samples.\n\n"
    "Results\n\nThe thing was larger than expected, t(39) = 2.10, p = .04.\n\n"
    "Discussion\n\nThe thing is now better understood.\n\n"
)

_REFS = (
    "References\n\n"
    "Jones, A. B., & Smith, C. (2019). A study of things. Journal of Things, 12, 1-10.\n"
    "Lee, K. (2020). Another study of things. Psychological Science, 31, 44-50.\n"
    "Ortiz, J. P., & Quinn, R. S. (2024). Statistics of a condition. Circulation, 149, e100.\n"
)


def test_reference_list_is_removed_and_body_kept():
    text = _BODY + _REFS
    body, report = body_scope_text(text)
    assert isinstance(report, BodyScopeReport)
    assert body == _BODY
    assert report.references_found
    assert [r.label for r in report.removed] == ["references"]
    r = report.removed[0]
    assert text[r.char_start:r.char_end] == _REFS


def test_back_matter_after_the_references_is_kept():
    tail = "Acknowledgments\n\nWe thank the participants.\n"
    body, _ = body_scope_text(_BODY + _REFS + "\n" + tail)
    assert body.startswith(_BODY)
    assert body.endswith(tail)
    assert "Psychological Science" not in body


def test_text_without_references_is_returned_unchanged():
    body, report = body_scope_text(_BODY)
    assert body == _BODY
    assert not report.references_found and report.removed == ()


def test_footnote_appendix_is_not_body():
    text = _BODY + _REFS + "\n\f\f\n1 A footnote the layout pass moved out of the body."
    body, _ = body_scope_text(text)
    assert body == _BODY
    assert "footnote" not in body


_PROSE = (
    "Rivera et al. classified retinal images with the aid of a convolutional network. In this "
    "work, the images were taken from a public archive and their visual properties were "
    "analysed against the clinical evaluation results reported for each patient.\n"
    "The authors used a regression-based network for detecting and classifying the abnormal "
    "images. The proposed work was tested on a large imaging dataset to evaluate its "
    "experimental and clinical results, with high sensitivity and specificity throughout.\n"
) * 4


def test_guard_keeps_body_paragraphs_placed_after_the_reference_entries():
    """The linearised text sometimes puts body paragraphs after the bibliography
    heading. The cut stops where entry-shaped lines stop."""
    text = _BODY + _REFS + _PROSE
    body, report = body_scope_text(text)
    assert body == _BODY + _PROSE
    assert report.kept_after_references == ((len(_BODY) + len(_REFS), len(text)),)


def test_guard_does_not_stop_inside_a_wrapped_entry():
    refs = (
        "References\n\n"
        "[1] A. B. Carter, D. E. Fox, G. H. Lund, I. J. Moss, K. L. Nash, M. N.\n"
        "Owens, P. Q. Reid, S. T. Ruiz, Science 2004, 306, 101.\n"
        "[2] J. K. Moreno, L. M. Ostrowski, N. P. Quist, R. S. Tan, U. V. Wells, X.\n"
        "Yoder, Z. Abbott, B. Diaz, J. Am. Chem. Soc. 2024, 146,\n"
        "12345.\n"
    )
    text = _BODY + refs
    assert reference_list_end(text, len(_BODY), len(text)) == len(text)
    body, _ = body_scope_text(text)
    assert body == _BODY


def test_public_names_are_exported():
    import docpluck

    for name in ("extract_pdf_body", "body_scope_text", "BodyScopeReport", "BODY_SCOPE_VERSION"):
        assert hasattr(docpluck, name), name
        assert name in docpluck.__all__, name


# --- real paper ---------------------------------------------------------------

pytest.importorskip("pdfplumber", reason="pdfplumber not installed (pip install docpluck[all])")


def test_extract_pdf_body_on_a_real_paper():
    """A real APA paper: the body ends before its References heading, the text
    before the cut is the layout-aware normalized text unchanged, and existing
    outputs (normalize_text) are untouched by the new function."""
    from docpluck import (
        NormalizationLevel, extract_pdf, extract_pdf_body, extract_pdf_layout, normalize_text,
    )
    from docpluck.testing.corpus import require_corpus_pdf

    pdf = Path(require_corpus_pdf("apa/chen_2021_jesp.pdf"))
    b = pdf.read_bytes()
    raw, _ = extract_pdf(b)
    full, _ = normalize_text(raw, NormalizationLevel.academic, layout=extract_pdf_layout(b))
    full_body = full.split("\n\f\f\n", 1)[0]

    body, report = extract_pdf_body(b)
    assert report.references_found
    refs = [r for r in report.removed if r.label.startswith("references")]
    assert refs, report.removed
    first = refs[0]
    assert body.startswith(full_body[:first.char_start])
    assert len(body) < len(full_body)
    ref_text = full_body[first.char_start:first.char_end]
    # the bibliography really went: its longest entry-shaped line is not in the body
    longest = max(ref_text.splitlines(), key=len)
    assert longest not in body
    assert report.normalization is not None


def test_table_titles_printed_after_the_reference_list_are_kept():
    """A short caption after the last entry is body, though far shorter than the
    non-entry run the main rule needs."""
    captions = "\nTable 1. Length of stay by offence\nTable 2. Sentencing range by institution\n"
    body, _ = body_scope_text(_BODY + _REFS + captions)
    assert body == _BODY + captions.lstrip("\n") or body == _BODY + captions
    assert "Psychological Science" not in body


def test_entries_continuing_under_a_heading_dropped_into_the_list_are_removed():
    """Column order can drop a back-matter heading ("Disclosure") into the middle
    of the bibliography; the entries after it are still the bibliography, the
    heading's own statement is not."""
    more = (
        "Abbott YZ, Carter AB and Diaz BC (1987) A rating scale for a common\n"
        "condition. Clinical Bulletin 13(2), 201-215.\n"
        "Fox DE, Lund GH, Moss IJ and Nash KL (2011) Properties of the\n"
        "rating scale. Clinical Research 125(2), 101-108.\n"
        "Owens MN, Reid PQ, Ruiz ST and Tan RS (2023) A combined treatment improves cognitive scale scores in a large randomised trial of adults.\n"
        "Journal of Clinical Studies 12(3), 45-67.\n"
    )
    disclosure = "Disclosure\n\nThe authors declare no competing interests.\n\n"
    body, report = body_scope_text(_BODY + _REFS + "\n" + disclosure + more)
    assert "The authors declare no competing interests." in body
    assert "Abbott YZ" not in body and "combined treatment" not in body
    assert "references_continued" in [r.label for r in report.removed]
