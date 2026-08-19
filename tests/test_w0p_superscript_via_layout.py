"""W0p: a typographic superscript digit is never fused into the number before it.

**Every test here was watched FAILING against the unfixed code first.**

THE DEFECT, proven on a real corpus paper (`10.1525/collabra.34606`, Collabra,
English). The text channel delivers:

    'Overall, N = 2,5801'

The layout channel shows what that actually is:

    '2'  size 8.00  top 80.52    body
    ','  size 8.00  top 80.52
    '5'  size 8.00  top 80.52
    '8'  size 8.00  top 80.52
    '0'  size 8.00  top 80.52
    '1'  size 6.64  top 78.94    83% of body size, raised 1.58pt  -> SUPERSCRIPT

A sample size of **2,580** with a **footnote marker 1** glued to it. The paper
contains ZERO Unicode superscript codepoints anywhere, so pdftotext emits an
ordinary ASCII digit and the A5 exponent guard — which keys on superscript
CODEPOINTS — cannot see it. Only font size plus baseline prove it.

TWO injuries, both silent:

1. The sample size reads as **25,801** instead of 2,580.
2. The fused token matches the numeric-locale rule's European marker
   `\\d,\\d{4,}`, so a footnote marker MANUFACTURED a false European signal —
   one of only two `conflict` verdicts among 396 English papers.

WHY IT WAS NOT CAUGHT EARLIER, stated plainly because it is the interesting
part: the superscript-detection signal had been validated and documented
(`docs/FINDINGS_2026-08-13`, capability A: median size ratio 0.667,
`upright == True` filtering mandatory) and then **wired into nothing**. It was
recorded as "signal validated, not yet wired". A capability that is built,
measured and then invoked by nothing is indistinguishable from one never built,
except that it carries the appearance of being handled.

THE RULE. Same rule A5 already applies to Unicode superscripts, sourced from
layout instead of from the codepoint: a superscript run directly after a digit
run becomes **caret notation**, never a bare fused digit. `2,5801` ->
`2,580^1`. That is lossless (`2,580^1` evaluates to 2,580), it keeps both
readings recoverable, it deletes nothing — decision D4 forbids deleting
superscript digits from body text because geometry cannot distinguish a footnote
marker from a real exponent like `×10⁹/L` — and it stops the locale false
positive dead.

GUARDS, each from a measured hazard:
  * `upright == True` only. 82% of raw superscript candidates are rotated
    watermark text, where pdfplumber reports impossible sizes.
  * the marker run must be meaningfully SMALLER than the base run and RAISED.
  * conservative correlation: rewrite at most as many text sites as the layout
    counted, left to right — the same mechanism W0h and W0m use.
"""

from __future__ import annotations


from docpluck.normalize import (
    NormalizationLevel,
    normalize_text,
    recover_superscript_via_layout,
)


class _FakeLayout:
    """Minimal LayoutDoc stand-in: only `.pages[i].chars` is read."""

    class _Page:
        def __init__(self, chars):
            self.chars = chars

    def __init__(self, *page_char_lists):
        self.pages = [self._Page(c) for c in page_char_lists]


def _ch(text, size, top, upright=True):
    return {"text": text, "size": size, "top": top, "upright": upright}


def _run(s, size, top, upright=True):
    return [_ch(c, size, top, upright) for c in s]


# ── the real corpus case ────────────────────────────────────────────────

def test_the_collabra_sample_size_is_not_fused():
    """`N = 2,5801` is 2,580 with footnote marker 1. Measured, not constructed."""
    layout = _FakeLayout(_run("N = ", 8.0, 80.52)
                         + _run("2,580", 8.0, 80.52)
                         + _run("1", 6.64, 78.94))
    assert recover_superscript_via_layout("Overall, N = 2,5801", layout) == (
        "Overall, N = 2,580^1"
    )


