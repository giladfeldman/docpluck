"""The v1.9.60 page gate: correct attribution, and never the last copy.

The gate shipped in v1.9.60 was blocked by a three-provider consult. Five
defects were scoped; this file pins the two that decide whether the gate is
safe, plus the seven form-feed sites that had to close before either could be
measured at all.

## 1. THE PAGE MAP WAS OFF BY ONE, ON HALF OF ALL BOUNDARIES

``_page`` was incremented AFTER a line was recorded, while pdftotext glues the
page separator to the FIRST LINE OF THE NEW PAGE. So the first line of page N
was filed under page N-1 -- and the first line of a page is exactly where a
running header sits.

Measured on a 6-page running header, the map came out ``[1, 1, 2, 3, 4, 5]``:
``max_per_page`` 2 instead of 1, so the once-per-page arm did NOT fire and all
six copies survived. The gate failed at its own purpose while staying live on
footers and on table content -- the two error directions it exists to separate.

Scope, over a 70-paper strided sample of the article repository
(``tools/diag/form_feed_page_attribution_census.py``)::

    form feeds total                          994
      alone on their line (HARMLESS)           70   7.0%
      glued, line not a 15-120 candidate      415  41.8%
      glued to a RECORDED candidate           509  51.2%   <- corrupts
      after content on the line                 0   0.0%

An independent 36-paper sample gave 1122/2218 (50.6%).

## 2. IT DELETED AN ARTICLE TITLE, EVERY COPY

``10.1001/jamanetworkopen.2023.39337`` (JAMA Network Open, 2023) prints
*"Effect of Time-Restricted Eating on Weight Loss in Adults With Type 2
Diabetes"* thirteen times: twelve running headers and, on page 1, the TITLE
BLOCK -- sitting between the article-type banner ``Original Investigation |
Nutrition, Obesity, and Exercise`` and the subtitle ``A Randomized Clinical
Trial`` plus the author list. The gate took all thirteen and the paper shipped
with no title. ``changes_made`` named nothing, so no consumer could see it.

CLAUDE.md rule 0g: a step that removes content "must refuse all-or-nothing per
run", and "deduplication is legitimate only when a copy demonstrably survives,
otherwise it is a deletion wearing a dedup's name".

**Neither of the two gates anyone would reach for can see this.** The corpus
idempotency test passes -- the deletion is perfectly idempotent, pass 1 and
pass 2 byte-identical with the title absent from both. The canary passes -- its
``--quick`` paper is byte-identical under both versions, and none of its 8
configured papers shows the signature. Both run honestly and are blind.

## 3. A CLEVERER SURVIVOR RULE WAS BUILT AND REFUTED

"Furniture travels with furniture": score each occurrence by how many of its
neighbouring lines are unique, keep the most content-like. It ties TWELVE
occurrences on the JAMA title and cannot pick it, and on
``10.1098/rsos.182237``'s genuine running footer it separates cleanly and picks
a copy sitting in the REFERENCES section. Wrong in both directions at once.
The surviving rule is the FIRST copy in document order, which is stable under
line removal and idempotent by construction (pass 2 sees one occurrence, which
fails the ``count >= 5`` floor).

Written 2026-08-28 against the unfixed working tree and watched fail.
"""

from __future__ import annotations

import pytest

from docpluck.extract import extract_pdf
from docpluck.normalize import (
    PAGE_BREAK,
    NormalizationLevel,
    _a1_stat_linebreak_repair,
    _strip_frontmatter_metadata_leaks,
    _strip_toc_dot_leader_block,
    keep_break_in_rejoin,
    normalize_text,
    page_break_residue,
)

from .conftest import pdf_available, pdf_path

_JAMA = ("articlerepo", "10.1001__jamanetworkopen.2023.39337.pdf")
_TITLE = "Effect of Time-Restricted Eating on Weight Loss in Adults With Type 2 Diabetes"

# A running header that is a 15-120 char candidate and trips none of the gate's
# content guards: no parenthesised year, fewer than 6 spaces, no terminal
# punctuation, no statistic.
_HEADER = "Journal of Measured Things Quarterly"


def _paginated(header: str, n_pages: int) -> str:
    """Text where the page separator is GLUED to the header, as pdftotext emits it.

    Page 1 carries no leading form feed, which is also what pdftotext does --
    the separator introduces each NEW page.
    """
    pages = []
    for i in range(n_pages):
        lines = [(PAGE_BREAK if i else "") + header]
        lines += [
            f"Body sentence {i}-{j} carrying ordinary prose for this page."
            for j in range(5)
        ]
        pages.append("\n".join(lines))
    return "\n".join(pages)


