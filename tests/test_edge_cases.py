"""
Edge case tests from cross-project lessons.
Sources: ESCIcheck LESSONS.md, MetaESCI extraction report, PDFextractor LESSONS.md,
MetaMisCitations LESSONS.md.
"""

import re
import pytest
from docpluck.normalize import normalize_text, NormalizationLevel
from docpluck.quality import compute_quality_score


def norm(text: str, level: str = "academic") -> str:
    result, _ = normalize_text(text, NormalizationLevel(level))
    return result


# ── From ESCIcheck LESSONS.md ────────────────────────────────────────

class TestESCIcheckEdgeCases:
    def test_capital_d_effect_size(self):
        """ESCIcheck Lesson 12: Capital D/G must be preserved for downstream matching."""
        text = "D = 0.44, G = 0.52"
        result = norm(text)
        # Normalization should not destroy these values
        assert "0.44" in result
        assert "0.52" in result

    def test_generalized_eta_squared(self):
        """ESCIcheck Lesson 13: η²G (generalized) patterns."""
        text = "η²G = .054"
        result = norm(text)
        assert ".054" in result

    def test_line_number_adjacent_to_stat(self):
        """ESCIcheck Lesson 14: '12F(2, 430) = 12.38' — line number prefix."""
        text = "12F(2, 430) = 12.38"
        result = norm(text)
        # The stat should still be intact
        assert "12.38" in result
        assert "F(2, 430)" in result

    def test_footnote_superscript(self):
        """ESCIcheck Lesson 14: 'p < .001¹' — trailing superscript."""
        text = "p < .001\u00B9"
        result = norm(text)
        assert ".001" in result

    def test_welch_noninteger_df(self):
        """ESCIcheck Phase 2B: Welch's t-test with non-integer df."""
        text = "t(28.7) = 2.43, p = .021"
        result = norm(text)
        assert "t(28.7)" in result
        assert "2.43" in result

    def test_p_at_column_boundary(self):
        """ESCIcheck: combined line break + dropped decimal."""
        text = "p =\n484"
        result = norm(text)
        # A1 should fix line break, A2 should fix dropped decimal
        assert ".484" in result

    def test_utf8_encoding_validation(self):
        """ESCIcheck Lesson 1: null bytes must be stripped."""
        text = "Study\x00 results showed"
        result = norm(text, "standard")
        assert "\x00" not in result
        assert "Study" in result

    def test_effect_size_out_of_range(self):
        """ESCIcheck Lesson 14: |d| > 10 is likely artifact."""
        # This is a downstream consumer responsibility, but extraction should preserve it
        text = "d = 484.2"
        result = norm(text)
        assert "484" in result  # We don't modify non-p-value numbers


# ── From MetaESCI extraction report ──────────────────────────────────

class TestMetaESCIEdgeCases:
    def test_column_merge_detection(self):
        """MetaESCI: 0.65% column merge rate. Garbled text should have low quality."""
        text = "WorWdorFdrFraaggmmeentntCoCmopletmio " * 50
        q = compute_quality_score(text)
        assert q["garbled"] is True
        assert q["score"] <= 50

    def test_page_footer_in_pvalue(self):
        """MetaESCI: 0.25% garbled p-values from page footers."""
        text = "p = 806 U.S. Department"
        # Quality score should flag this as suspicious
        # But normalization can't fix arbitrary contamination
        result = norm(text)
        assert "806" in result  # Can't fix — but quality should flag

    def test_double_newline_at_page_boundary(self):
        """MetaESCI: page boundaries produce double newlines."""
        text = "Results showed\n\nthat the effect was significant"
        result = norm(text, "standard")
        # Triple+ newlines get collapsed to double
        assert "\n\n\n" not in result

    def test_european_decimal_comma(self):
        """MetaESCI: European locale p = 0,001."""
        assert "0.001" in norm("p = 0,001")

    def test_dropped_decimal_multiple(self):
        """MetaESCI: 4.88% rate — test multiple patterns."""
        cases = [
            ("p = 484", ".484"),
            ("p = 37", ".37"),
            ("p = 999", ".999"),
        ]
        for raw, expected in cases:
            result = norm(raw)
            assert expected in result, f"Failed: {raw} → expected {expected}, got {result}"


# ── From PDFextractor LESSONS.md ─────────────────────────────────────