def test_the_fused_token_no_longer_has_the_ambiguous_four_decimal_shape():
    """RE-FIXTURED 2026-08-14 — the SUBJECT survived, the INSTRUMENT did not.

    This used to call `infer_numeric_locale()` before and after the repair and
    assert its European marker `\\d,\\d{4,}` appeared and then disappeared. The
    document-level locale inference was DELETED in v2.4.129: its verdict was
    confidently wrong on the only genuine European table ever found in an
    English paper, because every marker it used was operator-gated and a bare
    table cell has no operator — so it measured the INSTRUMENT, not the corpus.

    The defect W0p fixes is unchanged, and is now asserted DIRECTLY rather than
    through a deleted detector: a superscript footnote marker fused onto a
    sample size yields `2,5801`, a token no reader can interpret and which a
    naive parser reads as a four-decimal European value.
    """
    import re

    layout = _FakeLayout(_run("2,580", 8.0, 80.52) + _run("1", 6.64, 78.94))
    fused = "Overall, N = 2,5801 participants. p = .03, d = 0.45"
    four_decimals = re.compile(r"\d,\d{4,}")
    assert four_decimals.search(fused), "the fused token has the ambiguous shape"
    fixed = recover_superscript_via_layout(fused, layout)
    assert not four_decimals.search(fixed), "W0p must remove it"
    assert "2,580^1" in fixed


# ── the guards ──────────────────────────────────────────────────────────

def test_rotated_watermark_text_is_ignored():
    """82% of raw candidates are rotated watermark glyphs with nonsense sizes."""
    layout = _FakeLayout(_run("2,580", 8.0, 80.52)
                         + _run("1", 3.34, 78.94, upright=False))
    assert recover_superscript_via_layout("N = 2,5801", layout) == "N = 2,5801"


def test_same_size_digits_are_not_a_superscript():
    """A genuine 5-digit number must never be split."""
    layout = _FakeLayout(_run("25801", 8.0, 80.52))
    assert recover_superscript_via_layout("N = 25801", layout) == "N = 25801"


def test_a_lowered_run_is_not_a_superscript():
    """A subscript is smaller too — the RAISED baseline is load-bearing."""
    layout = _FakeLayout(_run("2,580", 8.0, 80.52) + _run("1", 6.64, 83.0))
    assert recover_superscript_via_layout("N = 2,5801", layout) == "N = 2,5801"


def test_no_layout_is_a_no_op():
    assert recover_superscript_via_layout("N = 2,5801", None) == "N = 2,5801"


def test_text_without_the_fused_token_is_untouched():
    """Layout says one thing, the text does not contain it — change nothing."""
    layout = _FakeLayout(_run("2,580", 8.0, 80.52) + _run("1", 6.64, 78.94))
    assert recover_superscript_via_layout("no such number here", layout) == (
        "no such number here"
    )


def test_idempotent():
    layout = _FakeLayout(_run("2,580", 8.0, 80.52) + _run("1", 6.64, 78.94))
    once = recover_superscript_via_layout("N = 2,5801", layout)
    assert recover_superscript_via_layout(once, layout) == once


# ── wired into the pipeline, not merely defined ─────────────────────────

def test_it_is_REACHABLE_through_normalize_text():
    """The point of this release: a capability nothing invokes is not shipped.

    `dropped_minus_layout` is the parameter the section and render paths already
    thread through for the other layout-gated repairs; W0p rides the same one.
    """
    layout = _FakeLayout(_run("2,580", 8.0, 80.52) + _run("1", 6.64, 78.94))
    out, report = normalize_text(
        "Overall, N = 2,5801 participants.",
        NormalizationLevel.academic,
        dropped_minus_layout=layout,
    )
    # RE-FIXTURED 2026-08-14: the end state used to be `2580^1`, because W0p
    # split the marker and A3a then stripped the thousands separator. A3a is
    # deleted, so the separator survives and the end state is `2,580^1` — the
    # sample size exactly as the paper printed it, the marker still visible,
    # and the fused `25801` never produced. This is a strictly better outcome:
    # one fewer rewrite, and the same defect fixed.
    assert "2,580^1" in out
    assert "25801" not in out
    assert "W0p_superscript_layout" in report.steps_applied


def test_without_layout_the_step_does_not_claim_to_have_run():
    """A step that reports work it could not do is the defect this release is about."""
    _, report = normalize_text(
        "Overall, N = 2,5801 participants.", NormalizationLevel.academic
    )
    assert "W0p_superscript_layout" not in report.steps_applied
