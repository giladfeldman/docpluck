"""A caption whose label stands ALONE on its line still gets its table's text.

Why this file exists (2026-09-25). Two upright tables came back from
``extract_pdf_structured`` with ``cells=[]``, ``raw_text=""`` and
``content_status="not_captured:no_text_after_caption"``:

* ``10.5465/annals.2016.0011`` (corpus ``aom/annals_2.pdf``) Table 2, page 10 --
  a numbered list of 28 journals (rasterized and read).
* ``10.15626/mp.2022.3108`` (corpus ``apa/chandrashekar_2023_mp.pdf``) Table 10,
  page 10 -- a findings grid over original / direct / conceptual replication
  (rasterized and read).

pdftotext holds every cell of both, straight after the caption. Neither Camelot nor
the whitespace path captured them (their regions miss the table), so the body walk
was the last channel -- and it returned nothing. Both captions print the label on a
line of its own (``TABLE 2``, ``Table 10``) with the title on the next line. The
caption-tail walk took the bare label as "the caption's first line", so the body
began AT the title; pdftotext joins each title into one line of 80+ characters,
which ``_line_is_body_prose`` reads as prose, and the walk stopped on its first
line.

The fix is keyed on the emitted line holding the label and nothing else, never on
the paper. Every assertion below is paired with its opposite.
"""

import pytest

from docpluck.testing import require_corpus_pdf

_ANNALS = "aom/annals_2.pdf"  # 10.5465/annals.2016.0011, Table 2 on p10
_CHANDRA = "apa/chandrashekar_2023_mp.pdf"  # 10.15626/mp.2022.3108, Table 10 on p10


def _walk(rel: str, label: str):
    """(caption_text, body, reason) for one table caption, as the pipeline sees it."""
    from docpluck import extract_structured as ES
    from docpluck.extract import extract_pdf
    from docpluck.tables.captions import find_caption_matches

    raw = ES._join_split_captions(extract_pdf(require_corpus_pdf(rel).read_bytes())[0])
    caps = sorted(find_caption_matches(raw, ES._page_offsets(raw)), key=lambda c: c.char_start)
    mine = [c for c in caps if c.label == label]
    cap = ([c for c in mine if not ES.caption_anchor_is_in_text_reference(raw, c)] or mine)[0]
    i = caps.index(cap)
    nb = caps[i + 1].char_start if i + 1 < len(caps) else None
    body, reason = ES._extract_table_body_text_and_reason(raw, cap, nb)
    return ES._extract_caption_text(raw, cap, nb), body, reason, cap


def test_annals_table2_journal_list_is_captured():
    caption, body, reason, cap = _walk(_ANNALS, "Table 2")
    assert cap.line_text.strip() == "TABLE 2"  # the shape under test
    assert reason is None, reason
    lines = body.split("\n")
    # First and last rows as printed, and the wrapped row in the middle.
    for row in ("Academy of Management Journal", "Strategic Management Journal",
                "Methodology: European Journal of Research Methods for"):
        assert row in lines, row
    # The row numbers 1..28 are the table's first column.
    assert [str(n) for n in range(1, 29)] == [ln for ln in lines if ln.isdigit()]
    # Opposite: the caption's own title is in the caption, not duplicated as a row.
    assert "List of Journals Included" in caption
    assert not any(ln.startswith("List of Journals Included") for ln in lines)


def test_chandrashekar_table10_findings_are_captured():
    caption, body, reason, cap = _walk(_CHANDRA, "Table 10")
    assert cap.line_text.strip() == "Table 10"
    assert reason is None, reason
    lines = body.split("\n")
    for cell in ("Predictor", "Default condition:", "Framing condition:",
                 "Original study’s findings", "Conceptual replication findings",
                 "Inconsistent - Opposite direction"):
        assert cell in lines, cell
    assert "Summary of the findings of Johnson et al. (2002)" in caption
    assert not any(ln.startswith("Summary of the findings") for ln in lines)


def test_a_caption_carrying_its_title_is_not_treated_as_label_alone():
    """Opposite shape: a caption line that carries text after its label. The
    first line IS the caption's first line, and the walk is unchanged
    (xiao_2021 Table 6 -- self-terminated caption; its first header row and
    first data row are the ones a mis-step would drop)."""
    _caption, body, _reason, cap = _walk("apa/xiao_2021_crsp.pdf", "Table 6")
    assert cap.line_text.strip() != "Table 6"
    assert "Choice of the target option" in body
    assert "216/337" in body


@pytest.mark.parametrize(
    "line, alone",
    [
        ("TABLE 2", True),
        ("Table 10", True),
        ("Table 10.", True),
        ("Table 3:", True),
        ("Table 1 |", True),
        ("Table 2. Body Weight, Glycemic Control", False),
        ("Table 6 Study 2 descriptive statistics.", False),
        ("TABLE 2 List of Journals", False),
    ],
)
def test_label_alone_predicate(line, alone):
    from docpluck.extract_structured import _LABEL_ALONE_RE

    assert bool(_LABEL_ALONE_RE.fullmatch(line.strip())) is alone


@pytest.fixture(scope="module")
def structured_annals():
    pytest.importorskip("camelot", reason="camelot not installed (pip install docpluck[all])")
    from docpluck.extract_structured import extract_pdf_structured

    return extract_pdf_structured(require_corpus_pdf(_ANNALS).read_bytes())


