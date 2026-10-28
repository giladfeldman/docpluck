"""An APA reference whose author is a group, a bare surname or a spelled-out
first name opens its own entry.

Rasterised 2026-10-27, each page prints these as separate hanging-indent
entries; normalization glued each onto the entry above:
10.1111/jasp.12453 p28 ("Public Health Oregon. (2015).", "Public Policy
Polling. (2013)."), 10.1016/j.jesp.2012.10.011 p5 ("Ladewski (2010)."),
10.1016/j.jesp.2013.11.010 p8 ("LaRiccia, Michael V. (2005)."),
10.1177/0956797615601103 p9 ("U.S. Centers for Disease Control and
Prevention. (2015).").
"""
from __future__ import annotations

import pytest

from docpluck.normalize import NormalizationLevel, normalize_text

_REFS = (
    "Body text of the article ends here.\n\nReferences\n"
    "Lewandowsky, S., Oberauer, K., & Gignac, G. E. (2013). NASA faked the moon landing.\n"
    "Psychological Science, 24, 622-633. doi: 10.1177/0956797612457686\n"
    "Pfau, M., & Van Bockern, S. (1994). The persistence of inoculation in conferring resistance\n"
    "to smoking initiation. Human Communication Research, 20, 413-430. doi: 10.1111/j.1468-2958.1994.tb00329.x\n"
    "Public Health Oregon. (2015). Nonmedical vaccination exemptions. Retrieved from:\n"
    "https://public.health.oregon.gov/exemption.aspx\n"
    "Ladewski (2010). Preserving a racial hierarchy. Michigan Law Review, 10, 577-601.\n"
    "LaRiccia, Michael V. (2005). Black mane. Suffolk, UK: One Time Press.\n"
    "Wood, M. J., Douglas, K. M., & Sutton, R. M. (2012). Dead and alive: Beliefs in\n"
    "contradictory conspiracy theories. Social Psychological and Personality Science, 3, 767-773.\n"
)


def test_group_and_bare_surname_authors_start_entries():
    out, _ = normalize_text(_REFS, NormalizationLevel.academic)
    lines = out.split("\n")
    for start in ("Public Health Oregon. (2015).", "Ladewski (2010).", "LaRiccia, Michael V. (2005)."):
        assert any(ln.startswith(start) for ln in lines), (start, lines)
    # Wrapped lines still join their entry.
    assert any(ln.startswith("Pfau, M.") and ln.rstrip().endswith("tb00329.x") for ln in lines), lines
    assert any(ln.startswith("Wood, M. J.") and "contradictory conspiracy theories" in ln for ln in lines)


def test_unfinished_entry_keeps_its_continuation():
    text = (
        "Body text of the article ends here.\n\nReferences\n"
        "Smith, A. B. (2001). A title. Journal of Things, 1, 1-2.\n"
        "Jones, C. D. (2002). Another title that the page wraps in the\n"
        "Theories of mind and society (1999). Its subtitle. Journal of Things, 2, 3-4.\n"
        "Brown, E. F. (2003). A third title. Journal of Things, 3, 5-6.\n"
        "Green, G. H. (2004). A fourth title. Journal of Things, 4, 7-8.\n"
        "White, I. J. (2005). A fifth title. Journal of Things, 5, 9-10.\n"
    )
    out, _ = normalize_text(text, NormalizationLevel.academic)
    assert any(ln.startswith("Jones, C. D.") and "Theories of mind" in ln for ln in out.split("\n")), out
    assert not any(ln.startswith("Theories of mind") for ln in out.split("\n")), out


@pytest.mark.parametrize("key,start", [
    ("10.1111__jasp.12453", "Public Health Oregon. (2015)."),
    ("10.1016__j.jesp.2012.10.011", "Ladewski (2010)."),
    ("10.1177__0956797615601103", "U.S. Centers for Disease Control and Prevention. (2015)."),
])
def test_real_entries_are_separate(key, start):
    from docpluck.testing.corpus import custody_path
    from docpluck.render import render_pdf_to_markdown
    p = custody_path("fulltext", key + ".pdf")
    if not p.is_file():
        pytest.skip(f"{key} not held")
    md = render_pdf_to_markdown(p.read_bytes())
    md = md[0] if isinstance(md, tuple) else md
    assert any(ln.startswith(start) for ln in md.split("\n")), start


