"""A running header's debris must not veto the heading that follows it.

## The defect

``sections/annotators/text.py::_prior_paragraph_is_sentence_terminated`` is the
corroboration a canonical heading needs when the ONLY rule admitting it is
"preceded by a blank line". It walks back over space/tab/newline and then
requires the character it lands on to be in ``".!?/"``.

Two characters pdftotext really emits are in neither set:

* **U+0008 BACKSPACE.** ``10.3389/fvets.2025.1645266`` (PMC13137375) p2 carries
  the Frontiers running header as form-feed + ``Abuna et al.`` + ``\\x08``. The
  period IS there; the BACKSPACE stands after it, so the walk lands on ``\\x08``
  and the guard returns False. The heading ``1 Introduction: the need for
  regenerative solutions in reproductive medicine`` is therefore never emitted --
  and because ``partition_into_sections`` fills each span up to the NEXT matched
  heading, the preceding ``KEYWORDS`` span swallows **69,849 characters**, the
  entire article.
* **U+000C FORM FEED.** F0's ``_drop()`` deliberately KEEPS the page boundary
  (LESSONS L-052), so a heading that is first on a page has a bare form feed
  before it and is rejected the same way. 2 sites in the same 30-paper corpus.

docpluck already owned half of this diagnosis. ``normalize.py`` records that
"One stray BACKSPACE was enough to make the line unequal to its layout-channel
twin and so unstrippable", and v1.9.57 fixed it -- **inside the F0 comparison
key only** (``_NONSPACE_CTRL_RE``, used solely by ``_key``). The character stayed
in the emitted text, where a second, unrelated rule then tripped over it.

## Why the strip is NARROW

Measured over the 30-paper held-out PMC corpus: **49 non-form-feed C0 controls in
16 of 30 papers**. All **33** U+0008 occurrences have the identical context
``'.'`` + BS + newline -- trailing furniture. **Zero** have the overstrike
signature ``(.)\\x08\\1``, so no doubled letter can be manufactured by removing
them.

The other control characters are NOT furniture -- they are corrupted content
glyphs, and deleting them would destroy text::

    Schri\\x02macher    -> "Schrittmacher"   (PMC13132920)
    No\\x04allsanitat   -> "Notfall..."      (same paper)
    A\\x03 -B\\x03 helices                   (PMC13134433)

So ``_strip_furniture_controls`` removes **line-final U+0008 only** and COUNTS
the rest, rather than deleting a class it has not proven to be furniture.

## Blast radius of the guard change

39 canonical headings across the 30 papers are rejected by this guard. Only 3 are
furniture-blocked (1x U+0008, 2x U+000C). The other 36 -- 20 blocked by a letter
(real pdftotext column-wrap), 9 by a comma, 6 by semicolon/paren/colon/digit,
including the founding CRediT case -- must STILL be rejected.
``test_founding_credit_wrap_is_still_rejected`` is that gate, and it is written
first precisely because no test exercised this helper on its founding input.
"""

from __future__ import annotations

import re


# -- The FP gate: the case the guard was written for must still be rejected --

def test_founding_credit_wrap_is_still_rejected():
    """ip_feldman/PSPB: pdftotext column-wraps a CRediT list so a blank line
    falls mid-list, making ``Funding`` look paragraph-isolated. Rejecting it is
    the guard's whole purpose. No test called this helper on that input before
    2026-08-21 -- ``test_sections_v161_text_annotator.py`` only covers the
    mid-line ``Funding acquisition`` form, which never reaches the guard.
    """
    from docpluck.sections.annotators.text import _prior_paragraph_is_sentence_terminated
    text = "...Conceptualization; Data curation;\n\nFunding acquisition; Writing.\n"
    line_start = text.index("Funding")
    assert _prior_paragraph_is_sentence_terminated(text, line_start) is False


def test_wrapped_mid_sentence_line_is_still_rejected():
    """The 20 letter-blocked sites: a prior line ending mid-phrase is a real
    column wrap, not a paragraph end."""
    from docpluck.sections.annotators.text import _prior_paragraph_is_sentence_terminated
    text = ("the participants were randomly assigned to a condition and\n\n"
            "Results were analysed with a mixed model.\n")
    assert _prior_paragraph_is_sentence_terminated(text, text.index("Results")) is False


def test_sentence_terminated_prior_paragraph_is_still_accepted():
    from docpluck.sections.annotators.text import _prior_paragraph_is_sentence_terminated
    text = "...and the effect was robust.\n\nMethods\n\nWe recruited 200 participants.\n"
    assert _prior_paragraph_is_sentence_terminated(text, text.index("Methods")) is True


# -- The defect: furniture must not veto ------------------------------------

