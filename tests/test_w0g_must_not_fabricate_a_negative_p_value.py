r"""W0g must not pair a correlation's CI with a p-value. RED as written.

`W0g_dropped_minus_ci_pairing` (`recover_dropped_minus_via_ci_pairing`, section A R5 /
B7, 2026-05-23) flips a bare positive decimal to negative when a confidence interval in
the same record "proves" the sign was dropped. **It does not check which statistic the
interval belongs to.**

THE REAL RECORD, `korbmacher_2022_kruger` (Kruger-Dunning replication, APA corpus).
The page prints, and pdftotext delivers verbatim:

    r(223) = -0.13 (p = .0498, 95% CI [-0.26, -0.0002])

The bracket is `r`'s interval. W0g takes the nearest bare positive decimal in the
record -- the **p-value** -- and re-signs it, publishing

    r(223) = -0.13 (p = -.0498, 95% CI [-0.26, -0.0002])

A negative p-value is impossible. The same paper yields `p = -.05` from the second
occurrence of the shape.

## Not a re-normalization artifact -- it is in the SHIPPED OUTPUT

The handoff that scoped this work recorded it as pass-2 only (raw 0, pass 1 zero, pass 2
two), which reads as an idempotency curiosity. Measured 2026-09-08 it is not. The render
channel calls W0g on markdown that `normalize_text` has ALREADY normalized, so the
render pass IS a second pass: `render_pdf_to_markdown` on this PDF emits both fabricated
values on the FIRST render. Every consumer of the rendered `.md` has been receiving them.

Why the raw text escapes and the normalized text does not: pdftotext delivers the
bracket with EN DASHES, which W0g's negative-bound pattern does not match.
`S5_dash_normalization` converts them to ASCII hyphens, and the next pass fires.

## Why the rule goes rather than gets a guard

THE THREE TIERS directive (CLAUDE.md, user directive 2026-09-06, committed `0c90a18`)
names **CI containment** verbatim as forbidden evidence, and W0g is CI containment by
name. It also fails the directive's gate test -- *if every surrounding word and number
were replaced with random garbage, would the same evidence still justify the output?*
No: its only inputs are the neighbouring tokens. And its signature is `text: str`, so it
can never consult the rendered page, which means it can never be licensed for a FILE LIE
even in principle. CHECK THE SIGNATURE BEFORE YOU CHECK THE LOGIC.

A "skip the token after `p =`" guard would fix this paper and not the class. The rule
cannot tell which statistic an interval describes, because that is a fact about the
sentence and not about anything the renderer emitted.

## ASSERTED THROUGH THE SHIPPED PATHS, NEVER THE RAW FUNCTION

`recover_dropped_minus_via_ci_pairing` is KEPT, unwired, so its evidence survives -- as
`f169c3d` kept W0i/W0k/W0l. A test that calls it directly therefore keeps FAILING after
the call sites are removed, because it measures the definition rather than the product.
That trap cost a cycle on the W0k removal. Everything here goes through `normalize_text`
or `render_pdf_to_markdown`.

## TWO-SIDED BY CONSTRUCTION

`test_the_minus_recoveries_that_stay_are_still_wired` pins W0b, W0d, W0q and S5, so
"return the input unchanged" is not a way to make this file green -- and in particular
W0b/W0d must survive. CLAUDE.md twice records "W0b/W0d/W0g fire 0 times in 226 papers";
that is WRONG for W0b and W0d, which fire on `efendic_2022_affect` and recover 62 real
minus signs correctly. Sweeping the family out together would destroy published values.
A FAMILY VERDICT MUST BE TESTED PER MEMBER.
"""

from __future__ import annotations

import re

import pytest

from docpluck.extract import extract_pdf
from docpluck.normalize import NormalizationLevel, normalize_text
from docpluck.render import render_pdf_to_markdown
from tests.conftest import pdf_available, pdf_path

# `p` followed by any comparison operator and a NEGATIVE decimal. A p-value is a
# probability: it cannot be negative, in any notation, at any precision.
_NEGATIVE_P = re.compile(r"\bp\s*[=<>]\s*-\s*\.?\d")

_CORPUS, _PAPER = "apa", "korbmacher_2022_kruger.pdf"


def _pdf_bytes() -> bytes:
    if not pdf_available("docpluck", _CORPUS, _PAPER):
        pytest.skip(
            f"SKIPPED, NOT PASSED: {_CORPUS}/{_PAPER} absent from the local corpus. "
            "Read a skip here as a check that did not run -- four sibling tests in "
            "this suite skipped silently for weeks on a filename typo."
        )
    with open(pdf_path("docpluck", _CORPUS, _PAPER), "rb") as fh:
        return fh.read()


