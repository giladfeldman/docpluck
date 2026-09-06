r"""W0k must not rewrite a real digit into a multiplication sign. RED as written.

Found 2026-09-05, starting from a report that `normalize_text` is not idempotent on
`demography_5`. The re-normalization symptom is the small half; that case is SECOND-PASS
only, and pass 1 leaves both of its phrases intact. The large half is that **W0k destroys
real published digits on the FIRST pass**, in different papers.

THE CHAIN. `W0k_prose_times_recovery` (`recover_times_interaction_glyph_in_prose`, added
v2.4.112 / `5e16de1`) exists to recover a `×` that a font rendered as `3` in an interaction
term. It rewrites the digit to `×`; `A5_math_symbol_normalization` then maps `×` to `*`
(`normalize.py:7357`). Both are present in `v2.4.137` and `v2.4.138`, i.e. in production.

MEASURED over the 101-PDF corpus, first pass, `steps_changed` inspected: W0k fires on 5
papers and **4 of the 5 firings destroy a real value.** Each case below is a real document,
named -- no constructed strings, per this project's evidence rule.

THE GUARD THAT FAILS. A line qualifies on `>= 2 pairs` even with no interaction context, so
two ordinary English sentences sharing a line are enough: `demography_5` turns
`Lines 3 and 4 represent ... Pensioner 3 was still alive` into `Lines * and 4 ... Pensioner *`.

WHY NOTHING CAUGHT IT -- three failures stacked, and the third is the reason this file exists:
  1. `changes_made` is a CHARACTER DELTA, so it is blind exactly when the rewrite is
     length-neutral. `3` -> `×` is neutral and reports nothing; `HapMap3` -> `HapMap ×`
     inserts a space and reports 1. The telemetry is therefore SILENT on the correct firing
     and LOUD on the fabrications -- the opposite of useful. (`steps_changed` does name it;
     nothing reads that field.)
  2. Four named regression tests over this corpus have been skipping on a hyphen/underscore
     typo (`chicago-ad/demography-5.pdf` asked for, `demography_5.pdf` on disk).
  3. `test_normalize_idempotent_corpus` samples `pdfs[::5]` -- 21 of 101 -- and
     `demography_5` is NOT in that stride. Its `except Exception: continue` also means a
     paper that CRASHES is not counted as non-idempotent, so a regression that turns a paper
     into a crash makes the ratchet go DOWN.

TWO-SIDED BY CONSTRUCTION. `test_w0k_still_recovers_the_interaction_term_it_exists_for`
pins the efendic case, so "delete W0k" is not a way to make this file green. A fix has to
NARROW the rule, not remove it.
"""

from __future__ import annotations

import os

import pytest

from docpluck.extract import extract_pdf
from docpluck.normalize import NormalizationLevel, normalize_text
from tests.conftest import pdf_available, pdf_path

TIMES = "\u00d7"


def _normalized(corpus_dir: str, name: str) -> str:
    if not pdf_available("docpluck", corpus_dir, name):
        pytest.skip(
            f"SKIPPED, NOT PASSED: {corpus_dir}/{name} absent from the local corpus. "
            "Four sibling tests in this suite skipped silently for weeks on a filename typo; "
            "read a skip here as a check that did not run."
        )
    with open(pdf_path("docpluck", corpus_dir, name), "rb") as fh:
        raw, _ = extract_pdf(fh.read())
    assert raw and len(raw) > 5000, f"{name}: extraction returned {len(raw or '')} chars -- vacuous"
    out, _report = normalize_text(raw, NormalizationLevel.academic)
    return out


@pytest.mark.parametrize(
    "corpus_dir,name,printed,fabricated",
    [
        # A genomics reference dataset NAME. `HapMap3` is the International HapMap
        # Project Phase 3 -- not a number, an identifier.
        ("nature", "nathumbeh_2.pdf", "HapMap3", f"HapMap {TIMES}"),
        # An Italian local health authority in an author affiliation:
        # Azienda Sanitaria Locale Torino 3.
        ("vancouver", "bmc_pub_health_1.pdf", "TO3", f"TO {TIMES}"),
    ],
)
def test_w0k_does_not_destroy_a_digit_glued_to_its_left_flank(corpus_dir, name, printed, fabricated):
    """A real `×` is SPACED ON BOTH SIDES. A digit glued to the preceding token is part
    of that token and can never be a corrupted multiplication sign."""
    out = _normalized(corpus_dir, name)
    assert fabricated not in out and fabricated.replace(TIMES, "*") not in out, (
        f"{name}: W0k rewrote the digit in {printed!r} to a multiplication sign, "
        f"publishing {fabricated!r} -- a token the paper never printed."
    )
    assert printed in out, f"{name}: {printed!r} is gone from the normalized text entirely"


def test_w0k_does_not_fire_on_two_ordinary_sentences_sharing_a_line():
    """`demography_5`, the paper that surfaced this. Two plain English clauses on one line
    satisfy the `>= 2 pairs` arm with no interaction context anywhere near them."""
    out = _normalized("chicago-ad", "demography_5.pdf")
    for phrase in ("Lines 3 and 4", "Pensioner 3"):
        assert phrase in out, f"demography_5: {phrase!r} was destroyed by W0k"