def _norm(text: str):
    out, report = normalize_text(text, level=NormalizationLevel.academic)
    assert isinstance(out, str), "normalize_text returns a TUPLE -- unpack it"
    return out, report


# ---------------------------------------------------------------------------
# 1. Page attribution
# ---------------------------------------------------------------------------

def test_a_glued_form_feed_attributes_its_line_to_the_NEW_page():
    """Six pages, one header each. Under the old map this scored 2-per-page."""
    out, _ = _norm(_paginated(_HEADER, 6))
    assert out.count(_HEADER) == 1, (
        "the once-per-page arm did not fire: the page map filed each page's "
        "FIRST line under the PREVIOUS page, so max_per_page came out 2"
    )


def test_the_body_is_untouched_while_the_header_goes():
    """Two-sided: the gate must remove furniture WITHOUT touching content."""
    out, _ = _norm(_paginated(_HEADER, 6))
    for i in range(6):
        assert f"Body sentence {i}-0" in out


def test_a_header_on_too_few_pages_is_left_alone():
    """Below the 5-page floor the line is table content, whatever its spacing."""
    out, _ = _norm(_paginated(_HEADER, 4))
    assert out.count(_HEADER) == 4, "4 distinct pages is under the furniture floor"


# ---------------------------------------------------------------------------
# 2. Rule 0g -- never the last copy
# ---------------------------------------------------------------------------

def test_the_last_surviving_copy_is_never_deleted():
    out, _ = _norm(_paginated(_HEADER, 12))
    assert out.count(_HEADER) == 1, (
        "rule 0g: a deleting step must refuse all-or-nothing per run -- "
        "deduplication is legitimate only when a copy demonstrably survives"
    )


def test_the_copy_that_survives_is_the_FIRST_one():
    """A title block precedes the running headers derived from it."""
    text = _paginated(_HEADER, 8)
    out, _ = _norm(text)
    body = [l for l in out.split("\n") if l.strip()]
    assert body[0].strip() == _HEADER, "the first copy is the one to keep"


def test_the_strip_is_idempotent_because_one_copy_remains():
    """Pass 2 sees a single occurrence, which fails the ``count >= 5`` floor."""
    once, _ = _norm(_paginated(_HEADER, 9))
    twice, _ = _norm(once)
    assert once == twice


# ---------------------------------------------------------------------------
# 3. Per-line telemetry -- a deletion that cannot be named cannot be challenged
# ---------------------------------------------------------------------------

def test_the_report_names_the_line_it_removed():
    _out, report = _norm(_paginated(_HEADER, 7))
    stripped = {
        k: v for k, v in report.fallbacks.items()
        if k.startswith("repeated_line_stripped")
    }
    assert stripped, "the strip fired but recorded no event"
    assert sum(stripped.values()) == 6, "7 copies, 6 removed, 1 kept"
    details = report.fallback_details
    assert any(
        _HEADER[:120] in d for d in details.values()
    ), "a character delta cannot say WHAT vanished; the line must be named"


def test_the_report_records_that_a_copy_was_deliberately_kept():
    """Rule 0g's promise must be CHECKABLE from one document's report."""
    _out, report = _norm(_paginated(_HEADER, 7))
    assert report.fallbacks.get("repeated_line_last_copy_kept") == 1
    assert _HEADER[:120] in report.fallback_details["repeated_line_last_copy_kept"]


def test_the_recorded_arm_says_which_rule_decided():
    _out, report = _norm(_paginated(_HEADER, 7))
    assert "repeated_line_stripped:once_per_page" in report.fallbacks


# ---------------------------------------------------------------------------
# 4. The real paper -- the whole reason any of this is here
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not pdf_available(*_JAMA), reason="article repository not available")
def test_the_jama_article_keeps_its_title():
    with open(pdf_path(*_JAMA), "rb") as fh:
        raw, engine = extract_pdf(fh.read())  # TUPLE -- unpack, never measure whole
    assert len(raw) > 10_000, "extraction failed; this test would pass vacuously"
    assert engine == "pdftotext_default", (
        "PIN THE ENGINE, NOT THE FLAG. docpluck never varies the pdftotext flag, "
        "but extract_pdf DOES vary the engine on SMP Unicode input -- the flag is "
        "chosen by a person, the engine is chosen by the PDF."
    )
    assert raw.count(_TITLE) == 13, "the source prints the title 13 times"

    out, _report = _norm(raw)
    assert out.count(_TITLE) == 1, (
        "the article title was deleted in every copy -- the paper shipped with "
        "no title at all"
    )


