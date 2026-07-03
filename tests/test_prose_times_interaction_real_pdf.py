"""Regression test for W0k: '×'-as-'3' glyph in body PROSE / flattened caption
interaction terms (v2.4.112).

The independent Sonnet canary audit (2026-07-03) found efendic_2022_affect's
interaction terms rendering with a corrupted '3' for '×' in the body prose and a
flattened italic table-caption run — the table-cell-scoped W0i (v2.4.103) never
saw these channels. The '3' is the single most dangerous glyph to touch in prose
(a genuine ordinal/count), so W0k fires only under a tight signature:
interaction-context + non-reference + non-count-noun + >=1 Title-Case/acronym
predictor flank, with a 2-pass relaxation for lowercase-lowercase pairs inside a
line that already resolved a '×' (a confirmed interaction-term run).
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("DOCPLUCK_DISABLE_CAMELOT", "1")

from docpluck.normalize import recover_times_interaction_glyph_in_prose as R


def test_body_interaction_parenthetical_recovered():
    t = "the three-way interaction (Direction 3 Manipulated Attribute 3 CMA) suggests"
    assert R(t) == "the three-way interaction (Direction × Manipulated Attribute × CMA) suggests"


def test_flattened_caption_run_fully_recovered():
    # A flattened caption run — the 2-pass relaxation recovers the trailing
    # lowercase-lowercase pair once the run is confirmed by earlier `×`.
    t = ("Direction 3 manipulated attribute PMA 3direction PMA 3 manipulated "
         "attribute PMA 3 direction 3 manipulated attribute")
    out = R(t)
    assert "3" not in out  # every interaction `3` became `×`
    assert out.count("×") == 5


def test_single_both_predictor_pair_recovered():
    # A single pair with BOTH flanks Title-Case is a strong-enough signal.
    assert R("Change in manipulated attribute (CMA) Direction 3 Manipulated Attribute") == (
        "Change in manipulated attribute (CMA) Direction × Manipulated Attribute"
    )


@pytest.mark.parametrize("s", [
    "Table 3 summarizes the results across conditions.",
    "as reported in Study 3 and replicated in Study 4.",
    "see the materials at osf.io/pg3ae for details.",
    "We ran 3 studies with 3 conditions each.",
    "participants rated 3 items on a 7-point scale.",
    "Model 3 included the covariates.",
    "the interaction between age and 3 groups was tested",
    "Figure 3 shows the distribution.",
    "at Time 3 we measured the outcome.",
    "we had 3 conditions and 2 groups",
    "participants (n = 3) in 2 waves",
    "the top 3 items on 5 scales",
])
def test_no_false_positive_on_counts_and_ordinals(s):
    assert R(s) == s


def test_lone_single_lowercase_pair_not_touched():
    # A single lowercase-lowercase pair with no interaction context / no `×` in
    # the line is left alone (could be a genuine "word 3 word" coincidence).
    assert R("we tested item 3 carefully") == "we tested item 3 carefully"


@pytest.mark.parametrize("s", [
    # The reference word is the LEFT FLANK of the pair (not just before it) — a
    # genuine ordinal. This broke normalize idempotency on socius_3/demography_3/
    # jmf_2 when a later reflow put "Model 3 Relationship" into a 2-pair line.
    "Later Model 3 Relationship Stress Health stress Relationship",
    "the interaction Model 3 Relationship was tested here",
    "Study 3 Condition A versus Study 3 Condition B",
    "Wave 3 Assessment and Wave 3 Follow-up data",
    "Factor 3 Loading and Factor 3 Structure",
])
def test_reference_word_left_flank_is_ordinal(s):
    assert R(s) == s
