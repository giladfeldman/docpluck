"""Reference-entry splitting and field parsing (docpluck.references).

Short synthetic entries (invented names, titles and DOIs), one per citation
style the library meets in its corpus: APA, Vancouver/AMA, Nature, IEEE,
Harvard/Royal Society, AOM, ASA, Chicago author-date, an APA chapter, an
organisation author. Each asserts the fields an arena-style scorer grades: the
surname sequence, year, title, container, volume, issue, first/last page, DOI.
"""

from __future__ import annotations

import pytest

from docpluck import parse_reference, parse_references


def _fields(raw: str) -> dict:
    r = parse_reference(raw)
    return {
        "families": [a.family for a in r.authors],
        "et_al": r.et_al,
        "year": r.year,
        "suffix": r.year_suffix,
        "title": r.title,
        "container": r.container,
        "volume": r.volume,
        "issue": r.issue,
        "pages": (r.first_page, r.last_page),
        "doi": r.doi,
    }


CASES = [
    (
        "apa",
        ("Ardent, H., Velmor, B., & Van Kestrel, A. (1998). Forecasting choices from earlier choices: "
        "Repeated deciding or a matter of routine? Journal of Applied Social Psychology, 28, 1355-1374."),
        {"families": ["Ardent", "Velmor", "Van Kestrel"], "year": "1998",
             "title": "Forecasting choices from earlier choices: Repeated deciding or a matter of routine?",
             "container": "Journal of Applied Social Psychology", "volume": "28", "pages": ("1355", "1374")},
    ),
    (
        "apa_doi_issue_suffix",
        ("Brisk, D. (2020a). How analysts can stop misleading themselves. Nature, 584(7819), 9. "
        "https://doi.org/10.1234/d41586-020-00000-1"),
        {"families": ["Brisk"], "year": "2020", "suffix": "a", "container": "Nature", "volume": "584", "issue": "7819",
             "pages": ("9", None), "doi": "10.1234/d41586-020-00000-1"},
    ),
    (
        "vancouver_et_al",
        ("Cobb SS, Halvard R, Narain K, et al. Global patterns of a heart rhythm disorder: a Burden "
        "of Disease 2010 Study. Circulation. 2014;129:837-47."),
        {"families": ["Cobb", "Halvard", "Narain"], "et_al": True, "year": "2014", "container": "Circulation",
             "volume": "129", "pages": ("837", "47")},
    ),
    (
        "ama_doi",
        ("Pell WJ, Dorn MD, Bunt CR. Relationship between household income and childhood "
        "injuries. J Urban Health. 2001;78(1):141-151. doi:10.1234/jurban/78.1.141"),
        {"families": ["Pell", "Dorn", "Bunt"], "year": "2001",
             "title": "Relationship between household income and childhood injuries",
             "container": "J Urban Health", "volume": "78", "issue": "1", "pages": ("141", "151"),
             "doi": "10.1234/jurban/78.1.141"},
    ),
    (
        "nature",
        ("Dunmore, T. M. et al. Complications seen in hospital patients with a viral illness. "
        "Lancet 398, 223-237 (2021)."),
        {"families": ["Dunmore"], "et_al": True, "year": "2021", "container": "Lancet", "volume": "398",
             "pages": ("223", "237")},
    ),
    (
        "ieee_initials_first",
        ('A. B. Smith, C. D. Jones, and E. Brown, "A title here," IEEE Trans. Pattern Anal., vol. 12, no. 3, '
        "pp. 45-67, 2020."),
        {"families": ["Smith", "Jones", "Brown"], "year": "2020", "title": "A title here", "volume": "12", "issue": "3",
             "pages": ("45", "67")},
    ),
    (
        "ieee_article_number",
        ('Yarrow W, Zell D, Penn L, Zhou C, and Holt L, "A comparison of several spread models," '
        "Epidemics, vol. 37, Dec. 2021, Art. no. 100501."),
        {"families": ["Yarrow", "Zell", "Penn", "Zhou", "Holt"], "year": "2021", "container": "Epidemics",
             "volume": "37", "pages": ("100501", None)},
    ),
    (
        "royal_society_bare_year",
        ("Gorse JL. 2005 A social network in the brain: themes and variations. "
        "Horm. Behav. 48, 11-22. (doi:10.1234/j.yhbeh.2005.00.001)"),
        {"families": ["Gorse"], "year": "2005", "volume": "48", "pages": ("11", "22"),
             "doi": "10.1234/j.yhbeh.2005.00.001"},
    ),
    (
        "aom_colon_pages",
        ("Ambrose, T. M. 2020. Novelty, machine learning, and a world of surprises. "
        "Academy of Management Discoveries, 6: 351-354."),
        {"families": ["Ambrose"], "year": "2020", "container": "Academy of Management Discoveries", "volume": "6",
             "pages": ("351", "354")},
    ),
    (
        "asa_full_names_quoted_title",
        ('Albrecht, Silke, and Anette Fassbinder. 2017. "The Interplay of Work and Home Paths over the Life '
        'Course." American Journal of Sociology 122(5):1448-84 (https://doi.org/10.1234/691128).'),
        {"families": ["Albrecht", "Fassbinder"], "year": "2017",
             "title": "The Interplay of Work and Home Paths over the Life Course",
             "container": "American Journal of Sociology", "volume": "122", "issue": "5", "pages": ("1448", "84"),
             "doi": "10.1234/691128"},
    ),
    (
        "title_with_question_and_subtitle",
        ("Alder D (2006). Is the old epidemic over? Long-term effects of early exposure in "
        "a later population. Journal of Political Economy, 114, 672-712."),
        {"families": ["Alder"], "year": "2006", "container": "Journal of Political Economy", "volume": "114",
             "pages": ("672", "712")},
    ),
    (
        "apa_chapter",
        ("Abernathy, K. L., & Varga, M. (2020). The reliability of attentional capture paradigms. In P. Delacroix & "
        "V. Kowalczyk (Eds.), The Handbook of Sleep and Memory (pp. 265-285). Guilford Press."),
        {"families": ["Abernathy", "Varga"], "year": "2020", "title": "The reliability of attentional capture paradigms",
             "container": "The Handbook of Sleep and Memory", "pages": ("265", "285")},
    ),
    (
        "organisation_author",
        "American Psychological Association. (2019). Implicit bias measurement in the field. Technical report.",
        {"families": ["American Psychological Association"], "year": "2019",
             "title": "Implicit bias measurement in the field"},
    ),
    (
        "particles_kept",
        ("van der Berg, P., de la Cruz, J. M., & Jablonski, F. (2022). Boundary conditions of moral licensing. "
        "Psychological Science, 147(7), 609-635."),
        {"families": ["van der Berg", "de la Cruz", "Jablonski"], "year": "2022", "volume": "147", "issue": "7"},
    ),
]