def test_annals_table2_through_the_shipped_pipeline(structured_annals):
    """The composition that ships: the record carries the rows, and says so."""
    t2 = [t for t in structured_annals["tables"] if t.get("label") == "Table 2"]
    assert len(t2) == 1
    t2 = t2[0]
    assert t2["content_status"] == "raw_text", t2["content_status"]
    assert "Strategic Management Journal" in t2["raw_text"]
    # Opposite: no table in the paper still reports an empty capture.
    assert not [
        t.get("label") for t in structured_annals["tables"]
        if str(t.get("content_status", "")).startswith("not_captured:")
    ]


# ── The two regressions the first version of the fix caused (census, 2026-09-25) ──


def test_a_lone_label_followed_by_a_cell_keeps_the_cell_in_the_body():
    """10.1177/23780231251314667 (``asa/socius_4.pdf``) p37: an author manuscript
    prints ``Table 2.`` and then the cells -- its title comes AFTER the table in text
    order. Stepping over the line after the label moved the first value ``.6***``
    out of the body. The step is taken only when that line carries words."""
    _caption, body, _reason, cap = _walk("asa/socius_4.pdf", "Table 2")
    assert cap.line_text.strip() == "Table 2."
    assert body.split("\n")[0] == ".6***"


def test_the_label_line_still_spends_the_wrap_budget():
    """10.5465/annals.2016.0011 p8, Table 1: ``TABLE 1`` / a two-line title / the
    header ``Step`` / ``1`` / blank line. A first version gave the label line a free
    pass, the walk reached the blank line, and ``Step`` and ``1`` fell into the gap
    between caption and body -- in neither."""
    caption, body, _reason, _cap = _walk(_ANNALS, "Table 1")
    lines = body.split("\n")
    assert "Step" in lines and "1" in lines
    assert "Detailed Description of Steps Used" in caption


def test_a_wrapped_title_tail_is_not_the_body_s_first_line():
    """10.15626/mp.2022.3108 p10, Table 8: the title wraps to ``regression analysis``.
    Left as the body's first line, its lowercase opening made the degenerate-prose
    guard suppress the whole table -- estimates, CIs and p-values -- as prose."""
    caption, body, reason, _cap = _walk(_CHANDRA, "Table 8")
    assert reason is None, reason
    assert body.split("\n")[0] == "Predictor"
    assert "0.72 (0.14)" in body and "2.05 [1.56, 2.71]" in body
    assert "regression analysis" in caption


@pytest.mark.parametrize(
    "line, continues",
    [
        ("regression analysis", True),
        ("of UMD Dataset used in [36] for multi-class task", True),
        ("ns", False),  # a lone lowercase cell
        ("df 1", False),
        ("Predictor", False),
        ("p < .05", False),
        (".6***", False),
    ],
)
def test_title_continuation_predicate(line, continues):
    from docpluck.extract_structured import _is_title_continuation

    assert _is_title_continuation(line) is continues


# ── Constructed inputs: they pin what the CODE does at two bounds raised in review
# (Sonnet, /consult tier 2, 2026-09-25). Neither shape was observed in the 102-paper
# manifest; they are not evidence that the shape occurs.


def _body_start_of(text: str) -> str:
    from docpluck import extract_structured as ES
    from docpluck.tables.captions import find_caption_matches

    cap = next(c for c in find_caption_matches(text, [0]) if c.kind == "table")
    return text[ES._caption_tail_body_start(text, cap, None):]


def test_the_label_step_never_crosses_a_page_break():
    body = _body_start_of("Intro text.\nTable 2\n\x0cJournal of Things Vol 12\nAuthor Name Here\nx\n")
    assert body.startswith("\x0cJournal of Things")  # unchanged from before the fix


def test_only_one_title_continuation_line_is_skipped():
    body = _body_start_of(
        "Intro.\nTable 3\nDemographic characteristics of the sample across all four\n"
        "study sites\nage group\nyoung\nold\n"
    )
    assert body.startswith("age group\n")


# ── Nothing falls between caption and body ───────────────────────────────────


@pytest.mark.parametrize(
    "rel, label, first_lines",
    [
        # 10.5465/amle.2017.0488 p9: the column header "Rank" (11 tables in this
        # paper alone) was in neither the caption nor the body.
        ("aom/amle_1.pdf", "Table 1", ["Rank"]),
        # 10.1001/jamanetworkopen.2023.16111 p6: the spanning header and first cells.
        ("ama/jama_open_11.pdf", "Table 1", ["Participants, No. (%)", "Whole cohort", "(N = 4260)"]),
        # 10.5465/annals.2022.0049 p4: the header and the first row number.
        ("aom/annals_3.pdf", "Table 2", ["Step", "1"]),
    ],
)
def test_header_cells_between_caption_and_walk_reach_the_body(rel, label, first_lines):
    caption, body, _reason, _cap = _walk(rel, label)
    lines = body.split("\n")
    assert lines[: len(first_lines)] == first_lines, lines[:5]
    # Opposite: they were not in the caption either -- that is why they were lost.
    for cell in first_lines:
        assert f" {cell} " not in f" {caption} "
