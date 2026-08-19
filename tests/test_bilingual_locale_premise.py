"""The "one article, one numeric convention" premise is FALSE. Measured.

This module exists to stop a specific future change: gating the thousands-strip
(A3a) on the document-level `numeric_locale` verdict. That change is the natural
next step from decision D5, it was the user-selected option, and **measurement
refuted it**. The refutation is recorded here as executable tests because a
negative result nobody can re-run gets re-proposed in six months.

## The premise

D5, and effectcheck's `infer_numeric_locale` (its L1/L2/L3 machinery), both rest
on this:

> The two conventions are MUTUALLY EXCLUSIVE within one article, so a single
> unambiguous token anywhere settles every ambiguous token in it.

If that holds, a `decisive_eu` verdict licenses reading every `1,234` in the
document as the decimal 1.234, and A3a's thousands-strip should be suppressed.

## The measurement that breaks it

21 European-locale papers were acquired through article-finder specifically to
make this feature measurable (the previous corpus had ZERO). All 21 measure
`decisive_eu` with gating confidence. Inside them, all four of these are real:

```
Turkish body      'chi2 degeri ise 528,329 (p<0,001)'  is 528.329   A3a strips -> 528329  WRONG
Turkish body      'toplam varyans %68,389'             is 68.389%   A3a strips -> 68389   WRONG
English abstract  'Data were collected from 1,738 adult patients'   A3a strips -> 1738    RIGHT
English abstract  'Results: From 1,958 women included'              A3a strips -> 1958    RIGHT
```

**Latin-American and Turkish journals publish bilingual abstracts.** The English
abstract uses English number conventions; the native-language body uses
continental ones. One article, two conventions, both correct in their own span.

So a document-level gate is wrong in BOTH directions at once: suppressing the
strip fixes the two body decimals and corrupts the two abstract counts
(`1,738 adult patients` -> `1.738 adult patients`, a cohort of one-point-seven
people). Leaving it fixes the counts and corrupts the decimals. There is no
document-level answer, because the question is not document-level.

## What this does NOT retract

Publishing the verdict stays right — `numeric_locale` is still the only channel
through which the fact reaches a consumer at all, since our own output inverts
the evidence. What it retracts is *acting* on the verdict as though it described
every span of the document uniformly. The published field's own docs now state
this limit.

## The direction that would actually work, unbuilt and unmeasured

Locale evidence scoped to a LOCAL window — line, sentence, or paragraph — rather
than the whole document. The bilingual-abstract problem is a locality problem:
`528,329` sits on a line with `p<0,001`, an unambiguous European marker, while
`1,738 adult patients` has no European marker anywhere near it. That is a
strictly better discriminator than a document verdict AND than a per-token
structural rule, and it is not what anyone proposed. It needs its own
measurement and its own adversarial review before anything ships.
"""

from __future__ import annotations

import pytest

from docpluck.normalize import (
    _LOCALE_EUROPEAN_MARKERS,
    NormalizationLevel,
    normalize_text,
)


def _norm(text: str) -> str:
    out, _ = normalize_text(text, NormalizationLevel.academic)
    return out.strip()


# Real content shapes from the acquired European corpus. Kept short and
# paraphrased to the numeric construct — article-finder is the sole custodian of
# publication text, so these are the minimal token contexts, not article body.
EU_BODY_DECIMAL = "chi2 degeri ise 528,329 (p<0,001, Sd=1)"
EU_BODY_PERCENT = "toplam varyans %68,389 olarak belirlenmistir"
EN_ABSTRACT_COUNT_1 = "Data were collected from 1,738 adult patients"
EN_ABSTRACT_COUNT_2 = "Results: From 1,958 women included in the study"


def test_a_bilingual_document_attests_BOTH_conventions():
    """The premise's counterexample, as one document.

    If this ever starts reporting a clean single-convention verdict, the
    measurement below has drifted and the whole argument needs re-running.
    """
    doc = "\n".join([EU_BODY_DECIMAL, EU_BODY_PERCENT,
                     EN_ABSTRACT_COUNT_1, EN_ABSTRACT_COUNT_2])
    # v2.4.129: the document-level VERDICT is deleted, so this now asserts on
    # the marker vocabulary directly. The premise it pins is unchanged and is
    # in fact the reason the verdict went: one document, two conventions, so no
    # document-scoped answer can be right for all of it.
    import re
    eu = sum(len(re.findall(pat, doc)) for pat in _LOCALE_EUROPEAN_MARKERS.values())
    # European evidence is present...
    assert eu > 0
    # ...yet the document demonstrably contains correct US-convention counts.
    assert "1,738" in doc and "1,958" in doc


@pytest.mark.parametrize("src", [EN_ABSTRACT_COUNT_1, EN_ABSTRACT_COUNT_2])
def test_english_abstract_counts_pass_through_UNCONVERTED(src):
    """RE-FIXTURED 2026-08-14 (A3a deleted). The DANGER here is unchanged.

    This pinned the trap facing any locale-gated design: `1,738 adult patients`
    is one thousand seven hundred and thirty-eight people, and CONVERTING it to
    `1.738` publishes a cohort of under two. A rule that suppressed the strip
    under a `decisive_eu` document verdict would have done exactly that, in a
    bilingual article whose English abstract sits over a native-language body.

    Retiring A3a resolves it in the only way that is safe in both directions:
    the token is neither stripped nor converted. `1,738` reaches the consumer as
    the paper printed it. **The assertion that matters — that we never emit
    `1.738` — is unchanged**, and is now guaranteed structurally rather than by
    a gate that had to be right.
    """
    out = _norm(src)
    assert "1,738" in out or "1,958" in out
    assert "1.738" not in out and "1.958" not in out
    assert "1738" not in out and "1958" not in out


@pytest.mark.parametrize(
    "src,wrong",
    [(EU_BODY_DECIMAL, "528329"), (EU_BODY_PERCENT, "68389")],
)
def test_continental_three_decimal_values_are_no_longer_stripped(src, wrong):
    """FIXED and INVERTED 2026-08-14 — the pin did its job.

    `528,329` is a Bartlett chi-square of 528.329 and `%68,389` is 68.389% of
    variance explained. A3a stripped both to integers: a 1000x error on a
    published statistic. This test pinned that as KNOWN-WRONG so it would stay
    visible in the suite rather than in a doc nobody reads, and it named the
    condition for flipping. A3a is deleted, so it flips.

    Note the fix is NOT the local-window locale this file anticipated, and not
    the "gate A3a on the document verdict" it warned against — both were
    attempts to make a rewrite smarter. The rewrite simply stopped.

    We do NOT assert `528.329` here: converting it would be a conversion, and
    docpluck does not convert. The value passes through as printed. (These
    fixtures are Turkish-body text, retained because this file's whole subject
    is the BILINGUAL premise — an English abstract over a native-language body,
    which is why no document-level verdict can be correct for the whole
    document. They are evidence ABOUT the premise, never about English-article
    behaviour; see docs/SCOPE.md.)
    """
    out = _norm(src)
    assert out.strip() == src.strip(), f"must pass through verbatim, got {out!r}"
    assert wrong not in out, "the 1000x strip must not return"
