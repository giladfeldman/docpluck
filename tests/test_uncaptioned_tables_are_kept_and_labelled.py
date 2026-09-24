"""A grid no caption claims is KEPT and LABELLED, never silently dropped.

Why this file exists (2026-09-24). `extract_structured` discarded every Camelot
grid on a page without a detected caption with a bare `continue` — no event, no
count — justified in a comment as "rare in the APA corpus", never measured. On
Nature-family papers it was not rare: their `Table 1 |` captions were invisible,
so real statistical tables went with it.

Owner directive, 2026-09-24: "best to retain information and not drop. if unsure
what that is - we keep but label it accordingly."

So such a grid is now kept with `caption_status="uncaptioned_candidate"` (label
and caption None), counted as `camelot_table_kept_without_caption`, and rendered
in its own clearly labelled section — never anchored beside a real table. The
label is honest about the uncertainty: on nature/nat_comms_1.pdf the two
candidates are the title block (p1) and a column of body prose (p6), not tables.
"""

import pytest

from docpluck.extract_structured import extract_pdf_structured
from docpluck.render import RenderReport, render_pdf_to_markdown
from docpluck.telemetry import fallback_scope
from docpluck.testing import require_corpus_pdf

pytest.importorskip("camelot", reason="camelot not installed (pip install docpluck[all])")

# Prints no table at all; Camelot finds grids on p1 (title block) and p6 (prose).
_PAPER = "nature/nat_comms_1.pdf"   # 10.1038/s41467-023-43885-w


@pytest.fixture(scope="module")
def paper() -> bytes:
    return require_corpus_pdf(_PAPER).read_bytes()


@pytest.fixture(scope="module")
def structured(paper):
    with fallback_scope() as fb:
        r = extract_pdf_structured(paper)
    return r, fb


def test_uncaptioned_grids_are_kept_and_labelled(structured):
    r, fb = structured
    cands = [t for t in r["tables"] if t.get("caption_status") == "uncaptioned_candidate"]
    assert cands, (
        "Camelot's grids on this paper were dropped again -- the silent `continue` "
        f"is back. tables={[(t.get('id'), t.get('caption_status')) for t in r['tables']]}"
    )
    for t in cands:
        assert t["label"] is None and t["caption"] is None, t["id"]
        assert t["id"].startswith("u"), f"candidate id collides with the t<N> scheme: {t['id']}"
    # counted, one event per kept grid -- a keep that is not recorded is a silent change
    assert fb.counters.get("camelot_table_kept_without_caption") == len(cands), fb.counters


def test_every_pdf_table_states_its_caption_status(structured):
    r, _ = structured
    for t in r["tables"]:
        assert t.get("caption_status") in ("matched", "uncaptioned_candidate"), t
        # a labelled table is a matched one, and only a labelled one
        assert (t.get("label") is not None) == (t["caption_status"] == "matched"), t


def test_render_puts_candidates_in_their_own_labelled_section(paper):
    report = RenderReport()
    md = render_pdf_to_markdown(paper, report=report)
    head = "## Uncaptioned table candidates (unverified)"
    assert head in md, "kept candidates are missing from the rendered document"
    assert "### Uncaptioned candidate u1" in md
    # never spliced into the body next to a caption
    before = md.split(head, 1)[0]
    assert "Uncaptioned candidate" not in before, "a candidate was placed inline in the body"
