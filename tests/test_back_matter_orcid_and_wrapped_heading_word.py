"""Back matter keeps ORCID iDs; a canonical heading word that ends a wrapped
sentence is not a section heading.

10.1177/01461672251327169, rasterised 2026-10-27:

* p18 "ORCID iDs" prints each author's name followed by an ORCID icon and
  ``https://orcid.org/0000-...``. The render listed the names only: a
  furniture pattern deleted every standalone ORCID URL line.
* p5 prints "The calculated effect sizes are summarized in the / Supplemental
  Materials." -- one sentence wrapped over two lines. The sectioner opened a
  ``supplementary`` section at "Supplemental Materials." that swallowed the
  whole Method (22k characters), leaving ``methods`` 326 characters long.
"""
from __future__ import annotations

import pytest

from docpluck.sections.annotators import text as text_annotator


def _heads(text):
    return [h.text for h in text_annotator.annotate_text(text)]


def test_wrapped_object_is_not_a_heading():
    text = ("We conducted a power analysis.\nThe calculated effect sizes are summarized in the\n"
            "Supplemental Materials.\nThere were several issues with this.\n")
    assert "Supplemental Materials" not in _heads(text), _heads(text)


def test_real_heading_after_terminated_line_is_kept():
    text = ("The last sentence of the discussion ends here.\nSupplemental Material\n"
            "Supplemental material is available online with this article.\n")
    assert any(h.startswith("Supplemental Material") for h in _heads(text)), _heads(text)


def test_helper_reads_only_the_directly_previous_line():
    f = text_annotator._previous_line_ends_mid_sentence
    t = "summarized in the\nSupplemental Materials."
    assert f(t, t.index("Supplemental"))
    t2 = "summarized in the\n\nSupplemental Materials."
    assert not f(t2, t2.index("Supplemental"))
    t3 = "See the results.\nMethods"
    assert not f(t3, t3.index("Methods"))
    t4 = "(Table 2)\nMethods"
    assert not f(t4, t4.index("Methods"))


def _pdf():
    from docpluck.testing.corpus import custody_path
    p = custody_path("fulltext", "10.1177__01461672251327169.pdf")
    if not p.is_file():
        pytest.skip("10.1177/01461672251327169 not held")
    return p.read_bytes()


def test_real_orcid_ids_and_method_span():
    from docpluck.render import render_pdf_to_markdown
    from docpluck.sections import extract_sections
    b = _pdf()
    md = render_pdf_to_markdown(b)
    md = md[0] if isinstance(md, tuple) else md
    tail = md[md.index("## ORCID iDs"):]
    tail = tail[: tail.index("## Supplemental Material")]
    assert "https://orcid.org/0000-0002-9549-7544" in tail, tail
    assert "https://orcid.org/0000-0003-2812-6599" in tail, tail
    secs = extract_sections(b).sections
    labels = [s.label for s in secs]
    assert "supplementary" not in labels[: labels.index("results")], labels
    meth = next(s for s in secs if s.label == "methods")
    assert meth.char_end - meth.char_start > 10000, (meth.char_start, meth.char_end)


def test_sentence_closing_heading_word_after_open_line_is_not_a_heading():
    # 10.1177/0956797615612694 p10, Note 2: "... are available in the online" /
    # "Supplemental Material." -- the render dropped the words as a heading.
    text = ("A description of this condition and analyses of the data are available in the online\n"
            "Supplemental Material.\n3. An additional study tested self-interest.\n")
    assert "Supplemental Material" not in _heads(text), _heads(text)


def test_real_note_keeps_its_supplemental_material_words():
    from docpluck.testing.corpus import custody_path
    from docpluck.render import render_pdf_to_markdown
    p = custody_path("fulltext", "10.1177__0956797615612694.pdf")
    if not p.is_file():
        pytest.skip("10.1177/0956797615612694 not held")
    md = render_pdf_to_markdown(p.read_bytes())
    md = md[0] if isinstance(md, tuple) else md
    flat = " ".join(md.split())
    assert "available in the online Supplemental Material." in flat
