"""The watermark arm fires on a WATERMARK and not on TABLE CONTENT.

WHY THIS FILE EXISTS. The repeated-line strip's second arm -- the one that
removes a line repeating several times on every page -- was DELETED on
2026-08-28 after Grok 4.6 (xai) showed its then-current form, a bare
``count >= 20``, deduplicating table content. It was REINSTATED on 2026-08-29
gated on PAGE COVERAGE, after each of the three stated reasons for deleting it
was re-tested and none survived. This file is the evidence, so that neither
decision has to be taken on trust again.

THE COST OF THE DELETION, which is what forced the re-test: with no watermark
arm, ``ieee_access_2.pdf`` retains all 220 copies of "Author Manuscript", and
one of them lands between a paragraph and the heading ``V.: SUPPLEMENTARY
INDEX``, which is therefore never promoted -- see
``tests/test_roman_numeral_section_promote_real_pdf.py``. That is section
STRUCTURE reaching sectioning consumers, not cosmetic noise, so the deletion
note's asymmetry argument ("furniture that survives is VISIBLE and reversible")
did not hold for this paper: the loss was neither.

A TRAP THIS FILE WALKED INTO, recorded because it produced a confident wrong
answer for a whole round: the first version of the synthetic fixtures below
reported UNTOUCHED on ALL THREE trees, *including* one with the original
``count >= 20`` arm restored -- so it looked as though Grok's finding did not
reproduce at all. It did. ``S8_line_break_joining`` was merging the label into
the following line before the strip ran, so the fixture never reached the
branch. Asserting the arm actually FIRED is what caught it, and every synthetic
test here asserts that before believing a negative.

REAL PAPERS DECIDE PREVALENCE; the synthetic cases only probe the gate's
arithmetic at coverages no real paper in the sample exhibits.
"""

from __future__ import annotations

import pytest

from docpluck.extract import extract_pdf_file
from docpluck.normalize import NormalizationLevel, normalize_text
from .conftest import pdf_available, pdf_path, requires_pdftotext

PAGE_BREAK = chr(12)

# The watermark line both real positives carry. Not a coincidence: it is what
# PubMed Central stamps on an author manuscript.
WATERMARK = "Author Manuscript"

JAMA_KEY = "10.1001__jamanetworkopen.2023.39337.pdf"
JAMA_TITLE = (
    "Effect of Time-Restricted Eating on Weight Loss in Adults With Type 2 Diabetes"
)


def _norm(text: str):
    return normalize_text(text, NormalizationLevel.academic)


def _arm_fired(report) -> bool:
    return "P0q_repeated_line_strip" in report.steps_changed


def _taken_by(report, arm: str) -> int:
    return report.fallbacks.get("repeated_line_stripped:" + arm, 0)


# ---------------------------------------------------------------------------
# REAL POSITIVES -- the watermark must go, all but one copy
# ---------------------------------------------------------------------------

@requires_pdftotext
@pytest.mark.parametrize(
    "corpus,parts,copies",
    [
        ("docpluck", ("ieee", "ieee_access_2.pdf"), 220),
        ("docpluck", ("ieee", "ieee_access_alt.pdf"), 92),
        ("articlerepo", ("10.1525__collabra.19525.pdf",), 112),
    ],
)
def test_a_publisher_watermark_is_deduplicated_to_one_copy(corpus, parts, copies):
    """Measured 2026-08-29: 4 copies on EVERY page, page coverage 0.96-0.98.

    ``copies`` is the raw count at the time of measurement and is asserted only
    as a floor, because it depends on the local pdftotext build. What is
    asserted exactly is the OUTPUT: rule 0g requires that exactly one survive.
    """
    if not pdf_available(corpus, *parts):
        pytest.skip("fixture not present: " + pdf_path(corpus, *parts))
    raw, _engine = extract_pdf_file(pdf_path(corpus, *parts))
    assert len(raw) > 10_000, "extraction produced too little text to trust"

    raw_lines = sum(1 for ln in raw.split("\n") if ln.strip() == WATERMARK)
    assert raw_lines >= copies * 0.8, (
        "fixture no longer carries the watermark (%d lines); this test is "
        "measuring nothing" % raw_lines
    )

    out, report = _norm(raw)
    assert _arm_fired(report), "the strip did not run - the test proves nothing"
    assert _taken_by(report, "watermark_every_page") > 0, (
        "the watermark arm did not fire; some other arm or an earlier step "
        "removed these lines, so this test is not exercising the gate"
    )

    survivors = [ln for ln in out.split("\n") if ln.strip() == WATERMARK]
    assert len(survivors) == 1, (
        "exactly one copy must survive - 0 is the all-or-nothing deletion "
        "rule 0g forbids, %d means the arm did not fire" % len(survivors)
    )
    assert report.fallbacks.get("repeated_line_last_copy_kept", 0) >= 1, (
        "rule 0g's spared copy must be ANNOUNCED, not merely performed"
    )


