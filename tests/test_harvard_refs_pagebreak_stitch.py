"""D1 + D2 regression tests — citationguard-iterate handoff 2026-06-12.

D1: Harvard / Cambridge name-year reference entries ("Surname A and Surname B
    (2020) …") were not recognised as reference-entry starts, so R3's
    continuation join collapsed an entire Harvard bibliography onto ONE line
    (British Journal of Political Science bjps_1: 109 entries → 1 paragraph).

D2: A running-header category label ("Article") printed at the top of every
    Nature-family page survived into the References section at a page break and
    got welded into an entry, while the page-break blank line orphaned the
    entry's year (nat_comms_2 ref 34's "(2008)").

Contract tests are synthetic (fast, no PDF). Real-PDF regression tests use the
manifest-with-skip pattern (fixtures live outside this repo per memory
``feedback_no_pdfs_in_repo``); they skip cleanly when the corpus is absent.
"""

from __future__ import annotations

import os
import re

import pytest

from docpluck.extract import extract_pdf_file
from docpluck.normalize import (
    NormalizationLevel,
    _CATEGORY_LABEL_HEADER,
    _REF_START_APA,
    _REF_START_HARVARD,
    _detect_recurring_running_headers,
    _looks_like_ref_start,
    _looks_like_running_header_or_footer,
    normalize_text,
)
from .conftest import requires_pdftotext


# ── D1: Harvard ref-start recognition (contract) ───────────────────────────

HARVARD_STARTS = [
    "Adler D and Ansell B (2020) Housing and populism.",
    "Ahlquist J et al. (2020) The political consequences",
    "Autor DH et al. (2020) Importing political polarization?",  # glued initials
    "Betz H-G (1993) The new politics of resentment",            # hyphenated initials
    "Häusermann S (2020) Dualization and electoral realignment",  # accented surname
    "Tuğal C (2021) Authoritarian populism",                      # Latin-Extended surname
    "Jin Z-C et al. (2015) Statistical methods",
    "Barros L and Santos Silva M (2019) Economic crisis",        # compound 2nd surname
    "van der Berg J (2018) Welfare states",                       # particle surname
    "Smith A, Jones B and Brown C (2019) Multi-author entry",
    "House R J (1971) A path goal theory of leader effectiveness",
]

# Lines that appear inside a Harvard bibliography but are mid-entry WRAP
# continuations / journal tails — they must NOT be seen as entry starts.
HARVARD_NON_STARTS = [
    "American Journal of Political Science 64, 904-20.",
    "Political Studies Review 17, 30-40.",
    "Brookings Papers on Economic Activity 2017, 309-400.",
    "Proceedings of the National Academy of Sciences 118, e2111611118.",
    "104000.",
    "increases support for the radical right.",
    "Cite this article: Scheiring G, Serrano-Alarcon M (2024) The title.",
]


@pytest.mark.parametrize("line", HARVARD_STARTS)
def test_harvard_entry_recognised_as_ref_start(line: str):
    assert _REF_START_HARVARD.match(line), line
    assert _looks_like_ref_start(line), line


@pytest.mark.parametrize("line", HARVARD_NON_STARTS)
def test_harvard_continuation_not_a_ref_start(line: str):
    assert not _REF_START_HARVARD.match(line), line


def test_r3_keeps_harvard_entries_one_per_line():
    """The exact bjps_1 defect at the text level: a Harvard reference block
    separated by single newlines (with one mid-entry wrap) must normalize to
    one reference per line — not collapse into a single paragraph."""
    refs = (
        "References\n"
        "Adler D and Ansell B (2020) Housing and populism. West European "
        "Politics 43, 344-65.\n"
        "Ahlquist J et al. (2020) The political consequences of external "
        "economic shocks. American Journal of\n"            # mid-entry wrap
        "Political Science 64, 904-20.\n"
        "Albanese G et al. (2022) Populist voting. European Economic Review "
        "141, 104000.\n"
        "Autor DH et al. (2020) Importing political polarization. American "
        "Economic Review 110, 3139-83.\n"
    )
    out, _ = normalize_text(refs, NormalizationLevel.academic)
    entry_lines = [
        l for l in out.splitlines() if _looks_like_ref_start(l.strip())
    ]
    # Four distinct entries, each on its own line.
    assert len(entry_lines) == 4, out
    # The mid-entry wrap rejoined (no orphan "Political Science 64" line).
    assert "American Journal of Political Science 64" in out
    # No two entries collapsed onto a single line.
    for l in out.splitlines():
        assert len(re.findall(r"\((?:1[89]|20)\d{2}[a-z]?\)", l)) <= 1, l


# ── APA ref-start: accented / particle / compound surnames (same class as D1) ──

# Surfaced during the D1 broad-read: the ASCII-only `[A-Z][a-z]+` APA pattern
# silently merged these entries into the preceding reference (nat_comms_5,
# nathumbeh_2). The broadened pattern reuses the shared surname machinery.
APA_STARTS = [
    "Smith, A. B. (2020). Plain ASCII still works.",
    "Tucker-Drob, E. M. (2014). Hyphenated surname.",
    "Yücel, M. et al. Morphology of the cortex.",          # accented
    "Öhman, A. (2001). Fear and anxiety.",                  # accented leading
    "de Kovel, C. G. F. et al. No alteration.",             # lowercase particle
    "van Dijk, T. A. (1998). Discourse.",                   # particle
    "Karlsson Linnér, R. et al. Genome-wide study.",        # compound + accent
]
APA_NON_STARTS = [
    "Developmental psychology, 50(12), 26-39.",
    "Nature genetics 50, 906-908 (2018).",
    "Proc. Natl Acad. Sci. USA 120, e2213880120 (2023).",
    "American Journal of Political Science 64, 904-20.",
]