@pytest.mark.skipif(not pdf_available(*_JAMA), reason="article repository not available")
def test_the_surviving_jama_copy_is_the_title_block_not_a_running_header():
    with open(pdf_path(*_JAMA), "rb") as fh:
        raw, _engine = extract_pdf(fh.read())
    assert len(raw) > 10_000
    out, _ = _norm(raw)
    lines = [l for l in out.split("\n")]
    idx = [i for i, l in enumerate(lines) if l.strip() == _TITLE]
    assert len(idx) == 1
    following = " ".join(lines[idx[0] + 1: idx[0] + 3])
    assert "A Randomized Clinical Trial" in following, (
        "the surviving copy must be the TITLE BLOCK -- the subtitle and author "
        "list follow it; a running header is followed by a section heading"
    )


@pytest.mark.skipif(not pdf_available(*_JAMA), reason="article repository not available")
def test_the_twelve_running_header_copies_are_still_removed():
    """Two-sided: keeping the title must not mean keeping the furniture."""
    with open(pdf_path(*_JAMA), "rb") as fh:
        raw, _engine = extract_pdf(fh.read())
    out, _ = _norm(raw)
    assert out.count(_TITLE) < 13, "the running headers must still go"


# ---------------------------------------------------------------------------
# 5. The form-feed sites -- nine in total, seven of them found this round
# ---------------------------------------------------------------------------

def test_a1_rejoins_a_statistic_without_eating_the_page_boundary():
    """All seven reachable A1 patterns spelled the gap ``\\s``, which matches U+000C."""
    text = "were significant, p\n" + PAGE_BREAK + "= .041 and so on"
    out = _a1_stat_linebreak_repair(text)
    assert out.count(PAGE_BREAK) == 1, "A1 swallowed the page boundary"


def test_a1_still_joins_within_a_page():
    """Page-scoping must not cost the repair it exists for."""
    out = _a1_stat_linebreak_repair("were significant, p\n= .041 and so on")
    assert "p = .041" in out


def test_a1_control_leaves_unrelated_prose_alone():
    text = "Ordinary prose with no statistics in it at all."
    assert _a1_stat_linebreak_repair(text) == text


def test_the_final_strip_keeps_a_trailing_page_boundary():
    """70 of 70 raw extractions end with one; ``str.strip()`` ate every one."""
    out, _ = _norm("Body prose for this document.\n" + PAGE_BREAK)
    assert out.count(PAGE_BREAK) == 1


def test_toc_strip_keeps_a_boundary_inside_a_dropped_paragraph():
    text = (
        "Table of Contents\nIntroduction ....... 1\n"
        + PAGE_BREAK
        + "Methods ______________________ 5\n\nBody text continues here.\n"
    )
    assert _strip_toc_dot_leader_block(text).count(PAGE_BREAK) == 1


def test_toc_strip_keeps_a_boundary_that_is_a_whole_paragraph():
    """``"\\f".strip()`` is ``""``, so the leading-blank trim took it."""
    text = (
        PAGE_BREAK
        + "\n\nTable of Contents\nIntro ______________________ 1\n\nBody text.\n"
    )
    assert _strip_toc_dot_leader_block(text).count(PAGE_BREAK) == 1


def test_toc_strip_control_returns_byte_identical_without_a_trigger():
    text = "Ordinary prose.\n" + PAGE_BREAK + "\nMore ordinary prose.\n"
    assert _strip_toc_dot_leader_block(text) == text


def test_frontmatter_leak_strip_keeps_the_boundary():
    lead = "Body prose sentence here. " * 30 + "\n"
    text = lead + PAGE_BREAK + "1234567\n" + lead
    out = _strip_frontmatter_metadata_leaks(text)
    assert "1234567" not in out, "the leak must still be dropped"
    assert out.count(PAGE_BREAK) == 1, "but not its page boundary"