def test_running_header_backspace_does_not_veto_the_next_heading():
    """10.3389/fvets.2025.1645266 (PMC13137375) p2, verbatim shape."""
    from docpluck.sections.annotators.text import _prior_paragraph_is_sentence_terminated
    text = (
        "extracellular vesicles, gonads, regeneration, stem cell therapy\n\n"
        "\x0cAbuna et al.\x08\n\n"
        "1 Introduction: the need for regenerative solutions in reproductive medicine\n\n"
        "Even though stem cell-based therapies are promising, evidence suggests...\n"
    )
    line_start = text.index("1 Introduction")
    assert _prior_paragraph_is_sentence_terminated(text, line_start) is True


def test_bare_page_break_does_not_veto_the_next_heading():
    """F0 keeps the form feed (L-052), so a heading first on a page has only a
    page break before it. A page boundary is a paragraph end, not a missing
    full stop."""
    from docpluck.sections.annotators.text import _prior_paragraph_is_sentence_terminated
    text = "...concluded the first study.\n\f\nMethods\n\nWe recruited 200 participants.\n"
    assert _prior_paragraph_is_sentence_terminated(text, text.index("Methods")) is True


# -- The strip itself -------------------------------------------------------

def test_strip_furniture_controls_removes_line_final_backspace():
    from docpluck.normalize import _strip_furniture_controls
    assert _strip_furniture_controls("Abuna et al.\x08\nbody") == "Abuna et al.\nbody"
    assert _strip_furniture_controls("Frey et al.\x08") == "Frey et al."


def test_strip_furniture_controls_preserves_corrupted_content_glyphs():
    """U+0002/3/4/7 are corrupted GLYPHS carrying content, not furniture.
    Deleting them turns "Schrittmacher" into "Schrimacher"."""
    from docpluck.normalize import _strip_furniture_controls
    for sample in ("Schri\x02macher", "No\x04allsanitat", "A\x03 -B\x03 helices",
                   "- \x07boldened"):
        assert _strip_furniture_controls(sample) == sample


def test_strip_furniture_controls_leaves_non_line_final_backspace_alone():
    """Only the measured furniture shape is removed. A BACKSPACE anywhere else
    is unproven and therefore passed through -- including the overstrike form,
    which does not occur in the corpus (0 of 33 sites) but would be CONTENT if
    it did."""
    from docpluck.normalize import _strip_furniture_controls
    assert _strip_furniture_controls("X\x08X") == "X\x08X"


def test_strip_furniture_controls_shares_one_vocabulary_with_the_f0_key():
    """One concept, one table: the characters this strip reasons about must be
    the same set ``_key()`` already discards, not a second hand-written list."""
    from docpluck import normalize as N
    for ch in ("\x02", "\x03", "\x04", "\x07", "\x08"):
        assert N._NONSPACE_CTRL_RE.search(ch), f"{ch!r} must be in the shared class"
    for ch in ("\n", "\t", "\f"):
        assert not N._NONSPACE_CTRL_RE.search(ch), f"{ch!r} must NOT be in the class"


def test_normalize_text_counts_the_control_chars_it_does_not_strip():
    """A control character we do NOT strip must be COUNTED, not silent. An
    unmeasured known limitation is an unpaid debt, not a disclosure."""
    from docpluck.normalize import normalize_text, NormalizationLevel
    out, report = normalize_text("Schri\x02macher runs A\x03 -B\x03 helices.",
                                 NormalizationLevel.academic)
    assert "\x02" in out and "\x03" in out
    assert report.residual_control_chars == 3


def test_normalize_text_emits_no_line_final_backspace():
    from docpluck.normalize import normalize_text, NormalizationLevel
    out, report = normalize_text("Abuna et al.\x08\n\nThe body starts here.\n",
                                 NormalizationLevel.academic)
    assert not re.search("\x08(?=\n|$)", out)
    assert report.residual_control_chars == 0
    assert "The body starts here." in out


def test_stripping_the_backspace_lets_H0_see_the_running_header():
    """A knock-on worth pinning rather than discovering later.

    ``_strip_document_header_banners`` (H0) already knew ``Abuna et al.`` was a
    header banner; it could not match the line while a BACKSPACE was glued to
    the end of it. Once C0 removes that character the banner strip fires, so the
    running header leaves the body as well -- which is the correct outcome and
    the same effect F0 achieves when it manages to detect the header.

    The body text must survive intact; only the banner goes.
    """
    from docpluck.normalize import normalize_text, NormalizationLevel
    with_bs, _ = normalize_text("Abuna et al.\x08\n\nThe body starts here.\n",
                                NormalizationLevel.academic)
    without_bs, _ = normalize_text("Abuna et al.\n\nThe body starts here.\n",
                                   NormalizationLevel.academic)
    assert with_bs == without_bs, "C0 must make the two inputs converge"
    assert "The body starts here." in with_bs


