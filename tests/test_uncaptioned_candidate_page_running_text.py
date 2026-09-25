"""An uncaptioned "grid" that is its page's own running text is deduplicated --
and a grid carrying statistics never is.

Why this file exists (2026-09-25). Kept uncaptioned candidates (see
test_uncaptioned_tables_are_kept_and_labelled.py) re-emit their cells in a
rendered appendix -- a text channel outside every furniture and metadata filter
the body gets. The canary caught it on 10.1177/01461672251327169 p1: candidate
u1 was the "Received August 22, 2023; revision accepted February 17, 2025"
history line (stripped from the body as metadata) plus the Introduction's first
sentence (already in the body).

`extract_structured._candidate_is_page_running_text` drops such a candidate as a
duplicate, recorded as `camelot_candidate_is_page_running_text`, ONLY when no
cell carries a statistic, every line of every cell is on the same page of the
text channel, and most words sit on lines long enough to be running text.
`_candidate_is_page_masthead` drops a page-1 grid with no statistic that the
body's own masthead test would strip (>= 2 hard-marker lines), recorded as
`camelot_candidate_is_page_masthead` -- the same page-1 region sometimes comes
back from Camelot as the title block instead of the prose grid.

Measured before shipping, over the 70 corpus papers holding a no-statistics
candidate (341 candidates; 185 carry a statistic once DOIs/URLs are blanked):
the two rules fire on 80 (79 running text, 1 masthead), on 0 of the 185. All 80
read as furniture or running text (mastheads, page headers, title blocks, figure
pages, prose columns, reference fragments); four rasterized to confirm. The 6
candidates whose only 'statistic' was a DOI are citation lines, reference-list
fragments and title blocks, none a table. A variant accepting
short lines that continue each other fired on 96 and removed REAL text tables
(the replication-taxonomy table in chandrashekar_2023_mp p47, the CRediT table in
maier_2023_collabra p17), so it was rejected.
"""

import pytest

from docpluck.extract_structured import extract_pdf_structured
from docpluck.render import render_pdf_to_markdown
from docpluck.testing import require_corpus_pdf

pytest.importorskip("camelot", reason="camelot not installed (pip install docpluck[all])")

_EVENT = "camelot_candidate_is_page_running_text"


def _candidates(r):
    return [t for t in r["tables"] if t.get("caption_status") == "uncaptioned_candidate"]


def _text(t) -> str:
    return " ".join((c.get("text") or "") for c in t.get("cells") or [])


# ---- one paper, both arms ---------------------------------------------------
# 10.1001/jamanetworkopen.2023.16111: the journal masthead + a section heading is
# gridded on p2 and p8 (furniture), and a real "Outcome / beta (95% CI)" results
# grid on p7 has no caption. pdftotext prints that results grid word for word, so
# "the words are on the page" alone WOULD drop it -- the statistics veto is what
# keeps it.

@pytest.fixture(scope="module")
def jama_open_11():
    return extract_pdf_structured(require_corpus_pdf("ama/jama_open_11.pdf").read_bytes())


def test_masthead_grids_are_deduplicated_and_recorded(jama_open_11):
    r = jama_open_11
    left = [t for t in _candidates(r) if "JAMA Network Open |" in _text(t)]
    assert not left, f"masthead grids still kept: {[(t['id'], t['page']) for t in left]}"
    pages = r["fallback_details"].get(_EVENT, {})
    assert "p2" in pages and "p8" in pages, (
        f"the dedupe did not run or was not recorded: {r['fallback_details']}"
    )


def test_a_results_grid_the_page_text_repeats_is_still_kept(jama_open_11):
    kept = [t for t in _candidates(jama_open_11) if "95% CI" in _text(t) and t["page"] == 7]
    assert kept, (
        "the uncaptioned beta (95% CI) results grid on p7 was dropped -- a "
        "statistical table is not a duplicate because pdftotext linearized it. "
        f"candidates: {[(t['id'], t['page'], _text(t)[:60]) for t in _candidates(jama_open_11)]}"
    )


# ---- real uncaptioned tables named by the release review: all must stay -------

@pytest.mark.parametrize("rel,page,marker", [
    ("chicago-ad/demography_3.pdf", 29, "Coeff. (SE)"),       # regression table
    ("apa/chandrashekar_2023_mp.pdf", 45, "Odds ratio"),      # logistic regression
    ("ama/jama_open_4.pdf", 7, "HR (95% CI)"),                # hazard ratios
])
def test_real_uncaptioned_tables_are_kept(rel, page, marker):
    r = extract_pdf_structured(require_corpus_pdf(rel).read_bytes())
    kept = [t for t in _candidates(r) if t["page"] == page and marker in _text(t)]
    assert kept, (
        f"{rel} p{page}: the uncaptioned table carrying {marker!r} is gone. "
        f"page events: {r['fallback_details'].get(_EVENT)}"
    )


# ---- the flagged paper: the history line reaches no output ------------------

def test_publication_history_line_is_not_re_emitted():
    """10.1177/01461672251327169 p1. The body strips this line as metadata; the
    candidate grid was the only thing putting it back into the document."""
    md = render_pdf_to_markdown(
        require_corpus_pdf("apa/ip_feldman_2025_pspb.pdf").read_bytes()
    )
    assert "revision accepted February 17, 2025" not in md
    # whichever page-1 grid Camelot returns, its masthead lines stay out too
    assert "Article reuse guidelines" not in md
    assert "by the Society for Personality" not in md
    # the sentence the grid duplicated is still in the body, once, where it belongs
    assert md.count("Our first goal was to conduct an") == 1


def test_a_page_one_masthead_grid_is_deduplicated_and_recorded():
    """10.1177/00031224241253268 p1: journal name, "2024, Vol. 89(4) 708-734",
    "(c) The Author(s) 2024", a DOI -- the masthead the body strips. Its only
    'statistic' is the DOI, which is why the guard is asked with DOIs blanked."""
    r = extract_pdf_structured(require_corpus_pdf("asa/am_sociol_rev_3.pdf").read_bytes())
    left = [t for t in _candidates(r) if t["page"] == 1 and "The Author(s)" in _text(t)]
    assert not left, f"page-1 masthead grid still kept: {[t['id'] for t in left]}"
    assert "p1" in r["fallback_details"].get("camelot_candidate_is_page_masthead", {}), (
        f"the masthead dedupe did not run or was not recorded: {r['fallback_details']}"
    )
