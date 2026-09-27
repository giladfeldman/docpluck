"""A prose rejection must never leave a caption with LESS than it had (v2.4.134).

`extract_structured` rejects a capture candidate that reads as running body prose
(`whitespace.grid_is_body_prose`) so a paragraph of Discussion cannot outrank a real
table on shape alone. The first version rejected UNCONDITIONALLY, and on
`10.5465/amc.2022.0006` — a management review whose tables are legitimately built
from sentence-length phrases — that dropped **Table 1 to 0 cells and 0 raw_text and
Table 4 to 0 cells and 0 raw_text**, destroying 70 cells and 2,008 characters of real
published content. A guard that substitutes nothing is not a guard; it is a deletion
wearing a guard's name.

The rejection is therefore PROVISIONAL: the candidate is stashed and put back unless
a replacement actually materialises, recording
`table_prose_rejection_reverted_no_replacement` when it does.

WHY THIS TEST EXISTS RATHER THAN A UNIT TEST OF THE BRANCH. On 2026-08-19 the
backstop was measured to fire **0 times in the 26-paper baseline**, because the
header-row veto spared amc's tables before the rejection was even considered — a
production path with no observed positive, which this project treats as unshipped.
Tightening the veto to require a row NAMING AT LEAST TWO COLUMNS (a reviewer finding)
moved amc Table 1 back onto the rejection path, and the backstop now has a real
positive on a real DOI. That is what this test pins: not that the branch computes,
but that the wiring carries it end to end and the content survives.

Re-runnable: `python tools/diag/table_capture_guard_diff.py --isolate prose_guard`.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from docpluck.extract_structured import extract_pdf_structured  # noqa: E402


def _amc_pdf() -> Path | None:
    """Locate the paper through article-finder, the sole custodian."""
    try:
        from tools.diag._corpus import baseline_corpus
    except Exception:
        return None
    try:
        for key, path in baseline_corpus():
            if "amc.2022.0006" in key:
                return path
    except SystemExit:
        return None  # custodian unavailable on this machine
    return None


@pytest.fixture(scope="module")
def amc_result():
    pdf = _amc_pdf()
    if pdf is None or not pdf.exists():
        pytest.skip("10.5465/amc.2022.0006 not resolvable from article-finder here")
    return extract_pdf_structured(pdf.read_bytes())


def _table(result, label):
    return next((t for t in result["tables"] if t.get("label") == label), None)


def _populated(table) -> int:
    return sum(1 for c in (table.get("cells") or []) if (c.get("text") or "").strip())


@pytest.mark.xfail(
    strict=True,
    reason=(
        "2026-09-28 (2.4.146): the backstop has NO real positive on this paper any more, "
        "and that is the correct outcome. It used to fire because the caption-only fallback "
        "shipped Table 1 EMPTY (a caption label alone on its line ended the body walk), so the "
        "revert put the rejected candidate back -- and that candidate's 5 cells were body "
        "prose from BELOW the table (`CURATION PROCESS AND`, `principles directly applicable "
        "to managerial practice`), checked on the rasterized p2. With the lone-label fix the "
        "fallback now carries the table's own Source column, so the rejection stands. "
        "strict=True: this goes red the day the backstop fires here again, which would mean "
        "the fallback lost Table 1's text. A real positive elsewhere is owed (TODO.md)."
    ),
)
def test_the_backstop_actually_fires_on_a_real_paper(amc_result):
    """A guard nobody has watched work is a guard nobody can trust.

    If this goes to zero, the revert path has become unreachable again — which is
    exactly the state it was found in on 2026-08-19 — and the assertions below stop
    proving anything about it.
    """
    fallbacks = amc_result.get("fallbacks") or {}
    assert fallbacks.get("table_prose_rejection_reverted_no_replacement", 0) >= 1, (
        "the provisional-rejection backstop never fired on the paper it was built "
        f"for; fallbacks were {sorted(fallbacks)}"
    )


def test_the_qualitative_review_tables_keep_their_content(amc_result):
    """The content the unconditional rejection destroyed."""
    t1, t4 = _table(amc_result, "Table 1"), _table(amc_result, "Table 4")
    assert t1 is not None and t4 is not None
    # Table 1 (p2) prints a Source column and a Definition column. What reaches the
    # consumer must be the TABLE: the five sources, and none of the body prose below
    # it. Until 2.4.146 this asserted ">= 5 cells", and the 5 cells it was satisfied
    # by were that body prose (rasterized p2, 2026-09-28) -- a pin on the defect.
    t1_text = " ".join(
        [t1.get("raw_text") or ""] + [c.get("text") or "" for c in (t1.get("cells") or [])]
    )
    for source in ("Davis (1973)", "Carroll (1979)", "Wood (1991)",
                   "McWilliams and Siegel (2001)", "Matten and Moon (2008)"):
        assert source in t1_text, f"Table 1 lost its source row {source!r}"
    for prose in ("CURATION PROCESS", "principles directly applicable"):
        assert prose not in t1_text, f"Table 1 carries body prose {prose!r}"
    assert len((t4.get("raw_text") or "")) >= 1500, (
        f"Table 4's raw_text collapsed to {len(t4.get('raw_text') or '')} chars "
        "(it carries ~2,008 in a healthy run)"
    )
    assert _populated(t4) >= 60, f"Table 4 lost cells: {_populated(t4)}"


def test_no_table_is_emitted_empty_on_both_channels(amc_result):
    """The invariant the backstop exists to hold: never trade content for emptiness.

    A caption may legitimately render as a caption-only stub, but not as a stub with
    NEITHER cells NOR raw_text when a candidate was available and rejected.
    """
    rejected = (amc_result.get("fallbacks") or {}).get(
        "table_candidate_rejected_as_body_prose", 0
    )
    if not rejected:
        pytest.skip("no candidate was rejected on this run; nothing to hold")
    starved = [
        t.get("label")
        for t in amc_result["tables"]
        if _populated(t) == 0 and not (t.get("raw_text") or "").strip()
    ]
    assert not starved, f"tables left with no cells AND no raw_text: {starved}"
