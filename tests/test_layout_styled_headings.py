"""A plain line printed in the paper's own heading style becomes a heading
(``render._promote_layout_styled_headings``).

10.1177/01461672251327169 p8 prints "Data Analysis Strategy" in the font and
size of "Measures" and "Participants"; it was left as a body line. The style is
learned from headings the render already found. The 2026-10-30 corpus diff
showed style alone also promoted "49.35", "(2002)", "Figure 5", a lowercase
phrase, and the first half of a two-line heading; those are refused by the
line's text shape.
"""

from __future__ import annotations

from types import SimpleNamespace

from docpluck.render import _promote_layout_styled_headings

BODY = ("Body-Regular", 10.0)
HEAD = ("Head-Bold", 12.0)


def _line(text, style, top, x0=50.0):
    font, size = style
    chars, x = [], x0
    for ch in text:
        if ch != " ":
            chars.append({"text": ch, "fontname": "ABCDEF+" + font, "size": size,
                          "top": top, "x0": x, "x1": x + size * 0.5, "upright": True})
        x += size * 0.5
    return chars


def _layout(heading_lines):
    chars, top = [], 50.0
    for text in ("Measures", "Participants", "Procedure"):
        chars += _line(text, HEAD, top)
        top += 14
        for k in range(4):
            chars += _line(f"body text line number {k} of this paragraph here", BODY, top)
            top += 12
    for text in heading_lines:
        chars += _line(text, HEAD, top)
        top += 14
        chars += _line("body text under the candidate line goes on here", BODY, top)
        top += 12
    return SimpleNamespace(pages=[SimpleNamespace(chars=chars)])


def _md(candidates):
    parts = ["## Method", "", "### Measures", "", "Some body.", "", "### Participants", "",
             "Some body.", "", "### Procedure", "", "Some body.", ""]
    for c in candidates:
        parts += [c, "Body text under the candidate line goes on here.", ""]
    return "\n".join(parts)


def test_a_line_in_the_heading_style_is_promoted():
    out = _promote_layout_styled_headings(_md(["Data Analysis Strategy"]),
                                          _layout(["Data Analysis Strategy"]))
    assert "### Data Analysis Strategy" in out.split("\n")


def test_a_number_or_label_in_the_heading_style_is_not():
    cands = ["49.35", "(2002)", "Figure 5"]
    out = _promote_layout_styled_headings(_md(cands), _layout(cands))
    for c in cands:
        assert f"### {c}" not in out


def test_a_lowercase_phrase_is_not():
    out = _promote_layout_styled_headings(_md(["reject decision"]), _layout(["reject decision"]))
    assert "### reject decision" not in out


def test_a_two_line_heading_is_one_heading():
    layout = _layout(["The Origins of the Field and"])
    # the wrapped second line, in the same style, directly under the first
    first = [c for c in layout.pages[0].chars if c["fontname"].endswith("Head-Bold")]
    top = max(c["top"] for c in first)
    layout.pages[0].chars += _line("Its Later Development", HEAD, top + 13)
    md = _md([]) + "\n".join(["The Origins of the Field and", "Its Later Development",
                              "Body text under the heading goes on here.", ""])
    out = _promote_layout_styled_headings(md, layout)
    assert "### The Origins of the Field and Its Later Development" in out
    assert "### The Origins of the Field and\n" not in out


def test_a_line_whose_sentence_carries_on_is_not():
    md = _md([]) + "\n".join(["Bei dieser Studie handelt", "es sich um eine Umfrage.", ""])
    out = _promote_layout_styled_headings(md, _layout(["Bei dieser Studie handelt"]))
    assert "### Bei dieser Studie handelt" not in out


def test_a_wrapped_heading_beside_another_column_is_still_one_heading():
    """Two-column page: the line printed under the heading's first line is in
    the same column; the next line in reading order is the OTHER column's
    (10.1525/collabra.92953 "Understanding the Survey of Professional" /
    "Forecasters" came out as two headings)."""
    layout = _layout([])
    top = max(c["top"] for c in layout.pages[0].chars) + 20
    layout.pages[0].chars += _line("Understanding the Survey of", HEAD, top)
    layout.pages[0].chars += _line("other column text in the heading font", HEAD, top, x0=320.0)
    layout.pages[0].chars += _line("Professional Forecasters", HEAD, top + 13)
    md = _md([]) + "\n".join(["Understanding the Survey of", "Professional Forecasters",
                              "Body text under the heading goes on here.", ""])
    out = _promote_layout_styled_headings(md, layout)
    assert "### Understanding the Survey of Professional Forecasters" in out


