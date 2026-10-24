"""Guards on the 2026-10-23 running-head and furniture-number rules.

An independent review of normalization 1.9.75 / table extraction 2.4.25 found
inputs on which each rule took real content for page furniture. Every test here
is one of those inputs (plus a control that the furniture is still recognised).
"""

from docpluck.extract_layout import LayoutDoc, PageLayout, TextSpan
from docpluck.extract_structured import _axis_scale_cells, _folio_cells
from docpluck.normalize import _detect_running_heads, _f0_strip_running_and_footnotes


def _span(text, page, y):
    return TextSpan(text=text, page_index=page, x0=50, y0=y, x1=300, y1=y + 10,
                    font_size=10, font_name="Times", bold=False)


def _doc(tops):
    """One page per entry; each page's TOP span is the given text (None = no span)."""
    pages = []
    for i, top in enumerate(tops):
        spans = [_span("body text of the page", i, 400)]
        if top is not None:
            spans.append(_span(top, i, 760))
        pages.append(PageLayout(page_index=i, width=600, height=800, spans=tuple(spans)))
    return LayoutDoc(pages=tuple(pages), raw_text="", page_offsets=tuple(range(len(tops))))


# ---- running heads -------------------------------------------------------------

def test_numbered_headings_are_not_a_folio_fused_head():
    """'Study 1' x3 then 'Study 2' x3 fold to 'Study'; their numbers are not page numbers."""
    doc = _doc(["Title page", "Study 1", "Study 1", "Study 1", "Study 2", "Study 2", "Study 2"])
    assert _detect_running_heads(doc, position="top") == set()


def test_a_real_folio_fused_head_is_still_found():
    doc = _doc(["Title page"] + [f"Mortensen et al. {440 + i}" for i in range(1, 7)])
    assert _detect_running_heads(doc, position="top") == {"Mortensen et al."}


def test_parity_rule_needs_three_pages_after_the_first():
    """Pages 1, 3, 5 of 6 (not a majority): page 1 must not count toward the three."""
    doc = _doc(["Footer line", "x a", "Footer line", "x b", "Footer line", "x c"])
    assert "Footer line" not in _detect_running_heads(doc, position="top")
    doc7 = _doc(["Front", "Short Title", "Authors", "Short Title", "Authors", "Short Title", "Authors"])
    assert {"Short Title", "Authors"} <= _detect_running_heads(doc7, position="top")


def test_page_one_title_equal_to_the_head_is_kept():
    """A head found on later pages is not stripped from page 1, where it is the title."""
    tops = ["Short Title", "Short Title 2", "Short Title 3", "Short Title 4", "Short Title 5"]
    doc = _doc(tops)
    raw = "\f".join([
        "Short Title\nAbstract text of the article goes here.",
        "2\nShort Title\nBody text of page two.",
        "3\nShort Title\nBody text of page three.",
        "4\nShort Title\nBody text of page four.",
        "5\nShort Title\nBody text of page five.",
    ])
    doc = LayoutDoc(pages=doc.pages, raw_text=raw, page_offsets=doc.page_offsets)
    out = _f0_strip_running_and_footnotes(raw, doc)[0]
    pages = out.split("\f")
    assert "Short Title" in pages[0], "the title on page 1 was stripped"
    assert all("Short Title" not in p for p in pages[1:5]), "control: the running heads go"


# ---- furniture numbers ---------------------------------------------------------

def _cells(rows):
    return [{"text": t, "r": r, "c": c} for r, row in enumerate(rows) for c, t in enumerate(row)]


def test_a_count_cell_matching_an_edge_line_is_not_a_folio():
    """Two counts, both also among the page's last lines: data, not a page number."""
    cells = _cells([["participants who completed the survey", "12"],
                    ["participants who were excluded", "8"]])
    page = "Body text.\nparticipants who completed the survey\nparticipants who were excluded\n12\n8\n30\n"
    assert _folio_cells(cells, page) == set()


def test_a_superscript_digit_is_not_a_folio():
    cells = _cells([["Note", "²"]])
    assert _folio_cells(cells, "²\nBody\n") == set()


def test_a_folio_in_the_grids_first_row_is_still_found():
    cells = _cells([["442", "Mortensen et al."], ["response to disease salience", ""]])
    assert _folio_cells(cells, "442\t\t\n\nMortensen et al.\n\nresponse to disease salience\n") == {0}


def test_descending_values_beside_labels_are_not_an_axis():
    """Years (or a Likert key) count down a column, each with its label in the same row."""
    years = _cells([["2023", "first wave of the panel"], ["2022", "second wave"],
                    ["2021", "third wave"], ["2020", "fourth wave"]])
    assert _axis_scale_cells(years) == set()
    likert = _cells([["5", "strongly agree"], ["4", "agree"], ["3", "neutral"],
                     ["2", "disagree"], ["1", "strongly disagree"]])
    assert _axis_scale_cells(likert) == set()


def test_an_axis_whose_ticks_stand_alone_is_still_found():
    ticks = [{"text": t, "r": i, "c": 1} for i, t in enumerate(["4.3", "4.2", "4.1", "4.0", "3.9"])]
    title = [{"text": "Perceived Vulnerability", "r": 2, "c": 0}]
    assert _axis_scale_cells(ticks + title) == set(range(5))


def test_a_significance_note_on_alternate_pages_is_not_a_running_head():
    """A legend that carries statistics is never taken by the weaker rules (review 2026-10-24)."""
    note = "Note. * p < .05, ** p < .01"
    doc = _doc(["Front", note, "x", note, "y", note, "z", note])
    assert note not in _detect_running_heads(doc, position="top")
    control = _doc(["Front", "Short Title", "x", "Short Title", "y", "Short Title", "z", "Short Title"])
    assert "Short Title" in _detect_running_heads(control, position="top")
