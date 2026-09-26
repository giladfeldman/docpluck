"""A table printed ROTATED is kept under its caption and labelled "not captured".

Why this file exists (2026-09-25). `10.1038/s41467-024-45528-0` (corpus name
`nature/nat_comms_4.pdf`) prints Table 4 -- "Effect sizes in ANCOVA models compared
to standard care, with 90% CIs", a full grid of effect sizes, CIs and p-values over
five treatment arms -- sideways on page 6 (rasterized and read). Every glyph of it is
drawn with the text matrix ``(0, s, -s, 0)``.

pdftotext cannot linearise it after its caption: it emits the table's cells BEFORE
the caption, so the caption-anchored walk found the next upright line instead -- the
page's running header, ``Article``. `extract_pdf_structured` shipped:

    id=t4  label="Table 4"  kind="isolated"  cells=[]  raw_text="Article"

a Table 4 that looked present, whose content was page furniture, with no event naming
either the rotation or the empty capture.

Owner directive (retain and label, never drop): keep the record, because its caption
is real, and mark its CONTENT as not captured with a recorded reason. The signal is
typographic -- the caption's own glyphs are drawn with a rotated text matrix
(`detect.caption_orientation`) -- and never the string ``Article``.

Every assertion below is paired with its opposite.

SINCE THE ROTATED READER (owner decision 2026-09-25, option B;
``docpluck/tables/rotated.py``, tested in ``test_rotated_table_extraction_real_pdf``)
Table 4 is READ, not labelled: it is a 14x5 grid. The label path below is now the
fallback for a rotated caption whose own frame cannot be read, so each test of it
first disables the reader (``_without_rotated_reader``) and a paired test shows
what the reader delivers instead.
"""

import pytest

from docpluck.testing import require_corpus_pdf

pytest.importorskip("camelot", reason="camelot not installed (pip install docpluck[all])")

_ROTATED = "nature/nat_comms_4.pdf"  # 10.1038/s41467-024-45528-0, Table 4 on p6


@pytest.fixture(scope="module")
def pdf_bytes() -> bytes:
    # require_, not corpus_pdf: a paper this gate claims to test and cannot read is
    # a FAILURE, never a skip.
    return require_corpus_pdf(_ROTATED).read_bytes()


@pytest.fixture(scope="module")
def layout(pdf_bytes):
    from docpluck.extract_layout import extract_pdf_layout

    return extract_pdf_layout(pdf_bytes)


@pytest.fixture(scope="module")
def structured(pdf_bytes):
    from docpluck.extract_structured import extract_pdf_structured

    return extract_pdf_structured(pdf_bytes)


@pytest.fixture(scope="module")
def structured_without_reader(pdf_bytes):
    """The pipeline with the rotated reader disabled: the fallback this file pins."""
    import docpluck.extract_structured as ES

    mp = pytest.MonkeyPatch()
    try:
        mp.setattr(ES, "_read_rotated_table", lambda *a, **k: None)
        return ES.extract_pdf_structured(pdf_bytes)
    finally:
        mp.undo()


def _tables_by_label(result) -> dict:
    return {t.get("label"): t for t in result["tables"] if t.get("label")}


def test_caption_orientation_reads_the_glyph_matrix(pdf_bytes, layout):
    """Rotated for Table 4 (p6); upright for Tables 1-3 of the same paper."""
    from docpluck import extract_structured as ES
    from docpluck.extract import extract_pdf
    from docpluck.tables.captions import find_caption_matches
    from docpluck.tables.detect import caption_orientation

    raw = ES._join_split_captions(extract_pdf(pdf_bytes)[0])
    caps = find_caption_matches(raw, ES._page_offsets(raw))
    # A label can match more than once (a body reference that wraps to a line start
    # also matches the caption pattern; its line is found in neither orientation,
    # which is correct), so judge the SET of verdicts per label.
    verdicts: dict = {}
    for c in caps:
        verdicts.setdefault((c.kind, c.label), set()).add(
            caption_orientation(layout.pages[c.page - 1], c)
        )
    assert "rotated" in verdicts[("table", "Table 4")], verdicts
    # Tables only: `_join_split_captions` rewrites `Fig.` to `Figure` in the shadow
    # string, so a Nature `Fig. 1 |` caption's line cannot be found on the page by
    # its (rewritten) text and reads None in either orientation. Figures never reach
    # this code path; the rotated verdict is only ever asked of table captions.
    others = {
        k: v for k, v in verdicts.items() if k[0] == "table" and k != ("table", "Table 4")
    }
    assert set(others) == {("table", f"Table {n}") for n in (1, 2, 3)}, verdicts
    for key, found in others.items():
        assert "rotated" not in found, (key, found)
        assert "upright" in found, (key, found)
    # No caption of any kind on this paper is called rotated except Table 4.
    assert [k for k, v in verdicts.items() if "rotated" in v] == [("table", "Table 4")]


