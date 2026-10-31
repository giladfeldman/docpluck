"""The layout title matches its text line when the text marks superscripts.

The layout glyph run reads "Petrillo1,2,3"; since 2026-10-30 the text channel
marks raised digits after a word ("Petrillo^1,2,3"). Token matching split the
marker off, the line no longer matched, and the front matter was rebuilt around
an unmatched title (10.1177/09567976221082938: the masthead strip then removed
the article title and the affiliations).
"""

from docpluck.render import _apply_title_rescue


def test_a_caret_marked_line_is_upgraded_in_place():
    out = "\n".join([
        "Psychological Science",
        "",
        "Ann Example^1,2, Bob Sample^1, and Cy Person^2",
        "",
        "## Abstract",
        "",
        "Text.",
    ])
    res = _apply_title_rescue(out, "Ann Example1,2, Bob Sample1, and Cy Person2")
    lines = res.split("\n")
    assert sum(1 for ln in lines if ln.startswith("# ")) == 1
    assert "Ann Example^1,2, Bob Sample^1, and Cy Person^2" not in res
    assert lines.index("Psychological Science") < next(
        i for i, ln in enumerate(lines) if ln.startswith("# "))
