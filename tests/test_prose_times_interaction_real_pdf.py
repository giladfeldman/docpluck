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
from docpluck.normalize import (
    recover_times_design_notation as RD,
    recover_times_wrapped_interaction as RW,
)


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


# ── W0l-A: factorial-design notation `<digit>(…) 3 <digit>(…)` ────────────────
# efendic residual: "2 (Between-subject factor--Direction: …) 3 2 (Between-
# subject factor--…) 3 3 (Within-subject factor--…) mixed-subject design". W0k's
# single-line word-pair regex can't see a `3` flanked by `)` and `<digit> (`.


def test_design_notation_both_boundaries_recovered_wrapped():
    # The real efendic paragraph, wrapped exactly as pdftotext emits it.
    t = (
        "Both studies had a 2 (Between-subject factor--Direction:\n"
        "High vs. Low) 3 2 (Between-subject factor--Manipulated\n"
        "Attribute: Risk vs. Benefit) 3 3 (Within-subject factor--\n"
        "Technology Scenario: Nuclear Power vs. Natural Gas vs.\n"
        "Food Preservative) mixed-subject design"
    )
    out = RD(t)
    assert ") × 2 (" in out
    assert ") × 3 (" in out
    assert out.count("×") == 2


def test_design_notation_factor_size_chain_with_design_tail():
    # No explicit between/within keyword, but a factor-size chain closed by a
    # `factorial design` tail — the branch-(b) signal.
    assert RD("We used a 2 (Gender) 3 2 (Condition) factorial design here.") == (
        "We used a 2 (Gender) × 2 (Condition) factorial design here."
    )


@pytest.mark.parametrize("s", [
    # No factor parenthetical + no design tail → left alone.
    "Scores ranged from (min 1) 3 2 (max 5) across the board.",
    "The three subscales (anxiety) 3 4 (depression) were summed.",
    # a formula, in a paragraph that also mentions design
    "In the factorial design section, the formula f(x) 3 2 (y) is not a factor.",
    # a range recode near the word 'design' but with no immediate design tail
    "Scores (bin 1) 3 5 (bin 9) informed the design later on.",
    # 'reduced conditions (from level 3) 3 2 (see note)' — not factor-size parens
    "The revised design reduced conditions (from level 3) 3 2 (see note) here.",
    # already correct — idempotency (no bare '3' boundary)
    "a 2 (Sex) × 2 (Cond) factorial design",
])
def test_design_notation_no_false_positive(s):
    assert RD(s) == s


def test_design_notation_idempotent():
    t = (
        "a 2 (Between-subject factor--A) 3 2 (Within-subject factor--B) "
        "mixed-subject design"
    )
    once = RD(t)
    assert RD(once) == once
    assert once.count("×") == 1


# ── W0l-B: line-wrapped interaction term `<Pred> 3` / next-line `<Pred>` ──────
# efendic residual: "the three-way interaction (Direction 3\nManipulated
# Attribute × CMA)" — the wrap splits `Direction × Manipulated` across lines.


def test_wrapped_interaction_recovered():
    t = (
        "Furthermore, the three-way interaction (Direction 3\n"
        "Manipulated Attribute × CMA) suggests that"
    )
    out = RW(t)
    assert "Direction ×\n" in out
    assert "Direction 3\n" not in out


@pytest.mark.parametrize("t", [
    # ordinal wrap, no interaction context
    "results shown in Model 3\nRelationship strength was measured",
    # count-noun head
    "the interaction between condition and 3\ngroups was tested",
    # count wrap, no interaction, lowercase-ish
    "we ran 3\nstudies in total",
    # interaction present but head is a plural count noun
    "we probed the interaction (Direction 3\ngroups) in Study 1",
    # both flanks present but no 'interaction' anywhere
    "as shown by Smith 3\nJones did not replicate",
    # ── the corpus FP scan caught these two (v2.4.116): a figure/table NUMBER
    # whose caption's next line starts Title-Case and mentions "interaction(s)".
    # The reference-word tail guard must reject them. (amj_1, jamison_2020_jesp.)
    "In the quarterly report\n\nFIGURE 3\nRegression Slopes for the Interaction of X",
    "J. Jamison, et al.\n\nTable 3\nMain-effects and interactions.\nScenario 1:",
    # more reference-word tails, same shape
    "see Model 3\nInteraction Effects were estimated",
    "as in Study 3\nInteraction of Condition and Time",
])
def test_wrapped_interaction_no_false_positive(t):
    assert RW(t) == t


def test_wrapped_interaction_idempotent():
    t = "the interaction (Direction 3\nManipulated Attribute) held"
    once = RW(t)
    assert RW(once) == once


# ── W0l end-to-end on the real efendic PDF (rule 0d: real library + real PDF) ──

_EFENDIC_KEY = "10.1177/19485506211056761"


def _load_efendic_pdf_bytes():
    """Locate efendic via article-finder's cache-check (rule I9 — never a direct
    test-pdfs path). Skips if the corpus PDF is not present locally."""
    import json
    import subprocess

    home = os.path.expanduser("~")
    cc = os.path.join(home, ".claude", "skills", "article-finder", "cache-check.py")
    if not os.path.exists(cc):
        pytest.skip("article-finder cache-check.py not available")
    try:
        raw = subprocess.check_output(["py", "-3", cc, _EFENDIC_KEY], text=True)
    except Exception as exc:  # pragma: no cover - environment dependent
        pytest.skip(f"cache-check failed: {exc}")
    info = json.loads(raw)
    if not info.get("found") or not info.get("path") or not os.path.exists(info["path"]):
        pytest.skip("efendic corpus PDF not present locally")
    with open(info["path"], "rb") as fh:
        return fh.read()


def test_efendic_times_residuals_gone_end_to_end():
    """Render efendic through the real library and confirm BOTH residual '×'-as-
    '3' shapes are gone from the rendered .md. Fails at HEAD (v2.4.115), passes
    with W0l (v2.4.116)."""
    pdf = _load_efendic_pdf_bytes()
    from docpluck.render import render_pdf_to_markdown

    md = render_pdf_to_markdown(pdf)
    # (A) factorial-design notation: the corrupted `) 3 2 (` / `) 3 3 (` must be
    # gone; the recovered `×` between factor sizes must be present.
    assert ") 3 2 (" not in md
    assert ") 3 3 (" not in md
    assert "× 2 (" in md or ") × 2 (" in md
    # (B) line-wrapped interaction term: no `Direction 3` at a line end.
    assert "Direction 3\n" not in md
    # The corrected three-way interaction term is present (either same-line or
    # wrap-joined) — the `Direction × Manipulated` pair is recovered.
    assert "Direction × Manipulated" in md
