"""W0v: a hyphen inside a DOI that pdftotext's dehyphenation removed is restored.

10.1001/jamanetworkopen.2023.39337 prints ``doi:10.3233/NHA-`` / ``170036``
(ref 5) and ``doi:10.1007/s00592-019-`` / ``01328-3`` (ref 21) across a line
end (rasterized 2026-10-27). pdftotext's default mode joins a line ending in a
hyphen to the next line and drops the hyphen, so the text channel says
``10.3233/NHA170036`` and ``10.1007/s00592-01901328-3``: DOIs that do not
resolve. pdfplumber's words keep the ``10.3233/NHA-`` fragment.

The gate mirrors W0u: restore only where the layout holds the DOI fragment
ending in ``-``, a word that opens with (or is opened by) the glued
continuation, never the glued form itself, and one fragment per restored site.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from docpluck.normalize import recover_doi_hyphens_via_layout


def _layout(*words):
    page = SimpleNamespace(words=tuple({"text": w} for w in words))
    return SimpleNamespace(pages=(page,))


def test_a_doi_hyphen_at_a_line_end_is_restored():
    text = "Aging. 2018;4(4):345-353. doi:10.3233/NHA170036\n6. Liu D"
    lay = _layout("Aging.", "2018;4(4):345-353.", "doi:10.3233/NHA-", "170036", "6.", "Liu", "D")
    n = [0]
    assert recover_doi_hyphens_via_layout(text, lay, n) == (
        "Aging. 2018;4(4):345-353. doi:10.3233/NHA-170036\n6. Liu D"
    )
    assert n[0] == 1


def test_a_glued_word_line_from_a_pdf_without_space_glyphs():
    text = "Acta Diabetol. 2019;56(8):947-954. doi:10.1007/s00592-01901328-3\n22. Zhen J"
    lay = _layout(
        "skeletalmusclewithtype2diabetesinadults.ActaDiabetol.2019;56(8):947-954.doi:10.1007/s00592-019-",
        "01328-3",
        "22.ZhenJ,LiuS",
    )
    assert recover_doi_hyphens_via_layout(text, lay, None) == (
        "Acta Diabetol. 2019;56(8):947-954. doi:10.1007/s00592-019-01328-3\n22. Zhen J"
    )


def test_a_url_doi_fragment_with_a_continuation_that_runs_on():
    text = "Emotion, 30(2), 1-5. https://doi.org/10.1007/s110316-9025-x McNulty"
    lay = _layout("https://doi.org/10.1007/s11031-", "6-9025-x", "McNulty,")
    assert recover_doi_hyphens_via_layout(text, lay, None) == (
        "Emotion, 30(2), 1-5. https://doi.org/10.1007/s11031-6-9025-x McNulty"
    )


def test_the_page_printing_the_glued_doi_is_never_touched():
    text = "doi:10.3233/NHA170036 and doi:10.3233/NHA170036"
    lay = _layout("doi:10.3233/NHA-", "170036", "doi:10.3233/NHA170036")
    assert recover_doi_hyphens_via_layout(text, lay, None) == text


def test_no_fragment_no_rewrite():
    text = "doi:10.3233/NHA170036"
    lay = _layout("doi:10.3233/NHA170036")
    assert recover_doi_hyphens_via_layout(text, lay, None) == text


def test_more_glued_sites_than_fragments_is_refused():
    text = "doi:10.1037/00223514.1 and doi:10.1037/00223514.2"
    lay = _layout("doi:10.1037/0022-", "3514.1", "3514.2")
    assert recover_doi_hyphens_via_layout(text, lay, None) == text


def test_a_continuation_the_layout_does_not_hold_is_refused():
    text = "doi:10.3233/NHA170036"
    lay = _layout("doi:10.3233/NHA-", "999999")
    assert recover_doi_hyphens_via_layout(text, lay, None) == text


def test_a_url_that_is_not_a_doi_is_never_touched():
    # the page hyphenates the host name `creative-commons` at a line end;
    # whether that hyphen is part of the URL is unknowable, so it stays as read
    text = "see http://creativecommons.org/licenses/by/4.0"
    lay = _layout("http://creativecom-", "mons.org/licenses/by/4.0")
    assert recover_doi_hyphens_via_layout(text, lay, None) == text


def test_a_hyphen_already_in_the_text_is_left_alone():
    text = "doi:10.3233/NHA-170036"
    lay = _layout("doi:10.3233/NHA-", "170036")
    assert recover_doi_hyphens_via_layout(text, lay, None) == text


def test_no_layout_is_a_no_op():
    assert recover_doi_hyphens_via_layout("doi:10.3233/NHA170036", None, None) == (
        "doi:10.3233/NHA170036"
    )


@pytest.mark.parametrize(
    "key, printed",
    [
        ("10.1001__jamanetworkopen.2023.39337", ["10.3233/NHA-170036", "10.1007/s00592-019-01328-3"]),
        ("10.1080__02699931.2024.2434156", [
            "10.1037/0022-3514.67.3.357",
            "10.1007/s11031-006-9025-x",
            "10.1146/annurev-psych-010418-103305",
        ]),
    ],
)
def test_reference_dois_survive_the_render(key, printed):
    from docpluck.render import render_pdf_to_markdown
    from docpluck.testing.corpus import custody_path

    md = render_pdf_to_markdown(custody_path("fulltext", f"{key}.pdf").read_bytes())
    for doi in printed:
        assert doi in md, doi
