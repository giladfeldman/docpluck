"""`extract_sections(docx|html).normalized_text` is normalized, and headings follow it.

Until 2026-10-08 only the PDF branch called `normalize_text`, so on DOCX and
HTML the field named `normalized_text` held the raw markup reconstruction --
a U+2212 minus reached consumers as U+2212, which a parser reading `-` misses.
"""
from __future__ import annotations

from docpluck.sections import extract_sections
from docpluck.sections._offsets import line_offset_mapper

_HTML = (
    "<html><body>"
    "<h2>Results</h2>"
    "<p>The effect was negative, t(28) = −2.10, p = .045.</p>"
    "<h2>Discussion</h2>"
    "<p>We discuss it.</p>"
    "</body></html>"
).encode("utf-8")


def test_html_normalized_text_is_normalized():
    doc = extract_sections(_HTML, source_format="html")
    assert "−" not in doc.normalized_text
    assert "t(28) = -2.10" in doc.normalized_text


def test_headings_still_anchor_their_sections_after_normalization():
    doc = extract_sections(_HTML, source_format="html")
    text = doc.normalized_text
    by_heading = {s.heading_text: s for s in doc.sections if getattr(s, "heading_text", None)}
    assert {"Results", "Discussion"} <= set(by_heading), [s.heading_text for s in doc.sections]
    results = by_heading["Results"]
    assert "-2.10" in text[results.char_start:results.char_end]
    discussion = by_heading["Discussion"]
    assert "We discuss it." in text[discussion.char_start:discussion.char_end]


def test_offset_mapper_keeps_columns_and_follows_deleted_lines():
    src = "alpha\nDELETE ME\nbeta − gamma\nend"
    dst = "alpha\nbeta - gamma\nend"
    m = line_offset_mapper(src, dst)
    assert m(0) == 0                                      # 'alpha'
    assert dst[m(src.index("beta")):].startswith("beta")  # reshaped line, same column
    assert dst[m(src.index("end")):] == "end"
    assert m(src.index("DELETE")) == dst.index("beta")    # deleted -> start of what follows
    assert m(len(src)) == len(dst)
    offsets = [m(i) for i in range(len(src) + 1)]
    assert offsets == sorted(offsets)


def test_identity_when_nothing_changes():
    s = "one\ntwo\nthree"
    m = line_offset_mapper(s, s)
    assert [m(i) for i in range(len(s) + 1)] == list(range(len(s) + 1))


def test_a_hint_ending_at_its_line_end_follows_a_lengthened_line():
    """Consult 2026-10-09 (Sonnet) finding 2: a ligature expansion lengthens the
    heading line; an offset at the END of a source line must map to the end of
    the normalized line, not to the same column."""
    src = "Modiﬁcation of Procedure\nBody."
    dst = "Modification of Procedure\nBody."
    m = line_offset_mapper(src, dst)
    end = src.index("\n")
    assert dst[m(0):m(end)] == "Modification of Procedure"
