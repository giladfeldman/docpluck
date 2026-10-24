"""The reference list is found when its heading is German, absent, or sits
below an abbreviation list.

Measured on a held-out benchmark (30 real biomedical papers, docpluck 2.4.154):
six papers came back with no ``references`` section. Three mechanisms, each
pinned here on short synthetic text shaped like the real output, and each with
its negative control so the fix cannot turn ordinary body text into a
bibliography:

1. ``Literatur`` (German) was not a references heading.
2. A numbered list ``[1] A. B. Carter, ... Science 2004, 306, 101.`` printed
   with NO heading after the ``Keywords`` / ``Received:`` lines was swallowed
   into the ``keywords`` section.
3. A ``References`` heading printed straight after an abbreviation list
   (``RT`` / ``reaction time`` ...) was rejected as a table column
   header, because the short blank-separated lines above it look like header
   cells.
"""

from docpluck.sections import SectionLabel, extract_sections


def _labels(text):
    return [s.canonical_label for s in extract_sections(text=text, source_format="pdf").sections]


def _section(text, label):
    for s in extract_sections(text=text, source_format="pdf").sections:
        if s.canonical_label is label:
            return s
    return None


_BODY = (
    "Title of the paper\n\n"
    "Abstract\n\nWe studied a thing and found a result.\n\n"
    "Introduction\n\nThe thing matters for many reasons. We explain them here.\n\n"
    "Methods\n\nWe measured the thing in 40 samples.\n\n"
    "Results\n\nThe thing was larger than expected.\n\n"
    "Discussion\n\nThe thing is now better understood.\n\n"
)


# --- 1. German heading -------------------------------------------------------

def test_literatur_heading_starts_the_references_section():
    text = _BODY + (
        "Literatur\n"
        "1. Becker T, Huber L, Maier S et al (2006) Wirksamkeit einer Schulung. Notfall Rettungsmed 98:110-114\n"
        "2. Baker H, Chen L (2019) Another study. Resuscitation 12:44-50\n"
    )
    refs = _section(text, SectionLabel.references)
    assert refs is not None, _labels(text)
    assert refs.heading_text == "Literatur"
    assert "Becker T" in refs.text


def test_literatur_inside_a_german_sentence_is_not_a_heading():
    text = _BODY.replace(
        "The thing is now better understood.",
        "Die Auswahl erfolgte basierend auf der aktuellen\n"
        "Literatur und nur wenige Bilder gingen in die Umfrage ein.",
    )
    assert SectionLabel.references not in _labels(text)


# --- 2. Unheaded numbered reference list ------------------------------------

_KEYWORDS_TAIL = (
    "Keywords thin films, surface chemistry, density functional theory\n"
    "Received: November 1, 2024\n"
    "Revised: January 30, 2025\n"
    "Published online: March 21, 2025\n\n"
)

_UNHEADED_LIST = (
    "[1] A. B. Carter, D. E. Fox, G. H. Lund, Science 2004, 306, 101.\n"
    "[2] J. K. Moreno, L. M. Ostrowski, N. P. Quist, R. S. Tan, J. Am. Chem. Soc. 2024, 146,\n"
    "12345.\n"
    "[3] T. U. Vance, W. X. Young, Proc. Natl. Acad. Sci 2015, 112, 2002.\n"
    "[4] Y. Z. Abbott, B. C. Diaz, Nano Lett. 2024, 4, 100001.\n"
)


def test_unheaded_numbered_list_after_keywords_is_the_reference_list():
    text = _BODY + _KEYWORDS_TAIL + _UNHEADED_LIST
    refs = _section(text, SectionLabel.references)
    assert refs is not None, _labels(text)
    assert refs.text.startswith("[1] A. B. Carter")
    kw = _section(text, SectionLabel.keywords)
    assert kw is not None and "Received: November 1, 2024" in kw.text
    assert "Carter" not in kw.text
    # universal coverage still holds
    doc = extract_sections(text=text, source_format="pdf")
    assert "".join(s.text for s in doc.sections) == text


def test_numbered_list_in_the_body_is_not_a_reference_list():
    """A numbered list of steps or items in a body section stays body text."""
    body_list = (
        "Methods\n\nThe protocol had four steps.\n\n"
        "[1] Participants read the instructions on the screen.\n"
        "[2] They rated each item on a seven-point scale.\n"
        "[3] They completed the attention check.\n"
        "[4] They were debriefed and paid.\n\n"
    )
    text = _BODY.replace("Methods\n\nWe measured the thing in 40 samples.\n\n", body_list)
    assert SectionLabel.references not in _labels(text)


def test_unheaded_list_is_not_added_when_a_references_heading_exists():
    """The fallback only fills a missing reference list; a headed one is untouched."""
    text = _BODY + "References\n\n" + _UNHEADED_LIST
    doc = extract_sections(text=text, source_format="pdf")
    refs = [s for s in doc.sections if s.canonical_label is SectionLabel.references]
    assert len(refs) == 1 and refs[0].heading_text == "References"


def test_two_numbered_entries_are_not_enough():
    two = "".join(_UNHEADED_LIST.splitlines(keepends=True)[:2])
    text = _BODY + _KEYWORDS_TAIL + two
    assert SectionLabel.references not in _labels(text)


# --- 3. References heading below an abbreviation list -----------------------

def test_references_heading_after_an_abbreviation_list_is_a_heading():
    text = _BODY + (
        "Appendix A.: Supplementary data\n"
        "Supplementary data to this article can be found online.\n\n"
        "Abbreviations\n\n"
        "ANOVA\n\n"
        "analysis of variance\n\n"
        "RT\n\n"
        "reaction time\n\n"
        "References\n\n"
        "[1]. Hartmann KL, Ortiz JP, Quinn RS, Sato M, Ulrich T, Varga E,\n"
        "Weber B, Statistics of a common condition, Circulation 149 (2024) e100.\n"
        "[2]. Smith J, Jones K, A second study, Nature 500 (2013) 12-19.\n"
    )
    refs = _section(text, SectionLabel.references)
    assert refs is not None, _labels(text)
    assert refs.heading_text == "References"
    appendix = _section(text, SectionLabel.appendix)
    assert appendix is not None and "Hartmann KL" not in appendix.text


def test_table_column_header_named_like_a_heading_stays_rejected():
    """The column-header guard still holds when the next line is a table cell,
    not a reference entry (amj Table 1: 'Study and Context / Feedback Directions /
    Findings')."""
    text = _BODY + (
        "Table 1\n\n"
        "Study and Context\n\n"
        "Feedback Directions\n\n"
        "Findings\n\n"
        "Field study of managers in a retail chain over two years\n\n"
    )
    labels = _labels(text)
    assert SectionLabel.results not in labels[labels.index(SectionLabel.discussion):]


# --- 4. "Literature Survey" is a literature review, not the bibliography -----

def test_literature_survey_heading_is_a_literature_review():
    text = _BODY.replace(
        "Methods\n\n",
        "LITERATURE SURVEY\n"
        "Rivera et al. (2023) classified retinal images with a convolutional network [26]. "
        "In this work, the images were taken from a public archive.\n\n"
        "Methods\n\n",
    )
    labels = _labels(text)
    assert SectionLabel.references not in labels, labels
    assert SectionLabel.literature_review in labels, labels