@pytest.mark.parametrize("name,raw,expected", CASES, ids=[c[0] for c in CASES])
def test_fields(name, raw, expected):
    got = _fields(raw)
    for key, value in expected.items():
        assert got[key] == value, f"{name}: {key} = {got[key]!r}, expected {value!r}"


def test_unprinted_fields_stay_none():
    r = parse_reference("Smith, J. (2020). A title. Journal of Things, 4, 1-9.")
    assert r.doi is None and r.url is None and r.pmid is None and r.issue is None


def test_numbered_list_with_number_alone_on_its_line():
    text = ("References\n1.\n\nDunmore, T. M. et al. A study. Lancet 398, 223-237 (2021).\n"
            "2. Xu, E. & Lee, A. Another. Nat. Med. 1, 1-10 (2022).\n")
    refs = parse_references(text)
    assert [r.reference_id for r in refs] == ["1", "2"]
    assert refs[0].authors[0].family == "Dunmore"


def test_numbered_list_run_together_on_one_line():
    # normalization can join "[16] ..." onto the end of entry 15
    text = ("References\n[14] Lee A (2001). One. Cognition, 5, 1-2.\n"
            "[15] Barnes J (2013). Two. Cognition, 105(3), 457-485. https://doi.org/10.1234/x.1 [16] Young G (2024). "
            "Three. Trends in Cognitive Sciences, 80(3), 28-49.\n")
    refs = parse_references(text)
    assert [r.reference_id for r in refs] == ["14", "15", "16"]
    assert refs[1].doi == "10.1234/x.1" and refs[2].authors[0].family == "Young"


