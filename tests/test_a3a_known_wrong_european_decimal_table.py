"""FIXED, and INVERTED: A3a's 1000x error class is closed (v2.4.130, 2026-08-14).

**This file used to assert behaviour that was WRONG**, deliberately, so the
defect could not be forgotten or silently "fixed" without someone reading it. It
worked exactly as intended: the pin survived one release, was read in the next
session, and the rule was retired. The assertions below have now INVERTED, as
the original header instructed.

THE FIX WAS NOT THE ONE ANTICIPATED, and the difference is the lesson. This file
predicted a **local-window numeric locale** would be needed to tell `185,178`
(a European decimal) from `N = 1,182` (a genuine thousands group). That remedy
was never built, because a prior question went unasked: **what was A3a FOR?**
Its own comment answered it — "strips commas ... SO A3 SEES THE ALREADY-CLEAN
INTEGER AND LEAVES IT ALONE". A3 had been deleted in v2.4.129. The rule was
guarding against something that no longer existed, so the correct fix was not a
better discriminator but no rewrite at all. **Before building a smarter version
of a rule, check whether the rule still has a job.**

REAL-PAPER EVIDENCE — DOI, page, and rasterized:

    10.1177/0956797620935584
    Battal, Occelli, Bertonati, Falagiarda & Collignon,
    "General enhancement of spatial hearing in congenitally blind people",
    Psychological Science. Table S2, PDF page 24.

    Rasterized at 600 dpi (poppler pdftoppm). The column header reads
    `df- satterthwaite` and the printed cells are:

        185,178      31,836      188,193      188,705      199,183

    A Satterthwaite degrees-of-freedom is FRACTIONAL by construction. `185,178`
    is 185.178. There is no reading of that table in which a Satterthwaite df is
    one hundred eighty-five thousand. The whole table is R output pasted under a
    comma-decimal locale — the t-ratios in the same rows read `-1,966`, `-2,252`,
    `-7,799`, `-4,575`, `-3,097`, `-4,021`, `-7,281`, `-3,188`.

WHAT DOCPLUCK DOES TODAY:

    '185,178'  ->  '185178'      A3a_thousands_separator_protect
    '-1,966'   ->  '-1966'       A3a_thousands_separator_protect

A **1000x error on a published inferential statistic**, and it is worse than the
defects this session retired, for a reason worth stating: a half-converted
interval (`0,85-0.99`) at least *looks* inconsistent and might prompt scrutiny.
`31836` looks like a perfectly ordinary number. Silent-but-plausible beats
silent-but-visibly-broken as a failure mode, and this is the former.

WHY IT IS NOT FIXED IN THIS RUN, stated rather than buried:

  * A3a's GENERIC arm fires **984 times across 157 of 297 English papers**. It is
    the second-most-fired step in the pipeline. Narrowing it is a coverage change
    for every consumer, and under the migration order agreed 2026-08-13 a
    coverage change goes to consumers BEFORE it ships, never after.
  * `\\d{1,3},\\d{3}` is structurally identical for a genuine thousands group
    (`N = 1,182 participants`) and a European decimal (`185,178`). Neither the
    label nor the magnitude decides it: `M = 1,234` could legitimately be a
    reaction time in milliseconds.
  * The discriminator that WOULD work is a **local-window numeric locale** —
    Battal's Table S2 also contains `0,355` and `0,050`, leading-zero comma
    decimals that prove the table's convention. That was already the identified
    remedy (session B punch-list 5.7), deferred with the precondition *"confirm
    the shape occurs in ENGLISH input before building"*. **This paper is that
    confirmation**, and it is the first one: it unblocks the work.

HOW IT WAS FOUND, because the method matters more than the instance: an
independent third-model review was asked to hunt in good faith for a case where
the comma rules are RIGHT. It found one — A3c's conversions in this very table
are correct — and in doing so surfaced this, in the one rule of the family that
had been marked KEEP and whose error rate nobody had measured. **The plan
measured A3 and A3c in detail and never asked the same question of A3a.**

A SECOND, INDEPENDENT PROBLEM THIS PAPER EXPOSED — recorded because it
invalidated a premise, not just a rule. The document-level `infer_numeric_locale()`
reported `decisive_us, european_markers=0, us_markers=61` here, despite ~130
European-decimal cells, because every marker is OPERATOR-GATED and these are bare
table cells. So the finding "396 English articles -> 0 European-locale documents"
described the reach of the INSTRUMENT, not the corpus. **That instrument was
deleted in v2.4.129** (user directive: English + US assumed, European numbers
passed through unconverted); its marker vocabulary was retained for a future
LINE- or TABLE-scoped guard, and this file's second test pins the blind spot that
guard must solve. See `tests/test_numeric_locale_markers.py`.
"""

from __future__ import annotations

import pytest

from docpluck.normalize import (
    _LOCALE_EUROPEAN_MARKERS,
    NormalizationLevel,
    normalize_text,
)


def _norm(s: str) -> str:
    return normalize_text(s, NormalizationLevel.academic)[0]


@pytest.mark.parametrize(
    "printed,wrong,right",
    [
        ("185,178", "185178", "185.178"),   # df- satterthwaite
        ("31,836", "31836", "31.836"),      # df- satterthwaite
        ("188,193", "188193", "188.193"),   # df- satterthwaite
        ("-1,966", "-1966", "-1.966"),      # t ratio
        ("-7,799", "-7799", "-7.799"),      # t ratio
    ],
)
def test_the_european_decimal_is_now_delivered_AS_PRINTED(printed, wrong, right):
    """10.1177/0956797620935584 Table S2 p24. INVERTED 2026-08-14, as instructed.

    We deliver `printed`. We no longer deliver `wrong` (the 1000x error), and we
    deliberately do NOT deliver `right` either: emitting `185.178` would be a
    conversion, and docpluck does not convert European numbers — it hands the
    consumer the source token so the consumer can decide. `right` is retained in
    the parametrisation as documentation of what the paper MEANS, which is the
    fact a reader of this file needs and the code must not act on.
    """
    got = _norm(printed)
    assert got == printed, f"{printed!r} must pass through, got {got!r}"
    assert got != wrong, "the 1000x error must not return"
    assert got != right, (
        "docpluck must not CONVERT a European decimal either — passing it "
        "through is what lets the consumer decide (docs/SCOPE.md)"
    )


def test_KNOWN_WRONG_the_marker_vocabulary_is_blind_to_bare_table_cells():
    """The operator gate makes the markers blind to this whole table.

    v2.4.129 deleted the document-level verdict this used to assert on — partly
    BECAUSE of this blindness. The limit itself is unchanged and still matters,
    because the marker vocabulary was retained as the intended foundation for a
    LOCAL-WINDOW guard: whatever is built on it must solve this, or it will
    inherit the same blind spot.

    Every European marker requires an operator (`=`, `<`, `>`) immediately
    before the value. A flattened table cell has none, so a table that is
    entirely comma-decimal contributes ZERO European evidence.
    """
    import re

    table = (
        "Contrast\tEstimate\tt-ratio\tp-value\tdf- satterthwaite\n"
        "blind vs sighted\t-0,697\t-1,966\t0,050\t185,178\n"
        "blind vs sighted\t-0,355\t-2,252\t0,031\t31,836\n"
    )
    hits = {k: len(re.findall(v, table)) for k, v in _LOCALE_EUROPEAN_MARKERS.items()
            if re.findall(v, table)}
    assert not hits, (
        f"the markers now see bare comma-decimal table cells ({hits}) — if that "
        "is deliberate, re-measure the '396 English papers' finding and "
        "re-report it to consumers, because it was produced by the blind version"
    )
