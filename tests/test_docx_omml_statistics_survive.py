"""DOCX equations must not delete the NAME of a statistic (v2.4.131).

**Same defect class as the render-channel deletion fixed in v2.4.130 (LESSONS.md
L-032), in the DOCX channel — and it was still shipping a day later.**

`mammoth` has no model of `m:oMath` at all (grepped: zero references), so it
skips the element as unrecognised markup. Measured end to end on a real paper:

    28_ImageMemorability.docx says   F(1,86) = 48.50, p < .001, ηp2 = .361.
    docpluck delivered               F(1,86) = 48.50, p < .001, = .361.

A bare `= .361` cannot be attributed to any statistic by any consumer. That is
**worse than a wrong number**: a wrong number can be challenged, an unlabelled
one is structurally unidentifiable.

WHY IT SURVIVED FOR YEARS — the module's own docstring said OMML was "rare in
social science papers where stats are written as plain text." Measured over 26
real papers from CitationGuard's validation corpus:

    4 / 26 papers (15%) contain OMML
    ~45 non-empty math spans
    EVERY ONE is `ηp2`, `χ2` or `ρ` — exactly the symbols docpluck exists to
    deliver. 8 of the 9 spans in the file above are `ηp2`.

The claim was not merely optimistic, it was inverted: OMML is uncommon per
document and, where it occurs, it is used almost exclusively for the effect
sizes that matter most. **An unmeasured "in practice this is rare" in a
docstring is the same failure mode as an unmeasured rule** (LESSONS.md L-027).

THE FIX: `_inline_omml_runs` rewrites each `m:oMath` element into a plain
`w:r`/`w:t` run carrying the equation's own `m:t` text, BEFORE mammoth sees the
file — so the symbol lands in exactly the position the equation occupied, which
is the whole point (`= .361` is only interpretable if its label precedes it).
"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pytest

pytest.importorskip("mammoth", reason="mammoth not installed (pip install docpluck[docx])")

from docpluck.extract_docx import _inline_omml_runs, extract_docx

_REAL = Path(
    r"C:/Users/filin/Vibe/MetaScienceTools/CitationGuard/apps/worker/testpdfs"
    r"/validation/docx/28_ImageMemorability.docx"
)


def _docx_with_body(body_xml: str) -> bytes:
    """Minimal but real DOCX carrying `body_xml` inside `word/document.xml`."""
    doc = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
        ' xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math">'
        f"<w:body>{body_xml}</w:body></w:document>"
    )
    rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Target="word/document.xml" Type="http://schemas.openxmlformats.org'
        '/officeDocument/2006/relationships/officeDocument"/></Relationships>'
    )
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml",
                   '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                   '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                   '<Default Extension="xml" ContentType="application/xml"/>'
                   '<Override PartName="/word/document.xml" ContentType="application/vnd'
                   '.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>')
        z.writestr("_rels/.rels", rels)
        z.writestr("word/document.xml", doc)
    return buf.getvalue()


_STAT_PARA = (
    "<w:p><w:r><w:t xml:space=\"preserve\">F(1,86) = 48.50, p &lt; .001, </w:t></w:r>"
    '<m:oMath><m:r><m:t>\u03b7p2</m:t></m:r></m:oMath>'
    "<w:r><w:t xml:space=\"preserve\"> = .361.</w:t></w:r></w:p>"
)


def test_the_effect_size_label_survives():
    text, _ = extract_docx(_docx_with_body(_STAT_PARA))
    assert "\u03b7p2" in text, "the statistic's NAME was deleted"
    assert "= .361" in text
    assert ", = .361" not in text, "a bare unlabelled value must not be emitted"


def test_the_symbol_lands_in_the_right_place():
    """Position is the information at risk — `= .361` only means something if
    its label immediately precedes it."""
    text, _ = extract_docx(_docx_with_body(_STAT_PARA))
    i = text.find("\u03b7p2")
    assert i != -1
    assert text[i:].startswith("\u03b7p2 = .361")


def test_a_docx_with_no_equations_is_returned_byte_identical():
    """The common case must pay nothing and must not be repacked."""
    plain = _docx_with_body("<w:p><w:r><w:t>No equations here.</w:t></w:r></w:p>")
    assert _inline_omml_runs(plain) is plain or _inline_omml_runs(plain) == plain


def test_an_equation_with_no_text_is_left_alone():
    """A pure graphic / bare fraction bar has nothing to recover — do not touch
    it, so nothing mammoth handles today changes behaviour."""
    body = "<w:p><m:oMath><m:f><m:num/><m:den/></m:f></m:oMath></w:p>"
    src = _docx_with_body(body)
    assert _inline_omml_runs(src) == src


def test_malformed_input_never_makes_extraction_worse():
    assert _inline_omml_runs(b"not a zip at all") == b"not a zip at all"


def test_the_guard_is_LOAD_BEARING_not_decoration():
    """Break the rewrite and the defect must come back.

    The FIRST version of `_inline_omml_runs` early-exited on
    `b"<m:oMath" not in docx_bytes` — but a DOCX is a ZIP, so those bytes are
    COMPRESSED and the marker never appears. The function was a silent no-op on
    every file in existence while looking correct. This asserts the rewrite is
    what saves the symbol, not something else in the pipeline.
    """
    import sys

    src = _docx_with_body(_STAT_PARA)
    # NOT `import docpluck.extract_docx as M` — `docpluck/__init__.py` does
    # `from .extract_docx import extract_docx`, so that name resolves to the
    # FUNCTION, not the module. Reach the module through sys.modules.
    M = sys.modules["docpluck.extract_docx"]

    original = M._inline_omml_runs
    try:
        M._inline_omml_runs = lambda b: b  # the pre-fix behaviour, exactly
        text, _ = extract_docx(src)
    finally:
        M._inline_omml_runs = original

    assert "\u03b7p2" not in text, (
        "with the rewrite disabled the symbol survived anyway — this test proves "
        "nothing about the fix"
    )
    assert "= .361" in text, "mammoth still emits the bare value, which is the defect"


@pytest.mark.skipif(not _REAL.exists(), reason=f"corpus fixture missing: {_REAL.name}")
def test_the_real_paper_recovers_all_eight_occurrences():
    """`28_ImageMemorability.docx` — 8 of its 9 OMML spans are partial eta squared.

    See the block at the end of this file for the two defects this fix itself
    shipped with, both found by an independent review on 2026-08-15.
    """
    text, _ = extract_docx(_REAL.read_bytes())
    assert text.count("\u03b7p2") == 8
    assert "F(1,86) = 48.50, p < .001, \u03b7p2 = .361." in text


# ── The v2.4.131 fix shipped with two defects of its own (found 2026-08-15) ────
#
# An independent review (Fable 5, via Claude Code CLI) read this module against
# the handoff that introduced it and found two classes the first version missed.
# BOTH were reproduced against the unfixed code before anything was changed —
# these are the outputs the shipped v2.4.131 actually returned:
#
#     display math   'Effect size: [W-S]/S end.'   ->  'Effect size:\nend.'
#     a fraction     'ratio = 1/2 of sample.'      ->  'ratio = 12 of sample.'
#
# The second is the worse of the two and is a REGRESSION, not a survival: before
# v2.4.131 the fraction was deleted, and after it the library manufactured the
# number `12`. **A fabricated plausible value does not announce itself**, which
# this project ranks as the worst class of wrong output -- strictly worse than
# the deletion it replaced. The cause was `b"".join(m:t)`: correct for a run of
# characters, catastrophic for a structured object.


def test_display_math_is_not_deleted():
    """`m:oMathPara` -- mammoth skips THAT element too, so rewriting only the
    inner `m:oMath` left the replacement run stranded inside a discarded parent.

    Real occurrence: `42_StressExposureTraining.docx`, one of the four OMML
    papers in this fix's own 26-paper measurement, defines
    `Excess Distance = (W-S)/S` in an `m:oMathPara` and lost it entirely.
    """
    body = (
        '<w:p><w:r><w:t xml:space="preserve">Effect size: </w:t></w:r></w:p>'
        "<w:p><m:oMathPara><m:oMath><m:r><m:t>W-S</m:t></m:r></m:oMath>"
        "</m:oMathPara></w:p>"
        '<w:p><w:r><w:t xml:space="preserve">end.</w:t></w:r></w:p>'
    )
    text, _ = extract_docx(_docx_with_body(body))
    assert "W-S" in text, "display math inside m:oMathPara was deleted"


def test_a_fraction_never_fuses_into_a_fabricated_number():
    """`1/2` must not become `12`.

    The anti-fabrication invariant of the linearizer: an operator is emitted for
    every structure whose relationship we can NAME, and a structure we cannot
    name joins its parts with a space, so it is incapable of manufacturing a
    value.
    """
    body = (
        '<w:p><w:r><w:t xml:space="preserve">ratio = </w:t></w:r>'
        "<m:oMath><m:f><m:num><m:r><m:t>1</m:t></m:r></m:num>"
        "<m:den><m:r><m:t>2</m:t></m:r></m:den></m:f></m:oMath>"
        '<w:r><w:t xml:space="preserve"> of sample.</w:t></w:r></w:p>'
    )
    text, _ = extract_docx(_docx_with_body(body))
    assert "ratio = 1/2 of sample." in text
    assert "12" not in text, "the fraction fabricated a number"


def test_a_compound_fraction_keeps_its_grouping():
    """`28_ImageMemorability.docx` span 9 -- the one span outside the eight etas.

    It reads `(Absent-Present)/Absent*100`; v2.4.131 delivered
    `Absent-PresentAbsent*100`, which reads as a single term and is not the
    published quantity.
    """
    body = (
        "<w:p><m:oMath><m:f>"
        "<m:num><m:r><m:t>Absent-Present</m:t></m:r></m:num>"
        "<m:den><m:r><m:t>Absent</m:t></m:r></m:den></m:f>"
        "<m:r><m:t>*100</m:t></m:r></m:oMath></w:p>"
    )
    text, _ = extract_docx(_docx_with_body(body))
    assert "(Absent-Present)/Absent*100" in text


def test_an_unnameable_structure_refuses_to_imply_an_operator():
    """A summation's bounds and body must not fuse into `19x`.

    We do not model `m:nary`, so we do not guess: the parts are space-joined.
    Lossy and VISIBLY so -- which is the point. The failure mode we will not
    accept is a plausible number nobody can challenge.
    """
    body = (
        '<w:p><m:oMath><m:nary><m:naryPr><m:chr m:val="\u2211"/></m:naryPr>'
        "<m:sub><m:r><m:t>1</m:t></m:r></m:sub>"
        "<m:sup><m:r><m:t>9</m:t></m:r></m:sup>"
        "<m:e><m:r><m:t>x</m:t></m:r></m:e></m:nary></m:oMath></w:p>"
    )
    text, _ = extract_docx(_docx_with_body(body))
    assert "19" not in text, "an unmodelled structure fused two numerals"
    assert "1 9 x" in text


def test_subscripts_still_concatenate_so_the_channels_agree():
    """`etap2` / `chi2` / `R2` must keep concatenating base+script.

    That is the convention pdftotext already produces for the same symbols, so
    the DOCX and PDF channels give one answer for one input
    (`docs/SYMBOL_CONTRACT.md`). The fraction fix must not disturb it.
    """
    body = (
        "<w:p><m:oMath><m:sSup>"
        "<m:e><m:r><m:t>R</m:t></m:r></m:e>"
        "<m:sup><m:r><m:t>2</m:t></m:r></m:sup></m:sSup></m:oMath></w:p>"
    )
    text, _ = extract_docx(_docx_with_body(body))
    assert "R2" in text


def test_an_empty_structure_emits_no_stray_operator():
    """A bare fraction bar has no text, so it must contribute no `/`.

    Caught by `test_an_equation_with_no_text_is_left_alone` when the first
    version of the linearizer emitted `/` for `<m:f><m:num/><m:den/></m:f>` --
    recorded here as its own case so the reason is not lost.
    """
    src = _docx_with_body("<w:p><m:oMath><m:f><m:num/><m:den/></m:f></m:oMath></w:p>")
    assert _inline_omml_runs(src) == src


_REAL_DISPLAY = Path(
    r"C:/Users/filin/Vibe/MetaScienceTools/CitationGuard/apps/worker/testpdfs"
    r"/validation/docx/42_StressExposureTraining.docx"
)


@pytest.mark.skipif(
    not _REAL_DISPLAY.exists(), reason=f"corpus fixture missing: {_REAL_DISPLAY.name}"
)
def test_the_real_display_math_paper_recovers_its_equation():
    """One of the four OMML papers in this fix's own 26-paper measurement.

    It defines `Excess Distance` with a display equation in `m:oMathPara`.
    v2.4.131 delivered the surrounding prose and dropped the defining equation,
    so 1 in 4 of the fix's own positives was still broken after the fix landed.
    """
    text, _ = extract_docx(_REAL_DISPLAY.read_bytes())
    assert "Excess Distance" in text
    assert "W-S" in text or "W\u2212S" in text, "the defining equation was deleted"


# ── The fix was BYPASSED by the public sections path (found 2026-08-15) ───────
#
# v2.4.131 fixed `extract_docx`. But `extract_sections(docx)` does NOT go
# through `extract_docx` — `sections/__init__.py` calls `annotate_docx`, which
# called mammoth directly. **So one release after the defect was declared
# fixed, the public sections path was still deleting the name of every
# statistic**, and MetaESCI runs an editable install of this tree.
#
# The four-checks rule's second item names this exactly: *every production path
# is wired, not just the one you were looking at.*


def test_the_sections_path_also_recovers_the_statistic_names():
    """`extract_sections(docx)` must not delete what `extract_docx` preserves."""
    from docpluck.sections import extract_sections

    doc = extract_sections(_docx_with_body(_STAT_PARA), source_format="docx")
    text = doc.normalized_text
    assert "\u03b7p2" in text, "the sections path still deletes the statistic's NAME"
    assert ", = .361" not in text, "a bare unlabelled value must not be emitted"


def test_mammoth_was_announcing_the_deletion_all_along():
    """The library NAMED the dropped element on every affected file, for years.

    `mammoth.convert_to_html(...).messages` carries
        "An unrecognised element was ignored: {…/2006/math}oMath"
    and both DOCX call sites discarded it. That message is why this defect was
    discoverable at any point in the last several years without a corpus, a
    raster, or a font census — nobody read the channel the dependency already
    provides.

    This test asserts the channel is real, so the decision to read it is not
    taken on trust.
    """
    import io

    import mammoth

    raw = _docx_with_body(_STAT_PARA)
    messages = [str(m) for m in (mammoth.convert_to_html(io.BytesIO(raw)).messages or ())]
    assert any("oMath" in m for m in messages), (
        f"mammoth no longer reports the dropped equation; messages={messages}"
    )

    # ...and once the rewrite runs, there is nothing left for it to complain about.
    fixed = _inline_omml_runs(raw)
    after = [str(m) for m in (mammoth.convert_to_html(io.BytesIO(fixed)).messages or ())]
    assert not any("oMath" in m for m in after), (
        f"the equation is still being dropped after the rewrite; messages={after}"
    )
