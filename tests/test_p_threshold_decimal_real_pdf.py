"""W0n is RETIRED (v2.4.130, 2026-08-14) — `p < 05` passes through as printed.

RE-FIXTURED, NOT DELETED. This module used to pin `recover_p_threshold_dropped_decimal`
(W0n, v2.4.118), which restored a dropped decimal point in a p-value significance threshold
(`p < 05` -> `p < .05`) on the theory that a dotless, leading-zero-free canonical threshold
after a comparator "is never legitimate notation". The two real papers below are the reason
the rule is gone, and they are the reason this file is kept: they carry the single most
important piece of evidence the 2026-08-14 audit produced.

## THE SAME TEXT SHAPE HAS OPPOSITE OWNERS IN TWO REAL ENGLISH PAPERS

Both verdicts were reached by RASTERIZING the page — never by asking an extractor, because
"pdftotext cannot see it" is not "it is not there" (CLAUDE.md, triple-verification rule).

    10.1016/j.jesp.2009.12.011  p3   PRINTS  `t(87) = 2.01, p < 05`   NO DOT
        THE PAPER's error. 6 of the 7 `p <` sites on that page carry the dot. The
        `<`-to-digit advance is 2.00pt where a dotted site on the same page measures
        3.90pt. There is NO rect/curve/line object in the gap, so no vector-painted dot.
        The page is natively typeset with no images. W0n was rewriting a published typo
        into a plausible statistic.

    10.1177/0956797613482946    p6   PRINTS  `F(2, 93) = 5.69, p < .05`   DOT PRESENT
        OURS. Page 6 is a SCAN with an OCR text layer in base-14 fonts; the same pass
        renders `F(2, 93)` as `K2, 93)` and eta-squared-p as `^p'`. Our extraction lost it.

## WHY NO GATE CAN SEPARATE THEM

A layout gate calibrated on advance-width ratio (0.51 dotless vs 0.99 dotted) was built and
REFUTED: Dong's char boxes come from an OCR ENGINE rather than the typesetter, so the gate
manufactures its own evidence for exactly the case it exists to catch. It is independently
broken by justified-text stretch, by mixed styles on one page, by pages with no healthy site
to calibrate against, and by pdfplumber's `x0`/`x1` being glyph BOUNDING BOXES, not advances.

**Under irreducible ambiguity the default is PASS-THROUGH.** Pass-through is reversible for
the consumer; a repair is not. The source token stays intact so the consumer can still
decide, which it could not once we had rewritten it. Flagging a suspected author error is
ESCImate's and Scimeto's role — they have the UI and the mandate for it.

STATED CONSEQUENCE: where the dot really was ours to restore (Dong), the consumer now
receives `p < 05` and must decide for itself. Accepted by the owner of every consumer,
2026-08-14. See docs/SCOPE.md and LESSONS.md L-031 trap 1.
"""

from __future__ import annotations

from pathlib import Path

import pytest

# Camelot is not needed by this module's tests; skipping it keeps them fast.
# Declarative on purpose: this was `os.environ.setdefault(...)` at module scope,
# which executes during COLLECTION and was never undone, so importing this file
# disabled Camelot for the WHOLE pytest process and every real-PDF table test
# collected afterwards found no tables. `conftest._camelot_disabled_per_module`
# reads this flag and restores the prior value when the module finishes.
DISABLE_CAMELOT = True

from docpluck.normalize import NormalizationLevel, normalize_text
from docpluck.render import render_pdf_to_markdown

TEST_PDFS = Path(__file__).resolve().parents[1].parent / "PDFextractor" / "test-pdfs"


def _norm(text: str) -> str:
    out, _ = normalize_text(text, NormalizationLevel.academic)
    return out


