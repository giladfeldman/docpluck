"""Numbered appendix labels: one section per appendix, none per figure panel.

Some journals print appendices as labelled blocks: "Appendix 1" (heading),
"Appendix 2. <title>" and "Appendix 3. <title>" (table-style labels),
"Appendix 5" (heading) followed by figure panels "Appendix 5A. <caption>" and
"Appendix 5B. <caption>". Shape checked on a real page raster (2026-10-24);
the text below is invented.

Before this change the sectioner admitted "Appendix 2." (its previous paragraph
happened to end with a full stop), rejected "Appendix 3." (its previous line was
a table cell), and split "Appendix 5A." off Appendix 5 as a new appendix.
"""

from docpluck.sections import SectionLabel, extract_sections

_TEXT = (
    "Title\n\nAbstract\n\nWe did a study.\n\n"
    "Introduction\n\nWater matters to people.\n\n"
    "Conclusions\n\nWater still matters.\n\n"
    "Appendix 1\n"
    "Recruitment details and screening\n"
    "Participants were recruited online. Responses were screened.\n\n"
    "Appendix 2. Exclusions and descriptive statistics by condition.\n"
    "Exclusions\n"
    "Total recruited\n"
    "Scale incomplete\n"
    "1% (6)\n\n"
    "Appendix 3. Manipulation prompts used in each condition.\n"
    "Condition\n"
    "Prompts for participant responses.\n\n"
    "Appendix 5\n\n"
    "The figures below show the scale scores.\n\n"
    "Appendix 5A. Distribution of scale scores across conditions.\n\n"
    "Appendix 5B. Mean scale scores across conditions.\n\n"
)


def _appendices(text):
    doc = extract_sections(text=text, source_format="pdf")
    return [s for s in doc.sections if s.canonical_label is SectionLabel.appendix]


def test_each_numbered_appendix_opens_one_section():
    starts = [_TEXT[a.char_start:].split("\n", 1)[0][:12] for a in _appendices(_TEXT)]
    assert starts == ["Appendix 1", "Appendix 2. ", "Appendix 3. ", "Appendix 5"], starts


def test_figure_panels_stay_inside_their_appendix():
    last = _appendices(_TEXT)[-1]
    assert "Appendix 5A. Distribution" in last.text
    assert "Appendix 5B. Mean" in last.text


def test_a_panel_label_with_no_parent_heading_still_opens_an_appendix():
    """Without an earlier "Appendix 5" heading, "Appendix 5A." is the only
    marker the appendix has, so it is kept."""
    text = _TEXT.replace("Appendix 5\n\nThe figures below show the scale scores.\n\n", "")
    starts = [text[a.char_start:a.char_start + 13] for a in _appendices(text)]
    assert starts[-1] == "Appendix 5A. ", starts


def test_appendix_reference_inside_a_sentence_is_not_a_heading():
    text = _TEXT.replace(
        "Water matters to people.",
        "Participants were excluded (see\nAppendix 2). The exclusion rate was within range.",
    )
    first = _appendices(text)[0]
    assert text[first.char_start:first.char_start + 10] == "Appendix 1"