@pytest.mark.parametrize("line", APA_STARTS)
def test_apa_entry_recognised_including_accented_particle_compound(line: str):
    assert _REF_START_APA.match(line), line
    assert _looks_like_ref_start(line), line


@pytest.mark.parametrize("line", APA_NON_STARTS)
def test_apa_journal_tail_not_a_ref_start(line: str):
    assert not _REF_START_APA.match(line), line


# ── D2: category-label running header + page-break stitch (contract) ────────

def test_article_category_label_is_running_header_shape():
    assert _CATEGORY_LABEL_HEADER.match("Article")
    assert _looks_like_running_header_or_footer("Article")
    # Repetition guard: detected only when it recurs ≥3× standalone.
    text = "Body line one.\nArticle\nmid\nArticle\nmore\nArticle\nend\n"
    assert "Article" in _detect_recurring_running_headers(text)


def test_pagebreak_stitch_recovers_orphaned_year_and_strips_header():
    """The nat_comms_2 ref 34 defect at the text level: a numbered reference
    split across a page break (blank line + form feed + 'Article' header) must
    rejoin so the trailing year is not orphaned, and the header must be gone."""
    refs = (
        "References\n"
        "33. Foo, A. B. & Bar, C. D. Some earlier study. J. Imm. 1, 1-9 "
        "(2020).\n"
        "34. Kroenke, M. A. & Segal, B. M. IL-12 and IL-23 modulated T cells "
        "induce distinct types of EAE based on\n"
        "\n"
        "\x0cArticle\n"
        "histology, CNS chemokine profile, and response to cytokine "
        "inhibition. J. Exp. Med. 205, 1535-1541 (2008).\n"
        "35. Yu, S. et al. Neutralizing antibodies to IL-18. J. Imm. 2, 1-9 "
        "(2021).\n"
        # Need ≥3 standalone "Article" occurrences for the P0r repetition guard.
        "\x0cArticle\nfiller body text one.\n"
        "\x0cArticle\nfiller body text two.\n"
    )
    out, _ = normalize_text(refs, NormalizationLevel.academic)
    ref34 = out[out.find("34."):].split("\n35.")[0]
    assert "(2008)" in ref34, f"year orphaned: {ref34!r}"
    assert "Article" not in ref34, f"running header welded in: {ref34!r}"
    # The split entry is a single logical line.
    assert ref34.strip().count("\n") == 0, f"entry not stitched: {ref34!r}"


def test_blank_bridge_does_not_absorb_post_reference_trailer():
    """A COMPLETED entry followed by a blank line and a non-reference trailer
    ('Cite this article: …') must NOT have the trailer joined into it."""
    refs = (
        "References\n"
        "Whelan CT and Maitre B (2005) Economic vulnerability. International "
        "Journal of Comparative Sociology 46, 215-39.\n"
        "\n"
        "Cite this article: Scheiring G, Serrano-Alarcon M (2024) The "
        "populist backlash. British Journal of Political Science.\n"
    )
    out, _ = normalize_text(refs, NormalizationLevel.academic)
    whelan = next(l for l in out.splitlines() if l.startswith("Whelan"))
    assert "Cite this article" not in whelan, whelan
    assert "(2005)" in whelan and "(2024)" not in whelan, whelan


# ── Real-PDF regression (manifest-with-skip) ───────────────────────────────

# Handoff fixtures live in the CitationGuard validation corpus, gitignored per
# ``feedback_no_pdfs_in_repo``. Resolve from there; skip if absent on this box.
_CG_VALIDATION = os.path.join(
    os.path.expanduser("~"), "Dropbox", "Vibe", "MetaScienceTools",
    "CitationGuard", "apps", "worker", "testpdfs", "validation",
)
_BJPS_1 = os.path.join(_CG_VALIDATION, "harvard", "bjps_1.pdf")
_NAT_COMMS_2 = os.path.join(_CG_VALIDATION, "nature", "nat_comms_2.pdf")


@requires_pdftotext
@pytest.mark.skipif(not os.path.isfile(_BJPS_1), reason="bjps_1 fixture absent")
def test_bjps_1_harvard_bibliography_splits_one_per_line():
    raw, _ = extract_pdf_file(_BJPS_1)
    out, _ = normalize_text(raw, NormalizationLevel.academic)
    idx = out.rfind("\nReferences")
    assert idx != -1
    ref_lines = [l for l in out[idx:].splitlines() if l.strip()]
    starts = [l for l in ref_lines if _looks_like_ref_start(l.strip())]
    # 109 Harvard entries — expect the vast majority recognised one-per-line.
    assert len(starts) >= 100, f"only {len(starts)} entry starts"
    # No line carries two parenthesised years (i.e. no two entries collapsed).
    for l in ref_lines:
        assert len(re.findall(r"\((?:1[89]|20)\d{2}[a-z]?\)", l)) <= 1, l


@requires_pdftotext
@pytest.mark.skipif(not os.path.isfile(_NAT_COMMS_2), reason="nat_comms_2 absent")
def test_nat_comms_2_ref34_carries_year_no_article_header():
    raw, _ = extract_pdf_file(_NAT_COMMS_2)
    out, _ = normalize_text(raw, NormalizationLevel.academic)
    j = out.find("Kroenke")
    assert j != -1
    ref34 = out[j:].split("\n35.")[0]
    assert "(2008)" in ref34, f"year orphaned: {ref34!r}"
    assert "Article" not in ref34, f"running header welded in: {ref34!r}"
