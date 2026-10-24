"""A fenced block is verbatim: no heading promoter may rewrite a line inside it.

The ``unstructured-table`` fence holds a table's raw cell text when no grid
could be rebuilt. ``_promote_isolated_titlecase_subsection_headings`` walked
into it and turned the table's own row-group labels into ``### Anxiety
subscale``-style headings inside the fence (10.1016/j.evolhumbehav.2016.06.001
Table 2: six fake headings).
"""

from __future__ import annotations

from docpluck.render import _promote_isolated_titlecase_subsection_headings as promote

BODY = (
    "## Method\n\n"
    "The first study ended here.\n\n"
    "Anxiety Subscale\n\n"
    "Participants were asked to rate how often they felt nervous during the past two weeks.\n"
)


def test_promoter_fires_outside_a_fence():
    # Control: the same lines outside a fence are promoted, so the test below
    # exercises the fence guard and not some other gate.
    assert "### Anxiety Subscale" in promote(BODY)


def test_promoter_leaves_fenced_lines_verbatim():
    fenced = "```unstructured-table\n" + BODY + "```\n"
    assert promote(fenced) == fenced


def test_promoter_resumes_after_the_fence_closes():
    doc = "```unstructured-table\nAnxiety Subscale\n```\n\n" + BODY
    out = promote(doc)
    assert out.startswith("```unstructured-table\nAnxiety Subscale\n```")
    assert "### Anxiety Subscale" in out


def test_numbered_subsection_promoter_leaves_fenced_lines_verbatim():
    from docpluck.render import _promote_numbered_subsection_headings as promote_num

    body = "Body.\n2.2.5. Self-Harm\nThe inventory has 17 items.\n"
    assert "### 2.2.5. Self-Harm" in promote_num(body)  # control
    fenced = "```unstructured-table\n" + body + "```\n"
    assert promote_num(fenced) == fenced


# A table's row-group labels in a text-channel dump that follows its caption
# with no blank line ("Table 2" / caption / "Item" / "Depression subscale" /
# "Little interest ...?" / "Anger subscale" ...) are cells, not subsections.
# The single-column relaxation promoted them (Hurst Table 2: ten fake
# "### <X> subscale" headings in the body).
_ROWS = (
    "Little interest or pleasure in doing things?\n"
    "Feeling down, depressed, or hopeless?\n"
    "Anger subscale\n"
    "Feeling more irritated, grouchy, or angry than usual?\n"
    "Mania subscale\n"
    "Sleeping less than usual, but still have a lot of energy?\n"
)


def test_rows_under_a_table_caption_are_not_promoted():
    doc = (
        "## Method\n\nEach item was rated on a 5-point scale.\n\n"
        "Table 2\nThe percentage of respondents who recorded a rating.\n"
        "Item\nDepression subscale\n" + _ROWS
    )
    out = promote(doc, is_single_column=True)
    assert "### Anger subscale" not in out
    assert "### Mania subscale" not in out
    assert "### Depression subscale" not in out


def test_same_lines_without_a_caption_still_promote():
    # Control: without the caption block the relaxation still fires, so the
    # test above exercises the caption guard and nothing else.
    doc = (
        "## Method\n\nEach item was rated on a 5-point scale.\n\n"
        "Depression subscale\n" + _ROWS
    )
    assert "### Anger subscale" in promote(doc, is_single_column=True)