def test_frontmatter_leak_strip_control_is_byte_identical():
    lead = "Body prose sentence here. " * 30 + "\n"
    text = lead + PAGE_BREAK + "An ordinary sentence of body text.\n" + lead
    assert _strip_frontmatter_metadata_leaks(text) == text


# ---------------------------------------------------------------------------
# 6. The rejoin helper -- the sites that MUST cross a page boundary
# ---------------------------------------------------------------------------

def test_keep_break_in_rejoin_moves_the_boundary_rather_than_deleting_it():
    import re

    out = re.sub(
        r"(CI)\s*\n\s*\n\s*(?=\d)",
        keep_break_in_rejoin(r"\1 "),
        "Mortality CI\n\n" + PAGE_BREAK + "2.046",
    )
    assert out.count(PAGE_BREAK) == 1, "the boundary must survive the rejoin"
    assert "CI 2.046" in out, (
        "and the statistic must stay contiguous -- a form feed BETWEEN the "
        "label and its value hands consumers a token no paper printed"
    )
    assert out.index(PAGE_BREAK) < out.index("CI 2.046"), (
        "the boundary is re-emitted BEFORE the rejoined token, so the error is "
        "bounded by the width of one label"
    )


def test_keep_break_in_rejoin_is_a_no_op_without_a_boundary():
    import re

    out = re.sub(
        r"(CI)\s*\n\s*\n\s*(?=\d)", keep_break_in_rejoin(r"\1 "), "Mortality CI\n\n2.046"
    )
    assert out == "Mortality CI 2.046"
    assert PAGE_BREAK not in out, "a boundary must never be manufactured"


def test_page_break_residue_is_the_one_definition():
    """ONE CONCEPT, ONE TABLE -- nine sites, one definition of the boundary."""
    assert page_break_residue(PAGE_BREAK * 2 + "junk") == PAGE_BREAK * 2
    assert page_break_residue("no boundary here") == ""


# ---------------------------------------------------------------------------
# 7. F0's FOOTNOTE branch -- the neighbour of a branch already fixed
# ---------------------------------------------------------------------------
#
# `_f0_strip_running_and_footnotes` splits on `([\n\f])`, so the separator
# AFTER a line belongs to that line. v1.9.57 gave the header/footer branch a
# `_drop()` that re-emits a page break; the FOOTNOTE branch four lines below it
# was left with a bare `continue`. A footnote is by definition the LAST content
# on its page, so the separator it consumed is a page boundary more often than
# not -- the fix covered the case in front of it and not its neighbour.
#
# THE FIXTURE PUTS THE FOOTNOTE LAST ON EACH PAGE ON PURPOSE. The sibling test
# in `test_f0_page_boundary_is_structure.py` records what happens otherwise:
# with the furniture FIRST its separator is a newline, and the test passes even
# with `_drop()` neutered -- a guard that cannot fail is decoration.

from docpluck.extract_layout import LayoutDoc, PageLayout, TextSpan  # noqa: E402
from docpluck.normalize import _f0_strip_running_and_footnotes  # noqa: E402


def _footnote_doc(n_pages: int) -> LayoutDoc:
    def page(i: int) -> PageLayout:
        mk = lambda t, y, sz: TextSpan(  # noqa: E731
            text=t, page_index=i, x0=49.6, y0=y, x1=545.0, y1=y + 9,
            font_size=sz, font_name="Times", bold=False)
        return PageLayout(i, 595.0, 842.0, spans=(
            mk(f"Body sentence {i} carrying the actual content of the page.", 400.0, 9.0),
            mk(f"Body sentence {i} continues with more ordinary prose here.", 380.0, 9.0),
            # Small font, low on the page, and UNIQUE per page so it is a
            # footnote rather than a repeating footer.
            mk(f"{i + 1}. A footnote unique to page {i} of this document.", 60.0, 7.0),
        ))
    pages = tuple(page(i) for i in range(n_pages))
    return LayoutDoc(pages=pages, raw_text="", page_offsets=tuple(range(n_pages)))


