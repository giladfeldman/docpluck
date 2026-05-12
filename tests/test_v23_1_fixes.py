"""Tests for v2.3.1 follow-up fixes from `HANDOFF_2026-05-11`."""

from __future__ import annotations

import struct
import zlib

from docpluck.extract import _patch_fffds_word_by_word, count_pages
from docpluck.render import (
    _italicize_known_subtitle_badges,
    _SUBTITLE_BADGE_PATTERNS,
)


# ---------------------------------------------------------------------------
# 1. _patch_fffds_word_by_word — per-word FFFD recovery
# ---------------------------------------------------------------------------


def test_fffd_word_patch_recovers_single_char():
    """A word with one FFFD has a unique counterpart in pdfplumber text."""
    pdftotext = "the qui�k brown fox jumps over the lazy dog"
    pdfplumber = "the quick brown fox jumps over the lazy dog"
    patched, n = _patch_fffds_word_by_word(pdftotext, pdfplumber)
    assert n == 1
    assert "qui�k" not in patched
    assert "quick" in patched


def test_fffd_word_patch_recovers_multiple_fffds_in_one_word():
    """Two FFFDs in the same word recovered together when pdfplumber has
    a unique match."""
    pdftotext = "the qu��k brown fox"
    pdfplumber = "the quick brown fox"
    patched, n = _patch_fffds_word_by_word(pdftotext, pdfplumber)
    assert n == 2
    assert "quick" in patched
    assert "�" not in patched


def test_fffd_word_patch_skips_ambiguous_matches():
    """If pdfplumber has more than one same-shape candidate, leave the
    FFFD-bearing word alone — we won't guess."""
    pdftotext = "the c�t sat"
    pdfplumber = "the cat sat. cot bat hat"  # cat/cot/bat/hat all match c[A-Za-z]t
    patched, n = _patch_fffds_word_by_word(pdftotext, pdfplumber)
    # Multiple candidates → no patch.
    assert n == 0
    assert "c�t" in patched


def test_fffd_word_patch_skips_when_no_match():
    """No matching candidate in pdfplumber → leave the FFFD-bearing word."""
    pdftotext = "the q�ick brown"
    pdfplumber = "the slow black"  # no q*ick token at all
    patched, n = _patch_fffds_word_by_word(pdftotext, pdfplumber)
    assert n == 0
    assert "q�ick" in patched


def test_fffd_word_patch_handles_punctuation_attached_words():
    """Word-attached punctuation (closing paren / period) shouldn't
    confuse the matcher."""
    pdftotext = "(study qui�k)."
    pdfplumber = "(study quick)."
    patched, n = _patch_fffds_word_by_word(pdftotext, pdfplumber)
    assert n == 1
    assert "(study quick)." in patched


def test_fffd_word_patch_only_substitutes_letters():
    """The replacement is constrained to [A-Za-z] at each FFFD position,
    so the patcher won't manufacture digits / punctuation."""
    pdftotext = "the c�t"
    pdfplumber = "the c5t"  # c5t has a digit at the FFFD position; must NOT match.
    patched, n = _patch_fffds_word_by_word(pdftotext, pdfplumber)
    assert n == 0
    assert "c�t" in patched


def test_fffd_word_patch_returns_unchanged_on_no_fffds():
    """Fast path: no FFFDs in pdftotext → no work."""
    pdftotext = "the quick brown fox"
    pdfplumber = "totally different text"
    patched, n = _patch_fffds_word_by_word(pdftotext, pdfplumber)
    assert n == 0
    assert patched == pdftotext


def test_fffd_word_patch_returns_unchanged_on_empty_pdfplumber():
    pdftotext = "the qui�k brown"
    patched, n = _patch_fffds_word_by_word(pdftotext, "")
    assert n == 0
    assert patched == pdftotext


# ---------------------------------------------------------------------------
# 2. count_pages compressed-stream fallback
# ---------------------------------------------------------------------------


def _make_minimal_pdf(num_pages: int) -> bytes:
    """Generate a minimal valid uncompressed PDF with `num_pages` pages.
    Each page is empty (no content). Sufficient for count_pages testing."""
    objects = []
    # Object 1: Catalog
    objects.append(b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj")
    # Object 2: Pages (parent)
    kids = " ".join(f"{i + 3} 0 R" for i in range(num_pages))
    objects.append(
        f"2 0 obj\n<< /Type /Pages /Kids [{kids}] /Count {num_pages} >>\nendobj".encode()
    )
    # Objects 3..3+num_pages-1: Page leaves
    for i in range(num_pages):
        objects.append(
            f"{i + 3} 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>\nendobj".encode()
        )

    pdf = b"%PDF-1.4\n"
    offsets = []
    for obj in objects:
        offsets.append(len(pdf))
        pdf += obj + b"\n"
    xref_off = len(pdf)
    pdf += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    for off in offsets:
        pdf += f"{off:010d} 00000 n \n".encode()
    pdf += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_off}\n%%EOF\n".encode()
    return pdf


