"""Column crops cut only through glyph-free space — real-PDF gate.

pdftotext keeps a glyph in a ``-x/-y/-W/-H`` crop when the glyph's advance box
merely TOUCHES the crop, so a vertical cut through a glyph puts it in both
columns. The column corrector used to cut at the detector's midline wherever it
fell, and over a 601-paper sample (500 drawn from the article repository with
seed 20260923, plus the 101-paper test corpus) 27 of the 38 pages the v2.4.143
corrector rewrote carried a duplicated or split character. 2.4.145 added a
character-multiset guard that REFUSES such a page, which is correct but loses
the reorder: ten non-reference pages fell back to pdftotext's own order.

The cut is now placed by ``_column_cut_layout``: an integer x no body glyph
reaches, with the rows that cross every such x (a "Downloaded from" line, a page
number, a running header) read full width above or below the columns. Two
further causes were found on the same pages and are gated here too:

* pdfplumber reports geometry in PDF user space, pdftotext measures crops from
  the MediaBox corner. The PDF held under 10.1177/0956797611420730 has
  ``/MediaBox [9 9 594 792]`` (pdfplumber ``bbox`` ``(9, -9, 594, 774)``), so
  every cut on it landed 9pt from where it was computed.
  (That file is MIS-FILED: the index names a Psychological Science article, the
  bytes are Cashen et al., Journal of Clinical Oncology 2010, on decitabine.
  The geometry is what matters here. `_pdf` fails loudly if the custodian
  ever replaces the file, so the fixture gets re-pointed rather than silently
  testing another page.)
* a glyph the layout channel does not report at all (collabra.95 p17: a
  "\\t\\x08" with 720pt of advance) was reached by a full-height margin crop and
  by the bottom band both.

Every page below is checked against the RAW pdftotext page: not a character may
be gained or lost, only the order may change.
"""

from __future__ import annotations

import re
import subprocess
import tempfile
from collections import Counter
from pathlib import Path

import pytest

from docpluck.extract import extract_pdf
from docpluck.extract_columns import (
    _accept_reorder,
    _char_multiset,
    _column_cut_layout,
    _crop_space_words,
    _detect_2col_midline,
    _pdftotext_crop,
    extract_page_text_columns,
)
from docpluck.extract_layout import extract_pdf_layout
from docpluck.testing.corpus import repository_root
from docpluck.version import resolve_pdftotext_executable


JCO = "10.1177/0956797611420730"  # see the module docstring: mis-filed


def _pdf(doi: str) -> Path:
    root = repository_root()
    if root is None:
        pytest.skip("article repository not on this machine")
    p = root / "fulltext" / (doi.replace("/", "__") + ".pdf")
    if not p.is_file():
        pytest.skip(f"{doi} not in custody")
    if doi == JCO:
        assert "Decitabine" in _raw_pages(p)[0], (
            f"the file held under {JCO} is no longer the mis-filed J Clin Oncol "
            "decitabine article these tests were measured on; re-point the fixture")
    return p


def _raw_pages(pdf: Path) -> list[str]:
    return subprocess.run(
        [resolve_pdftotext_executable(), "-enc", "UTF-8", str(pdf), "-"],
        capture_output=True, encoding="utf-8", errors="replace", check=True,
    ).stdout.split("\f")


def _corrected(method: str) -> set[int]:
    m = re.search(r"column_corrected:([\d,]+)", method)
    return {int(x) for x in m.group(1).split(",")} if m else set()


# The pages the 2.4.145 character guard refused, now reordered exactly.
REENABLED = [
    ("10.1098/rsos.180914", 1),
    ("10.1098/rsos.192015", 1),
    ("10.1098/rsos.202251", 1),
    ("10.1098/rsos.210050", 1),
    ("10.1098/rsos.230196", 1),
    (JCO, 2),
    ("10.3389/fpsyg.2023.1045974", 1),
    ("10.1525/collabra.95", 17),
]