def test_f0_footnote_branch_keeps_the_page_boundary():
    n = 8
    doc = _footnote_doc(n)
    raw = PAGE_BREAK.join(
        f"Body sentence {i} carrying the actual content of the page."
        f"\nBody sentence {i} continues with more ordinary prose here."
        f"\n{i + 1}. A footnote unique to page {i} of this document."
        for i in range(n)
    )
    before = raw.count(PAGE_BREAK)
    body, spans, texts = _f0_strip_running_and_footnotes(raw, doc)
    assert texts, "the fixture produced no footnotes; this test would be vacuous"
    # The appendix marker adds its own `\n\f\f\n`, so count the BODY only.
    body_only = body.split("\n\f\f\n")[0]
    assert body_only.count(PAGE_BREAK) == before, (
        f"page breaks {before} -> {body_only.count(PAGE_BREAK)}: the footnote "
        f"branch consumed the boundary its neighbour branch preserves"
    )
    for i in range(n):
        assert f"Body sentence {i} carrying" in body_only


# ---------------------------------------------------------------------------
# 8. The adversarial layout -- raised by Sonnet 5 (anthropic), consult 2026-08-28
# ---------------------------------------------------------------------------
#
# THE REVIEW'S SHARPEST FINDING, and it was right about the test suite even
# though the defect it predicted does not exist.
#
# Sonnet observed that "keep the FIRST copy" rests on content preceding the
# furniture derived from it, that this was measured on exactly one paper, and
# that EVERY fixture above constructs the favourable layout -- `_paginated()`
# says outright that page 1 carries no leading form feed. If a journal prints
# its running head ABOVE the title on page 1 (common), document order becomes
# [header (furniture), title (data)] and "keep first" would keep the header and
# delete the title -- the same defect, shifted.
#
# REPRODUCED AND REFUTED, by the gate's own arm rather than by argument: that
# layout puts the string TWICE on page 1, so `max_per_page` is 2, and with
# `count < 20` the line does not qualify as furniture at all. Measured on the
# fixture below: 9 occurrences in, 9 out, `changes_made` empty, the strip never
# fires. The layout that would make the survivor rule choose wrongly is exactly
# the layout that disqualifies the line -- two-per-page is the TABLE CONTENT
# signature the page gate exists to protect.
#
# So the rule is safe BY CONSTRUCTION and not by luck -- BUT ONLY BECAUSE THE
# WATERMARK ARM IS GONE, AND THIS COMMENT ORIGINALLY GOT THAT WRONG.
#
# It first said reopening the hole "would need the floor LOWERED below 20".
# Grok 4.6 (xai), same consult round, pointed out the floor WAS already 20 and
# reached it with THIS VERY FIXTURE at `n_pages=19`: page 1 prints the string
# twice and pages 2-19 once each, giving `count = 20`, so the `count >= 20`
# disjunct fired and took 19 of the 20 copies. Reproduced exactly as predicted.
# The arm is deleted (see `normalize.py`); the test below now runs at 19 and 25
# pages so the claim is pinned where it used to fail rather than where it
# happened to hold.

_DUAL = "Journal of Measured Things Quarterly Review"  # header text == title text


def _adversarial(n_pages: int = 8) -> str:
    """Running head ABOVE the title block on page 1 -- the shape Sonnet named."""
    pages = []
    for i in range(n_pages):
        if i == 0:
            lines = [_DUAL, _DUAL, "A Randomized Clinical Trial",
                     "Ann Author, PhD; Bo Writer, MSc"]
        else:
            lines = [PAGE_BREAK + _DUAL]
        lines += [f"Body sentence {i}-{j} of ordinary prose here." for j in range(5)]
        pages.append("\n".join(lines))
    return "\n".join(pages)


@pytest.mark.parametrize("n_pages", [8, 19, 25])
def test_a_header_printed_above_the_title_disqualifies_the_line_entirely(n_pages):
    """19 and 25 pages cross `count >= 20`, where this used to fail."""
    text = _adversarial(n_pages)
    out, report = _norm(text)
    assert out.count(_DUAL) == text.count(_DUAL) == n_pages + 1, (
        "two occurrences on page 1 make max_per_page 2, so the line is not "
        "furniture and NOTHING may be removed -- at ANY page count"
    )
    assert not [k for k in report.fallbacks if k.startswith("repeated_line")], (
        "the strip must not fire at all on this layout"
    )


def test_the_favourable_layout_still_strips_so_the_test_above_is_not_vacuous():
    """Two-sided: same header, same page count, title NOT doubled on page 1."""
    pages = [
        "\n".join([_DUAL, "A Randomized Clinical Trial"]
                  + [f"Body sentence 0-{j} of ordinary prose here." for j in range(5)])
    ]
    for i in range(1, 8):
        pages.append("\n".join(
            [PAGE_BREAK + _DUAL]
            + [f"Body sentence {i}-{j} of ordinary prose here." for j in range(5)]))
    out, _ = _norm("\n".join(pages))
    assert out.count(_DUAL) == 1, "the favourable layout must still be stripped"