def test_a_wrapped_author_initial_does_not_open_an_entry():
    # 10.1525/collabra.77608 references: an author list wrapped after an
    # initial ("... & Ruiz, J." / "G. (2015). ...", "... Ardoin, S." /
    # "P., Shoots-Reinhard, ...") is one entry; the wrapped initial is not a
    # group author.
    text = (
        "Body text of the article ends here.\n\nReferences\n"
        "Garcia-Retamero, R., Andrade, A., Sharit, J., & Ruiz, J.\n"
        "G. (2015). Is numeracy related to health? Medical Decision Making, 35(4), 501-511.\n"
        "Peters, E., Tompkins, M. K., Knoll, M. A. Z., Ardoin, S.\n"
        "P., Shoots-Reinhard, B., & Meara, A. S. (2019). Despite high numeracy. PNAS, 116, 1-2.\n"
        "Reyna, V. F., Nelson, W. L., Han, P. K., & Dieckmann, N.\n"
        "F. (2009). How numeracy influences risk comprehension. Psychological Bulletin, 135, 943-973.\n"
        "U.S. Centers for Disease Control and Prevention. (2015). Measles cases. Atlanta, GA.\n"
    )
    out, _ = normalize_text(text, NormalizationLevel.academic)
    lines = out.split("\n")
    assert any(ln.startswith("Garcia-Retamero") and "G. (2015)" in ln for ln in lines), lines
    assert any(ln.startswith("Peters, E.") and "Shoots-Reinhard" in ln for ln in lines), lines
    assert any(ln.startswith("Reyna, V. F.") and "F. (2009)" in ln for ln in lines), lines
    assert any(ln.startswith("U.S. Centers for Disease") for ln in lines), lines


def test_a_wrapped_journal_line_ending_in_the_year_stays_with_its_entry():
    # 10.1038/s41467-023-42320-4 (Nature style): "3. Varatharaj, A. et al. ...
    # surveillance study." / "Lancet Psychiatry 7, 875-882 (2020)." is one
    # entry; the journal line is not an author-year start.
    text = (
        "Body text of the article ends here.\n\nReferences\n"
        "1. Smith, A. et al. A first study of things. Nature 1, 1-2 (2019).\n"
        "2. Jones, B. et al. A second study of things across a wrapped line of the\n"
        "page. Science 2, 3-4 (2020).\n"
        "3. Varatharaj, A. et al. Neurological complications of COVID-19 in 153 patients: a UK-wide surveillance study.\n"
        "Lancet Psychiatry 7, 875-882 (2020).\n"
        "4. Brown, C. et al. A fourth study. Cell 4, 5-6 (2021).\n"
    )
    out, _ = normalize_text(text, NormalizationLevel.academic)
    lines = out.split("\n")
    assert any(ln.startswith("3. Varatharaj") and "Lancet Psychiatry 7" in ln for ln in lines), lines
    assert not any(ln.startswith("Lancet Psychiatry") for ln in lines), lines


def test_an_initialism_below_a_complete_doi_is_not_its_tail():
    # 10.1177/0956797615601103 p9: "... doi:10.1016/j.appet.2014.06.108" then
    # the next entry "U.S. Centers for Disease Control and Prevention. (2015)."
    # S6u (the URL/DOI line-break join) glued "U.S." onto the DOI.
    from docpluck.normalize import _rejoin_broken_urls
    text = ("Appetite, 82, 8-15. doi:10.1016/j.appet.2014.06.108\n"
            "U.S. Centers for Disease Control and Prevention. (2015). National death index.")
    assert _rejoin_broken_urls(text) == text
    # A real DOI tail on the next line is still joined.
    cut = "Appetite, 82, 8-15. doi:10.1016/j.appet.2014.\n06.108\nNext entry."
    assert _rejoin_broken_urls(cut) == "Appetite, 82, 8-15. doi:10.1016/j.appet.2014.06.108\nNext entry."
