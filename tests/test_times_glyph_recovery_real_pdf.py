"""Regression test for the '×'-for-'3' glyph corruption (v2.4.103, W0i).

The APA Phase-5d canary sweep (2026-07-03) found efendic_2022_affect rendering
every interaction-term predictor name with the multiplication sign '×' turned
into the digit '3': "Direction × manipulated attribute" reads "Direction 3
manipulated attribute", "PMA × direction" reads "PMA 3 direction", across all
four regression tables (Tables 2-5). Diagnosis: the same broken-ToUnicode
AdvPS… subset font that maps U+2212 minus to '2' and '<' to '\\' also maps '×'
to '3' (pdffonts: uni:no).

Fix (v2.4.103): `normalize.py::recover_times_interaction_glyph` (W0i), wired ONLY
into `cell_cleaning._html_escape` (the Camelot table-cell channel). A bare '3'
between letters is ambiguous in free prose ("Table 3 summarizes", "osf.io/pg3ae"),
so the recovery is TABLE-CELL SCOPED: inside a Camelot predictor cell a '3'
flanked by letters is unambiguously a corrupted '×'. Self-guards a genuine
ordinal after a reference word (Model/Study/Wave/…).
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

# The two "(Camelot ON)" tests below exercise the production Camelot HTML-table
# channel. Under DOCPLUCK_DISABLE_CAMELOT=1 (the broad-suite default) the render
# has no <td> cells at all, so their positive assertions fail and their
# negative assertions false-pass — either way the test is meaningless. Skip
# VISIBLY instead; the tests run in Camelot-enabled per-file gates.
requires_camelot = pytest.mark.skipif(
    os.environ.get("DOCPLUCK_DISABLE_CAMELOT") == "1",
    reason="Camelot-ON production-path test; meaningless under DOCPLUCK_DISABLE_CAMELOT=1",
)

from docpluck.normalize import recover_times_interaction_glyph
from docpluck.render import render_pdf_to_markdown

TEST_PDFS = Path(__file__).resolve().parents[1].parent / "PDFextractor" / "test-pdfs"


# ── Unit tests on recover_times_interaction_glyph (cell-scoped) ─────────────

def test_recovers_two_way_interaction():
    assert (
        recover_times_interaction_glyph("Direction 3 manipulated attribute")
        == "Direction × manipulated attribute"
    )


def test_recovers_allcaps_predictor_interaction():
    assert recover_times_interaction_glyph("PMA 3 direction") == "PMA × direction"
    assert recover_times_interaction_glyph("PNMA 3 Attribute") == "PNMA × Attribute"


def test_recovers_three_way_interaction():
    assert (
        recover_times_interaction_glyph("Pleasure 3 Arousal 3 CMA")
        == "Pleasure × Arousal × CMA"
    )


def test_recovers_glued_form():
    # Camelot sometimes glues "PMA 3direction" (no trailing space).
    assert recover_times_interaction_glyph("PMA 3direction") == "PMA × direction"


def test_recovers_across_cell_wrap_break():
    # A 3-way interaction can wrap: "A × B<br>C" where the merge placeholder
    # (\x00BR\x00) or a <br> sits between the operands. Both × must recover.
    merge = "\x00BR\x00"
    out = recover_times_interaction_glyph(f"PNMA 3 Direction{merge}3 Attribute")
    assert out.count("×") == 2, out
    assert "3" not in out.replace(merge, "")
    # literal <br> form too
    out2 = recover_times_interaction_glyph("PNMA 3 Direction<br>3 Attribute")
    assert out2.count("×") == 2, out2


def test_leaves_genuine_ordinal_after_reference_word():
    # A reference/enumeration word before the 3 makes it a genuine ordinal.
    assert recover_times_interaction_glyph("Model 3 predictors") == "Model 3 predictors"
    assert recover_times_interaction_glyph("Study 3 sample") == "Study 3 sample"
    assert recover_times_interaction_glyph("Wave 3 data") == "Wave 3 data"


def test_leaves_decimal_and_numeric_cells():
    # A '3' inside a number has a digit (not a letter) on at least one side.
    assert recover_times_interaction_glyph("0.34") == "0.34"
    assert recover_times_interaction_glyph("1.23") == "1.23"
    assert recover_times_interaction_glyph("[-0.31, 0.30]") == "[-0.31, 0.30]"


def test_leaves_trailing_or_leading_3():
    # '3' at a cell boundary (Model label "M3", "Group 3") has no letter on one
    # side, so it is never an interaction ×.
    assert recover_times_interaction_glyph("Group 3") == "Group 3"
    assert recover_times_interaction_glyph("3 items") == "3 items"


def test_leaves_cell_without_letters():
    assert recover_times_interaction_glyph("3") == "3"
    assert recover_times_interaction_glyph("33") == "33"


def test_leaves_glued_hypothesis_labels():
    # H3a / H3b are Hypothesis-3a/3b labels (maier_2023_collabra), NOT interaction
    # terms. They are fully GLUED (single letter + 3 + single letter, no space), so
    # the whitespace-on-at-least-one-side requirement excludes them. Regression for
    # a false positive caught by the cycle-2 canary-coverage render.
    assert (
        recover_times_interaction_glyph("H3a: Explicit (Identifiable & Statistical) vs. Control")
        == "H3a: Explicit (Identifiable & Statistical) vs. Control"
    )
    assert recover_times_interaction_glyph("H3b: Explicit") == "H3b: Explicit"
    assert recover_times_interaction_glyph("H1a") == "H1a"
    # glued model/code labels with an embedded 3 must also stay
    assert recover_times_interaction_glyph("Model3fit") == "Model3fit"
    assert recover_times_interaction_glyph("x3y") == "x3y"


# ── W0i-range: a RANGE bound is not an interaction operator (v2.4.122) ──────

def test_range_notation_lower_bound_is_never_times():
    """`from 3 to 15` is a scale RANGE, not an interaction — the '3' is a real
    number and must survive.

    Found 2026-08-04 by the cycle-1 canary audit on chan_feldman_2025_cogemo:
    its Table-2 note "Avoidance behaviour scores ranged from 3 to 15" rendered
    as "ranged from × to 15" in the Camelot <td> channel, i.e. the library
    DELETED a published scale bound and replaced it with an operator. Both text
    channels confirm the source says '3'; this is docpluck corruption, not a
    source artifact.

    Root cause: W0i's only pre-digit guard was a reference-word list
    (Model/Study/Table/…) that has no notion of range grammar. `from`/`to`
    around the digit satisfied "letter, space, 3, space, letter", so EVERY
    `from 3 to N` in any table cell was rewritten. A range bound is the single
    most common numeric shape in a table note, so this is corpus-wide, not
    paper-specific.
    """
    for cell in (
        "Note: Avoidance behaviour scores ranged from 3 to 15. **p < .01.",
        "Apology scores ranged from 2 to 10. Avoidance scores ranged from 3 to 15.",
        "scores range from 3 to 7",
        "increased from 3 to 5 points",
        "aged from 3 to 12 years",
        "Scores varied from 3 to 21 across conditions",
    ):
        assert recover_times_interaction_glyph(cell) == cell, (
            f"range bound wrongly ×-converted: {recover_times_interaction_glyph(cell)!r}"
        )


def test_range_guard_covers_every_real_corpus_instance():
    """The four range-frame sites that actually exist in the 101-PDF corpus.

    Enumerated 2026-08-04 by a pdftotext sweep of ALL 152 corpus PDFs: 8 sites
    with a `3` bound across 5 distinct articles (3 of the 8 are duplicate copies
    of the same papers in the ESCIcheck corpus), out of 380 range frames overall.
    Pinning the REAL population (not invented examples) is what makes this a
    corpus guard rather than a spot check — and it is why the `between … and`
    frame is in the guard at all: maier's Bayes-factor sentence and bmc_med_3's
    lesion diameter both use it, so a `from … to`-only guard would have left
    those exposed.
    """
    for cell in (
        # chan_feldman Table-2 note — the site that exposed the defect
        "Avoidance behaviour scores ranged from 3 to 15. **p < .01.",
        # chen_2021_jesp — a reference TITLE carrying a range
        "Hindsight bias from 3 to 95 years of age. Journal of Experimental",
        # jdm_2023_15 — a payment range
        "Earnings in this task varied from 3 to 18 Swiss francs (CHF) (mean = 10.6).",
        # maier_2023_collabra — `between … and`, not `from … to`
        "Bayes factors between 3 and 10 are often regarded as moderate evidence",
        # bmc_med_3 — a clinical measurement range (Vancouver-style medical paper)
        "the other half had a diameter between 3 and 10 mm, with only one lesion",
    ):
        assert recover_times_interaction_glyph(cell) == cell, (
            f"real corpus range instance corrupted: {recover_times_interaction_glyph(cell)!r}"
        )


def test_range_guard_does_not_disarm_genuine_interactions():
    """The range guard must not cost W0i its real recoveries — an interaction
    term that merely happens to sit near range words still recovers."""
    assert (
        recover_times_interaction_glyph("Direction 3 manipulated attribute")
        == "Direction × manipulated attribute"
    )
    # 'to'/'from' as part of a predictor NAME, not range grammar around the digit
    assert (
        recover_times_interaction_glyph("Openness 3 Attitude to risk")
        == "Openness × Attitude to risk"
    )


@requires_camelot
def test_chan_feldman_range_bound_survives_with_camelot_on():
    """Real-PDF gate for the range false positive (Camelot ON = production path).

    chan_feldman's Table-2 note must render the true lower bound `from 3 to 15`;
    `from × to 15` anywhere in the document is the defect.
    """
    pdf = TEST_PDFS / "apa" / "chan_feldman_2025_cogemo.pdf"
    if not pdf.exists():
        pytest.skip(f"fixture missing: {pdf}")
    md = render_pdf_to_markdown(pdf.read_bytes())  # Camelot ON
    assert "from × to" not in md, "range lower bound wrongly ×-converted in a table cell"
    assert "ranged from 3 to 15" in md, "the true scale bound 3 is missing from the render"


# ── Real-PDF regression test (Camelot ON — the production path) ─────────────

@requires_camelot
def test_efendic_interaction_terms_recovered_with_camelot_on():
    """Every efendic interaction-term predictor cell must render with '×', not
    the corrupted '3', in the Camelot HTML-table channel (production default).
    Genuine references in body prose ("Table 3 summarizes", "Figure 3 and") must
    be untouched — the recovery is table-cell scoped."""
    pdf = TEST_PDFS / "apa" / "efendic_2022_affect.pdf"
    if not pdf.exists():
        pytest.skip(f"fixture missing: {pdf}")
    md = render_pdf_to_markdown(pdf.read_bytes())  # Camelot ON
    # No table cell may still carry a corrupted '×'-as-'3' interaction term.
    surviving = re.findall(r"<td[^>]*>[^<]*[A-Za-z]\s*3\s?[A-Za-z][^<]*</td>", md)
    # Filter to genuinely interaction-shaped survivors (letters both sides, not a
    # reference-word ordinal cell).
    real = [
        c
        for c in surviving
        if not re.search(
            r"\b(?:Study|Model|Wave|Phase|Item|Table|Figure|Group|Level|Sample)\s*3",
            c,
        )
    ]
    assert not real, f"corrupted '×'-as-3 interaction cells survive: {real[:6]}"
    # The canonical interaction terms must be present with '×'.
    assert "Direction × manipulated attribute" in md
    assert "Pleasure × Arousal" in md
    # Body-prose genuine references must NOT have been corrupted to '×'.
    assert "Table 3" in md  # "Table 3 summarizes" preserved
    assert "Direction × manipulated attribute" in md and "Table × summarizes" not in md


@requires_camelot
def test_maier_hypothesis_labels_not_corrupted_with_camelot_on():
    """maier_2023_collabra has hypothesis-label cells H3a/H3b (Hypothesis 3a/3b),
    which are GLUED (H+3+a, no space) and must NOT be read as an interaction ×.
    Regression for the false positive the cycle-2 canary-coverage render caught:
    the first W0i cut turned "H3a: Explicit …" into "H × a: Explicit …". The
    whitespace-on-at-least-one-side requirement now excludes glued labels."""
    pdf = TEST_PDFS / "apa" / "maier_2023_collabra.pdf"
    if not pdf.exists():
        pytest.skip(f"fixture missing: {pdf}")
    md = render_pdf_to_markdown(pdf.read_bytes())  # Camelot ON
    assert "H × a" not in md and "H × b" not in md, "hypothesis label H3a/H3b wrongly ×-converted"
    # The genuine factorial-design "× 3 (" notation (× followed by the number 3,
    # then a paren) must also stay — the 3 is not followed by a letter.
    assert "× 3 (" in md or "H3a" in md  # at least the labels survive intact