def test_numbered_columns_read_out_of_order():
    nums = [1, 2, 3, 7, 8, 4, 9, 5, 6]
    text = "References\n" + "\n".join(
        f"[{n}] Author{chr(64 + n)} A ({2000 + n}). Title {n}. Journal, {n}, 1-2." for n in nums)
    refs = parse_references(text)
    assert sorted(int(r.reference_id) for r in refs) == list(range(1, 10))


def test_continuation_line_starting_with_a_number_is_not_an_entry():
    text = ("References\n1. Smith A, Lee B. A long title that wraps. J Things.\n2020;12(3):45-67.\n"
            "2. Park C. Another. J Things. 2019;11:1-2.\n")
    refs = parse_references(text)
    assert [r.reference_id for r in refs] == ["1", "2"]
    assert refs[0].volume == "12" and refs[0].first_page == "45"


def test_author_year_entries_run_together_are_split():
    text = ("References\nQuinn K, Robinson L (2020). Replication of publication bias. Behavior Research Methods, "
            "204(6), 62-79. Harris A, Sanchez J (2002). Predicting adoption. Trends in Cognitive Sciences, 111, "
            "808-828. https://doi.org/10.5438/j.2002.6359\n")
    refs = parse_references(text)
    assert [r.authors[0].family for r in refs] == ["Quinn", "Harris"]
    assert refs[1].doi == "10.5438/j.2002.6359"


def test_author_year_wrapped_lines_join():
    text = ('References\nAlbrecht, Silke, and Anette Fassbinder. 2017. "The Interplay of Work and Home Paths '
            'over the Life\nCourse: Two Countries in Comparison." American Journal of Sociology '
            "122(5):1448-84.\nAnsel, Joshua D., and Jorn-Steffen Pilcher. 2009.\nMostly Useful Methods: An "
            "Analyst's\nCompanion. Princeton, NJ: Princeton University\nPress.\n")
    refs = parse_references(text)
    assert [r.authors[0].family for r in refs] == ["Albrecht", "Ansel"]
    assert refs[0].title.endswith("in Comparison")


def test_a_pmid_label_whose_value_was_lost_does_not_hide_the_source():
    # the PMID number sat on its own line and did not survive extraction
    r = parse_reference("Varga F, Rasmussen C. Does the decoy effect generalize? Adv Methods Pract Psychol Sci. "
                        "2018;55(12):119-130. doi:10.5404/sa.2018.3327 PMID:")
    assert (r.volume, r.issue, r.first_page, r.last_page) == ("55", "12", "119", "130")
    assert r.pmid is None


def test_run_together_entries_split_after_a_doi_ending_in_a_letter():
    text = ("References\nAlvarez, A. S., & Sorel, P. (1994). A psychological study. Risk Analysis, 14(6), "
            "1085-1096. https://doi.org/10.1234/j.1539-6924.1994.tb00000.x Andover, A. (1981). Foundations of "
            "a measurement theory. Academic Press.\n")
    refs = parse_references(text)
    assert [r.authors[0].family for r in refs] == ["Alvarez", "Andover"]
    assert refs[0].doi == "10.1234/j.1539-6924.1994.tb00000.x"


def test_a_url_with_a_space_after_the_scheme_is_still_a_doi_link():
    r = parse_reference("Bates, I., & Stark, C. (2007). A feeling heuristic. Journal of Behavioral Decision "
                        "Making, 20(4), 365-380. https: //doi.org/10.1234/bdm.558")
    assert r.doi == "10.1234/bdm.558"
    assert (r.container, r.volume, r.issue) == ("Journal of Behavioral Decision Making", "20", "4")


@pytest.mark.parametrize("tail,doi", [
    ("doi:10.1161/ CIRCULATIONAHA.109.901801", "10.1161/circulationaha.109.901801"),
    ("doi:10.1016/j. ijcard.2013.08.088", "10.1016/j.ijcard.2013.08.088"),
    ("doi:10.1001/jama. 2017.7967", "10.1001/jama.2017.7967"),
])
def test_a_doi_broken_by_a_space_at_the_end_of_the_entry_is_rejoined(tail, doi):
    r = parse_reference(f"Gold DJ, Yen G, Nye AB, et al. A cohort study of sleep. Circulation. "
                        f"2010;122(4):352-360. {tail}")
    assert r.doi == doi
    assert (r.container, r.volume, r.issue, r.first_page, r.last_page) == ("Circulation", "122", "4", "352", "360")


