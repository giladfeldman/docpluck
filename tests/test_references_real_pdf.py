"""docpluck.references on real corpus papers (one per citation family).

Every expectation was read off the rendered reference pages (110 dpi rasters),
not off docpluck's own text: the entry count and numbering, and the printed
volume / page / container of the entries checked. Only those field values are
asserted here; no entry text is copied.
"""

from __future__ import annotations

import pytest

DISABLE_CAMELOT = True

from docpluck import extract_citations, extract_references
from docpluck.testing import require_corpus_pdf


@pytest.mark.parametrize("rel,count", [
    ("vancouver/bmc_med_1.pdf", 38),
    ("nature/nat_comms_4.pdf", 53),
])
def test_numbered_list_is_complete_and_in_order(rel, count):
    refs = extract_references(require_corpus_pdf(rel).read_bytes())
    assert [r.number for r in refs] == list(range(1, count + 1))


def test_back_matter_after_the_last_numbered_entry_is_cut():
    # The publisher's note and the journal's advert follow entry 38 on the page.
    refs = extract_references(require_corpus_pdf("vancouver/bmc_med_1.pdf").read_bytes())
    last = refs[-1]
    assert (last.year, last.volume, last.first_page) == ("2022", "9", "1027000")
    assert "Publisher" not in last.raw_text
    # printed "e153-639" (Vancouver elides the repeated digits; the scorer wants it as printed)
    assert (refs[2].first_page, refs[2].last_page) == ("e153", "639")


def test_nature_entries_keep_volume_and_pages():
    refs = extract_references(require_corpus_pdf("nature/nat_comms_4.pdf").read_bytes())
    by_num = {r.number: r for r in refs}
    assert (by_num[52].volume, by_num[52].first_page, by_num[52].last_page, by_num[52].year) == (
        "112", "1069", "1079", "2020")
    assert (by_num[53].volume, by_num[53].first_page, by_num[53].year) == ("15", "364", "2014")


def test_apa_list_ends_at_its_last_entry_and_reads_elocators():
    a = extract_citations(require_corpus_pdf("apa/chen_2021_jesp.pdf").read_bytes())
    refs = a.references
    assert a.style == "author_year"
    last = refs[-1]
    # the author biographies that follow the list are not part of the last entry
    assert (last.authors[0].family, last.year, last.container, last.volume) == (
        "Zwaan", "2018", "Behavioral and Brain Sciences", "41")
    by_first = {(r.authors[0].family, r.year): r for r in refs if r.authors}
    open_sc = by_first[("Open", "2015")]
    assert (open_sc.container, open_sc.volume, open_sc.issue, open_sc.first_page) == (
        "Science", "349", "6251", "aac4716")
    pohl = by_first[("Pohl", "2007")]
    assert (pohl.container, pohl.volume, pohl.first_page, pohl.last_page) == ("Social Cognition", "2", "14", "31")
    # sanity bounds (not read off the page): nearly every entry is cited, nearly every citation resolves
    assert len(a.uncited_reference_ids) <= len(refs) * 0.1
    assert len(a.orphan_citations) <= len(a.citations) * 0.05