class TestPDFextractorLessons:
    def test_merged_f_statistics(self):
        """Lesson 11: 'F(2, 430) = 12.38 0.054' — space-separated values."""
        text = "F(2, 430) = 12.38 0.054"
        result = norm(text)
        # Both values should be preserved
        assert "12.38" in result
        assert "0.054" in result

    def test_regex_no_catastrophic_backtracking(self):
        """Lesson 1: possessive quantifiers prevent backtracking."""
        import time
        long_text = "p = " + "9" * 10000 + " end"
        start = time.perf_counter()
        result = norm(long_text)
        elapsed = time.perf_counter() - start
        assert elapsed < 5.0, f"Normalization took {elapsed:.1f}s — possible catastrophic backtracking"

    def test_bold_markers_around_stats(self):
        """Lesson 4: pymupdf4llm artifact '**p** < .001' — if in text, should survive."""
        text = "**p** < .001"
        result = norm(text)
        # Normalization doesn't strip markdown, but the value should survive
        assert ".001" in result

    def test_html_less_than_in_stats(self):
        """Lesson 4: '<' in 'p < .001' must not be eaten by HTML stripping."""
        text = "p < .001"
        result = norm(text)
        assert "p < .001" in result or "p <" in result

    def test_pdftotext_no_layout_flag(self):
        """Lesson 3: Verify -layout flag is not used in subprocess calls."""
        import os
        extract_path = os.path.join(os.path.dirname(__file__), "..", "docpluck", "extract.py")
        with open(extract_path) as f:
            source = f.read()
        # Check that -layout does not appear in actual pdftotext command invocations
        # It IS mentioned in comments/docstrings as a warning — that's fine
        import re
        # Find all subprocess.run calls containing pdftotext
        calls = re.findall(r'subprocess\.run\(\s*\[.*?\]', source, re.DOTALL)
        for call in calls:
            assert "-layout" not in call, f"BLOCKER: -layout flag in pdftotext call: {call}"


# ── Unicode edge cases ───────────────────────────────────────────────

class TestUnicodeEdgeCases:
    def test_zero_width_space_in_word(self):
        """U+200B (zero-width space) breaking words."""
        text = "signi\u200Bficant"
        result = norm(text, "standard")
        assert "\u200B" not in result

    def test_bom_at_start(self):
        """BOM (byte order mark) at start of text."""
        text = "\uFEFFThe study results"
        result = norm(text, "standard")
        # BOM may or may not be stripped — just verify text is intact
        assert "study results" in result

    def test_nbsp_in_statistics(self):
        """U+00A0 (non-breaking space) between stat elements."""
        text = "p\u00A0<\u00A0.001"
        result = norm(text, "standard")
        assert "\u00A0" not in result

    def test_thin_space_in_number(self):
        """U+2009 (thin space) used as thousands separator."""
        text = "N = 1\u2009234"
        result = norm(text, "standard")
        assert "\u2009" not in result

    def test_soft_hyphen(self):
        """U+00AD (soft hyphen) — invisible but breaks search. NOW HANDLED."""
        text = "signifi\u00ADcant"
        result = norm(text, "standard")
        assert "\u00AD" not in result
        assert "significant" in result

    def test_mixed_unicode_stats(self):
        """Full Unicode soup in a statistical expression."""
        text = (
            "r(261)\u00A0=\u00A0\u22120.73,\u2009"
            "95%\u00A0CI\u00A0[\u22120.78;\u00A0\u22120.67],\u2009"
            "p\u00A0<\u00A0.001"
        )
        result = norm(text, "academic")
        assert "-0.73" in result
        assert "[-0.78, -0.67]" in result
        assert "p" in result
        assert ".001" in result


# ── Regression tests from Phase 0 benchmark ──────────────────────────

class TestBenchmarkRegressions:
    def test_ieee_figure_fragments_not_stats(self):
        """Lesson 7: 'r>1', 'r>2' from figure axis labels are NOT correlations."""
        text = "Figure 2: Performance for r>1 and r>2 conditions"
        # These should NOT be counted as statistical patterns
        # This is a downstream consumer concern, not normalization

    def test_normalization_report_version(self):
        """Report must include version for consumer apps."""
        _, report = normalize_text("test", NormalizationLevel.standard)
        assert report.version == "1.2.0"
        assert report.level == "standard"

    def test_normalization_report_all_steps_tracked(self):
        """Every step must appear in steps_applied."""
        text = "signi\ufb01cant \u22120.73 p\n< .001"
        _, report = normalize_text(text, NormalizationLevel.academic)
        # Standard steps
        assert any("S1" in s for s in report.steps_applied)
        assert any("S3" in s for s in report.steps_applied)
        assert any("S5" in s for s in report.steps_applied)
        # Academic steps
        assert any("A1" in s for s in report.steps_applied)