def test_an_elocator_page_with_letters():
    r = parse_reference("Moss A, Ayer I. Metrics of severity. Sleep. 2021;44(7):zsab030. doi:10.1234/sleep/zsab030")
    assert (r.volume, r.issue, r.first_page) == ("44", "7", "zsab030")


def test_a_group_author_after_et_al_is_not_the_title():
    r = parse_reference("Mack RD, Ant NA, Hale E, et al; SAVE Investigators and Coordinators. CPAP for prevention of "
                        "events in sleep apnea. N Engl J Med. 2016;375(10):919-931.")
    assert r.title == "CPAP for prevention of events in sleep apnea"
    assert (r.container, r.volume) == ("N Engl J Med", "375")


@pytest.mark.parametrize("tail,doi", [
    ("DOI: https://doi.org/10.1234/irsp.571", "10.1234/irsp.571"),
    ("http s://doi.org/10.1234/jrsm.1594", "10.1234/jrsm.1594"),
    ("https://doi.org/1 0.1234/1076-898x.2.2.107", "10.1234/1076-898x.2.2.107"),
])
def test_doi_link_artefacts_do_not_leak_into_the_source(tail, doi):
    r = parse_reference(f"Baker, J., & Green, J. (1996). Determinants of insensitivity. Journal of Experimental "
                        f"Psychology: Applied, 2(2), 107-125. {tail}")
    assert r.doi == doi
    assert (r.container, r.volume, r.issue, r.first_page, r.last_page) == (
        "Journal of Experimental Psychology: Applied", "2", "2", "107", "125")


@pytest.mark.parametrize("raw,families,givens", [
    ('Orwin Clara. 2015. "A Study of Lanterns." Sociology Notes 4(2):11-20.',
     ["Orwin"], ["Clara"]),
    ('Bexley Hana, Morrow Ivo, and Tallis Petra. 2012. "Rivers and Roads." Social Ledger 9:1-9.',
     ["Bexley", "Morrow", "Tallis"], ["Hana", "Ivo", "Petra"]),
    ('Quell Dana P., Fenwick Ruth J., and Ashby Tom N.. 2019. "Night Shifts." Work Review 3(1):5-8.',
     ["Quell", "Fenwick", "Ashby"], ["Dana P.", "Ruth J.", "Tom N."]),
    ('Quell Dana P. 2018. "Night Shifts." Work Review 3(1):5-8.', ["Quell"], ["Dana P."]),
])
def test_surname_then_given_name_without_a_comma(raw, families, givens):
    r = parse_reference(raw)
    assert [a.family for a in r.authors] == families
    assert [a.given for a in r.authors] == givens
    assert r.year and r.year in raw
    assert r.title is not None and r.title.split()[0] in raw


def test_surname_given_entries_run_together_are_split():
    text = ('Quell Dana P. 2018. "Night Shifts." Work Review 3(1):5-8. '
            'Quell Dana P., Fenwick Ruth J., and Ashby Tom N.. 2019. "Day Shifts." Work Review 4(1):9-12.\n'
            'Tallis Petra. 2005. "Bridges." Social Ledger 2:1-4.\n')
    refs = parse_references(text)
    assert [r.year for r in refs] == ["2018", "2019", "2005"]
    assert [a.family for a in refs[1].authors] == ["Quell", "Fenwick", "Ashby"]


def test_back_matter_after_the_last_numbered_entry_is_not_part_of_it():
    text = ("References\n1. Quinn K, Robinson L. Replication of publication bias. Behav Res. 2020;12:62-79.\n"
            "2. Harris A, Sanchez J. Predicting adoption. Trends Cogn Sci. 2002;11:808-28.\n"
            "3. Lund P, Ortiz M. Rivers and roads in practice. Front Hydrol. 2022;9:1027000.\n"
            "Publisher's Note\nThe publisher stays neutral with regard to jurisdictional claims in published maps "
            "and institutional affiliations. Submit your next manuscript with us and benefit from fast online "
            "submission, thorough peer review and rapid publication on acceptance, with wide visibility.\n")
    refs = parse_references(text)
    assert len(refs) == 3
    last = refs[-1]
    assert last.raw_text.endswith("2022;9:1027000.")
    assert (last.container, last.volume, last.first_page) == ("Front Hydrol", "9", "1027000")
    assert text[last.char_start:last.char_end].endswith("1027000.")


