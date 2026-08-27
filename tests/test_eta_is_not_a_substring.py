"""`eta` must not match inside ordinary English words.

Filed by Scimeto/CitationGuard in `INBOX_FROM_SCIMETO_2026-08-21b_flatten_typing_and_sections.md`
§1, with a three-line reproduction:

    from docpluck.tables.flatten import _effect_type_for
    _effect_type_for('Table 2. Body Weight, Glycemic Control, and Cardiometabolic Risk Factors')
    # -> 'eta_squared'

`_EFFECT_TYPE_PATTERNS` ended its eta alternatives with a bare, unanchored `eta`.
`_effect_type_for(vocab_all)` runs it over the whole CAPTION AND FOOTNOTE, so any
table whose caption contains `Cardiom-eta-bolic`, `b-eta`, `th-eta` or `M-eta-`
was typed `eta_squared`, and `_effect_key` then keyed **every unlabeled estimate
column in that table** as `eta2`.

Measured by the reporter on JAMA Netw Open Table 2 (*"Body Weight, Glycemic
Control, and Cardiometabolic Risk Factors"*): 19 rows emitted with an `eta2`
field, **18 of them outside η²'s domain [0, 1]** (17 negative, one at 10.65),
against **0** occurrences of `η` / `eta squared` / `partial eta` / `eta2`
anywhere in the extracted text. The column was headed "mean change from baseline
(95% CI)" — kilograms and percent, not variance proportions.

`beta coefficient` -> `eta_squared` is the same defect and is worse: an
unstandardized coefficient column relabelled as a partial eta-squared.

This is a FABRICATION, not a miss: docpluck names a statistic the paper does not
report. Fixed 2026-08-22.
"""

from __future__ import annotations

import pytest

from docpluck.tables.flatten import _effect_type_for


@pytest.mark.parametrize(
    "caption",
    [
        "Table 2. Body Weight, Glycemic Control, and Cardiometabolic Risk Factors",
        "beta coefficient",
        "Beta (SE)",
        "theta",
        "Meta-analysis of replication effects",
        "Metabolic outcomes by arm",
        "Zeta potential of the nanoparticles",
    ],
)
def test_eta_inside_an_english_word_is_not_an_effect_type(caption: str):
    assert _effect_type_for(caption) != "eta_squared", (
        f"{caption!r} was typed as eta-squared on a substring match"
    )
    assert _effect_type_for(caption) != "eta_squared_partial", (
        f"{caption!r} was typed as partial eta-squared on a substring match"
    )


@pytest.mark.parametrize(
    "header",
    ["eta2", "eta 2", "eta squared", "η²", "η2", "Eta2"],
)
def test_a_real_eta_header_still_types(header: str):
    assert _effect_type_for(header) in {"eta_squared", "eta_squared_partial"}, (
        f"{header!r} is a genuine eta-squared header and must still be recognised"
    )


@pytest.mark.parametrize(
    "header",
    ["partial eta squared", "η²p", "ηp²", "eta2_p", "eta squared partial"],
)
def test_a_real_partial_eta_header_still_types(header: str):
    assert _effect_type_for(header) == "eta_squared_partial", (
        f"{header!r} is a genuine partial-eta header"
    )