def test_the_paper_s_own_dotless_threshold_is_no_longer_laundered_real_pdf():
    """`10.1016/j.jesp.2009.12.011` p3 PRINTS `p < 05`. We now deliver it.

    The rasterized page is the authority: the author dropped the period. Restoring it
    would launder a published defect into a meta-science pipeline, where a consumer would
    then validate a number the paper never printed and the author would never learn.
    """
    pdf = TEST_PDFS / "apa" / "ar_apa_j_jesp_2009_12_011.pdf"
    if not pdf.exists():
        pytest.skip(f"fixture missing: {pdf}")
    md = render_pdf_to_markdown(pdf.read_bytes())
    assert "p < 05" in md, "the paper's own dotless threshold must survive verbatim"
    assert "p < .05 (see" not in md, "W0n is retired; this is the laundered form"
    # Every HEALTHY threshold in the same paper is still byte-identical — retiring a
    # repair must not disturb text that was already correct.
    assert "p < .001" in md
    assert "p < .068" in md
    assert "p < .025" in md


def test_the_rule_itself_is_gone_not_merely_disabled():
    """A rule left in place "disabled" is dead code the next reader re-enables.

    Same standard as the A3d retirement: assert the symbol is absent, not that it
    happens to return its input.
    """
    import docpluck.normalize as N
    import docpluck.render as R

    assert not hasattr(N, "recover_p_threshold_dropped_decimal")
    assert not hasattr(R, "recover_p_threshold_dropped_decimal")


def test_no_step_named_W0n_is_tracked():
    out, report = normalize_text("t(87) = 2.01, p < 05 (see Fig. 1)", NormalizationLevel.academic)
    assert out == "t(87) = 2.01, p < 05 (see Fig. 1)"
    assert not any("W0n" in s for s in report.steps_applied), report.steps_applied
    assert "p_decimal_points_recovered" not in report.changes_made


class TestBothOwnersNowPassThroughIdentically:
    """The point of the retirement: one shape, one behaviour, regardless of owner.

    These were the rule's POSITIVE cases — every one of them used to be rewritten. They
    are kept verbatim because they are the shapes the corpus actually contains; only the
    expected answer inverted.
    """

    @pytest.mark.parametrize(
        "src",
        [
            "t(87) = 2.01, p < 05 (see",
            "F(1, 88) = 7.49, p < 01.",
            "F(1, 88) = 13.14, p < 001. Consistent",
            "(p > 05)",
            "(p <= 05)",
            "z = 2.1, P < 05,",
            "* p < 05. ** p < 01.",
        ],
    )
    def test_passes_through(self, src):
        assert _norm(src) == src

    def test_line_wrapped_legend_keeps_the_value_while_A1_joins_the_wrap(self):
        """The ONE case where the whole string changes, and W0n is not why.

        `A1` rejoins a statistical line-break (`note\\np < 05` -> `note p < 05`). That is
        a separate, still-live NOTATION rule about layout, not about the value. Asserted
        explicitly rather than dropped, so a future reader does not mistake the join for
        a surviving W0n.
        """
        assert _norm("note\np < 05 level") == "note p < 05 level"


class TestTextTheGuardsAlwaysProtectedIsStillProtected:
    """W0n's four guards each excluded a shape. Those shapes must be unchanged now too.

    Retiring a rule can EXPOSE a sibling it was masking (LESSONS.md L-031 trap 4), so the
    negative battery is more valuable after the retirement than before it, not less.
    """

    @pytest.mark.parametrize(
        "src",
        [
            "F(3, 90) = 6.62, p < .05. Again",
            "significant, p < 0.05, two-tailed",
            "participant p = 05 was excluded",
            "p = 01 in the log",
            "p < 10 in the marginal test",
            "n < 05 impossible but not a p",
            "p < 052 items",
            "p < 05.3 units",
            "reported p < 005 threshold",
            "strict p < 0001 criterion",
            "the probability p < 05 in our model",
            "whenever p < 05 we reject",
        ],
    )
    def test_untouched(self, src):
        assert _norm(src) == src


def test_idempotent():
    s = "t(87) = 2.01, p < 05 (see Fig. 1), * p < 05."
    once = _norm(s)
    assert _norm(once) == once == s