@pytest.mark.parametrize("doi, page", REENABLED)
def test_reenabled_page_is_corrected_and_character_identical(doi, page):
    pdf = _pdf(doi)
    text, method = extract_pdf(pdf.read_bytes())
    assert page in _corrected(method), f"{doi} p{page} not corrected: {method}"
    out = text.split("\f")[page - 1]
    raw = _raw_pages(pdf)[page - 1]
    assert _char_multiset(out) == _char_multiset(raw), (
        f"{doi} p{page}: +{dict(_char_multiset(out) - _char_multiset(raw))} "
        f"-{dict(_char_multiset(raw) - _char_multiset(out))}")
    assert out.split() != raw.split(), "a no-op is not a reorder"


def test_a_page_already_in_reading_order_is_left_alone():
    """rsos.191114 p1 was one of the ten refused pages, and the glyph-free read
    shows why the old corrector touched it at all: token for token it IS the
    raw pdftotext page. The only thing the v2.4.143 rewrite changed there was a
    duplicated "a" and "." on the cut. The splice declines a no-op, so the page
    is correctly left as pdftotext read it."""
    pdf = _pdf("10.1098/rsos.191114")
    b = pdf.read_bytes()
    raw = _raw_pages(pdf)[0]
    out = extract_page_text_columns(extract_pdf_layout(b, pages=[0]), 0, pdf_bytes=b)
    assert out.split() == raw.split()
    assert not _accept_reorder(out, raw, False)
    _text, method = extract_pdf(b)
    assert 1 not in _corrected(method)


# ── two-sided: the old cut really did duplicate glyphs on these pages


def _old_cut_read(pdf: Path, page: int) -> str:
    """The pre-fix read: two full-height crops meeting at int(midline), in the
    coordinates pdfplumber reported (no MediaBox shift)."""
    b = pdf.read_bytes()
    lp = extract_pdf_layout(b, pages=[page - 1]).pages[page - 1]
    mid = int(_detect_2col_midline(list(lp.words), lp.width))
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(b)
    try:
        left = _pdftotext_crop(tmp.name, page - 1, 0, 0, mid, lp.height)
        right = _pdftotext_crop(tmp.name, page - 1, mid, 0, lp.width, lp.height)
    finally:
        Path(tmp.name).unlink()
    return left + "\n\n" + right


@pytest.mark.parametrize("doi, page, dup", [
    ("10.1098/rsos.180914", 1, {".": 2, ",": 1}),
    (JCO, 2, {"f": 1, "F": 1}),
    ("10.3389/fpsyg.2023.1045974", 1, {"s": 1}),
])
def test_the_detector_midline_cut_duplicates_glyphs(doi, page, dup):
    """Without this the tests above could pass on a page that never had the
    defect. Counts measured 2026-09-25."""
    pdf = _pdf(doi)
    old = _old_cut_read(pdf, page)
    raw = _raw_pages(pdf)[page - 1]
    assert dict(_char_multiset(old) - _char_multiset(raw)) == dup
    assert not _accept_reorder(old, raw, False)


# ── the coordinate system


def test_crop_space_matches_pdftotext_bbox_on_a_shifted_mediabox():
    """10.1177/0956797611420730 p2 has /MediaBox [9 9 594 792]. After the shift,
    a word's x0/x1 must be where ``pdftotext -bbox`` puts it; before it they are
    9pt apart, which is the two-sided control."""
    pdf = _pdf(JCO)
    lp = extract_pdf_layout(pdf.read_bytes(), pages=[1]).pages[1]
    assert lp.origin == (9.0, -9.0)
    bbox = subprocess.run(
        [resolve_pdftotext_executable(), "-f", "2", "-l", "2", "-bbox", str(pdf), "-"],
        capture_output=True, encoding="utf-8", errors="replace", check=True,
    ).stdout
    ptt = {(t, round(float(a), 1), round(float(c), 1)) for a, c, t in re.findall(
        r'<word xMin="([\d.]+)" yMin="[\d.]+" xMax="([\d.]+)" yMax="[\d.]+">([^<]+)</word>',
        bbox)}

    def matches(words):
        return sum((w["text"], round(w["x0"], 1), round(w["x1"], 1)) in ptt
                   for w in words)

    assert matches(_crop_space_words(lp)) >= 100
    assert matches(lp.words) == 0


