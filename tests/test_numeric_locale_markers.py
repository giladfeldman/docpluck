"""The locale MARKER VOCABULARY survives; the document-level VERDICT does not.

v2.4.129 deleted `NumericLocale`, `infer_numeric_locale()`,
`LOCALE_MIN_GATING_CONFIDENCE`, `is_gating` and `NormalizationReport.numeric_locale`
(user directive 2026-08-14: docpluck assumes **English papers in US numeric
convention** and passes European numbers through unconverted).

The marker tables in `normalize.py` were kept, and this file is the reason that is
a decision rather than dead code. **Retaining an unwired table is only defensible
if the table is tested**, so every exclusion below is pinned. Each one was paid for
by a real corpus regression, and an independent reviewer writing a fresh detector
on 2026-08-14 immediately reproduced one of them (the RGB-triple false positive),
which is the concrete argument against "just rebuild it later".

**These markers must never again drive a document-level verdict.** The instrument
was blind exactly where European decimals live: every European marker is
OPERATOR-GATED, and a flattened table cell has no operator, so
`10.1177/0956797620935584` — ~130 comma-decimal cells in an English paper — scored
`european_markers=0` and was certified `decisive_us` with confidence 1.0. Anything
built on this vocabulary is LINE- or TABLE-scoped.
"""

from __future__ import annotations

import re

import pytest

from docpluck.normalize import (
    _LOCALE_EUROPEAN_MARKERS,
    _LOCALE_GROUP_SEP,
    _LOCALE_OP,
    _LOCALE_US_MARKERS,
)


def _hits(markers: dict[str, str], text: str) -> dict[str, int]:
    return {k: len(re.findall(v, text)) for k, v in markers.items()
            if re.findall(v, text)}


def test_the_verdict_api_is_gone():
    """The output surface must not come back. If this fails, someone
    reintroduced a document-level locale verdict — read the comment above the
    marker tables in normalize.py before doing that."""
    import docpluck
    import docpluck.normalize as n

    for name in ("NumericLocale", "infer_numeric_locale",
                 "LOCALE_MIN_GATING_CONFIDENCE"):
        assert not hasattr(n, name), f"normalize.{name} is back"
        assert not hasattr(docpluck, name), f"docpluck.{name} is back"


def test_markers_still_recognise_their_own_shapes():
    """The vocabulary works — otherwise keeping it is pure cost."""
    assert _hits(_LOCALE_EUROPEAN_MARKERS, "p = ,001 and d = 0,45")
    assert _hits(_LOCALE_US_MARKERS, "p = .001 and d = 0.45")


# ── the exclusions, each paid for by a real regression ──────────────────


def test_plain_space_is_NOT_a_group_separator():
    """`403,669 107,081` is two English table counts, not one European number.

    Admitting a plain space to the group-separator class read them as a single
    European value and flipped a whole document's verdict. The class admits `.`,
    U+00A0, U+202F and `'` only — spelled with explicit escapes in the source so
    a copy-paste can never lose the distinction again.

    A 2026-08-13 review reported this class as admitting a plain space; checked
    against the source it does not, and the finding was REFUTED — it was the
    review DOCUMENT that had transcribed the no-break spaces as ordinary ones.
    """
    assert " " not in _LOCALE_GROUP_SEP.strip("[]")
    assert not re.findall(_LOCALE_EUROPEAN_MARKERS["F1_full_notation"],
                          "403,669 107,081")


def test_european_markers_are_operator_gated_and_this_is_their_LIMIT():
    """The gate is real, and it is also the reason the verdict was deleted.

    An operator makes a marker trustworthy — and makes it blind to every bare
    table cell, which is where European decimals actually occur.
    """
    assert _LOCALE_OP.startswith("[=<>")
    # With an operator: seen.
    assert _hits(_LOCALE_EUROPEAN_MARKERS, "d = 0,45")
    # The same value as a bare table cell: invisible. This is not a bug to fix
    # here — it is the documented limit that a LOCAL-WINDOW guard must solve.
    assert not _hits(_LOCALE_EUROPEAN_MARKERS,
                     "Contrast\testimate\t-0,697\t0,355\t185,178")


@pytest.mark.parametrize(
    "text,why",
    [
        ("purple (128,0,128), orange (255,165,0)", "RGB stimulus triples"),
        ("input shape (70,64472) after flattening", "an ML tensor shape"),
        ("Median (Q1,Q3) was 148 (52,272)", "a bracketed interquartile pair"),
    ],
)
def test_bracketed_numeric_runs_do_not_vote_european(text, why):
    """A bracket-delimited numeric run is a tuple, never a decimal.

    The RGB case is the one an independent reviewer's fresh detector
    reproduced on 2026-08-14 — direct evidence that rebuilding this vocabulary
    from scratch means rediscovering the same false positives.
    """
    eu = _hits(_LOCALE_EUROPEAN_MARKERS, text)
    assert not eu, f"{why} voted European: {eu}"