def test_an_unclosed_parenthesis_is_not_a_heading():
    cand = "Means and (standard deviations) of expression (frequency"
    out = _promote_layout_styled_headings(_md([cand]), _layout([cand]))
    assert f"### {cand}" not in out


def test_a_centred_two_line_heading_is_one_heading():
    """10.1177/0146167214563672: "Liberals May Be More Individualistic" /
    "Analytically" -- the second line is centred, not flush with the first."""
    layout = _layout(["Liberals May Be More Individualistic"])
    first = [c for c in layout.pages[0].chars if c["fontname"].endswith("Head-Bold")]
    top = max(c["top"] for c in first)
    # centred under the first line: (50 + 266) / 2 == (122 + 194) / 2
    layout.pages[0].chars += _line("Analytically", HEAD, top + 13, x0=122.0)
    md = _md([]) + "\n".join(["Liberals May Be More Individualistic", "Analytically",
                              "Body text under the heading goes on here.", ""])
    out = _promote_layout_styled_headings(md, layout)
    assert "### Liberals May Be More Individualistic Analytically" in out


def test_two_headings_in_a_row_stay_two():
    """10.1177/01461672251327169 p8: "Data Analysis Strategy" (12 pt) over
    "Replication Measures" (the next level down) came out as one heading; the
    smaller line is the next level down (second canary audit, 2026-10-31)."""
    sub = (HEAD[0], 11.0)
    layout = _layout(["Data Analysis Strategy"])
    top = max(c["top"] for c in layout.pages[0].chars) + 20
    layout.pages[0].chars += _line("Replication Measures", sub, top)
    layout.pages[0].chars += _line("body text under the candidate line goes on here", BODY, top + 12)
    md = _md([]) + "\n".join(["Data Analysis Strategy", "Replication Measures",
                              "Body text under the heading goes on here.", ""])
    out = _promote_layout_styled_headings(md, layout).split("\n")
    assert "### Data Analysis Strategy" in out
    assert "#### Replication Measures" in out


def test_a_run_in_heading_is_not_promoted():
    """10.1177/19485506211056761: "Naturally Occurring Incidental Mood and the
    Negative Relationship" / "Between Risks and Benefits. We conducted ..." --
    the heading runs in to its paragraph, whose first line opens in the heading
    style (Sonnet page check, 2026-10-31)."""
    cand = "Naturally Occurring Incidental Mood and the Negative Relationship"
    layout = _layout([])
    top = max(c["top"] for c in layout.pages[0].chars) + 20
    layout.pages[0].chars += _line(cand, HEAD, top)
    run = _line("Between Risks and Benefits.", HEAD, top + 13)
    layout.pages[0].chars += run + _line("We conducted an analysis", BODY, top + 13,
                                         x0=run[-1]["x1"] + 4.0)
    md = _md([]) + "\n".join([cand, "Between Risks and Benefits. We conducted an analysis.", ""])
    out = _promote_layout_styled_headings(md, layout)
    assert f"### {cand}" not in out


def test_the_second_line_of_a_promoted_heading_joins_it():
    """10.1177/0146167210386968: "Predicting the Nature of Prime-to-Behavior"
    was already a heading; its second line "Effects in Interpersonal Contexts"
    became a heading of its own (Sonnet page check, 2026-10-31)."""
    layout = _layout([])
    top = max(c["top"] for c in layout.pages[0].chars) + 20
    layout.pages[0].chars += _line("Predicting the Nature of Prime-to-Behavior", HEAD, top)
    layout.pages[0].chars += _line("Effects in Interpersonal Contexts", HEAD, top + 13)
    md = _md([]) + "\n".join(["### Predicting the Nature of Prime-to-Behavior", "",
                              "Effects in Interpersonal Contexts",
                              "Body text under the heading goes on here.", ""])
    out = _promote_layout_styled_headings(md, layout)
    assert "### Predicting the Nature of Prime-to-Behavior Effects in Interpersonal Contexts" in out
    assert "### Effects in Interpersonal Contexts" not in out


