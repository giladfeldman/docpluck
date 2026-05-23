"""Tests for P0r — repetition-driven running-header / page-footer strip.

Added 2026-05-23 cycle 2 of the docpluck-iterate gate run. Defends against
the running-header / page-footer leaks the cycle-1 Phase 5d AI-verify
surfaced on ip_feldman_2025_pspb, plos_med_1, and chan_feldman_2025_cogemo.

Contract tests are synthetic (fast). Real-PDF regression tests use the
manifest-with-skip pattern: fixtures live outside this repo per memory
``feedback_no_pdfs_in_repo``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from docpluck.normalize import (
    NORMALIZATION_VERSION,
    _detect_recurring_running_headers,
    _is_all_caps_journal_banner,
    _looks_like_running_header_or_footer,
    _strip_recurring_running_headers,
)
from docpluck.render import render_pdf_to_markdown


_PDF_ROOT = Path(__file__).resolve().parents[1] / ".." / "PDFextractor" / "test-pdfs"


def _maybe_render(rel: str) -> str:
    pdf = (_PDF_ROOT / rel).resolve()
    if not pdf.is_file():
        pytest.skip(f"fixture not available locally: {rel}")
    return render_pdf_to_markdown(pdf.read_bytes())


def test_p0r_version_bumped():
    # P0r was added in NORMALIZATION_VERSION 1.9.22.
    parts = tuple(int(x) for x in NORMALIZATION_VERSION.split("."))
    assert parts >= (1, 9, 22), f"expected ≥ 1.9.22, got {NORMALIZATION_VERSION}"


# ── Content-shape guard tests ───────────────────────────────────────────


class TestIsAllCapsJournalBanner:
    def test_plos_medicine(self):
        assert _is_all_caps_journal_banner("PLOS MEDICINE")

    def test_cognition_and_emotion(self):
        assert _is_all_caps_journal_banner("COGNITION AND EMOTION")

    def test_jama_network_open(self):
        assert _is_all_caps_journal_banner("JAMA NETWORK OPEN")

    def test_short_abbreviation_excluded(self):
        # PSA / ECG / etc. are too short — would false-positive on table cells.
        assert not _is_all_caps_journal_banner("PSA")
        assert not _is_all_caps_journal_banner("ECG")

    def test_single_word_excluded(self):
        # Single-word all-caps lines are ambiguous (could be a table column
        # header). Banner shape requires ≥2 words.
        assert not _is_all_caps_journal_banner("NATURE")
        assert not _is_all_caps_journal_banner("MEDICINE")

    def test_with_digits_excluded(self):
        # Digits indicate a column header or stat row, not a banner.
        assert not _is_all_caps_journal_banner("TABLE 5 SAE")
        assert not _is_all_caps_journal_banner("OR 95 CI")

    def test_with_parens_excluded(self):
        assert not _is_all_caps_journal_banner("PSA (N = 98)")

    def test_lowercase_excluded(self):
        assert not _is_all_caps_journal_banner("Cognition and Emotion")


class TestLooksLikeRunningHeaderOrFooter:
    def test_ip_and_feldman(self):
        # Mixed-case bare author-pair.
        assert _looks_like_running_header_or_footer("Ip and Feldman")

    def test_smith_and_jones(self):
        assert _looks_like_running_header_or_footer("Smith and Jones")

    def test_smith_and_jones_ampersand(self):
        assert _looks_like_running_header_or_footer("Smith & Jones")

    def test_chan_feldman_caps_initials(self):
        # All-caps author-pair with initials.
        assert _looks_like_running_header_or_footer("C. F. CHAN AND G. FELDMAN")

    def test_chan_feldman_with_page_number(self):
        # Same shape with leading page number.
        assert _looks_like_running_header_or_footer("1232 C. F. CHAN AND G. FELDMAN")

    def test_plos_footer(self):
        # Journal name + | + DOI URL + date.
        line = "PLOS Medicine | https://doi.org/10.1371/journal.pmed.1004323 December 28, 2023"
        assert _looks_like_running_header_or_footer(line)

    def test_pspb_proof_header(self):
        # Journal + issue placeholder NN(N).
        line = "Personality and Social Psychology Bulletin 00(0)"
        assert _looks_like_running_header_or_footer(line)

    def test_body_prose_not_matched(self):
        # Legitimate body sentences are NOT matched.
        assert not _looks_like_running_header_or_footer(
            "We summarized the comparison of the target article."
        )
        assert not _looks_like_running_header_or_footer(
            "Smith and Jones (2009) demonstrated that participants underestimated."
        )

    def test_table_cell_not_matched(self):
        # Table cell values must NOT be matched (these often repeat too).
        assert not _looks_like_running_header_or_footer("<.001")
        assert not _looks_like_running_header_or_footer("0/4 (0.0%)")
        assert not _looks_like_running_header_or_footer("N = 106")
        assert not _looks_like_running_header_or_footer("estimate")
        # — character alone (em-dash) is too short
        assert not _looks_like_running_header_or_footer("—")


# ── Detection: requires ≥3 repetition AND shape match ───────────────────


class TestDetectRecurringRunningHeaders:
    def test_detects_when_repeated_3x(self):
        text = "\n".join([
            "Body paragraph one.",
            "Ip and Feldman",
            "More body content.",
            "Ip and Feldman",
            "Even more body content.",
            "Ip and Feldman",
        ])
        headers = _detect_recurring_running_headers(text)
        assert "Ip and Feldman" in headers

    def test_does_not_detect_when_repeated_only_2x(self):
        # ≥3 threshold — exactly 2 is below threshold.
        text = "\n".join([
            "Body.",
            "Ip and Feldman",
            "Body.",
            "Ip and Feldman",
        ])
        headers = _detect_recurring_running_headers(text)
        assert "Ip and Feldman" not in headers

    def test_repeated_table_cell_not_detected(self):
        # `<.001` appears 5 times — repetition ✓ — but shape fails.
        text = "\n".join(["body", "<.001", "more", "<.001", "still", "<.001", "and", "<.001", "the", "<.001"])
        headers = _detect_recurring_running_headers(text)
        assert "<.001" not in headers

    def test_detects_plos_footer(self):
        line = "PLOS Medicine | https://doi.org/10.1371/journal.pmed.1004323 December 28, 2023"
        text = "\n".join([f"body content {i}\n{line}" for i in range(5)])
        headers = _detect_recurring_running_headers(text)
        assert line in headers

    def test_detects_plos_banner_via_repetition(self):
        text = "\n".join(["intro"] + ["PLOS MEDICINE\nbody"] * 5)
        headers = _detect_recurring_running_headers(text)
        assert "PLOS MEDICINE" in headers


# ── Strip behavior ──────────────────────────────────────────────────────


class TestStripRecurringRunningHeaders:
    def test_strips_standalone_occurrences(self):
        text = "\n".join([
            "First body paragraph.",
            "Ip and Feldman",
            "Second body paragraph.",
            "Ip and Feldman",
            "Third body paragraph.",
            "Ip and Feldman",
            "Fourth body paragraph.",
        ])
        out = _strip_recurring_running_headers(text)
        assert "Ip and Feldman" not in out
        assert "First body paragraph." in out
        assert "Fourth body paragraph." in out

    def test_strips_welded_leading_prefix(self):
        # The cycle-1 finding: "Ip and Feldman events (Srivastava et al.,
        # 2009) yet are less able …" — running header welded INTO a body
        # sentence. After ≥3 standalone occurrences are detected, the
        # leading prefix is also stripped from this welded line.
        standalone_block = "\n".join(["Ip and Feldman"] * 3)
        welded = (
            "Ip and Feldman events (Srivastava et al., 2009) yet are less "
            "able to suppress their high intensity emotional events."
        )
        text = standalone_block + "\n" + welded
        out = _strip_recurring_running_headers(text)
        # Welded variant cleaned to start with body.
        assert "events (Srivastava et al., 2009) yet are less able" in out
        # The running-header text itself is gone (everywhere).
        assert "Ip and Feldman events" not in out

    def test_strips_welded_from_reference_line(self):
        # Cycle-1 finding: running header welded into a reference entry.
        standalone_block = "\n".join(["Ip and Feldman"] * 3)
        reference = "Ip and Feldman of scientific findings. Advances in Methods and Practices."
        text = standalone_block + "\n" + reference
        out = _strip_recurring_running_headers(text)
        assert "of scientific findings. Advances in Methods and Practices." in out
        assert "Ip and Feldman of scientific findings" not in out

    def test_preserves_table_cells(self):
        # Table cell values that repeat must survive.
        cells = "\n".join(["<.001"] * 6 + ["0/4 (0.0%)"] * 5 + ["N = 106"] * 4)
        out = _strip_recurring_running_headers(cells)
        assert "<.001" in out
        assert "0/4 (0.0%)" in out
        assert "N = 106" in out

    def test_strips_plos_footer_and_banner_pair(self):
        # The recurring-pair from plos_med_1.
        footer = "PLOS Medicine | https://doi.org/10.1371/journal.pmed.1004323 December 28, 2023"
        banner = "PLOS MEDICINE"
        text = "\n".join(
            [f"Body paragraph {i}. Some text here." for i in range(5)] +
            [footer, banner] * 4
        )
        out = _strip_recurring_running_headers(text)
        assert footer not in out
        assert banner not in out
        assert "Body paragraph 1." in out  # body content preserved

    def test_strips_chan_feldman_running_header(self):
        # All-caps initials + AND surname.
        header = "C. F. CHAN AND G. FELDMAN"
        text = "\n".join(
            [f"Methods paragraph {i}." for i in range(4)] +
            [header] * 5
        )
        out = _strip_recurring_running_headers(text)
        assert header not in out
        assert "Methods paragraph 0." in out

    def test_no_op_when_no_recurring_headers(self):
        text = "Body paragraph one.\nBody paragraph two.\nBody paragraph three."
        out = _strip_recurring_running_headers(text)
        assert out == text

    def test_does_not_strip_legitimate_2x_author_mention(self):
        # If "Smith and Jones" appears only twice as a body-line citation
        # (e.g. in different paragraphs), it must NOT be stripped — the
        # ≥3 guard catches this.
        text = "\n".join([
            "Smith and Jones (2009) showed that participants underestimated.",
            "Body paragraph.",
            "We replicated Smith and Jones (2009) with N=200.",
            "Body paragraph.",
        ])
        out = _strip_recurring_running_headers(text)
        assert "Smith and Jones (2009)" in out

    def test_idempotent(self):
        # P0r must be idempotent — running normalize twice on the same text
        # should produce the same result.
        text = "\n".join([
            "Body.",
            "Ip and Feldman",
            "Body.",
            "Ip and Feldman",
            "Body.",
            "Ip and Feldman",
            "Body.",
        ])
        once = _strip_recurring_running_headers(text)
        twice = _strip_recurring_running_headers(once)
        assert once == twice


# ── Real-PDF regression tests ───────────────────────────────────────────


class TestP0rRealPdfRegression:
    def test_ip_feldman_no_standalone_running_header(self):
        md = _maybe_render("apa/ip_feldman_2025_pspb.pdf")
        # The standalone "Ip and Feldman" running-header occurrences from
        # cycle 1 must all be gone after P0r.
        lines = md.split("\n")
        standalone = [ln for ln in lines if ln.strip() == "Ip and Feldman"]
        assert len(standalone) == 0, (
            f"Expected 0 standalone 'Ip and Feldman' lines, got {len(standalone)}"
        )

    def test_ip_feldman_no_welded_running_header(self):
        md = _maybe_render("apa/ip_feldman_2025_pspb.pdf")
        # The welded-into-sentence variant from cycle-1 (line 2612 in the
        # cycle-1 render) must also be gone.
        assert "Ip and Feldman events (Srivastava" not in md
        assert "Ip and Feldman of scientific findings" not in md

    def test_plos_med_1_no_banner_or_footer(self):
        md = _maybe_render("vancouver/plos_med_1.pdf")
        lines = md.split("\n")
        # 15+ "PLOS MEDICINE" standalone lines must be gone.
        plos_banner_lines = [ln for ln in lines if ln.strip() == "PLOS MEDICINE"]
        assert len(plos_banner_lines) == 0
        # 16+ DOI-footer occurrences must be gone.
        plos_footer_lines = [
            ln for ln in lines
            if "PLOS Medicine | https://doi.org" in ln
        ]
        assert len(plos_footer_lines) == 0

    def test_chan_feldman_no_running_header(self):
        md = _maybe_render("apa/chan_feldman_2025_cogemo.pdf")
        # The "C. F. CHAN AND G. FELDMAN" standalone running-header lines
        # from cycle 1 must all be gone.
        lines = md.split("\n")
        standalone = [
            ln for ln in lines if ln.strip() == "C. F. CHAN AND G. FELDMAN"
        ]
        assert len(standalone) == 0
        # The all-caps "COGNITION AND EMOTION" banner must be gone too.
        banner_lines = [ln for ln in lines if ln.strip() == "COGNITION AND EMOTION"]
        assert len(banner_lines) == 0

    def test_chan_feldman_table_cell_text_not_eaten(self):
        # Table cell values like "Replication", "Same", "<.001" must NOT
        # be stripped despite being short and recurring (they fail the
        # shape guard).
        md = _maybe_render("apa/chan_feldman_2025_cogemo.pdf")
        # At least some "Replication" should survive (it's a table column
        # label across multiple tables).
        assert "Replication" in md
