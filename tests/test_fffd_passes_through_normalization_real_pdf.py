"""U+FFFD passes through normalization unchanged -- S5a and S5b are retired.

WHAT WAS HERE. Two normalize steps rewrote the replacement character from the
text around it: S5a (``<U+FFFD>2 = .04`` -> ``eta2 = .04``, from ESCImate
Request 1.2) and S5b, ``recover_fffd_comparison_operators`` (v2.4.57): a
``<U+FFFD>N`` became ``>=N`` / ``<=N`` by pairing it with a nearby ``<N`` (Rule
1), then every other ``<U+FFFD>N`` in the document took the same operator (Rule
2) -- and, when Rule 1 found nothing, whichever of ``>=`` / ``<=`` the document
already used anywhere. The render channel ran S5b a second time over the
assembled Markdown.

WHY THEY WERE RETIRED (owner decision 2026-09-25). Both decided on INFERENTIAL
evidence: they received only ``text: str``, never the glyph's font or slot, so
they fail the project's gate test ("replace every surrounding word with
garbage -- does the evidence survive?"). Measured over all 9,988 PDFs in the
article repository: S5a fired 0 times; S5b fired 20 times in 6 papers, 15
correct (all in 10.1371/journal.pmed.1004323) and 5 wrong -- on HAL cover pages
(10.1016/j.jesp.2010.12.004, 10.1016/j.jesp.2011.03.003,
10.1016/j.jesp.2011.03.007, 10.1016/j.jesp.2024.104697, 10.1098/rsos.230219)
the blank bracket before the DOI became ``<=`` or ``>=``; the rasterized page
prints nothing there. A further 199 ``<U+FFFD>N`` sites in 92 papers were one
``>=`` away from the same fallback, and on the page they are as often an
asterisk or an equals sign (``n = 100`` in 10.1287/mnsc.2023.03556) as an
operator. Decided by the maintainer 2026-09-25.

Every input below is a shape S5a/S5b used to rewrite. Each must now come out
still carrying its U+FFFD and with no comparison operator invented beside it.
Non-ASCII codepoints are built with ``chr()`` on purpose.
"""

from __future__ import annotations

import pytest

from docpluck.testing import require_corpus_pdf

# Camelot is not needed by the unit tests; the real-PDF test at the bottom reads
# the table channel through render and sets nothing globally.
DISABLE_CAMELOT = True

import docpluck.normalize as normalize_module
from docpluck.normalize import NormalizationLevel, normalize_text
from docpluck.render import render_pdf_to_markdown

FFFD = chr(0xFFFD)
GE = chr(0x2265)
LE = chr(0x2264)

# (input, the U+FFFD-bearing fragment that must survive verbatim)
SHAPES = [
    # S5b Rule 1 -- the plos_med_1 partition (it IS >= on that page; we no longer guess)
    ("fibroid size (<20/" + FFFD + "20 mm) was a factor", "/" + FFFD + "20 mm"),
    ("<20 mm versus " + FFFD + "20 mm", "versus " + FFFD + "20 mm"),
    (FFFD + "20 or <20 mm", FFFD + "20 or"),
    (">50 vs " + FFFD + "50", "vs " + FFFD + "50"),
    # S5b Rule 2 seeded by Rule 1 -- a lone site in the same document
    ("size (<20/" + FFFD + "20 mm); age " + FFFD + "18 years", "age " + FFFD + "18 years"),
    # S5b Rule 2 FALLBACK -- the HAL cover-page line (10.1016/j.jesp.2010.12.004),
    # with the article's own <= elsewhere in the document. The page prints nothing
    # before the DOI; S5b wrote `<=10.1016/...`.
    (
        "Psychology, 2011, 47 (2), pp.455.\n" + FFFD + "10.1016/j.jesp.2010.12.004"
        + FFFD + ". " + FFFD + "hal-00956611" + FFFD + "\n\nscores " + LE + " 3 were excluded",
        FFFD + "10.1016/j.jesp.2010.12.004",
    ),
    # S5b Rule 2 FALLBACK on a sample size (10.1287/mnsc.2023.03556 prints `n = 100`)
    ("(Collaboration 2015, n " + FFFD + " 100), and a cut-off of " + GE + " 5", "n " + FFFD + " 100"),
    # S5a -- eta before `2 =`, never observed in 9,988 papers
    ("Main effect, " + FFFD + "2 = 0.04, was strong", FFFD + "2 = 0.04"),
    ("Main effect (" + FFFD + "² = 0.04)", FFFD),
]


@pytest.mark.parametrize("text,survivor", SHAPES)
@pytest.mark.parametrize("level", [NormalizationLevel.standard, NormalizationLevel.academic])
def test_fffd_survives_normalize_text(text, survivor, level):
    out, _report = normalize_text(text, level)
    assert out.count(FFFD) == text.count(FFFD), f"a U+FFFD was rewritten: {out!r}"
    if level is NormalizationLevel.standard:
        # standard keeps >= / <= as printed, so the fragment is byte-identical
        assert survivor in out, out
    # nothing was invented directly before the surviving character
    for op in (GE, LE, ">=", "<=", "eta"):
        assert op + FFFD not in out and op + "10.1016" not in out, out


@pytest.mark.parametrize("text,survivor", SHAPES)
def test_fffd_survives_render_path_normalization(text, survivor):
    # preserve_math_glyphs=True is the render path's call into normalize_text.
    out, _ = normalize_text(text, NormalizationLevel.academic, preserve_math_glyphs=True)
    assert out.count(FFFD) == text.count(FFFD), out
    assert survivor in out, out


def test_no_fffd_step_or_count_in_the_report():
    text = "fibroid size (<20/" + FFFD + "20 mm); " + FFFD + "2 = .04"
    _, report = normalize_text(text, NormalizationLevel.academic)
    assert not [s for s in report.steps_applied if "fffd" in s.lower()], report.steps_applied
    assert not [k for k in report.changes_made if "fffd" in k.lower()], report.changes_made


def test_the_rewrite_function_is_gone():
    # A retired rule that stays importable gets re-wired by the next session.
    assert not hasattr(normalize_module, "recover_fffd_comparison_operators")
    import docpluck.render as render_module
    assert not hasattr(render_module, "recover_fffd_comparison_operators")


def test_plos_med_1_fffd_reaches_the_rendered_md_real_pdf():
    """10.1371/journal.pmed.1004323 carries 9 U+FFFD, all a `>=` drawn in
    TeX_CM_Maths_Symbols. S5b rewrote all 9 (correctly, on this paper) in body
    text and 6 again in the table channel. They now reach the rendered .md as
    U+FFFD in BOTH channels -- the body prose and the Table 2 remnant-size rows."""
    pdf = require_corpus_pdf("vancouver/plos_med_1.pdf")
    md = render_pdf_to_markdown(pdf.read_bytes())
    assert ("age " + FFFD + "18 years") in md
    assert ("<20/" + FFFD + "20 mm") in md
    assert ("versus " + FFFD + "20 mm") in md
    assert (FFFD + "5–10 mm") in md or (FFFD + "5-10 mm") in md, "table row"
    assert (GE + "18 years") not in md and (">=18 years") not in md