# ---------------------------------------------------------------------------
# REAL NEGATIVES -- table content must survive intact, every copy
# ---------------------------------------------------------------------------

@requires_pdftotext
@pytest.mark.parametrize(
    "pdf,label",
    [
        # `Number of trained architectures` is THE label Grok used to reproduce
        # the defect that got this arm deleted. On the real paper it occurs 5
        # times on 3 of 18 pages -- page coverage 0.17. The reproduction that
        # condemned the arm was a SYNTHETIC document built to the reported
        # shape; the shape is reachable and this paper is not an instance of it.
        ("ieee_access_5.pdf", "Number of trained architectures"),
        ("ieee_access_5.pdf", "Performance metric"),
        ("ieee_access_6.pdf", "Feature Categories"),
        ("ieee_access_6.pdf", "Global Features"),
        ("ieee_access_6.pdf", "Neural Network Fusion"),
        ("ieee_access_10.pdf", "Unsigned integer"),
        ("ieee_access_10.pdf", "Character string"),
    ],
)
def test_real_table_content_keeps_every_copy(pdf, label):
    """Repeated table labels are NOT furniture, whatever their raw count.

    All seven sit at page coverage <= 0.22, far below the 0.90 gate. Measured
    2026-08-29: raw count == normalized count for every one.
    """
    if not pdf_available("docpluck", "ieee", pdf):
        pytest.skip("fixture not present: " + pdf_path("docpluck", "ieee", pdf))
    raw, _engine = extract_pdf_file(pdf_path("docpluck", "ieee", pdf))
    assert len(raw) > 10_000
    n_raw = raw.count(label)
    assert n_raw >= 5, "fixture no longer carries %r (%d copies)" % (label, n_raw)

    out, _report = _norm(raw)
    assert out.count(label) == n_raw, (
        "%r: %d copies in, %d out - the watermark arm has reached table "
        "content, which is the exact defect it was deleted for on 2026-08-28"
        % (label, n_raw, out.count(label))
    )


# ---------------------------------------------------------------------------
# SYNTHETIC -- the gate's arithmetic, including the residual it does NOT cover
# ---------------------------------------------------------------------------

def _paginated_doc(
    marker_pages: int, per_page: int, marker: str, pad_pages: int = 0
) -> str:
    """``marker`` ``per_page`` times on each of ``marker_pages`` pages, + padding.

    The blank lines around each marker are load-bearing: without them
    ``S8_line_break_joining`` merges the marker into the next line and the strip
    never sees a repeated line at all. That is the trap named in the module
    docstring.

    So is the TRAILING page break. pdftotext emits a form feed after the LAST
    page as well as between pages, so an n-page document carries n breaks and
    the gate's ``_total_pages`` counter reads n+1. A builder that only joins
    pages produces n-1 breaks and therefore a document TWO pages shorter than
    it looks -- which silently inflates every coverage ratio computed from it.
    Caught 2026-08-29 when
    ``test_a_short_document_fully_covered_is_below_the_effective_floor``
    measured 5/5 = 1.00 and stripped, where the real arithmetic is 5/6 = 0.833
    and keeps. A synthetic fixture can only confirm your model of the input;
    this one had the wrong model.
    """
    pages = []
    for p in range(marker_pages):
        page: list[str] = []
        for k in range(per_page):
            page += [marker, "", "%0.3f" % (p + k / 10.0), ""]
        page += [
            "Ordinary prose sentence number %d on page %d ends here." % (i, p)
            for i in range(20)
        ]
        pages.append("\n".join(page))
    pages += [
        "\n".join(
            "Unrelated closing prose sentence %d on page %d ends here." % (i, p)
            for i in range(24)
        )
        for p in range(pad_pages)
    ]
    return (PAGE_BREAK + "\n").join(pages) + "\n" + PAGE_BREAK + "\n"


