"""In-text citation linking (docpluck.link_citations), synthetic text.

Numeric forms resolve by list number; author-year forms by first-author surname
+ year (+ a/b suffix), with the second author or "et al." choosing between
same-surname, same-year entries. A citation that matches nothing is an orphan
(empty ``reference_ids``); its unmatched parts are in ``unresolved``.
"""

from __future__ import annotations

from docpluck import link_citations, parse_references

APA_LIST = """References
Smith, J. (2020a). First paper. Journal of Things, 1, 1-2.
Smith, J. (2020b). Second paper. Journal of Things, 1, 3-4.
Smith, J., & Lee, K. (2020). Third paper. Journal of Things, 2, 1-2.
Smith, J., Lee, K., & Park, M. (2020). Fourth paper. Journal of Things, 3, 1-2.
Park, M. (2019). Fifth paper. Journal of Things, 4, 1-2.
van Dijk, E. (2018). Sixth paper. Journal of Things, 5, 1-2.
"""


def _links(text: str, refs) -> list[tuple[str, tuple[str, ...]]]:
    return [(c.marker_text, c.reference_ids) for c in link_citations(text, refs)]


def _apa():
    refs = parse_references(APA_LIST)
    ids = {r.title: r.reference_id for r in refs}
    return refs, ids


def test_apa_parenthetical_single_and_suffix():
    refs, ids = _apa()
    got = _links("as shown before (Smith, 2020a) and later.", refs)
    assert got == [("(Smith, 2020a)", (ids["First paper"],))]


def test_apa_two_authors_and_et_al_choose_the_entry():
    refs, ids = _apa()
    got = dict(_links("One (Smith & Lee, 2020). Two (Smith et al., 2020).", refs))
    assert got["(Smith & Lee, 2020)"] == (ids["Third paper"],)
    assert got["(Smith et al., 2020)"] == (ids["Fourth paper"],)


def test_apa_multiple_works_in_one_parenthesis_with_prefix_and_page():
    refs, ids = _apa()
    got = _links("Known (e.g., Park, 2019; Smith, 2020a, 2020b; van Dijk, 2018, p. 4).", refs)
    assert len(got) == 1
    assert got[0][1] == (ids["Fifth paper"], ids["First paper"], ids["Second paper"], ids["Sixth paper"])


def test_apa_year_suffix_list_shorthand():
    refs, ids = _apa()
    got = _links("Twice (Smith, 2020a, b).", refs)
    assert got[0][1] == (ids["First paper"], ids["Second paper"])


def test_apa_narrative_forms():
    refs, ids = _apa()
    got = dict(_links("Park (2019) argued, and Smith and Lee (2020) agreed; Smith et al. (2020) did not.", refs))
    assert got["Park (2019)"] == (ids["Fifth paper"],)
    assert got["Smith and Lee (2020)"] == (ids["Third paper"],)
    assert got["Smith et al. (2020)"] == (ids["Fourth paper"],)


def test_chicago_author_date_without_comma():
    refs, ids = _apa()
    got = _links("as before (Park 2019; Smith and Lee 2020).", refs)
    assert got[0][1] == (ids["Fifth paper"], ids["Third paper"])


def test_bare_author_year_is_linked_only_when_it_resolves():
    refs, ids = _apa()
    got = dict(_links("The data of Park 2019 were reused, unlike Murphy 2011.", refs))
    assert got == {"Park 2019": (ids["Fifth paper"],)}


def test_apa_orphan_is_reported():
    refs, _ = _apa()
    cits = link_citations("Unknown work (Nobody, 1999).", refs)
    assert len(cits) == 1 and cits[0].reference_ids == () and cits[0].unresolved


def test_a_year_in_parentheses_that_is_not_a_citation_is_ignored():
    refs, _ = _apa()
    assert _links("Data were collected in spring (April 2019) and in (2020).", refs) == []


NUM_LIST = "References\n" + "\n".join(
    f"{n}. Author{chr(64 + n)} A, Other B. Title number {n}. J Things. 20{10 + n};{n}:1-9." for n in range(1, 13)
)


def test_numeric_brackets_ranges_and_lists():
    refs = parse_references(NUM_LIST)
    got = _links("One [1]. Range [3-5]. List [1, 7]. Pair [2]-[4]. Too big [99].", refs)
    assert got == [("[1]", ("1",)), ("[3-5]", ("3", "4", "5")), ("[1, 7]", ("1", "7")),
                   ("[2]-[4]", ("2", "3", "4"))]


def test_numeric_superscripts_glued_to_words():
    refs = parse_references(NUM_LIST)
    text = ("seizures, and stroke3-6. Neurons can be infected7,8, unlike in vivo9. "
            "Care,5 matters. SARS-CoV-2 and COVID19 and p=0.05 and 2.5 mg/kg2 are not citations.")
    got = _links(text, refs)
    assert ("3-6", ("3", "4", "5", "6")) in got
    assert ("7,8", ("7", "8")) in got
    assert ("9", ("9",)) in got
    assert ("5", ("5",)) in got
    assert len(got) == 4


def test_superscripts_are_not_searched_when_the_paper_uses_brackets():
    refs = parse_references(NUM_LIST)
    got = _links("Shown [1], [2] and [3]; the model2 term is not a citation.", refs)
    assert [g[0] for g in got] == ["[1]", "[2]", "[3]"]


def test_bibliography_itself_is_excluded():
    refs = parse_references(NUM_LIST)
    text = "Body [2].\n" + NUM_LIST
    cits = link_citations(text, refs, exclude_spans=[(len("Body [2].\n"), len(text))])
    assert [c.marker_text for c in cits] == ["[2]"]


def test_affiliation_numbers_in_an_author_list_are_not_citations():
    refs = parse_references(NUM_LIST)
    text = ("Consortium members: Kai Lund1, Mara Ortiz2, Petra Quinn3, Tom N. Ashby1 and Hana Bexley2.\n"
            "Rivers rise in spring1, and fall in autumn2,3.")
    got = _links(text, refs)
    assert [g[0] for g in got] == ["1", "2,3"]


def test_a_bracketed_value_after_a_number_is_not_a_citation():
    refs = parse_references(NUM_LIST)
    got = _links("Age, mean (SD) 48 (18) 51 (2) years. Rivers rise (1).", refs)
    assert [g[0] for g in got] == ["(1)"]


def test_a_cell_type_name_is_not_a_superscript_citation():
    refs = parse_references(NUM_LIST)
    got = _links("It orchestrates Th1 and Th2 responses in rivers3.", refs)
    assert [g[0] for g in got] == ["3"]
