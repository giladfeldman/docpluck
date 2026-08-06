"""RC-T Layer-2 — raw_text-fallback prose contamination (v2.4.98, 2026-06-22).

When Camelot recovers no cells, ``_extract_table_body_text`` linearizes the
text following a table caption as the ``unstructured-table`` fallback. Its
per-line prose gate (``_line_is_body_prose``, len>=80) cannot see body prose
that pdftotext WRAPPED into short (~48-char) lines, so the region overshoot
swallowed Results/Discussion prose into the block:

  * chan_feldman Table 1 — Discussion prose ("Our main focus was the
    replication …") accumulated AFTER the table's ``Note:`` footnote.
  * chan_feldman Table 9 — the block was ENTIRELY flowing prose ("than
    empathy. We provided full analyses …") duplicating the real ``##
    Discussion`` section verbatim.

Two structural-signature fixes (rule 16), both FP-safe by construction:
  1. Note-anchor: a table's ``Note:`` is its last element — trim everything
     after the note paragraph (T1).
  2. Degenerate-prose guard: suppress a block that STARTS mid-sentence with a
     lowercase multi-letter word AND is majority prose; render then emits a
     clean caption-only table (T9).

Contract tests pin the FP-safe predicate deterministically; real-PDF tests
(rule 0d) confirm on chan_feldman. PDFs are closed-access
(``feedback_no_pdfs_in_repo``); real-PDF tests skip when the fixture is absent.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from docpluck.extract_structured import (
    _join_wrapped_lines,
    _raw_text_is_degenerate_prose,
)
from docpluck.render import render_pdf_to_markdown

from .conftest import pdf_available, pdf_path, requires_pdftotext

_skip_under_xdist = pytest.mark.skipif(
    bool(os.environ.get("PYTEST_XDIST_WORKER")),
    reason="real-PDF Camelot extraction is non-deterministic under parallel "
    "xdist load; runs serially (isolation/serial run is the real gate)",
)


# ── contract tests: the FP-safe degenerate-prose predicate (deterministic) ────

# All-prose block that STARTS mid-sentence (lowercase multi-letter word) — the
# region-overshoot signature. Must be flagged degenerate.
_DEGENERATE = (
    "than empathy. We provided full analyses and results\n"
    "for the comparisons in the supplementary materials\n"
    "section of this paper across all of the conditions.\n"
    "We replicated all of the supported findings of the\n"
    "target article and summarised the results below here."
)
# Hypotheses table (legit, degraded): starts with a single-letter item marker.
_HYPOTHESES = (
    "a There is a positive association between a wronged\n"
    "person's empathy for an offender and reported\n"
    "forgiveness for the offender.\n"
    "b Apology increases the likelihood of forgiving."
)
# Descriptive rows (legit): starts with a Capitalized label.
_DESCRIPTIVE = "Median age (years)\n24.0\nAverage age\n28.8\n(years)\nStandard deviation"
# Instrument-table fragment (legit): starts with a single-letter token "h".
_INSTRUMENT = "h et al., 1997)\nPerceived apology\nEmpathy\nThe offender has apologised?"


def test_degenerate_prose_flagged():
    assert _raw_text_is_degenerate_prose(_DEGENERATE) is True


def test_hypotheses_not_flagged():
    """Single-letter item marker ('a ...') => not a mid-sentence continuation."""
    assert _raw_text_is_degenerate_prose(_HYPOTHESES) is False


def test_descriptive_rows_not_flagged():
    assert _raw_text_is_degenerate_prose(_DESCRIPTIVE) is False


def test_instrument_fragment_not_flagged():
    assert _raw_text_is_degenerate_prose(_INSTRUMENT) is False


def test_short_block_not_flagged():
    assert _raw_text_is_degenerate_prose("than empathy.\nWe provided.") is False


def test_join_wrapped_lines_merges_to_sentence():
    assert _join_wrapped_lines(["a foo", "bar baz.", "next one."]) == [
        "a foo bar baz.",
        "next one.",
    ]


# ── real-PDF tests (chan_feldman) ─────────────────────────────────────────────


def _unstructured_blocks(md: str) -> str:
    """Whitespace-normalized concatenation of every ```unstructured-table``` block."""
    blocks = re.findall(r"```unstructured-table\n(.*?)```", md, re.DOTALL)
    return re.sub(r"\s+", " ", "\n".join(blocks))


@pytest.fixture(scope="module")
def chan_md() -> str:
    key = "10.1080__02699931.2024.2434156"
    if not pdf_available("articlerepo", f"{key}.pdf"):
        pytest.skip(f"closed-access fixture missing: {key}.pdf")
    return render_pdf_to_markdown(Path(pdf_path("articlerepo", f"{key}.pdf")).read_bytes())


@requires_pdftotext
@_skip_under_xdist
def test_t1_note_anchor_trims_trailing_prose(chan_md: str):
    """Table 1: body prose after the ``Note:`` footnote must be trimmed from the
    fallback block (FAIL at HEAD — it was swallowed)."""
    blocks = _unstructured_blocks(chan_md)
    assert "Our main focus was the replication" not in blocks, (
        "chan_feldman T1 still swallows post-Note Discussion prose — the "
        "Note-anchor trim in _extract_table_body_text did not fire."
    )


@requires_pdftotext
@_skip_under_xdist
def test_t1_table_content_and_note_retained(chan_md: str):
    """FP guard: the Note-anchor must KEEP the table content + the note itself
    (hypotheses come before the note; trimming starts after it)."""
    blocks = _unstructured_blocks(chan_md)
    assert "There is a positive association" in blocks, "T1 hypothesis content lost (over-trim)"
    assert "Hypothesis 3 is not included in the replication" in blocks, "T1 Note paragraph lost (over-trim)"


@requires_pdftotext
@_skip_under_xdist
def test_t9_degenerate_block_suppressed_no_duplication(chan_md: str):
    """Table 9: the all-prose fallback (a verbatim duplicate of ## Discussion)
    must be suppressed — the Discussion opener appears exactly once, never inside
    an unstructured-table block."""
    opener = "We conducted a replication and extensions Registered Report"
    assert opener not in _unstructured_blocks(chan_md), (
        "chan_feldman T9 still dumps Discussion prose into an unstructured-table "
        "block — the degenerate-prose guard did not fire."
    )
    assert "### Table 9" in chan_md, "T9 heading lost (table_parity broken)"
    n = len(re.findall(re.escape(opener), chan_md))
    assert n == 1, f"Discussion opener appears {n}x (expected 1 — T9 duplication not resolved)"


@requires_pdftotext
@_skip_under_xdist
def test_t3_legit_fallback_table_survives(chan_md: str):
    """FP guard: Table 3 (a real descriptive table starting with a Capitalized
    label) must keep its fallback block + its Note — never suppressed/over-trimmed."""
    blocks = _unstructured_blocks(chan_md)
    assert "Median age" in blocks, "chan_feldman T3 descriptive fallback wrongly suppressed (FP)"
    assert "Origin was not explicitly mentioned" in blocks, "T3 Note over-trimmed (FP)"


# ── RC-T TEXT-LOSS: the caption-tail-walk overshoot (FIXED, v2.4.119) ─────────
#
# The chan_feldman Table 3 fallback DROPPED its first four rows (Sample size
# 239/794, Geographic origin, Gender, Ethnic group). Root cause (2026-07-04
# run 3): `_extract_table_body_text`'s body_start walk preferred the next `\n\n`
# paragraph break over the caption's OWN sentence terminator. Fixed in the
# gated RC-T cycle (2026-08-04 run 4): `_caption_tail_body_start` walks
# per-LINE with a whole-line terminator test (xiao T6 guard), a blank-line
# stop, and a max-wrap-lines cap (amc_1 T3 guard); `_skip_leading_nontable_junk`
# rejects a recovered leading chunk that is a figure caption or wrapped body
# prose. The former XFAIL guard below is now a REAL assert (it XPASS-alerted
# the moment the fix landed, as designed); the amc_1/xiao guards pin the two
# truncation shapes the prototype walk regressed on. See
# an internal findings doc (2026-07-04).


@requires_pdftotext
@_skip_under_xdist
def test_t3_first_rows_not_dropped(chan_md: str):
    """TEXT-LOSS guard (real assert since v2.4.119): Table 3's FIRST rows must
    be present. Gold Table 3 is a 2-column comparison (McCullough 1997 vs US
    Prolific) whose first four rows the pre-v2.4.119 caption-tail walk
    dropped."""
    blocks = _unstructured_blocks(chan_md)
    for needle in ("Sample size", "Geographic origin", "Gender", "Ethnic group", "239", "US Prolific"):
        assert needle in blocks, (
            f"chan_feldman T3 dropped a leading row: {needle!r} missing from the "
            f"unstructured-table block (body_start caption-tail walk over-skipped)."
        )


# ── The two truncation shapes the PROTOTYPE per-line walk regressed on ────────


@requires_pdftotext
def test_amc1_t3_bibliography_table_not_truncated_real_pdf():
    """amc_1 Table 3 is a bibliography table: caption `TABLE 3` + an
    UNTERMINATED title line, then reference rows with no sentence-terminated
    line for hundreds of chars. The unguarded per-line walk consumed rows as
    'caption tail' until the 800-char cap (−352 chars vs HEAD). The
    max-wrap-lines cap must put body_start right after the caption's own
    line, keeping the title line and every leading reference row."""
    from docpluck.extract import extract_pdf
    from docpluck.tables.captions import find_caption_matches
    import docpluck.extract_structured as ES

    pdf = pdf_path("docpluck", "aom", "amc_1.pdf")
    if not os.path.isfile(pdf):
        pytest.skip(f"fixture missing: {pdf}")
    raw = extract_pdf(Path(pdf).read_bytes())[0]
    caps = [c for c in find_caption_matches(raw, list(ES._page_offsets(raw))) if c.kind == "table"]
    t3 = next((c for c in caps if c.label == "Table 3"), None)
    assert t3 is not None, "amc_1 Table 3 caption not found"
    starts = sorted(c.char_start for c in caps)
    later = [s for s in starts if s > t3.char_end]
    nb = later[0] if later else None
    body = ES._extract_table_body_text(raw, t3, nb)
    # The title line and the first bibliography rows must survive.
    assert "Academy of Management Collection" in body, (
        "amc_1 T3 lost its title line (caption-tail walk consumed content)"
    )
    assert "Davis, K. 1973" in body, (
        "amc_1 T3 lost its first bibliography row (truncation regression)"
    )


@requires_pdftotext
def test_xiao_t6_selfterminated_caption_not_truncated_real_pdf():
    """xiao_2021 Table 6's caption is SELF-terminated (`…statistics.`) and ends
    exactly at a line break. The prototype walk measured only the post-match
    remainder (empty), missed the terminator, and consumed table rows until a
    `.`-ending line (−799 chars). The whole-line terminator test must break
    immediately, keeping every leading data row."""
    from docpluck.extract import extract_pdf
    from docpluck.tables.captions import find_caption_matches
    import docpluck.extract_structured as ES

    pdf = pdf_path("docpluck", "apa", "xiao_2021_crsp.pdf")
    if not os.path.isfile(pdf):
        pytest.skip(f"fixture missing: {pdf}")
    raw = extract_pdf(Path(pdf).read_bytes())[0]
    caps = [c for c in find_caption_matches(raw, list(ES._page_offsets(raw))) if c.kind == "table"]
    t6 = next((c for c in caps if c.label == "Table 6"), None)
    assert t6 is not None, "xiao Table 6 caption not found"
    starts = sorted(c.char_start for c in caps)
    later = [s for s in starts if s > t6.char_end]
    nb = later[0] if later else None
    body = ES._extract_table_body_text(raw, t6, nb)
    assert "Choice of the target option" in body, (
        "xiao T6 lost its first header row (self-terminated-caption truncation)"
    )
    assert "216/337" in body, "xiao T6 lost its first data row"


# ── v2.4.119: page-break furniture suppression + FFFD third channel ──────────
#
# Both defects were EXPOSED by the corrected caption-tail walk: it recovers
# leading content the old walk silently skipped, so a caption sitting at a page
# foot now surfaces the next page's running header, and plos_med Table 2's
# recovered rows carry the cmsy10 `≥`-as-U+FFFD corruption that only the
# channel-1 normalize pass had been fixing.


def test_page_furniture_only_block_detected():
    """A fallback holding ONLY a next-page running header + page marker is
    suppressed (jama_open_1 Table 2's exact shape)."""
    from docpluck.extract_structured import _raw_text_is_page_furniture_only as furn

    assert furn(
        "JAMA Network Open | Nutrition, Obesity, and Exercise\n"
        "Effect of Time-Restricted Eating on Weight Loss in Adults With Type 2 Diabetes\n"
        "October 27, 2023\n"
        "8/13"
    ) is True


def test_page_furniture_guard_keeps_real_tables():
    """FP battery: real table content is never suppressed — including a lone
    page-like number, a table whose CELL is a date, and number-dense rows."""
    from docpluck.extract_structured import _raw_text_is_page_furniture_only as furn

    for block in (
        "8/13",  # bare marker, no running-header text ⇒ not a furniture block
        "Median age\n24.0\nAverage age\n28.8\n8",
        "Enrollment start\nOctober 27, 2023\nSites\n12\nPatients enrolled overall\n284",
        "Intracavitary remnant (mean SD) measured at baseline visit\n23.9 (13.7)\n5",
        "Control\n12\nTreatment\n15\n3",
    ):
        assert furn(block) is False, block


@requires_pdftotext
def test_jama_open_1_t2_furniture_not_dumped_real_pdf():
    """jama_open_1 Table 2's caption sits at a page foot; its raw_text fallback
    was the next page's banner/title/date/page-number with no table content.
    The rendered .md must not carry that furniture as an unstructured-table."""
    pdf = pdf_path("docpluck", "ama", "jama_open_1.pdf")
    if not os.path.isfile(pdf):
        pytest.skip(f"fixture missing: {pdf}")
    md = render_pdf_to_markdown(Path(pdf).read_bytes())
    blocks = _unstructured_blocks(md)
    assert "JAMA Network Open | Nutrition, Obesity, and Exercise" not in blocks, (
        "jama_open_1 T2 still dumps page-break furniture as table content"
    )
    assert not re.search(r"^October 27, 2023\s*$", md, re.M), (
        "standalone publication-date furniture line leaks into the render"
    )


@requires_pdftotext
def test_plos_med_t2_ge_glyph_recovered_in_table_rows_real_pdf():
    """plos_med Table 2's remnant-size rows reach the .md via the raw_text
    fallback (channel 3), which bypasses normalize_text — the cmsy10 `≥` must
    still be recovered there, not left as U+FFFD mojibake."""
    pdf = pdf_path("docpluck", "vancouver", "plos_med_1.pdf")
    if not os.path.isfile(pdf):
        pytest.skip(f"fixture missing: {pdf}")
    md = render_pdf_to_markdown(Path(pdf).read_bytes())
    assert "�" not in md, f"{md.count(chr(0xFFFD))} replacement char(s) remain"
    assert "≥5–10 mm" in md, "Table 2 remnant-size row lost its recovered ≥"