def _overlay_doc(
    marker_pages: int, per_page: int, marker: str, pad_pages: int = 0
) -> str:
    """``marker`` as a PUBLISHER OVERLAY -- never followed by its own value.

    ⚠️ THIS BUILDER EXISTS BECAUSE ``_paginated_doc`` DOES NOT MODEL A
    WATERMARK, which nobody noticed until 2026-09-01. It emits
    ``marker / "" / "%0.3f" / ""`` -- a value directly under every copy --
    which is the TABLE ROW LABEL shape, the exact thing the arm must refuse.
    Two tests here used it to assert the arm FIRES, so the file's whole
    positive direction was pinned on the wrong shape; the arm's real gate
    (`_value_followed_fraction`) now refuses it and those tests went red.

    They were red for the right reason. ``_paginated_doc`` is KEPT and still
    used by the negative tests, where "a row label must survive" is precisely
    what it should model -- it is a good fixture that was being asked the wrong
    question.

    A real overlay is followed by whatever the page held: measured over three
    real papers, `Author Manuscript` is followed by a bare value on 0%, 2% and
    2% of its occurrences, against 78-100% for real table row labels.
    """
    pages = []
    for p in range(marker_pages):
        page: list[str] = []
        for k in range(per_page):
            page += [marker, "", "Body prose %d-%d runs on after it." % (p, k), ""]
        page += [
            "Ordinary prose sentence number %d on page %d ends here." % (i, p)
            for i in range(20)
        ]
        pages.append("\n".join(page))
    pages += [
        "\n".join(
            "Unrelated closing prose sentence %d on page %d ends here." % (i, p)
            for i in range(24)
        )
        for p in range(pad_pages)
    ]
    return (PAGE_BREAK + "\n").join(pages) + "\n" + PAGE_BREAK + "\n"


def test_a_repeated_label_below_the_coverage_floor_is_untouched():
    """THE CASE THE 2026-08-28 DELETION WAS ABOUT, and the one now fixed.

    A 15-120 char label printed 4x per page on 5 pages reaches ``count == 20``
    and satisfied the old bare-count arm, which took 19 of the 20 copies. Here
    those 5 pages sit in a 20-page document -- coverage 0.25 -- and the gate is
    idle.
    """
    label = "Number of trained architectures"
    text = _paginated_doc(5, 4, label, pad_pages=15)
    assert text.count(label) == 20

    out, report = _norm(text)
    assert out.count(label) == 20, (
        "a table label covering a quarter of the document was deduplicated - "
        "this is the 2026-08-28 defect, reopened"
    )
    assert _taken_by(report, "watermark_every_page") == 0


def test_a_row_label_at_full_page_coverage_is_now_REFUSED_not_merely_bounded():
    """⚠️ CONTRACT REVERSED 2026-09-01. This test used to assert the opposite.

    It was `test_the_residual_is_real_and_is_documented_not_denied`, and it
    pinned a table row label at >=90% page coverage being DEDUPLICATED to one
    copy -- 75 of 76 copies taken. The reasoning was that "at that coverage no
    POSITIONAL signal separates a table label from a watermark", which was true
    and beside the point: the separating signal is not positional. A row label
    is followed by the number it labels; an overlay is not.

    That residual left FOUR RED TESTS standing in
    `test_page_gate_never_deletes_the_last_copy.py`, which is how it was
    caught -- by a conductor sweep, not by this file.

    Measured (`_value_followed_fraction`): real watermarks 0.00 / 0.02 / 0.02,
    real row labels 0.78 / 1.00, this fixture 1.00. The arm now declines, and
    ALL 76 copies survive rather than 1.

    DO NOT "FIX" A FAILURE HERE BY LOOSENING THE GATE BACK. Losing 75 of 76
    copies of a row label orphans every number underneath it, which rule 0g
    names as the harm that outranks leaving furniture visible.
    """
    label = "Number of trained architectures"
    # 19 pages, all covered, plus the trailing break -> 19/20 = 0.95.
    text = _paginated_doc(19, 4, label)
    assert text.count(label) == 76

    out, report = _norm(text)
    assert _taken_by(report, "watermark_every_page") == 0, (
        "a line followed by its own value is a ROW LABEL and the watermark "
        "arm must not touch it at any page coverage"
    )
    assert out.count(label) == 76, (
        "every copy must survive - this fixture puts a value under each one"
    )


def test_a_genuine_overlay_at_the_same_coverage_still_fires():
    """TWO-SIDED. The test above must not pass because the arm is dead.

    Same page count, same copies per page, same coverage -- the ONLY
    difference is that this marker is followed by prose rather than by a
    value, which is what makes it an overlay rather than a row label. If this
    goes red, the arm has stopped working and the test above proves nothing.
    """
    marker = "Author Manuscript Draft Copy"
    text = _overlay_doc(19, 4, marker)
    assert text.count(marker) == 76

    out, report = _norm(text)
    assert _arm_fired(report), "fixture did not reach the strip"
    assert _taken_by(report, "watermark_every_page") == 75
    assert out.count(marker) == 1, (
        "rule 0g: exactly one copy survives - 0 would be a deletion"
    )


