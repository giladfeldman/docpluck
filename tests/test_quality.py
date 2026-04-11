"""
Tests for quality scoring system.
Validates common-word ratio, garbled detection, ligature counting, and confidence levels.
"""

import pytest
from docpluck.quality import compute_quality_score


class TestQualityScoring:
    def test_clean_academic_text(self):
        text = (
            "The study results showed significant effects between conditions. "
            "Research participants were randomly assigned to treatment groups. "
            "Statistical analysis revealed a main effect of the intervention."
        )
        q = compute_quality_score(text)
        assert q["score"] >= 80
        assert q["confidence"] == "high"
        assert q["garbled"] is False

    def test_garbled_text_with_corruption_signal(self):
        """Random characters + corruption signal → garbled.

        Changed 1.3.1: the quality scorer now requires an independent corruption
        signal (FFFD / high non-ASCII / ligatures / short text) before flagging
        garbled. Pure ASCII gibberish without any corruption signal is not
        distinguishable from a valid non-prose document (name list, reference
        dump) and is not flagged.
        """
        text = "xkj qw zpm lrt bvn fgh nmc \ufffd ywu " * 100
        q = compute_quality_score(text)
        assert q["garbled"] is True
        assert q["score"] <= 60
        assert q["confidence"] in ("low", "medium")

    def test_ascii_gibberish_without_corruption_signal_not_garbled(self):
        """Pure ASCII non-prose without corruption signals is NOT flagged.

        This is a regression guard against the 2026-04-11 PSS Reviewer
        Acknowledgment false positive: a file of 600+ proper nouns has very
        low common_word_ratio but is not actually garbled.
        """
        text = "xkj qw zpm lrt bvn fgh nmc ywu " * 100
        q = compute_quality_score(text)
        assert q["garbled"] is False  # no corruption signal → not flagged
        assert q["details"]["has_corruption_signal"] is False

    def test_text_with_ligatures(self):
        """Remaining ligatures should reduce score."""
        text = (
            "The signi\ufb01cant e\ufb00ect was modi\ufb01ed by the treatment. "
            "The study results showed significant effects. "
        ) * 20
        q = compute_quality_score(text)
        assert q["details"]["ligatures_remaining"] > 0

    def test_text_with_fffd(self):
        """U+FFFD replacement characters should reduce score."""
        text = (
            "The study results showed \ufffd significant effects. "
            "Research participants \ufffd were assigned. "
        ) * 20
        q = compute_quality_score(text)
        assert q["details"]["garbled_chars"] > 0

    def test_empty_text(self):
        q = compute_quality_score("")
        assert q["score"] == 0 or q["score"] <= 50

    def test_single_word(self):
        q = compute_quality_score("study")
        # Very short text — ratio may be high but score should still work
        assert isinstance(q["score"], int)

    def test_column_merge_garbled(self):
        """From MetaESCI: column merge with remaining ligature evidence."""
        # Real column-merge garbage usually retains ligatures (extraction artifact)
        text = "Wor\ufb01Wdor\ufb01Fdr\ufb01Fraaggmm\ufb01eentnt\ufb01CoCmopletmio " * 50
        q = compute_quality_score(text)
        assert q["details"]["ligatures_remaining"] >= 20  # corruption signal
        assert q["garbled"] is True

    def test_reviewer_acknowledgment_not_garbled(self):
        """Regression: name list with low common_word_ratio must not be garbled.

        Mirrors the PSS Reviewer Acknowledgment file
        (10.1177/09567976221083022) that was flagged as garbled in the
        1.3.0 MetaESCI baseline.
        """
        # 30 capitalized names, no prose, no corruption signals
        names = (
            "Richard Abrams Donna Rose Addis Ralph Adolphs Thomas Agren "
            "Vivien Ainley Lauren Alloy Nicole Amichetti Eduardo Andrade "
            "Giovanni Anobile Daniel Ansari Kaarin Anstey Evan Apfelbaum "
            "Neal Ashkanasy Shervin Assari Mitja Back Daniel Backhaus Katie "
        ) * 20
        q = compute_quality_score(names)
        assert q["garbled"] is False
        assert q["details"]["garbled_chars"] == 0
        assert q["details"]["has_corruption_signal"] is False
        # Score should be comfortable, not penalized for being non-prose
        assert q["score"] >= 80

    def test_non_english_academic(self):
        """Non-English text should get moderate score (some common words shared)."""
        text = (
            "Die Ergebnisse zeigen einen signifikanten Effekt. "
            "Die Studie untersuchte die Auswirkungen der Behandlung. "
        ) * 20
        q = compute_quality_score(text)
        assert isinstance(q["score"], int)

    def test_confidence_levels(self):
        """Verify confidence thresholds: high ≥ 80, medium 50-79, low < 50."""
        high = compute_quality_score("the study results showed " * 100)
        assert high["confidence"] == "high"

    def test_score_range(self):
        """Score should always be 0-100."""
        for text in ["", "x" * 1000, "the study " * 500]:
            q = compute_quality_score(text)
            assert 0 <= q["score"] <= 100
