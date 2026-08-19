"""A comma-separated run of 3+ integers is a TUPLE or an IDENTIFIER, never a number.

REAL-PAPER EVIDENCE (the directive requires a DOI + page, never a hypothetical):

    10.1177/0146167210380928, page 13, reference list:
        http://content.time.com/time/specials/article/0,9171,1848755,00.html
    A3c read the `0,9171` as a leading-zero European decimal and rendered
        .../article/0.9171,1848755,00.html
    which is a different URL, and it 404s. The paper printed a correct link and
    docpluck broke it — so this is OURS to fix under the separation-of-duties
    directive (2026-08-13), independent of whether A3c itself is later retired.

    Found by `tools/diag/repair_site_scan.py --sample 40`, which reports A3c
    firing exactly ONCE across 40 English-language papers from the custodian —
    and this is that one firing. The rule was 0 right and 1 wrong on that sample.

WHY THE GUARD IS SHAPED THIS WAY. v2.4.128 already refused a *bracket-delimited*
numeric tuple (the RGB stimulus spec `purple (128,0,128)`), but the bracket was
doing the work, so an identifier in a URL path or an ISBN — same shape, no
bracket — was untouched. The guard now keys on the RUN itself.

Distinguishing a tuple from a genuine thousands-grouped number is POSITIVE, not
an exclusion list (an enumeration is never complete — the recurring failure in
this module):

    a thousands-grouped number has EVERY group after the first exactly 3 digits
        1,234,567     234 / 567         -> a NUMBER, keep stripping (A3a)
    anything else with 3+ comma-separated integers is a tuple or an identifier
        0,9171,1848755,00   9171/1848755/00  -> a URL path
        978,0,306,40615,7   0/306/40615/7    -> an ISBN
        128,0,128           0/128            -> an RGB triple

Two elements stay ambiguous and are deliberately NOT covered here: `(52,272)` is
an interquartile range and `(0,003)` is a p-value, and the two rules that own
them already resolve them (A3a's whole-bracket pair guard; A3c's leading zero).
Only at three elements does the tuple reading become unambiguous, because no
decimal has two commas in it.
"""

from __future__ import annotations

import pytest

from docpluck.normalize import NormalizationLevel, normalize_text


def _norm(s: str) -> str:
    return normalize_text(s, NormalizationLevel.academic)[0]


def test_url_path_identifier_survives_real_paper():
    """10.1177/0146167210380928 p13 — the reference-list Time.com link."""
    src = (
        "Kluger, J. (2008, November 26). Why we worry about the wrong things. "
        "Time. Retrieved from http://content.time.com/time/specials/"
        "article/0,9171,1848755,00.html"
    )
    assert "article/0,9171,1848755,00.html" in _norm(src)


def test_isbn_run_survives():
    """Same shape, no bracket: an ISBN's hyphen-free comma form."""
    assert "978,0,306,40615,7" in _norm("ISBN 978,0,306,40615,7 was used")


def test_rgb_triple_survives_unbracketed():
    """The v2.4.128 RGB defect, with the bracket removed — same shape."""
    out = _norm("stimulus colours were purple 128,0,128 and orange 255,165,0")
    assert "128,0,128" in out
    assert "255,165,0" in out


def test_bracketed_rgb_still_survives():
    """The v2.4.128 case must not regress when the guard generalises."""
    out = _norm("purple (128,0,128), orange (255,165,0)")
    assert "(128,0,128)" in out
    assert "(255,165,0)" in out


@pytest.mark.parametrize(
    "src",
    [
        # RE-FIXTURED 2026-08-14: these used to assert the STRIP (`1234567`).
        # A3a is deleted, so a thousands-grouped number is delivered as printed.
        # This was the guard's load-bearing boundary — the one case it had to
        # let through — and it is now simply the same as every other case,
        # which is what retiring the rule bought.
        "N = 1,234,567 records",
        "we screened 12,345,678 tweets",
    ],
)
def test_thousands_grouped_numbers_pass_through(src):
    assert _norm(src).strip() == src


@pytest.mark.parametrize(
    "src",
    [
        # Two elements were the ambiguous case the guard deliberately did not
        # claim, leaving them to A3a's pair guard and A3c's leading zero. All
        # three are now deleted, so the ambiguity is resolved the only way it
        # safely can be: the token is delivered exactly as the paper printed it.
        "the p-value was (0,003) overall",
        "Median (Q1,Q3) was 148 (52,272)",
    ],
)
def test_two_element_cases_pass_through(src):
    """Both readings are preserved because NEITHER is imposed.

    `(52,272)` is an interquartile range and `(0,003)` is a p-value, and no
    structural signal separates them — that was true when the guard was written
    and it is still true. What changed is the response to it: we no longer
    guess. The consumer holds the parsed statistic and its context, so it can
    decide; we hold text, so we cannot.

    Note this also pins the v2.4.129 fix for a sibling A3c had been MASKING:
    with A3c gone, `(0,003)` reached A4's delimiter-spacing arm intact and
    became `(0, 003)` — a European p-value rendered as a two-element pair.
    """
    assert _norm(src).strip() == src


def test_a_tuple_and_a_value_on_one_line_are_BOTH_passed_through():
    """RE-FIXTURED: this used to assert the tuple survived WHILE `d = 0,45`
    converted, proving the guard was scoped to the run rather than the line.

    That scoping question dissolved with the rules. The line is kept because it
    is the sharpest single example of the ambiguity docpluck refuses to
    resolve: `128,0,128` and `0,45` are the same shape, and only meaning
    separates them.
    """
    src = "purple 128,0,128 was used; the effect was d = 0,45 overall"
    assert _norm(src).strip() == src
