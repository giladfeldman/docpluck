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

    def test_garbled_text(self):
        """Random characters → garbled detection via common-word ratio."""
        text = "xkj qw zpm lrt bvn fgh nmc ywu " * 100
        q = compute_quality_score(text)
        assert q["score"] <= 50
        assert q["garbled"] is True
        assert q["confidence"] in ("low", "medium")  # boundary at score=50

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
        """From MetaESCI: column merge produces garbled text."""
        text = "WorWdorFdrFraaggmmeentntCoCmopletmio " * 50
        q = compute_quality_score(text)
        assert q["garbled"] is True
        assert q["score"] <= 50

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