def test_a_short_document_fully_covered_is_below_the_effective_floor():
    """A line on EVERY page of a SHORT document is kept — an emergent page floor.

    ``_total_pages`` counts N+1 for an N-page document, because pdftotext emits
    a form feed after the last page as well as between pages. Measured
    2026-08-29 against pdfplumber: ieee_access_2 55 true / 56 counted,
    ieee_access_alt 23/24, ieee_access_5 17/18 — delta +1 on all three.

    So a fully-covering line scores ``n/(n+1)`` and clears 0.90 only from 9
    pages up: 5 -> 0.833, 6 -> 0.857, 8 -> 0.889, 9 -> 0.900, 55 -> 0.982.

    That removes the arm's stated residual — a table label spanning every page
    — for any document under 9 pages, which is the direction worth erring in: a
    missed watermark leaves furniture, visible and reversible for a consumer,
    while an extra deduplication is neither.

    This is pinned because an off-by-one that happens to be safe is one
    "cleanup" away from not being. If someone corrects the denominator to the
    true page count, this test goes red and they must add a deliberate page
    floor in its place rather than silently widening the arm onto short papers.
    """
    label = "Number of trained architectures"
    text = _paginated_doc(5, 4, label)  # 5 pages, all covered, no padding
    assert text.count(label) == 20, "fixture must clear the count >= 20 floor"

    out, report = _norm(text)
    assert out.count(label) == 20, (
        "a fully-covered 5-page document scores 5/6 = 0.833 and must stay "
        "below the 0.90 gate"
    )
    assert _taken_by(report, "watermark_every_page") == 0


def test_a_header_above_title_layout_is_refused_by_the_arm_entirely():
    """⚠️ CONTRACT TIGHTENED 2026-09-01, and the old FIXTURE was wrong too.

    This was `test_a_title_repeated_on_every_page_keeps_its_first_copy`. It
    asserted the arm FIRES on a header-above-title layout and deduplicates to
    one copy, treating "rule 0g spares the title block" as sufficient. Two
    things were wrong with it:

    1. It built the fixture with ``_paginated_doc``, which puts ``0.000``
       under every copy. A title is not followed by a number. The fixture
       modelled a row label and called it a title.
    2. Surviving by rule 0g is a LAST line of defence, not a licence to fire.
       The arm should never have been interested: Grok 4.6 named this exact
       shape on 2026-08-28 as a reason to delete the arm, and it was right
       that the arm reached it.

    The modal per-page count settles it. A header-above-title prints the
    string twice on page 1 and ONCE on every page after, so its typical page
    carries one copy -- a RUNNING HEADER, which is the `once_per_page` arm's
    business, and that arm correctly declines because `max_per_page` is 2.
    Measured: real watermarks are modal 4; this shape is modal 1 at both 19
    and 25 pages, where `count >= 20` used to catch it.

    So nothing is removed at all now, which is strictly safer than removing
    all-but-one. The paired assertions in
    `test_page_gate_never_deletes_the_last_copy.py` cover the same shape.
    """
    title = "Effect of Time-Restricted Eating on Weight Loss"
    # Twice on page 1, once on each page after -- modal per-page count of 1.
    pages = [
        "\n".join([title, "", title, "", "A Randomized Clinical Trial", "",
                   "Ann Author, PhD; Bo Writer, MSc"]
                  + ["Body sentence 0-%d of ordinary prose here." % j
                     for j in range(20)])
    ]
    for p in range(1, 25):
        pages.append("\n".join(
            [title, ""]
            + ["Body sentence %d-%d of ordinary prose here." % (p, j)
               for j in range(20)]))
    text = (PAGE_BREAK + "\n").join(pages) + "\n" + PAGE_BREAK + "\n"
    assert text.count(title) == 26, "the fixture must cross the count>=20 floor"

    out, report = _norm(text)
    assert _taken_by(report, "watermark_every_page") == 0, (
        "modal per-page count is 1, so this is a running header and the "
        "watermark arm must not reach it"
    )
    assert out.count(title) == 26, (
        "nothing may be removed - the once_per_page arm also declines, "
        "because page 1 carries two copies"
    )


@requires_pdftotext
def test_the_jama_title_survives_on_the_real_paper():
    """The defect that created rule 0g, on its own source document.

    Measured 2026-08-29 across three trees, separate interpreters:
    1.9.59 gives 13 -> 13 (the page map was wrong, so the arm never fired),
    the uncommitted 1.9.60 gave 13 -> 0 (the data loss), and 1.9.61 onward
    gives 13 -> 1. The defect was never in project history.
    """
    if not pdf_available("articlerepo", JAMA_KEY):
        pytest.skip("JAMA fixture not present in the article repository")
    raw, _engine = extract_pdf_file(pdf_path("articlerepo", JAMA_KEY))
    assert len(raw) > 10_000
    assert raw.count(JAMA_TITLE) >= 5, "fixture no longer carries the repeated title"

    out, _report = _norm(raw)
    assert out.count(JAMA_TITLE) == 1, (
        "%d copies in, %d out - 0 is the title deletion, more than 1 means "
        "the dedup did not fire" % (raw.count(JAMA_TITLE), out.count(JAMA_TITLE))
    )