def test_author_notes_after_the_last_author_year_entry_are_not_part_of_it():
    text = ("References\nQuinn, K., & Robinson, L. (2020). Replication of publication bias. Behavior Research, "
            "12, 62-79.\nLund, P., & Ortiz, M. (2018). Making rivers mainstream. Hydrology Letters, 41.\n"
            "Kai Lund is an assistant professor at the Department of Geography of a mid-sized university. Her "
            "research focuses on rivers, roads and the people who build them. Mara Ortiz was a teaching "
            "assistant in the same department during the academic year 2017-8.\n")
    refs = parse_references(text)
    assert len(refs) == 2
    assert refs[-1].raw_text.endswith("Hydrology Letters, 41.")
    assert (refs[-1].container, refs[-1].volume) == ("Hydrology Letters", "41")


def test_an_elocator_after_the_issue_and_a_full_stop():
    r = parse_reference("Lund, P. (2015). Estimating river depth. Hydrology, 349(6251). aac4716.")
    assert (r.container, r.volume, r.issue, r.first_page) == ("Hydrology", "349", "6251", "aac4716")


def test_a_misspelt_retrieved_from_is_not_the_container():
    r = parse_reference("Lund, P. (2012). A rule for river journals. Retreived from: https://example.org/2012/rule/.")
    assert r.title == "A rule for river journals"
    assert r.container is None
    assert r.url == "https://example.org/2012/rule/"


@pytest.mark.parametrize("lead", ["", "\f"], ids=["plain", "after-page-break"])
def test_a_references_heading_inside_another_section_is_found(lead):
    from types import SimpleNamespace

    from docpluck.references import _references_spans

    entries = " ".join(
        f'Lund{c} Petra, and Ortiz Mara. 20{10 + i}. "River Study {c}." Hydrology Letters {i + 1}:{i}1-{i}9.'
        for i, c in enumerate("ABCDEF"))
    body = "Appendix\n\nTable A1 shows the river depths by year.\n\n" + lead + "References\n\n" + entries + "\n"
    text = "Introduction\n\nRivers matter (LundA and Ortiz 2010).\n\n" + body
    start = text.index("Appendix")
    doc = SimpleNamespace(
        normalized_text=text,
        sections=[SimpleNamespace(canonical_label="introduction", char_start=0, char_end=start, text=text[:start]),
                  SimpleNamespace(canonical_label="appendix", char_start=start, char_end=len(text), text=body)])
    spans = _references_spans(doc)
    assert len(spans) == 1
    a, b = spans[0]
    assert text[a:b].lstrip().startswith("References") or text[a:b].lstrip().startswith("LundA")
    assert len(parse_references(text[a:b], offset=a)) == 6


def test_list_numbers_printed_apart_from_their_entries_are_paired_in_order():
    text = ("References\n1. 2.\n\n3.\n\n"
            "Lund, K. et al. Rivers in spring. J. Hydrol. 29, 12-23 (2009).\n"
            "Ortiz, M. & Quinn, P. Roads in autumn. Road Res. 95, 301-310 (2017).\n"
            "Ashby, T. N. Bridges and the people who\nbuild them. Bridge Sci. 117, 18-28 (2020).\n\n"
            "4.\n\n5.\n\n"
            "Bexley, H. Lakes. Lake Lett. 4, 1-9 (2001).\n"
            "Tallis, P. & Morrow, I. Wells. Well Sci. 7, 2-5 (2011).\n")
    refs = parse_references(text)
    assert [r.number for r in refs] == [1, 2, 3, 4, 5]
    assert [r.authors[0].family for r in refs] == ["Lund", "Ortiz", "Ashby", "Bexley", "Tallis"]
    assert refs[2].title == "Bridges and the people who build them"


