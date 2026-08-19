"""The symbol-font corruption report must not spend a consumer's trust on nothing.

## The defect (R8), named by a post-fix review of v2.4.133

``extract_layout.detect_symbol_font_corruption`` reports a font whose entire
whole-document repertoire is ASCII letters that are all Adobe-Symbol Greek
preimages. That set covers **25 of the 26 lowercase letters**, so the test is far
weaker than it reads: any SUBSET FACE drawing only a couple of statistical
italics — ``{'p': 20, 't': 5}`` under ``Times-Italic`` — satisfies every
condition and is reported as corruption.

The report is record-only, so it cannot corrupt a number. What it can do is
worse in its own way: it is the channel that tells a consumer *which document to
distrust*, and a false positive there is indistinguishable from the real thing.

## The fix, and why these two exclusions specifically

Both were already validated against known NEGATIVES by
``tools/diag/glyph_font_discontinuity_scan.py`` and are now imported from the
library rather than re-implemented (one concept, one table):

* ``fonts_are_same_family`` — a narrow face sitting beside the SAME family
  styled is ordinary italic statistical notation.
* ``font_size_variant_base`` — ``CMR5`` is a TeX optical-size cut of ``CMR10``,
  narrow only because the document sets few characters at 5pt.

Measured on the real corpus by disabling each exclusion (2026-08-15):

    ieee_access_7   6 false positives  MSBM10 CMEX10 CMBX7 CMMI5 CMEX7 CMBX8
    bmc_med_3       2 false positives  MyriadPro-LightIt  MyriadPro-SemiboldIt
    amj_1           true positive PRESERVED (AdvPS7DA6, 13 glyphs)

Note what the "family root" idea is and is not: it is a NEGATIVE filter only. As
a positive discriminator it was refuted — Elsevier's ``AdvTT`` faces are opaque
hashes, so a shared root either misses the known positive or fires on
everything.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from docpluck.extract_layout import (
    detect_symbol_font_corruption,
    font_size_variant_base,
    fonts_are_same_family,
    strip_font_subset_prefix,
)

TEST_PDFS = Path(__file__).resolve().parents[1].parent / "PDFextractor" / "test-pdfs"


class _FakePage:
    def __init__(self, chars):
        self.chars = chars


class _FakeLayout:
    def __init__(self, spec: dict[str, str]):
        """``{fontname: characters_it_draws}``, each character repeated enough to
        clear ``_NARROW_MIN_GLYPHS``."""
        chars = []
        for font, text in spec.items():
            for ch in text * 5:
                chars.append({"fontname": font, "text": ch})
        self.pages = [_FakePage(chars)]


# ── the name discriminators, in isolation ──────────────────────────────────

def test_style_suffixes_are_recognised_as_one_family():
    assert fonts_are_same_family("MyriadPro-Light", "MyriadPro-LightIt")
    assert fonts_are_same_family("MyriadPro-Regular", "MyriadPro-Semibold")
    assert fonts_are_same_family("AdvTimes", "AdvTimes-i")


def test_unrelated_faces_are_not_one_family():
    assert not fonts_are_same_family("AdvPS7DA6", "AdvOT463cc31e")
    assert not fonts_are_same_family("AdvPSMP10", "AdvGulliv")
    # A hash-named face must never collapse to a shared stem — that is the
    # refutation that made this a negative-only filter.
    assert not fonts_are_same_family("AdvOT3a8a92a3", "AdvOT463cc31e")


def test_tex_optical_size_cuts_share_a_base():
    assert font_size_variant_base("CMR5") == "CMR"
    assert font_size_variant_base("CMR10") == "CMR"
    assert font_size_variant_base("CMBX7") == "CMBX"
    # Not a TeX optical-size name — must not be folded.
    assert font_size_variant_base("AdvOT463cc31e") is None
    assert font_size_variant_base("MyriadPro-LightIt") is None


def test_subset_prefix_is_stripped():
    assert strip_font_subset_prefix("MIICOL+AdvPSMP10") == "AdvPSMP10"
    assert strip_font_subset_prefix("AdvPSMP10") == "AdvPSMP10"


# ── the detector ───────────────────────────────────────────────────────────

def test_a_subset_italic_drawing_only_stat_letters_is_not_reported():
    """THE R8 REGRESSION. `Times-Italic` drawing only `p` and `t` is statistical
    notation set in italics, not a mis-decoded symbol face — and it is excluded
    because the document plainly carries the same family in roman."""
    layout = _FakeLayout({
        "Times-Italic": "pt",
        "Times-Roman": "The quick brown fox jumps over 0123456789",
    })
    assert detect_symbol_font_corruption(layout) == {}


def test_a_genuinely_isolated_symbol_face_is_still_reported():
    """The converse, so the test above cannot pass by disabling the detector. A
    narrow face with NO styled sibling anywhere in the document is the shape that
    ships a Cronbach's alpha as `a5(.93)`."""
    layout = _FakeLayout({
        "AdvPS7DA6": "Dabx",
        "AdvTimes": "The quick brown fox jumps over 0123456789",
    })
    assert detect_symbol_font_corruption(layout) == {"AdvPS7DA6": 20}


def test_tex_optical_size_cut_is_not_reported():
    layout = _FakeLayout({
        "CMMI5": "abx",
        "CMMI10": "The quick brown fox jumps over 0123456789",
    })
    assert detect_symbol_font_corruption(layout) == {}


def test_a_font_drawing_non_ascii_is_never_reported():
    """Already-correct Unicode Greek decodes fine and is not a corruption."""
    layout = _FakeLayout({"NewTXMI": "αχβ", "AdvTimes": "The quick brown fox 0123"})
    assert detect_symbol_font_corruption(layout) == {}


# ── against the real papers the exclusions were measured on ────────────────

@pytest.mark.parametrize(
    "relpath,expect_font",
    [
        ("aom/amj_1.pdf", "AdvPS7DA6"),                     # the alpha class
        ("apa/ar_apa_j_jesp_2009_12_010.pdf", "AdvPSMP10"),  # the beta class (W0m)
    ],
)
def test_known_positives_still_fire(relpath, expect_font):
    pdf = TEST_PDFS / relpath
    if not pdf.is_file():
        pytest.skip(f"fixture not available: {pdf}")
    from docpluck.extract_layout import extract_pdf_layout

    found = detect_symbol_font_corruption(extract_pdf_layout(pdf.read_bytes()))
    assert expect_font in found, (
        f"the exclusions killed a TRUE positive on {relpath}: {found}"
    )


@pytest.mark.parametrize(
    "relpath",
    [
        "ieee/ieee_access_7.pdf",     # 6 FPs: TeX optical-size cuts
        "vancouver/bmc_med_3.pdf",    # 2 FPs: MyriadPro italics
    ],
)
def test_known_negatives_are_silent(relpath):
    pdf = TEST_PDFS / relpath
    if not pdf.is_file():
        pytest.skip(f"fixture not available: {pdf}")
    from docpluck.extract_layout import extract_pdf_layout

    found = detect_symbol_font_corruption(extract_pdf_layout(pdf.read_bytes()))
    assert found == {}, f"false positives on a known negative: {found}"