def test_w0k_passes_the_interaction_term_through_as_the_file_declares_it():
    """THE ORIGINAL PAPER NOW PASSES THROUGH, AND THAT IS THE POINT.

    THIS ASSERTION IS DELIBERATELY INVERTED FROM THE VERSION STAGED ON 2026-09-05, WHICH
    PINNED THE RECOVERY. That version was written before the owner ruled, and pinning it
    now would pin the wrong direction of the rule -- it would make "narrow W0k" the only
    passing outcome and lock out the outcome actually ordered.

    `efendic_2022_affect` really is corrupted: font `LGBBBB+AdvP586B` paints a multiplication
    sign, and the page shows `PNMA × Direction`. Verified at the source, object 25:

        /Differences : [46 /period, 50 /two, /three]
        /ToUnicode   : bfrange <32> <33> <0032>

    Both declare a DIGIT. The file is internally consistent and consistently wrong, so there
    is no metadata contradiction to detect -- the only contradiction is against the printed
    page. Under the THREE TIERS directive (CLAUDE.md, user directive 2026-09-06) that makes
    it a FILE LIE, and a file lie is never silently corrected. A rule whose signature is
    `text: str` can never consult the rendered page, so it can never be licensed for one.

    So the corruption is real AND docpluck must not guess at it. The text now carries what
    the file declares. Flagging the span belongs to the consumers, which is the whole
    separation-of-duties rule this project runs on.
    """
    out = _normalized("apa", "efendic_2022_affect.pdf")
    assert "PNMA 3" in out, (
        "efendic: the interaction term is not present as the file declares it. W0k (or a "
        "successor) is still rewriting it."
    )
    assert f"PNMA {TIMES}" not in out and "PNMA *" not in out, (
        "efendic: a multiplication sign was substituted for the digit the file declares. "
        "That is the FILE-LIE repair the 2026-09-06 directive forbids -- the corruption is "
        "real, but docpluck has no channel to announce a guess, so it passes through."
    )



# -- W0i is the same rule with a denylist, in the table-cell channel ---------


def test_w0i_does_not_destroy_a_digit_glued_to_its_left_flank():
    """W0i fails the directive's gate test for the same reason W0k does.

    `recover_times_interaction_glyph(cell: str)` is the TABLE-CELL sibling of W0k.
    Its signature is `cell: str`, so it can never consult the rendered page and can
    never be licensed for a FILE LIE (CLAUDE.md, THE THREE TIERS, 2026-09-06).

    Its guards were genuinely better than W0k's -- a reference-word denylist keeps
    `Model 3`, `Study 3`, `Wave 3`, `Factor 3`, `Cluster 3`, `Grade 3` and
    `Phase 3` intact, all verified. **A denylist of ordinal nouns can never be
    complete**, and that is the objection: measured 2026-09-06, W0i rewrote
    `HapMap3 SNPs` -> `HapMap x SNPs` and `ASL TO3 Piedmont Region` ->
    `ASL TO x Piedmont Region` -- the same two real tokens W0k destroyed, in the
    other channel.

    Leaving W0i wired while W0k is unwired would give one input two answers
    depending only on whether the text arrived as a body sentence or a table cell.

    ASSERTED THROUGH THE SHIPPED PATH, NOT THE RAW FUNCTION. `clean_cell_text` is
    what the table channel actually calls. The first draft of this test called
    `recover_times_interaction_glyph` directly and kept failing after the call site
    was unwired -- it was measuring the DEFINITION, which is deliberately KEPT so
    the evidence survives, rather than the product. A test of a function the
    product no longer calls pins nothing about the product.
    """
    from docpluck.tables.cell_cleaning import clean_cell_text

    for cell, printed in (
        ("HapMap3 SNPs", "HapMap3"),
        ("ASL TO3 Piedmont Region", "TO3"),
    ):
        out = clean_cell_text(cell)
        assert printed in out, (
            f"the table-cell channel rewrote the digit in {printed!r}, publishing "
            f"{out!r} -- a token the paper never printed."
        )
        assert TIMES not in out and "*" not in out, out

    # CONTROL: the cell channel must still be doing its other work, or this test
    # would pass equally against a function that returned its input unchanged.
    # These are repairs of characters that CANNOT legitimately occur -- an
    # unmapped-glyph marker and a ligature -- i.e. the class the directive keeps.
    assert clean_cell_text("(cid:0)0.42") == "-0.42", "unmapped-glyph minus recovery is gone"
    assert clean_cell_text(chr(0) + "0.42") == "-0.42", (
        "NUL-form unmapped-glyph recovery is gone. NOTE: the NUL is built with "
        "chr(0) and never pasted -- a literal NUL in a source file makes it "
        "binary to git and grep, which this repo has hit before."
    )
    assert clean_cell_text("ﬁnal") == "final", "ligature expansion is gone"
    assert clean_cell_text("Model 3 predictor") == "Model 3 predictor"