def test_a_three_line_heading_is_one_heading():
    """10.5465/amc.2022.0006: "A SYNTHESIS AND EVALUATION OF THE CSR" /
    "LITERATURE, WITH RECOMMENDATIONS FOR" / "FUTURE RESEARCH" -- the first
    line stayed body text and the last two became a heading of their own."""
    layout = _layout([])
    top = max(c["top"] for c in layout.pages[0].chars) + 20
    heading = ["A SYNTHESIS AND EVALUATION OF THE CSR", "LITERATURE, WITH RECOMMENDATIONS FOR",
               "FUTURE RESEARCH"]
    for k, t in enumerate(heading):
        layout.pages[0].chars += _line(t, HEAD, top + 13 * k)
    md = _md([]) + "\n".join(heading + ["We now return to our evaluation criteria.", ""])
    out = _promote_layout_styled_headings(md, layout)
    assert "### " + " ".join(heading) in out
    assert "### LITERATURE" not in out


def test_a_centred_heading_whose_first_line_is_off_the_margin():
    """10.5465/amc.2022.0006 p9: the centred heading's first line starts 2 pt
    inside the column margin, its second line on it."""
    layout = _layout([])
    top = max(c["top"] for c in layout.pages[0].chars) + 20
    # widths 28*6 and 33*6: centres (65 + 233) / 2 == (50 + 248) / 2
    layout.pages[0].chars += _line("Evaluation of the Literature", HEAD, top, x0=65.0)
    layout.pages[0].chars += _line("With Recommendations For Research", HEAD, top + 13, x0=50.0)
    md = _md([]) + "\n".join(["Evaluation of the Literature", "With Recommendations For Research",
                              "We now return to our evaluation criteria.", ""])
    out = _promote_layout_styled_headings(md, layout)
    assert "### Evaluation of the Literature With Recommendations For Research" in out


def test_a_line_in_the_style_of_an_existing_level_3_heading_stays_level_3():
    """10.3389/fpsyg.2023.1170855 p4 (Sonnet page check, 2026-10-31): "Empathy"
    is set at 13.2 pt like "Veracity", already a ### heading, while the most
    used heading style is a larger one. Compared with that style alone it was
    taken for the level below. A style an existing heading already uses keeps
    that heading's level."""
    big, mid = HEAD, (HEAD[0], 11.0)
    chars, top = [], 50.0
    for text, st in (("Measures", big), ("Participants", big), ("Procedure", big),
                     ("Datasets", mid), ("Empathy", mid)):
        chars += _line(text, st, top)
        top += 14
        for k in range(3):
            chars += _line(f"body text line number {k} of this paragraph here", BODY, top)
            top += 12
    layout = SimpleNamespace(pages=[SimpleNamespace(chars=chars)])
    md = _md([]) + "\n".join(["### Datasets", "", "Some body.", "",
                              "Empathy", "Body text under the heading goes on here.", ""])
    out = _promote_layout_styled_headings(md, layout).split("\n")
    assert "### Empathy" in out, out[-6:]


def test_a_title_sized_level_3_line_does_not_demote_a_heading():
    """10.1111/j.0956-7976.2004.00737.x p5 (Sonnet page check, 2026-10-31):
    title fragments at ### are set at about 3x the size of "Day 1: ..."; a
    face that much larger is not the heading level above it."""
    title, sub = (HEAD[0], 33.0), (HEAD[0], 11.0)
    chars, top = [], 50.0
    for text, st in (("Measures", title), ("Participants", title), ("Procedure", title),
                     ("Day 1: Exploration", sub)):
        chars += _line(text, st, top)
        top += 40
        for k in range(3):
            chars += _line(f"body text line number {k} of this paragraph here", BODY, top)
            top += 12
    layout = SimpleNamespace(pages=[SimpleNamespace(chars=chars)])
    md = _md([]) + "\n".join(["### Equivalence", "", "Some body.", "",
                              "Day 1: Exploration", "Body text under the heading goes on here.", ""])
    out = _promote_layout_styled_headings(md, layout).split("\n")
    assert "### Day 1: Exploration" in out, out[-6:]