def test_w0g_does_not_fabricate_a_negative_p_value_in_the_rendered_markdown():
    """THE SHIPPED OUTPUT. `render_pdf_to_markdown` runs W0g over already-normalized
    markdown, so its call is effectively a second pass and the fabrication lands in the
    `.md` every consumer reads -- on the first render, with no re-normalization."""
    md = render_pdf_to_markdown(_pdf_bytes())
    if isinstance(md, tuple):
        md = md[0]
    assert md and len(md) > 20000, f"render returned {len(md or '')} chars -- vacuous"

    found = _NEGATIVE_P.findall(md)
    assert not found, (
        f"{_PAPER}: the rendered markdown publishes {len(found)} negative p-value(s) "
        f"{found[:4]} -- W0g re-signed a p-value using a correlation's confidence "
        f"interval. A probability cannot be negative; the paper printed `p = .0498`."
    )
    # The record must still be PRESENT and as printed -- an absence assertion alone
    # would also pass if the sentence had been deleted outright.
    assert "p = .0498" in md, (
        f"{_PAPER}: `p = .0498` is not in the rendered markdown as the paper printed it"
    )


def test_w0g_does_not_fabricate_a_negative_p_value_on_re_normalization():
    """The same defect through the text channel. A consumer that normalizes stored text
    a second time -- which the idempotency contract says must be a no-op -- gets it too."""
    raw, _ = extract_pdf(_pdf_bytes())
    assert raw and len(raw) > 50000, f"extraction returned {len(raw or '')} chars -- vacuous"
    assert not _NEGATIVE_P.search(raw), (
        "the RAW text already carries a negative p-value -- this test's premise is that "
        "docpluck introduces it, so a positive here means the paper or pdftotext did"
    )

    once, _r1 = normalize_text(raw, NormalizationLevel.academic)
    twice, _r2 = normalize_text(once, NormalizationLevel.academic)

    for label, text in (("pass 1", once), ("pass 2", twice)):
        found = _NEGATIVE_P.findall(text)
        assert not found, (
            f"{_PAPER}, {label}: normalization published {len(found)} negative "
            f"p-value(s) {found[:4]} -- W0g paired a correlation's CI with a p-value."
        )
    assert once == twice, (
        f"{_PAPER}: normalization is not idempotent. W0g fires only on pass 2 here, "
        "because pass 1's S5 dash normalization is what makes its pattern match."
    )


def test_the_minus_recoveries_that_stay_are_still_wired():
    """THE CONTROL, and the reason this file cannot be satisfied by disarming the
    pipeline. Each input below is a shape a KEPT rule repairs, asserted through
    `normalize_text`.

    W0b and W0d are the load-bearing pair. CLAUDE.md twice records that they fire
    "0 times in 226 papers"; re-measured 2026-09-07 over the 101-paper corpus they fire
    on `efendic_2022_affect` and recover 62 real minus signs -- `r = 2.74 [20.92, 20.30]`
    back to `r = -.74 [-0.92, -0.30]`, an impossible correlation and a descending
    interval, repaired properly. They must survive W0g's removal.
    """
    checks = [
        # W0b + W0d: the '2'-for-U+2212 corruption class, gated on a DESCENDING
        # interval -- an arrangement no real interval can have.
        (
            "the correlation was r = 20.74, 95% CI [20.92, 20.30] in that sample",
            "r = -0.74, 95% CI [-0.92, -0.30]",
            "W0b/W0d",
        ),
        # W0q: a minus DETACHED from its digits by pdftotext, reattached. The
        # character is present on the page; nothing is being inferred.
        (
            "t(399) = -3.79, p < .001, d = -0.38, 95% CI [- 0.58,\n- 0.18]. Similarly",
            "95% CI [-0.58, -0.18]",
            "W0q",
        ),
        # S5: U+2212 MINUS SIGN to ASCII hyphen. Pure notation.
        ("d = −0.38, 95% CI [−0.58, −0.18]", "d = -0.38", "S5"),
    ]
    for src, expected, rule in checks:
        out, _rep = normalize_text(src, NormalizationLevel.academic)
        assert expected in out, (
            f"{rule} no longer fires -- W0g's removal took a rule with it. "
            f"in={src!r} out={out!r}"
        )
