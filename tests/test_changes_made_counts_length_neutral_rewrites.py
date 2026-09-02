"""``changes_made`` must report HOW MANY times a rule fired, not how much the
text length happened to change.

MetaESCI and effectcheck consume ``changes_made`` as a count of upstream
rewrites.  It has never been one: ``NormalizationReport._track`` derives the
value from ``abs(len(before) - len(after))`` unless the call site passes an
explicit ``count``, and exactly 3 of 46 call sites do.  Two consequences,
measured 2026-09-02 at NORMALIZATION_VERSION 1.9.63:

* A length-neutral rewrite records NOTHING -- the key is ABSENT, not 0.  Three
  U+2212 rewritten to ASCII hyphen is the paradigm case, and it is the exact
  sign-corruption class the metric exists to expose.  ``S4_quote_normalization``
  is length-neutral in ALL cases, so it has never reported anything.
* Worse, a MIXED rewrite reports a WRONG NUMBER rather than none: one en-dash
  and two em-dashes is three dashes normalised, but em-dash expands to ``--``
  and en-dash does not, so the length delta is 2 and ``dashes_normalized`` says
  2.  A plausible wrong count reaching a consumer with nothing failing is the
  most expensive shape this project has.

A comment at ``normalize.py`` around line 3176 states that a wired count is
authoritative even at zero delta.  That is true and did not apply here: the
dash and quote steps wired no count.
"""

from __future__ import annotations

import pytest

from docpluck.normalize import NormalizationLevel, normalize_text

EN, EM, MINUS, HYPHEN_U, NBHYPHEN = "\u2013", "\u2014", "\u2212", "\u2010", "\u2011"
LDQ, RDQ, LSQ, RSQ = "\u201C", "\u201D", "\u2018", "\u2019"


def _changes(raw: str) -> dict:
    _, report = normalize_text(raw, level=NormalizationLevel.academic)
    return report.to_dict().get("changes_made") or {}


@pytest.mark.parametrize(
    "raw, expected",
    [
        (f"a {MINUS}1 b {MINUS}2 c {MINUS}3", 3),        # length-neutral: was ABSENT
        (f"a {EN} b {EN} c {EN} d", 3),                  # length-neutral: was ABSENT
        (f"a {EM} b {EM} c", 2),                         # +1 char each: delta happened to agree
        (f"Scores 10{EN}20 {EM} see Table 1 {EM} here.", 3),  # MIXED: was 2, truth is 3
        (f"a {HYPHEN_U} b {NBHYPHEN} c", 2),             # length-neutral: was ABSENT
    ],
    ids=["minus-x3", "en-x3", "em-x2", "mixed-en1-em2", "hyphen+nbhyphen"],
)
def test_dashes_normalized_is_a_count_not_a_length_delta(raw: str, expected: int) -> None:
    assert _changes(raw).get("dashes_normalized") == expected


def test_quotes_normalized_is_reported_at_all() -> None:
    """S4 is length-neutral in every case, so it reported nothing, ever."""
    assert _changes(f"{LDQ}a{RDQ} and {LSQ}b{RSQ}").get("quotes_normalized") == 4


def test_a_document_with_no_dashes_reports_no_dash_key() -> None:
    """Two-sided control: the fix must not manufacture a count where the rule
    did not fire.  Without this, asserting 'the key is present' would be
    satisfied by a step that always reports something."""
    assert "dashes_normalized" not in _changes("plain ascii text, nothing to do")


def test_the_minus_rewrite_actually_happened() -> None:
    """Control on the fixture itself: a count is only meaningful if the rewrite
    occurred.  A test asserting counts against text that was never rewritten
    would pass for the wrong reason."""
    out, _ = normalize_text(f"d = {MINUS}0.42", level=NormalizationLevel.academic)
    assert MINUS not in out and "-0.42" in out