def test_rotated_table_is_read_when_its_frame_can_be_read(structured):
    """The reader's side of the pair below: Table 4 is a grid, nothing is
    labelled not-captured, and the running header is not its content."""
    t4 = _tables_by_label(structured)["Table 4"]
    assert t4["content_status"] == "cells" and t4["cells"]
    assert t4["cell_geometry"] == "whitespace_rotated"
    assert "Article" not in " ".join(c["text"] for c in t4["cells"])
    assert not structured["fallback_details"].get("table_content_not_captured")


def test_rotated_table_is_kept_and_labelled_not_captured(structured_without_reader):
    structured = structured_without_reader
    tables = _tables_by_label(structured)
    t4 = tables.get("Table 4")
    assert t4 is not None, f"Table 4 must be KEPT: {sorted(tables)}"
    # The caption is the rotated caption line and nothing else. Before, the walk ran
    # on into the upright running header and the table's rotated footnote:
    # "... with 90% CIs Article (continuous); and study site (Lusaka/Harare). ..."
    assert t4["caption"] == (
        "Table 4 | Effect sizes in ANCOVA modelsa compared to standard care, with 90% CIs"
    ), repr(t4["caption"])
    assert t4["caption_status"] == "matched"
    assert t4["cells"] == []
    # The defect: the page's running header shipped as the table's content.
    assert t4["raw_text"] == "", repr(t4["raw_text"])
    assert t4["content_status"] == "not_captured:rotated_table"
    # ...and it is COUNTED, so a consumer can see it without opening the record.
    assert structured["fallbacks"].get("table_content_not_captured", 0) >= 1
    assert "Table 4:rotated_table" in structured["fallback_details"]["table_content_not_captured"]


def test_upright_tables_on_the_same_paper_keep_their_cells(structured_without_reader):
    """Two-sided: the rotated verdict must not reach the paper's upright tables."""
    structured = structured_without_reader
    tables = _tables_by_label(structured)
    for label in ("Table 1", "Table 2", "Table 3"):
        t = tables.get(label)
        assert t is not None, f"{label} missing: {sorted(tables)}"
        assert t["cells"], f"{label} lost its cells"
        assert t["content_status"] == "cells", (label, t["content_status"])
    details = structured["fallback_details"].get("table_content_not_captured", {})
    assert set(details) == {"Table 4:rotated_table"}, details


def test_every_table_states_what_its_content_is(structured):
    for t in structured["tables"]:
        status = t.get("content_status")
        if t.get("cells"):
            assert status == "cells", t["id"]
        elif (t.get("raw_text") or "").strip():
            assert status == "raw_text", t["id"]
        else:
            assert status and status.startswith("not_captured:"), (t["id"], status)


def test_the_gate_detects_the_regression_it_exists_for(pdf_bytes, monkeypatch):
    """Blind the orientation signal and the original defect must come back: the
    running header as Table 4's content, and the caption running on into it."""
    import docpluck.extract_structured as ES

    monkeypatch.setattr(ES, "caption_orientation", lambda *a, **k: None)
    monkeypatch.setattr(ES, "_read_rotated_table", lambda *a, **k: None)
    t4 = _tables_by_label(ES.extract_pdf_structured(pdf_bytes))["Table 4"]
    assert t4["raw_text"] == "Article", repr(t4["raw_text"])
    assert t4["content_status"] == "raw_text"
    assert "Article" in t4["caption"], repr(t4["caption"])


def test_a_wrapped_rotated_caption_keeps_its_second_line():
    """Two-sided for the caption bound: the bound must stop at the first UPRIGHT line,
    not at the caption's first line. `10.1098/rsos.140072` p5 prints Table 1 sideways
    with a caption that wraps onto a second rotated line ("... (25th-75th
    percentile)).)"); both lines must survive."""
    from docpluck import extract_structured as ES
    from docpluck.extract import extract_pdf
    from docpluck.extract_layout import extract_pdf_layout
    from docpluck.tables.captions import find_caption_matches
    from docpluck.tables.detect import caption_orientation, rotated_caption_end

    data = require_corpus_pdf("harvard/ar_royal_society_rsos_140072.pdf").read_bytes()
    raw = ES._join_split_captions(extract_pdf(data)[0])
    cap = next(
        c for c in find_caption_matches(raw, ES._page_offsets(raw))
        if c.kind == "table" and c.label == "Table 1" and c.page == 5
    )
    page = extract_pdf_layout(data).pages[4]
    assert caption_orientation(page, cap) == "rotated"
    caption = ES._extract_caption_text(raw, cap, rotated_caption_end(page, raw, cap))
    assert caption.startswith("Table 1. Sample sizes, masses and social behaviour")
    assert caption.endswith("(i.e. the 50th percentile (25th–75th percentile)).)"), caption


