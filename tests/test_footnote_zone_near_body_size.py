"""Page footnotes printed only a little smaller than the body text.

F0 found the body band from every span within 1 pt of the body size, so a 9 pt
footnote under 10 pt body text counted as body: the band reached the page
bottom and no footnote on that page could ever qualify. Measured on a humanities
paper with 149 numbered page footnotes in 9 pt (read on the page raster,
2026-10-24): F0 moved 4 of them. ``_footnote_zone_spans`` finds the zone below
the lowest span at true body size and starts it at the first marker-led line,
so a small block quote above the notes, a caption, a table note and a small
abstract under a short title block all stay in the body.

The layouts below are synthetic (PDF coordinates, y grows upward).
"""

from __future__ import annotations

from docpluck.extract_layout import LayoutDoc, PageLayout, TextSpan
from docpluck.normalize import _f0_strip_running_and_footnotes, _footnote_zone_spans

_BODY = [f"Body sentence number {i} keeps the argument going here." for i in range(30)]


def _page(index: int, bottom_lines: list[tuple[str, float]]):
    spans = []
    y = 740.0
    for line in _BODY:
        spans.append(TextSpan(line, index, 72, y, 520, y + 10, 10.0, "Times", False))
        y -= 18.0
    # The lowest body line sits at y=218. Bottom lines start 40+ pt below it.
    # A size under 7.5 is a superscript marker on the NEXT line's baseline.
    y = 160.0
    for text, size, *x in bottom_lines:
        x0 = x[0] if x else 72
        if size == 0:  # a blank line: the gap that sets footnotes apart
            y -= 12.0
            continue
        if size < 7.5:
            spans.append(TextSpan(text, index, x0 - 6, y + 3, x0, y + 9, size, "Times", False))
            continue
        spans.append(TextSpan(text, index, x0, y, 520, y + size, size, "Times", False))
        y -= 12.0
    return PageLayout(page_index=index, width=612, height=792, spans=tuple(spans))


def _on_page(bottom_lines, index):
    """Page 2 carries different notes: identical bottom lines on every page
    would be a running foot, not footnotes."""
    if index == 0:
        return bottom_lines
    return [(t.replace("the", "a"), *rest) for t, *rest in bottom_lines]


def _doc(bottom_lines):
    pages = tuple(_page(i, _on_page(bottom_lines, i)) for i in range(2))
    texts = [
        "\n".join(_BODY) + "\n" + "\n".join(t for t, *_ in _on_page(bottom_lines, i)) + "\n"
        for i in range(2)
    ]
    raw = texts[0] + "\f" + texts[1]
    return LayoutDoc(pages=pages, raw_text=raw, page_offsets=(0, len(texts[0]) + 1)), raw


def _moved(bottom_lines):
    layout, raw = _doc(bottom_lines)
    _text, _spans, texts = _f0_strip_running_and_footnotes(raw, layout)
    return {t.strip() for t in texts}


def test_numbered_nine_point_footnotes_are_moved():
    lines = [
        ("12 The archive holds the letters from the later period only.", 9.0),
        ("13 A second edition corrected the dates in the first chapter.", 9.0),
    ]
    moved = _moved(lines)
    assert lines[0][0] in moved and lines[1][0] in moved, moved


def test_a_superscript_marker_span_corroborates_the_zone():
    lines = [
        ("7", 6.0),
        ("The archive holds the letters from the later period only.", 9.0),
    ]
    assert lines[1][0] in _moved(lines)


def test_a_small_caption_at_the_page_bottom_stays_in_the_body():
    lines = [
        ("Figure 2. Mean ratings by condition across the three sessions.", 9.0),
        ("1 Error bars show standard errors of the mean in each panel.", 9.0),
    ]
    assert _moved(lines) == set()


def test_unmarked_small_text_at_the_page_bottom_stays_in_the_body():
    lines = [
        ("The archive holds the letters from the later period only.", 9.0),
        ("A second edition corrected the dates in the first chapter.", 9.0),
    ]
    assert _moved(lines) == set()


def test_a_table_region_is_never_a_footnote_zone():
    lines = [
        ("12 The archive holds the letters from the later period only.", 9.0),
    ]
    layout, raw = _doc(lines)
    regions = [{"page": p, "bbox": (60, 100, 560, 200)} for p in (1, 2)]
    _t, _s, texts = _f0_strip_running_and_footnotes(raw, layout, regions)
    assert texts == []


def test_a_block_quote_above_the_footnotes_stays_in_the_body():
    quote = [
        ("was set in the smaller size and indented from the left margin", 9.0, 90),
        ("so that the quotation reads apart from the running argument.", 9.0, 90),
    ]
    notes = [("", 0), ("4", 6.0), ("The archive holds the letters from the later period only.", 9.0)]
    moved = _moved(quote + notes)
    assert notes[2][0] in moved, moved
    assert not any(q[0] in moved for q in quote), moved


def test_a_small_abstract_under_a_short_title_block_stays_in_the_body():
    """A first page with a few lines at body size (title block) and the
    abstract set small below it, the affiliations carrying superscripts."""
    spans = [
        TextSpan(f"Title block line {i}", 0, 72, 720 - 14 * i, 520, 730 - 14 * i, 10.0, "T", False)
        for i in range(3)
    ]
    spans.append(TextSpan("1", 0, 66, 603, 72, 609, 5.0, "T", False))
    y = 600.0
    for i in range(30):
        spans.append(TextSpan(f"Abstract line {i} of the summary text.", 0, 72, y, 520, y + 8, 8.0, "T", False))
        y -= 12.0
    page = PageLayout(page_index=0, width=612, height=792, spans=tuple(spans))
    assert _footnote_zone_spans(page, 10.0, lambda *a: False) == set()


def test_a_table_note_block_stays_in_the_body():
    """A table note set under the table: "Note. ..." then starred notes."""
    lines = [
        ("Note. Values are means across both sessions; brackets give 95% CIs.", 9.0),
        ("* indicates the p-value of a binomial test against one half.", 9.0),
        ("** indicates the p-value of a test of association.", 9.0),
    ]
    assert _moved(lines) == set()


def test_numbered_table_rows_above_a_caption_set_below_the_table_stay():
    """Hypothesis rows "1 ...", "2 ..." spaced like footnotes, with the table's
    caption printed under the table."""
    lines = [
        ("1 Ratings fall as the described capacity of the animal rises.", 9.0),
        ("", 0),
        ("2 Describing the meat use lowers the rated capacity of the animal.", 9.0),
        ("", 0),
        ("Table 1 Summary of the hypotheses tested in both studies.", 9.0),
    ]
    assert _moved(lines) == set()


def test_real_paper_first_page_notes_move_to_the_footnote_appendix():
    """An Elsevier first page sets its notes (corresponding author, the
    equal-contribution note, DOI, dates) in 7 pt under 9 pt body text, which
    the 1 pt body band counted as body. They now move; nothing else does."""
    from pathlib import Path

    from docpluck import NormalizationLevel, extract_pdf, extract_pdf_layout, normalize_text
    from docpluck.testing.corpus import require_corpus_pdf

    pdf = Path(require_corpus_pdf("apa/ziano_2021_joep.pdf")).read_bytes()
    raw, _ = extract_pdf(pdf)
    text, report = normalize_text(raw, NormalizationLevel.standard, layout=extract_pdf_layout(pdf))
    body = text.split("\n\f\f\n", 1)[0]
    notes = [t.strip() for t in report.footnote_texts]
    assert "* Corresponding author." in notes
    assert "Contributed equally, joint first authors." in notes
    assert "* Corresponding author." not in body
    assert "Contributed equally, joint first authors." not in body
