"""Side-by-side captions are found when the PDF draws its spaces as glyphs.

10.1186/s12916-023-03146-5 p6 prints Table 1 (left column) and Table 2 (right column)
side by side on one caption line, checked on the page 2026-10-14. The PDF carries SPACE
glyphs, so the caption row reads "Table 1 Participant ...Table 2 Adherence ...".
`_label_x_midpoint` looked for "table1" in a row string that still held its spaces,
found neither label, so the two captions were never assigned to their columns, the
narrow per-column grids were not marked side-by-side, and both captions were delivered
the SAME merged 23x7 grid of both tables.
"""
from __future__ import annotations

from types import SimpleNamespace

from docpluck.extract_structured import _label_x_midpoint
from docpluck.testing import require_corpus_pdf


def _chars(text, x0, top=89.0, w=5.0):
    out = []
    for i, ch in enumerate(text):
        out.append({"text": ch, "x0": x0 + i * w, "x1": x0 + (i + 1) * w,
                    "top": top, "bottom": top + 9})
    return out


def test_label_found_with_space_glyphs(monkeypatch):
    import docpluck.tables.detect as D
    page = SimpleNamespace(chars=_chars("Table 1 Participant", 57.0) + _chars("Table 2 Adherence", 305.0))
    monkeypatch.setattr(D, "_bbox_of_caption_line", lambda p, c: (57.0, 89.0, 468.0, 98.0))
    one = SimpleNamespace(label="Table 1")
    two = SimpleNamespace(label="Table 2")
    x1, x2 = _label_x_midpoint(page, one), _label_x_midpoint(page, two)
    assert x1 is not None and x2 is not None, (x1, x2)
    assert x1 < 300 < x2, (x1, x2)


def test_real_tables_are_not_the_same_grid():
    from docpluck.extract_structured import extract_pdf_structured
    pdf = require_corpus_pdf("vancouver/bmc_med_4.pdf").read_bytes()
    ts = {t.get("label"): t for t in extract_pdf_structured(pdf)["tables"] if t.get("page") == 6}
    t1, t2 = ts["Table 1"], ts["Table 2"]
    txt1 = " ".join(c["text"] for c in t1.get("cells") or [])
    txt2 = " ".join(c["text"] for c in t2.get("cells") or [])
    assert "Age in years" in txt1 and "Age in years" not in txt2, (txt1[:200], txt2[:200])
    assert "Any side effects" in txt2 and "Any side effects" not in txt1, (txt1[:200], txt2[:200])


def test_in_text_reference_is_not_a_caption_label(monkeypatch):
    """10.1016/j.jesp.2021.104154 p6: the caption-line locator lands on "summarized in
    Table 2." in the right column; the full-width Table 2 caption sits at the left margin.
    A label with a word right before it is a reference, so no side-by-side layout is
    inferred from it (it made Table 2's means/SD grid reach no table at all)."""
    import docpluck.tables.detect as D
    page = SimpleNamespace(chars=_chars("Table 1 Study 1", 37.0) + _chars("summarized in Table 2.", 300.0))
    monkeypatch.setattr(D, "_bbox_of_caption_line", lambda p, c: (37.0, 89.0, 500.0, 98.0))
    assert _label_x_midpoint(page, SimpleNamespace(label="Table 2")) is None
    assert _label_x_midpoint(page, SimpleNamespace(label="Table 1")) is not None


def test_reference_opening_a_line_is_not_the_bare_caption(monkeypatch):
    """The chen p6 shape exactly: the reference OPENS a right-column line ("Table 2.
    Violin plots ..."), so no glyph precedes it; the text channel's caption line is the
    bare label "Table 2". A label followed in its own block by words the caption line
    does not have is not the caption."""
    import docpluck.tables.detect as D
    page = SimpleNamespace(chars=_chars("DV stimuli Same", 37.0) + _chars("Table 2. Violin plots", 320.0))
    monkeypatch.setattr(D, "_bbox_of_caption_line", lambda p, c: (37.0, 89.0, 500.0, 98.0))
    assert _label_x_midpoint(page, SimpleNamespace(label="Table 2", line_text="Table 2")) is None
    lone = SimpleNamespace(chars=_chars("Table 2", 37.0))
    assert _label_x_midpoint(lone, SimpleNamespace(label="Table 2", line_text="Table 2")) is not None


def test_chen_table2_values_stay_in_a_structured_table():
    """10.1016/j.jesp.2021.104154 p6: Table 2's means and SDs (After / Outcome 1 = 45.51)
    must reach a structured table."""
    from docpluck.extract_structured import extract_pdf_structured
    from docpluck.testing.corpus import custody_path
    p = custody_path("fulltext", "10.1016__j.jesp.2021.104154.pdf")
    ts = extract_pdf_structured(p.read_bytes())["tables"]
    assert any("45.51" in " ".join(c["text"] for c in t.get("cells") or []) for t in ts)