def test_with_camelot_off_a_rotated_tables_values_are_kept(monkeypatch):
    """The data-preservation half, and the reason the first version of this fix
    was wrong. With Camelot off (not installed, or failing under memory pressure)
    EVERY rotated table reaches the caption-only path, and for most of them the
    text after the caption IS the table. Discarding it outright deleted those
    values; only lines positively drawn upright may go.

    10.1177/01461672251327169 (corpus `apa/ip_feldman_2025_pspb.pdf`) p12 prints
    Table 7 sideways; its CIs must survive."""
    from docpluck.extract_structured import extract_pdf_structured

    monkeypatch.setenv("DOCPLUCK_DISABLE_CAMELOT", "1")
    data = require_corpus_pdf("apa/ip_feldman_2025_pspb.pdf").read_bytes()
    t7 = _tables_by_label(extract_pdf_structured(data))["Table 7"]
    assert t7["kind"] == "isolated", "the Camelot-off arm must reach the caption-only path"
    assert "0.76 [0.67, 0.86]" in t7["raw_text"], repr(t7["raw_text"][:300])
    assert t7["content_status"] == "raw_text", t7["content_status"]
    # Since the rotated reader: the text is the table's own, in reading order --
    # the first row's label precedes its values.
    raw = t7["raw_text"]
    assert raw.index("Had fight/argument") < raw.index("42.63") < raw.index("0.76 [0.67, 0.86]")


def test_with_camelot_off_upright_furniture_alone_is_not_content(monkeypatch):
    """The other side: 10.1177/23780231251327540 (corpus `asa/socius_5.pdf`) Table 2
    (p24, printed sideways), whose caption-only walk with Camelot off found only
    the upright running header ``Roth et al.`` and
    ``Page 24``. Both are drawn upright, so both go, nothing is left, and the table
    is kept as not captured -- and its caption no longer carries them."""
    import docpluck.extract_structured as ES
    from docpluck.extract_structured import extract_pdf_structured

    monkeypatch.setenv("DOCPLUCK_DISABLE_CAMELOT", "1")
    data = require_corpus_pdf("asa/socius_5.pdf").read_bytes()
    # The reader's side: Table 2's summary statistics, in reading order, and
    # neither upright line.
    read = _tables_by_label(extract_pdf_structured(data))["Table 2"]
    assert read["content_status"] == "raw_text"
    assert "284.32\n115.08\n46.50\n1,226.00" in read["raw_text"], read["raw_text"][:300]
    for upright in ("Roth et al.", "Page 24"):
        assert upright not in read["raw_text"] and upright not in read["caption"]
    # The fallback's side, with the reader disabled:
    monkeypatch.setattr(ES, "_read_rotated_table", lambda *a, **k: None)
    result = extract_pdf_structured(data)
    t2 = _tables_by_label(result)["Table 2"]
    assert t2["raw_text"] == "", repr(t2["raw_text"])
    assert t2["content_status"] == "not_captured:rotated_table"
    assert "Roth et al." not in t2["caption"], repr(t2["caption"])
    assert "Page 24" not in t2["caption"], repr(t2["caption"])
    assert "Table 2:2" in result["fallback_details"]["rotated_table_upright_lines_dropped"]


def test_a_sideways_margin_banner_is_not_a_rotated_tables_content(monkeypatch):
    """Found by the second-model review: furniture drawn SIDEWAYS cannot be proven
    upright. 10.1098/rsos.140072 p5 prints Table 1 sideways and its journal banner
    ("rsos.royalsocietypublishing.org R. Soc. open sci. 2: 140072") and a dotted
    rule run up the margin in the same orientation, on every page. That was all the
    caption-only walk found, so it shipped as the table's `raw_text`.

    Camelot is switched off to reach the caption-only path: since the 2.4.145
    table-region fix, Camelot captures this table as a real grid, which this
    change leaves untouched (asserted below as the other side)."""
    from docpluck.extract_structured import extract_pdf_structured

    data = require_corpus_pdf("harvard/ar_royal_society_rsos_140072.pdf").read_bytes()
    import docpluck.extract_structured as ES

    with monkeypatch.context() as m:
        m.setenv("DOCPLUCK_DISABLE_CAMELOT", "1")
        # The label fallback, which is what this test pins: the rotated reader
        # (tests/test_rotated_table_extraction_real_pdf.py) grids this table.
        m.setattr(ES, "_read_rotated_table", lambda *a, **k: None)
        t1 = _tables_by_label(extract_pdf_structured(data))["Table 1"]
    assert t1["raw_text"] == "", repr(t1["raw_text"])
    assert t1["content_status"] == "not_captured:rotated_table"

    grid = _tables_by_label(extract_pdf_structured(data))["Table 1"]
    assert grid["cells"] and grid["content_status"] == "cells"
    assert "breeder male 9 10.0 (9.6–11.2)" in grid["raw_text"]