def test_a_restored_trailing_boundary_never_glues_to_a_line_of_statistics():
    """The first version of the strip fix produced a WORSE defect than the one it fixed.

    Concatenating the residue directly gave, on `10.1016/j.jesp.2022.104282`,
    a last line of ``'voxels. * p < .05, ** p < .01, *** p < .001.\f'`` -- a
    control character welded to published statistics, breaking any consumer
    anchoring on the end of that line.

    Own-line is what the SOURCE does (40 of 40 raw trailing form feeds sit
    alone on their line, 0 glued) and what ``keep_page_break`` does at the
    other eight sites. Raised as UNVERIFIED by Sonnet 5 in the 2026-08-28
    consult round and found real on measurement.
    """
    out, _ = _norm("Body prose ending in a statistic, p < .001.\n" + PAGE_BREAK)
    assert out.count(PAGE_BREAK) == 1, "the boundary must survive"
    assert out.split("\n")[-1] == PAGE_BREAK, "and it must be alone on its line"
    last_content = out.rstrip(PAGE_BREAK).rstrip("\n").split("\n")[-1]
    assert last_content.endswith("p < .001."), (
        "the last line of content must be unchanged -- no control character "
        "may be welded onto a published statistic"
    )


def test_a_restored_leading_boundary_also_gets_its_own_line():
    out, _ = _norm(PAGE_BREAK + "\nBody prose for this document.")
    assert out.count(PAGE_BREAK) == 1
    assert out.split("\n")[0] == PAGE_BREAK


# ---------------------------------------------------------------------------
# 9. The `count >= 20` watermark arm -- DELETED. Found by Grok 4.6 (xai),
#    consult round 2026-08-28, reproduced both ways before acting.
# ---------------------------------------------------------------------------
#
# The arm was a second disjunct: `max_per_page == 1 or count >= 20`, meant for
# a watermark repeating several times per page on every page. It handed back
# the exact class the page gate was created to protect.
#
# `Number of trained architectures` is not a hypothetical: it is one of the
# THIRTEEN table lines the v1.9.60 entry lists as content the OLD line-index
# rule was wrongly deleting. Four copies per page over five pages reaches
# count 20, and the arm took 19 of them.
#
# Deleted rather than tightened because a 390-paper sweep of the article
# repository found exactly ONE paper exercising it (`10.1525/collabra.19525`,
# "Author Manuscript", 112 copies on 28/29 pages), and n=1 cannot calibrate a
# page-coverage threshold. Furniture that survives is visible and reversible
# for a consumer; a deleted table row label is neither.

_STUB = "Number of trained architectures"


def _spread_table(n_pages: int = 5, per_page: int = 4) -> str:
    """A repeated table ROW LABEL spread across pages -- content, not furniture."""
    pages = []
    for i in range(n_pages):
        lines = [(PAGE_BREAK if i else "")
                 + f"Table {i + 1}. Results for configuration set {i + 1}."]
        for k in range(per_page):
            lines += [_STUB, f"{100 + k * 7}"]
        lines.append(f"Body sentence {i} of ordinary prose for this page.")
        pages.append("\n".join(lines))
    return "\n".join(pages)


def test_a_spread_table_row_label_is_never_taken_as_a_watermark():
    """count=20, max_per_page=4, distinct_pages=5 -- the arm took 19 of 20."""
    text = _spread_table()
    assert text.count(_STUB) == 20, "the fixture must actually reach the old floor"
    out, report = _norm(text)
    assert out.count(_STUB) == 20, (
        "a table row label repeated within each page is CONTENT; deleting it "
        "orphans the numbers underneath it"
    )
    assert not [k for k in report.fallbacks if k.startswith("repeated_line_stripped")]


def test_no_arm_named_for_the_watermark_count_survives():
    """The arm is gone, not merely unreachable -- telemetry would still name it."""
    _out, report = _norm(_spread_table())
    assert not [k for k in report.fallbacks if "watermark" in k]


def test_a_genuine_running_header_is_still_stripped_after_the_arm_is_gone():
    """TWO-SIDED. Removing the arm must not stop the once-per-page rule working."""
    out, _ = _norm(_paginated(_HEADER, 9))
    assert out.count(_HEADER) == 1