# ── the layout never places a cut on a body glyph


@pytest.mark.parametrize("doi, page", REENABLED[:7])
def test_cut_x_is_clear_of_every_body_word(doi, page):
    pdf = _pdf(doi)
    lp = extract_pdf_layout(pdf.read_bytes(), pages=[page - 1]).pages[page - 1]
    words = _crop_space_words(lp)
    ox = lp.origin[0]
    hint = _detect_2col_midline(list(lp.words), lp.width) - ox
    shape = _column_cut_layout(words, lp.width, hint_x=hint)
    assert shape is not None
    x, cut_top, cut_bot, _margin = shape
    bottom = lp.height if cut_bot < 0 else cut_bot
    body = [w for w in words if w.get("upright", True)
            and w["top"] >= cut_top and w["bottom"] <= bottom]
    assert body
    assert not [w["text"] for w in body if int(w["x0"]) <= x <= int(w["x1"])]


# ── what is still refused, and why


def test_arxiv_2403_07183_p11_stays_refused_because_raw_pdftotext_drops_a_printed_hyphen():
    """The page prints "Nat-" at the foot of the left column and "ural Language
    Watermarking" at the head of the right one (rasterized 2026-09-25). Full-
    page pdftotext de-hyphenates "Nat-" into the page number below it and emits
    "Nat11"; the column read keeps the printed hyphen. The column read is the
    faithful one, but it is one "-" away from raw, so the character guard
    refuses it and the page keeps pdftotext's order. Pinned so that a change
    to either side of that is noticed."""
    pdf = _pdf("10.48550/arxiv.2403.07183")
    b = pdf.read_bytes()
    raw = _raw_pages(pdf)[10]
    assert "Nat11" in raw.split()
    layout = extract_pdf_layout(b, pages=[10])
    out = extract_page_text_columns(layout, 10, pdf_bytes=b, allow_gutter_fallback=True)
    assert "Nat-" in out.split() and "11" in out.split()
    assert _char_multiset(out) - _char_multiset(raw) == Counter({"-": 1})
    assert not _char_multiset(raw) - _char_multiset(out)
    _text, method = extract_pdf(b)
    assert 11 not in _corrected(method)


# ── what the reading-order review of every changed page found (2026-09-25)


def test_a_boxed_note_under_the_columns_stays_in_one_piece():
    """collabra.95 p17 closes on a boxed "Editor Decision Letter". Its heading
    fits inside the left column, its text line crosses the gutter; read as
    column text, the heading came out after the whole right column, parted from
    the line it heads. It now travels with the full-width band."""
    pdf = _pdf("10.1525/collabra.95")
    text, _m = extract_pdf(pdf.read_bytes())
    page = text.split("\f")[16]
    i = page.index("Editor Decision Letter")
    assert page[i:].split("\n", 2)[1].startswith("The author(s) of this paper chose")
    assert page.index("Yaniv, I.") < i  # the right column is read before it


@pytest.mark.parametrize("doi, page, why", [
    ("10.1177/0146167218760798", 1,
     "an eScholarship cover sheet: one column, one ragged line past the midline"),
    ("10.1109/access.2024.3421281", 17,
     "the histogram midline falls between an author photo and its biography"),
])
def test_a_cut_with_next_to_nothing_on_one_side_is_refused(doi, page, why):
    """Both pages were rewritten by an intermediate version of this change and
    both rewrites were wrong in the reading-order review (see ``why``). The smaller
    side of the cut held 0.7% (IEEE) of the body's words; every genuine two-
    column page among the 150 rewritten held at least 21.5%."""
    pdf = _pdf(doi)
    _text, method = extract_pdf(pdf.read_bytes())
    assert page not in _corrected(method), method


def test_a_refused_cut_does_not_fall_back_to_a_word_join():
    """The word-join read splits at the raw midline with none of the cut
    layout's checks; after the layout refuses a page it must not be tried."""
    pdf = _pdf("10.1177/0146167218760798")
    b = pdf.read_bytes()
    out = extract_page_text_columns(extract_pdf_layout(b, pages=[0]), 0, pdf_bytes=b)
    assert out == ""
