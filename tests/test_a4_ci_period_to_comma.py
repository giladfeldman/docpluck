"""
Regression tests for A4 CI delimiter harmonization — middle-period → comma.

ESCIcheck handoff 2026-05-24 D2: `collabra_57785` abstract carried
`d=0.39[0.25.0.54]` where the CI comma was rendered as a period (font
substitution / pdftotext glyph map). Downstream parsers cannot disambiguate
`0.25.0.54` from a decimal continuation and drop the CI. A4 now rewrites
`[d.d.d.d]` → `[d.d, d.d]` and likewise for parens.

Triage source:
docs/TRIAGE_2026-05-14_phase_5d_gold_audit.md → cluster EC-T3.
"""

from __future__ import annotations

from docpluck import NormalizationLevel, normalize_text


class TestA4PeriodToComma:
    def test_square_bracket_period_rewritten_to_comma(self):
        text = "Effect was d=0.39 [0.25.0.54] across replications."
        out, report = normalize_text(text, NormalizationLevel.academic)
        assert "[0.25, 0.54]" in out
        assert "[0.25.0.54]" not in out
        assert "A4_ci_delimiter_harmonization" in report.steps_changed

    def test_no_space_before_bracket_still_rewritten(self):
        # The original handoff verbatim: `d=0.39[0.25.0.54]` (no space).
        text = "Abstract: d=0.39[0.25.0.54]"
        out, _ = normalize_text(text, NormalizationLevel.academic)
        assert "[0.25, 0.54]" in out

    def test_parens_period_rewritten_to_comma(self):
        text = "95% CI (0.25.0.54) overlapped zero."
        out, _ = normalize_text(text, NormalizationLevel.academic)
        assert "(0.25, 0.54)" in out

    def test_negative_lower_bound_preserved(self):
        text = "d = 0.04 [-0.19.0.27] H1."
        out, _ = normalize_text(text, NormalizationLevel.academic)
        assert "[-0.19, 0.27]" in out

    def test_already_correct_comma_unchanged(self):
        text = "Effect d=0.39 [0.25, 0.54] survived."
        out, _ = normalize_text(text, NormalizationLevel.academic)
        assert "[0.25, 0.54]" in out
        # No spurious double-rewrite or duplication.
        assert out.count("[0.25, 0.54]") == 1

    def test_section_reference_not_rewritten(self):
        # `[1.2.3]` looks like 3 dot-separated tokens but the trailing `3`
        # is not `\d+\.\d+` shape, so the A4a rule must NOT match.
        text = "As shown in section [1.2.3] the design replicated."
        out, _ = normalize_text(text, NormalizationLevel.academic)
        assert "[1.2.3]" in out

    def test_single_decimal_in_brackets_unchanged(self):
        text = "Subscale [0.5] correlates with outcome."
        out, _ = normalize_text(text, NormalizationLevel.academic)
        assert "[0.5]" in out

    def test_t_test_with_ci_period_full_pattern(self):
        # The downstream-effectcheck shape: `t(741) = 3.93, p < .001, d = 0.29
        # [0.20.0.38]` — after A4a, the bracket binds as a real CI.
        text = "Importance: t(741) = 3.93, p < .001, d = 0.29 [0.20.0.38]"
        out, _ = normalize_text(text, NormalizationLevel.academic)
        assert "[0.20, 0.38]" in out
