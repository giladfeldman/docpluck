"""Affiliation markers kept by 2.4.152 must not reshape the Abstract.

2.4.152 stopped deleting bare integers as page numbers unless they chain like pages.
Affiliation superscripts printed on their own line ("2", "3") therefore survive, and
in 4 of 125 manifest papers they moved the affiliation block under `## Abstract`
(10.15626/MP.2022.3108 p1) or were folded into the heading as "## 2. Abstract"
(10.1037/pspp0000586 p1, 10.1037/cns0000401, 10.48550/arXiv.2406.05529). Found by the
2.4.152 pre-push canary.
"""

from docpluck.render import (
    _fold_orphan_arabic_numerals_into_headings,
    _strip_abstract_zone_affiliation_remnant,
)

BODY = "People tend to stick with a default option instead of switching to another option."


def test_markers_before_the_orphaned_affiliation_are_part_of_the_remnant():
    # 10.15626/MP.2022.3108 p1, as rendered by 2.4.152 before this fix.
    md = (
        "## Abstract\n\n2\n3\nDepartment of Philosophy, Lake Forest College\n"
        "*Joint first authors\n" + BODY + "\n"
    )
    out = _strip_abstract_zone_affiliation_remnant(md)
    assert out.split("\n")[2] == BODY
    assert "Lake Forest" not in out


def test_markers_between_affiliation_lines_are_part_of_the_remnant():
    # 10.1037/pspp0000586 p1 shape: affiliation, affiliation, marker, affiliation.
    md = (
        "## Abstract\n\nDepartment of Psychology, University of Hong Kong\n"
        "Department of Marketing, University of Maastricht\n3\n"
        "Department of Banking and Finance, University of Innsbruck\n" + BODY + "\n"
    )
    out = _strip_abstract_zone_affiliation_remnant(md)
    assert out.split("\n")[2] == BODY


def test_a_bare_number_opening_real_prose_is_never_stripped():
    # A marker counts only when an affiliation line follows it.
    md = "## Abstract\n\n2\n" + BODY + "\n"
    assert _strip_abstract_zone_affiliation_remnant(md) == md


def test_an_orphan_number_is_not_folded_into_a_front_matter_heading():
    md = "reserved.\n\n2\n\n## Abstract\n\n" + BODY
    out = _fold_orphan_arabic_numerals_into_headings(md)
    assert "## 2. Abstract" not in out
    assert "## Abstract" in out
    assert "## 2. Keywords" not in _fold_orphan_arabic_numerals_into_headings("2\n\n## Keywords\n")
    # 10.48550/arXiv.2406.05529 prints the heading in capitals.
    assert "## 2. ABSTRACT" not in _fold_orphan_arabic_numerals_into_headings("2\n\n## ABSTRACT\n")


def test_an_orphan_number_still_folds_into_a_numbered_section_heading():
    assert "## 1. Introduction" in _fold_orphan_arabic_numerals_into_headings("1.\n\n## Introduction\n")