def test_with_camelot_off_a_watermark_goes_and_the_values_stay(monkeypatch):
    """Two-sided on one table: 10.1177/23780231221103044 (corpus `asa/socius_2.pdf`)
    Table 1 (p37) is a PMC author manuscript whose margin carries
    `Author Manuscript` four times, sideways, on every page. With Camelot off the
    watermark must leave the table's text and its values must not."""
    from docpluck.extract_structured import extract_pdf_structured

    import docpluck.extract_structured as ES

    monkeypatch.setenv("DOCPLUCK_DISABLE_CAMELOT", "1")
    data = require_corpus_pdf("asa/socius_2.pdf").read_bytes()
    # The reader's side: a grid, with the values and without the watermark.
    read = _tables_by_label(extract_pdf_structured(data))["Table 1"]
    assert read["content_status"] == "cells"
    read_text = " ".join(c["text"] for c in read["cells"]) + " " + read["caption"]
    assert "72.8" in read_text and "Author Manuscript" not in read_text
    # The fallback's side, with the reader disabled:
    monkeypatch.setattr(ES, "_read_rotated_table", lambda *a, **k: None)
    t1 = _tables_by_label(extract_pdf_structured(data))["Table 1"]
    assert "Author Manuscript" not in t1["raw_text"], repr(t1["raw_text"][:200])
    lines = t1["raw_text"].split("\n")
    assert "72.8" in lines and "Black (%)" in lines, repr(t1["raw_text"][:300])
    assert t1["content_status"] == "raw_text"


def test_a_rotated_captions_own_title_is_not_its_content():
    """10.1177/23780231251314667 (corpus `asa/socius_4.pdf`) p39: after the sideways
    caption `Table 3.` the walk re-reads the caption's own title line, which the
    caption already carries. A repeat is dropped only when long enough that a cell
    value cannot coincide with caption text."""
    from docpluck.extract_structured import _caption_dedupe_key, _line_repeats_caption

    caption = _caption_dedupe_key(
        "Table 3. American Time Use Survey Housework and Childcare Activity Codes."
    )
    assert _line_repeats_caption(
        "American Time Use Survey Housework and Childcare Activity Codes.", caption
    )
    # Two-sided: a short fragment, and a value that happens to sit in a caption,
    # are never treated as repeats.
    assert not _line_repeats_caption("Housework", caption)
    # A long run from the MIDDLE of the caption (a column header restating the
    # caption's wording) is table content, not a repeat of the title.
    assert not _line_repeats_caption("Time Use Survey Housework", caption)
    assert not _line_repeats_caption(
        "2,469", _caption_dedupe_key("Summary Statistics (n = 2,469).")
    )


def test_rendered_markdown_shows_the_read_table(pdf_bytes):
    """The reader's side: Table 4 renders as a grid with its values, and no
    table on the paper says "not captured"."""
    from docpluck.render import render_pdf_to_markdown

    md = render_pdf_to_markdown(pdf_bytes)
    at = md.find("### Table 4")
    assert at != -1
    block = md[at:at + 6000]
    assert "<table" in block and "-5.9 (-10.3, -1.4) P = 0.03" in block
    assert "Table content not captured (" not in md


def test_rendered_markdown_keeps_the_heading_and_says_why(pdf_bytes, monkeypatch):
    import docpluck.extract_structured as ES
    from docpluck.render import render_pdf_to_markdown

    monkeypatch.setattr(ES, "_read_rotated_table", lambda *a, **k: None)
    md = render_pdf_to_markdown(pdf_bytes)
    at = md.find("### Table 4")
    assert at != -1, "Table 4 heading must be kept"
    block = md[at:at + 1200]
    assert "Effect sizes in ANCOVA models" in block
    assert "Table content not captured (rotated_table)" in block
    # Two-sided: the running header is not presented as the table's content, and
    # the upright tables are NOT labelled.
    assert "```unstructured-table\nArticle" not in md
    assert md.count("Table content not captured (") == 1, md.count("Table content not captured (")