def test_detached_list_numbers_that_do_not_cover_the_list_number_nothing():
    # a number missing from the blocks: pairing by position could be wrong, so no entry is numbered
    text = ("References\n1. 2.\n\n3.\n\n"
            "Lund, K. et al. Rivers in spring. J. Hydrol. 29, 12-23 (2009).\n"
            "Ortiz, M. & Quinn, P. Roads in autumn. Road Res. 95, 301-310 (2017).\n"
            "Ashby, T. N. Bridges. Bridge Sci. 117, 18-28 (2020).\n\n5.\n\n"
            "Bexley, H. Lakes. Lake Lett. 4, 1-9 (2001).\n"
            "Tallis, P. & Morrow, I. Wells. Well Sci. 7, 2-5 (2011).\n")
    refs = parse_references(text)
    assert len(refs) == 5
    assert [r.number for r in refs] == [None] * 5


def test_a_list_number_printed_at_the_end_of_the_previous_entry():
    text = ("References\n1.\n\nLund K, Ortiz M. Rivers in spring. J Hydrol. 2009; 29:12-23. PMID: 1234567 2.\n\n"
            "Quinn P. Roads in autumn. Road Res. 2017; 95:301-10. 3.\n\n"
            "Ashby TN. Bridges. Bridge Sci. 2020; 117:18-28. 4.\n\n"
            "Bexley H. Lakes. Lake Lett. 2001; 4:1-9.\n")
    refs = parse_references(text)
    assert [r.number for r in refs] == [1, 2, 3, 4]
    assert [r.authors[0].family for r in refs] == ["Lund", "Quinn", "Ashby", "Bexley"]
    assert (refs[0].volume, refs[0].first_page, refs[0].pmid) == ("29", "12", "1234567")


def test_a_list_number_without_a_full_stop_before_vancouver_names():
    text = ("REFERENCES\n\n1 Lund K, Ortiz M. Rivers in spring. J Hydrol 2009;29:12-23.\n"
            "2 Quinn P. Roads in autumn. Road Res 2017;95:301-10.\n"
            "3 Ashby TN, Bexley H, Tallis P, et al. Bridges. Bridge Sci 2020;117:18-28.\n")
    refs = parse_references(text)
    assert [r.number for r in refs] == [1, 2, 3]
    assert [r.authors[0].family for r in refs] == ["Lund", "Quinn", "Ashby"]


def test_harvard_initials_after_the_surname_joined_by_and():
    text = ("References\nLund K and Ortiz M (2020) Rivers in spring. Hydrology Letters 29, 12-23.\n"
            "Quinn P (2017) Roads in autumn. Road Research 95, 301-310.\n"
            "Ashby TN, Bexley H and Tallis P (2019) Bridges. Bridge Science 117,\n18-28.\n")
    refs = parse_references(text)
    assert [r.authors[0].family for r in refs] == ["Lund", "Quinn", "Ashby"]
    assert [len(r.authors) for r in refs] == [2, 1, 3]
    assert refs[2].last_page == "28"


def _fake_doc(text, cuts):
    """A sectioned document: cuts = [(label, start_marker), ...] in order."""
    from types import SimpleNamespace

    starts = [(lab, text.index(mark)) for lab, mark in cuts]
    secs = []
    for k, (lab, a) in enumerate(starts):
        b = starts[k + 1][1] if k + 1 < len(starts) else len(text)
        secs.append(SimpleNamespace(canonical_label=lab, char_start=a, char_end=b, text=text[a:b]))
    return SimpleNamespace(normalized_text=text, sections=secs)


# six entries; the fourth wraps over five lines, which breaks a run of entry-opening lines
_ASA_ENTRIES = "".join(
    f'Lund{c}, Petra, and Mara Ortiz. 20{10 + i}. "River Study {c}'
    + ("\nwith a title\nthat wraps\nover several\nshort lines" if c == "D" else "")
    + f'." Hydrology Letters {i + 1}:{i}1-{i}9.\n'
    for i, c in enumerate("ABCDEF"))


def test_a_references_heading_run_into_its_first_entry_is_found():
    from docpluck.references import _references_spans

    text = ("Introduction\n\nRivers matter (LundA and Ortiz 2010).\n\nFunding\nThe work had no funding.\n\n"
            "ORCID iD\nPetra Lund\n\nReferences " + _ASA_ENTRIES)
    doc = _fake_doc(text, [("introduction", "Introduction"), ("funding", "Funding")])
    (a, b), = _references_spans(doc)
    assert len(parse_references(text[a:b], offset=a)) == 6