# -- The numbered-subtitle heading, and the near-miss that bounds it ---------
#
# Fixing the BACKSPACE alone does NOT fix PMC13137375, and finding that out is
# the reason this section exists. C0 runs BEFORE H0, so once the BACKSPACE is
# gone H0 can finally match and remove the whole running-header line -- which
# leaves the KEYWORD LIST adjacent to the heading. The guard then rejects on the
# letter `y` of "...stem cell therapy" instead of on the BACKSPACE, and the
# 69,849-character `keywords` span survives. An offline probe that stripped the
# character from an ALREADY-NORMALIZED string showed a large gain; the shipped
# composition did not. Test the composition that ships.
#
# The remaining evidence is typographic and narrow: the line carries an explicit
# SECTION-NUMBER PREFIX and the canonical word is immediately followed by a
# COLON, i.e. `1 Introduction: <subtitle>`. Both halves are required, and the
# near-miss below is why: on the SAME paper `2 Literature search` also carries a
# number prefix, and `literature` resolves canonically to **references** -- so a
# number-prefix-only escape would open a `references` section in the middle of
# the article and hand the entire body to a DROP label. The colon excludes it.

def _hints(text):
    from docpluck.sections.annotators.text import annotate_text
    return {h.char_start: h.text for h in annotate_text(text)}


def test_numbered_colon_subtitle_heading_is_admitted():
    """10.3389/fvets.2025.1645266 (PMC13137375) p2, post-H0 shape: the keyword
    list sits directly above the heading, so no prior sentence terminator
    exists and only the number-plus-colon evidence remains."""
    text = (
        "KEYWORDS\n\n"
        "extracellular vesicles, gonads, regeneration, stem cell therapy\n\n"
        "1 Introduction: the need for regenerative solutions in reproductive medicine\n\n"
        "Even though stem cell-based therapies are promising, evidence suggests...\n"
    )
    assert _hints(text).get(text.index("Introduction")) == "Introduction"


def test_numbered_heading_without_a_colon_is_still_rejected():
    """The near-miss, from the same paper: `2 Literature search` carries the
    same number prefix, and `literature` is a canonical synonym for
    **references**. Admitting it would open a back-matter label mid-article."""
    text = (
        "...promote angiogenesis and reduce fibrosis in the treated tissue and\n\n"
        "2 Literature search\n\n"
        "A structured search of PubMed and Scopus was performed...\n"
    )
    assert text.index("Literature") not in _hints(text)


def test_numbered_escape_does_not_rescue_the_founding_credit_wrap():
    """No number prefix, so the escape cannot reach it however the line ends."""
    text = "...Conceptualization; Data curation;\n\nFunding acquisition; Writing.\n"
    assert text.index("Funding") not in _hints(text)


def test_unnumbered_colon_heading_after_an_unterminated_line_is_still_rejected():
    """The colon alone is not enough: without a section number there is no
    typographic evidence that the line is a heading rather than prose."""
    text = ("the analysis proceeded in three stages and\n\n"
            "Results: we found a reliable effect of condition on choice.\n")
    assert text.index("Results") not in _hints(text)


# -- The counter must describe the string it is returned WITH ---------------

def test_residual_control_chars_is_correct_at_every_level():
    """`NormalizationLevel.none` returns EARLY, before the counter is set, so
    the field reported 0 while the returned text held 4 control characters.

    A provenance field that is right on two paths and silently wrong on the
    third is worse than no field at all: a consumer that gates on
    ``residual_control_chars == 0`` would have concluded the text was clean.
    The count must always describe the string it is returned alongside.
    """
    from docpluck.normalize import normalize_text, NormalizationLevel
    sample = "Schri\x02macher and A\x03 -B\x03 helices.\nFrey et al.\x08\n"
    for level in (NormalizationLevel.none, NormalizationLevel.standard,
                  NormalizationLevel.academic):
        out, report = normalize_text(sample, level)
        actual = sum(1 for ch in out if ord(ch) < 32 and ch not in "\n\t\f")
        assert report.residual_control_chars == actual, (
            f"level={level.value}: report says {report.residual_control_chars}, "
            f"returned text holds {actual}"
        )


def test_level_none_passes_control_characters_through_untouched():
    """`none` means none: C0 is a normalization step and must not run."""
    from docpluck.normalize import normalize_text, NormalizationLevel
    sample = "Frey et al.\x08\nbody"
    out, _ = normalize_text(sample, NormalizationLevel.none)
    assert out == sample