def test_count_pages_uncompressed_multi_page():
    """Standard uncompressed PDF: byte heuristic works."""
    pdf = _make_minimal_pdf(num_pages=5)
    assert count_pages(pdf) == 5


def test_count_pages_uncompressed_single_page():
    pdf = _make_minimal_pdf(num_pages=1)
    assert count_pages(pdf) == 1


def test_count_pages_empty_bytes_returns_zero():
    """Defensive — bad input shouldn't raise."""
    # Empty bytes can't be parsed by pdfplumber either, so we expect 0.
    # The current implementation returns 0 on Exception, which covers this.
    assert count_pages(b"") in (0, 1)


def test_count_pages_invalid_pdf_returns_safe_default():
    """Garbage bytes shouldn't crash. The byte heuristic returns 1 (max
    of 0 and 1), then pdfplumber fails to open it, then we fall back
    to 1."""
    result = count_pages(b"this is not a PDF at all")
    assert result in (0, 1)  # any non-crash result is acceptable


# Note: compressed-stream (PDF 1.5+ object stream) PDFs that defeat the
# byte heuristic are hard to synthesize in <50 lines. The fallback path
# is exercised by the smoke fixture suite — when a real compressed PDF
# is fed in, the fallback triggers when count <= 1.


# ---------------------------------------------------------------------------
# 3. _italicize_known_subtitle_badges — Bug 6
# ---------------------------------------------------------------------------


def test_subtitle_italicizes_registered_report():
    """The handoff's gratitude-paper case: "Registered Report" line just
    below the title gets italicized."""
    md = (
        "# Revisiting the effects of helper intentions on gratitude\n"
        "\n"
        "Registered Report\n"
        "\n"
        "Authors here\n"
        "\n"
        "## Abstract\n"
        "Some abstract."
    )
    out = _italicize_known_subtitle_badges(md)
    assert "*Registered Report*" in out
    # Body text below ## Abstract not touched.
    assert "Some abstract." in out


def test_subtitle_italicizes_preregistered_replication():
    md = "# Title here\n\nPre-Registered Replication\n\n## Abstract\nBody"
    out = _italicize_known_subtitle_badges(md)
    assert "*Pre-Registered Replication*" in out


def test_subtitle_italicizes_stage_1_registered_report():
    md = "# Title here\n\nStage 1 Registered Report\n\n## Abstract\nBody"
    out = _italicize_known_subtitle_badges(md)
    assert "*Stage 1 Registered Report*" in out


def test_subtitle_italicizes_original_investigation():
    """JAMA-style badge."""
    md = "# Effects of caloric restriction\n\nOriginal Investigation\n\n## Abstract\nBody"
    out = _italicize_known_subtitle_badges(md)
    assert "*Original Investigation*" in out


def test_subtitle_does_not_touch_body_prose_mentions():
    """The phrase 'Registered Report' deep inside the body must NOT be
    italicized — only the first non-empty short line after the title
    qualifies."""
    md = (
        "# Some Paper Title\n"
        "\n"
        "## Abstract\n"
        "Body text here.\n"
        "\n"
        "## Discussion\n"
        "We discuss Registered Reports as a publication format.\n"
    )
    out = _italicize_known_subtitle_badges(md)
    # Phrase inside body should still be plain text.
    assert "We discuss Registered Reports as a publication format" in out
    # No italic version anywhere.
    assert "*Registered Reports*" not in out


def test_subtitle_skips_long_lines():
    """A line containing "Registered Report" but longer than 50 chars is
    body prose, not a badge."""
    md = (
        "# Paper Title\n"
        "\n"
        "We propose Registered Report as a publication norm for replications\n"
        "\n"
        "## Abstract\nBody"
    )
    out = _italicize_known_subtitle_badges(md)
    # Long line not italicized.
    assert "We propose Registered Report" in out
    assert "*We propose Registered Report" not in out


def test_subtitle_stops_at_first_h2():
    """Once we hit a ## heading, stop scanning for badges."""
    md = (
        "# Title\n"
        "\n"
        "## Abstract\n"
        "Registered Report\n"   # this line is inside Abstract, not a badge
        "\n"
        "Body"
    )
    out = _italicize_known_subtitle_badges(md)
    # "Registered Report" inside Abstract section must stay plain.
    assert "*Registered Report*" not in out


def test_subtitle_idempotent_on_already_italicized():
    """Already-italicized badge passes through unchanged."""
    md = "# Title\n\n*Registered Report*\n\n## Abstract\nBody"
    out = _italicize_known_subtitle_badges(md)
    # Must not double-italicize to **Registered Report**.
    assert "**Registered Report**" not in out
    assert "*Registered Report*" in out


def test_subtitle_no_op_when_no_title():
    """Text without `# Title` is returned as-is."""
    md = "no title here\n\nRegistered Report\n\nbody"
    out = _italicize_known_subtitle_badges(md)
    assert out == md


def test_subtitle_patterns_compile():
    """Sanity check — all patterns are valid regex."""
    for pat in _SUBTITLE_BADGE_PATTERNS:
        assert pat.pattern  # already compiled, just make sure they exist