def test_an_empty_references_section_takes_the_list_filed_under_the_next_section():
    from docpluck.references import _references_spans

    text = ("Introduction\n\nRivers matter (LundA and Ortiz 2010).\n\nNotes\n1.\n\n6. References\n\n"
            "Funding\n\nPetra Lund\n\n5.\n\nUnited Kingdom.\n\n" + _ASA_ENTRIES)
    doc = _fake_doc(text, [("introduction", "Introduction"), ("references", "6. References"),
                           ("funding", "Funding")])
    (a, b), = _references_spans(doc)
    refs = parse_references(text[a:b], offset=a)
    assert len(refs) == 6
    # the furniture lines before the first entry ("Funding", a name, "United Kingdom.") are not an entry
    assert refs[0].authors[0].family == "LundA"


def test_list_numbers_alone_on_their_lines_next_to_each_entry():
    text = ("References\n1.\n\nLund K, Ortiz M. Rivers in spring. J Hydrol. 2009; 29:12-23.\n\n2.\n\n"
            "Quinn P. Roads in autumn. Road Res. 2017; 95:301-10.\n\n3.\n\n"
            "Ashby TN. Bridges. Bridge Sci. 2020; 117:18-28.\n\n4.\n\nBexley H. Lakes. Lake Lett. 2001; 4:1-9.\n")
    refs = parse_references(text)
    assert [r.number for r in refs] == [1, 2, 3, 4]
    assert [r.authors[0].family for r in refs] == ["Lund", "Quinn", "Ashby", "Bexley"]


def test_numbers_next_to_their_entries_win_over_a_detached_reading_that_splits_more():
    # the wrapped journal line opens like an entry; read as a detached list it would be split off
    text = ("References\n1.\n\nLund K, Ortiz M. Rivers in spring.\nHydrology Letters. 2009; 29:12-23.\n\n2.\n\n"
            "Quinn P. Roads in autumn.\nRoad Research. 2017; 95:301-10.\n\n3.\n\n"
            "Ashby TN. Bridges.\nBridge Science. 2020; 117:18-28.\n\n4.\n\nBexley H. Lakes. Lake Lett. 2001; 4:1-9.\n")
    refs = parse_references(text)
    assert [r.number for r in refs] == [1, 2, 3, 4]
    assert [r.container for r in refs][:3] == ["Hydrology Letters", "Road Research", "Bridge Science"]


def test_an_author_year_list_after_a_block_of_note_numbers_is_read_as_author_year():
    text = ("References\n1.\n\n2.\n\n3.\n\n4.\n\n"
            "Lund KP, & Ortiz M (2012). Rivers in spring. Hydrology Letters, 1, 8. 10.1186/2193-9039-1-8\n"
            "Quinn J-P (2004). Roads in autumn. Road Research, 6, 253-279.\n"
            "Ashby TN (1980). Bridges and the people who build them. Washington.\n"
            "Bexley H, & Tallis P (2016). Lakes. Lake Letters, 53, 1453-1476.\n"
            "Morrow I (2011). Wells. Well Science, 2011, 420714.\n")
    refs = parse_references(text)
    assert [r.authors[0].family for r in refs] == ["Lund", "Quinn", "Ashby", "Bexley", "Morrow"]


def test_bmj_entries_run_together_are_split_and_not_trimmed_as_back_matter():
    text = ("References\n1 Lund K, Ortiz M. Rivers in spring. J Hydrol 2019; 62: 56-76.\n"
            "2 Quinn P. Roads in autumn. Road Res 1988; 319(25): 1635-8.\n"
            "3 Ashby TN. Bridges. Bridge Sci 2007; 357(18): 1834-40. 4 Bexley H, Tallis P. Lakes and the people "
            "who live by them. Lake Lett 1999; 14(1): 27-34. 5 Morrow I. Wells in the hills. Well Sci 2004; "
            "24(2): 105-12. 6 Fenwick R, Quell D. Ponds. Pond Res 2010; 304(5): 563-4. 7 Orwin C. Brooks. "
            "Brook Lett 2012; 8(1): 1-9.\n")
    refs = parse_references(text)
    assert [r.number for r in refs] == [1, 2, 3, 4, 5, 6, 7]
    assert refs[-1].authors[0].family == "Orwin"


def test_entries_run_into_the_last_entry_are_not_cut_off_as_back_matter():
    text = ("References\n1. Lund K, Ortiz M. Rivers in spring. J Hydrol 2019; 62: 56-76.\n"
            "2. Quinn P. Roads in autumn. Road Res 1988; 319(25): 1635-8.\n"
            "3. Ashby TN. Bridges. Bridge Sci 2007; 357(18): 1834-40. Morrow I. Wells in the hills. Well Sci "
            "2004; 24(2): 105-12. Fenwick R, Quell D. Ponds. Pond Res 2010; 304(5): 563-4. Orwin C. Brooks. "
            "Brook Lett 2012; 8(1): 1-9.\n")
    refs = parse_references(text)
    assert refs[-1].raw_text.endswith("Brook Lett 2012; 8(1): 1-9.")


def test_a_numbered_entry_with_an_organisation_author_does_not_break_the_sequence():
    # columns read out of order (1, 4, 5, 2, 3), then entry 6 is an organisation the
    # BMJ number reader does not take; 7 and 8 must still start entries
    e = {n: f"{n} Lund{n} K, Ortiz M. Rivers {n}. J Hydrol 2019; {n}: 56-76.\n" for n in range(1, 9)}
    e[6] = "6 World Rivers Organization. River guidance. Geneva: WRO, 2023.\n"
    text = "References\n" + "".join(e[n] for n in (1, 4, 5, 2, 3, 6, 7, 8))
    refs = parse_references(text)
    assert [r.number for r in refs] == [1, 4, 5, 2, 3, 7, 8]
    assert "World Rivers Organization" in refs[4].raw_text  # kept, inside the previous entry


def test_the_list_chosen_is_the_one_whose_entries_read_as_references():
    from docpluck.references import _references_spans

    notes = "".join(f"{n}. See the appendix table {n} for the river counts.\n" for n in range(1, 11))
    refs_text = "".join(
        f"Lund{c}, P., & Ortiz, M. (20{10 + i}). River study {c}. Hydrology Letters, {i + 1}, {i}1-{i}9.\n"
        for i, c in enumerate("ABCDEF"))
    text = ("Introduction\n\nRivers matter (LundA & Ortiz, 2010).\n\nNotes\nReferences\n" + notes
            + "\nAppendix\n\nTable A1 shows river depths.\n\n" + refs_text)
    doc = _fake_doc(text, [("introduction", "Introduction"), ("notes", "Notes"), ("appendix", "Appendix")])
    (a, b), = _references_spans(doc)
    got = parse_references(text[a:b], offset=a)
    assert [r.authors[0].family for r in got] == [f"Lund{c}" for c in "ABCDEF"]


def test_a_numbered_list_whose_wrapped_lines_open_like_names_stays_one_run():
    from docpluck.references import _references_spans

    # every other entry wraps its author list: the wrapped line opens like an author-year entry
    entries = "".join(
        f"{n}. Lund{n} K, Ortiz M, Quinn P, Ashby T,"
        + (f"\nBexley H, Tallis P. 2008 Rivers {n}." if n % 2 else f" Bexley H. 2008 Rivers {n}.")
        + f" Hydrol. Lett. {n}, 1-9.\n"
        for n in range(1, 11))
    text = "Introduction\n\nRivers matter [1].\n\nAppendix\n\nTable A1 shows river depths.\n\n" + entries
    doc = _fake_doc(text, [("introduction", "Introduction"), ("appendix", "Appendix")])
    (a, b), = _references_spans(doc)
    assert [r.number for r in parse_references(text[a:b], offset=a)] == list(range(1, 11))


def test_volumes_ending_lines_are_not_read_as_the_next_entry_number():
    # author-year entries wrapped so that lines end in a volume number ("... Psychol. 12.")
    text = ("References\nLund, K., & Ortiz, M. (2019). Rivers in spring. J. Hydrol. Psychol.\n12.\n"
            "Quinn, P. (2017). Roads in autumn. Road Res. Lett. 47.\n"
            "Ashby, T. N. (2020). Bridges. Bridge Sci. 3.\n"
            "Bexley, H. (2001). Lakes. Lake Lett. 88.\n")
    refs = parse_references(text)
    assert [r.authors[0].family for r in refs] == ["Lund", "Quinn", "Ashby", "Bexley"]
