"""W0h must not flip a token the layout never proved (Risk A / register C1, F7f).

## The defect, fixed v2.4.133

Every layout-gated repair proves *"N glyphs of shape X are corrupt"* in
**pdfplumber's** character stream, then rewrites **pdftotext's** text. Until
v2.4.133 the bridge was a bare count:

    counts = {".022": 1}                       # what the layout proved
    text = pattern.sub(replace_first_n, text)  # applied to the WHOLE document

The counts carried **no page key** and the substitution ran over the entire
document, so **a glyph proven on page 7 licensed flipping the first matching
`= .022` anywhere in the paper** — including on page 2, on a statistic that was
never corrupt. That fabricates a minus sign on a published number, and nothing
downstream can tell: the output is a plausible value, not a crash.

This is the same class as the v2.4.131 OMML regression (a repair that emits a
WRONG value rather than no value), living inside the rules the project treats
as safely typographic. The glyph evidence was always real; the ASSIGNMENT of
that evidence to a particular token was positional.

## Why page-scoping was not the fix

Measured on `10.1177/19485506211056761`: by the time W0h runs, the text carries
**7 form feeds for a 12-page document** — earlier normalization steps consume
them. Aligning text page *k* to layout page *k* is therefore an off-by-k that
produces a confidently WRONG pairing rather than an empty one, which no
emptiness check catches. The evidence's own line text needs no page alignment.

## The contract

* one candidate  -> apply (unchanged from before; the common case)
* many candidates, context separates them -> apply to the corroborated one
* many candidates, context does NOT separate them -> **REFUSE**, and record it

Refusing leaves the paper's own token intact, which a consumer can still
challenge. Guessing invents a number that looks published.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from docpluck import normalize as N

TEST_PDFS = Path(__file__).resolve().parents[1].parent / "PDFextractor" / "test-pdfs"
# The W0h source paper: three coefficients whose dropped U+2212 survives in the
# layout channel as an unmapped `(cid:N)` glyph.
W0H_PDF = TEST_PDFS / "apa" / "ar_apa_j_jesp_2009_12_011.pdf"

pytestmark = pytest.mark.skipif(
    not W0H_PDF.is_file(), reason=f"fixture not available: {W0H_PDF}"
)


@pytest.fixture(scope="module")
def evidence():
    from docpluck.extract import extract_pdf
    from docpluck.extract_layout import extract_pdf_layout

    data = W0H_PDF.read_bytes()
    text, _engine = extract_pdf(data)
    layout = extract_pdf_layout(data)
    sites = N._layout_negative_coefficient_sites(layout)
    return text, layout, sites


def test_the_known_positive_actually_fires(evidence):
    """A ZERO IS A CLAIM ABOUT THE INSTRUMENT UNTIL PROVEN OTHERWISE. Every
    other test here is meaningless if the detector finds nothing."""
    _text, _layout, sites = evidence
    assert len(sites) >= 3, f"W0h found no evidence on its own source paper: {sites}"
    assert {s["num"] for s in sites} >= {".022", ".88", ".428"}


def test_each_site_carries_its_own_location_and_line(evidence):
    """A count cannot say WHICH token it licenses. These fields are what make
    the pairing identity-based."""
    _text, _layout, sites = evidence
    for s in sites:
        assert isinstance(s["page"], int)
        assert s["line"], "no layout line captured — the anchor is missing"
        assert s["num"] in s["line"].replace(" ", "")


def test_the_layout_line_is_readable_not_glued(evidence):
    """pdfplumber's char stream contains no space characters, so a naive join
    yields 'Thedatawasanalyzedusinga4' and every word token fails to match
    pdftotext's spaced text — silently disabling the anchor."""
    _text, _layout, sites = evidence
    assert any(" " in s["line"] for s in sites)


def test_a_decoy_elsewhere_in_the_document_is_not_flipped(evidence):
    """THE REGRESSION. A second `= .428` that the layout never proved must not
    absorb the evidence just because it appears earlier in the document."""
    text, layout, _sites = evidence
    decoy = "\n\nUnrelated aside: the calibration constant q = .428, reported elsewhere.\n"
    out = N.recover_dropped_minus_via_layout(decoy + text, layout)
    assert "q = .428" in out, "the decoy was flipped — evidence assigned positionally"
    assert "q = -.428" not in out
    # ...and the genuine one still IS repaired.
    assert "b = -.428" in out


def test_two_indistinguishable_candidates_are_refused_not_guessed(evidence):
    """When the context cannot separate the candidates, docpluck passes through
    and records the refusal. A repair it cannot justify is a repair it must not
    make — pass-through is reversible for the consumer, a rewrite is not."""
    text, _layout, sites = evidence
    site = next(s for s in sites if s["num"] == ".428")
    twin = text + "\n\nb = .428, t(44) = 3.14, p < .01. Working hard on a task that\n"
    pat = re.compile(r"(?<=[\w\s])(=\s{0,3})" + re.escape(".428") + r"(?![\d.])")
    candidates = list(pat.finditer(twin))
    assert len(candidates) > 1, "fixture did not create an ambiguity"
    assert N._best_context_match(candidates, twin, site["line"], ".428") is None


def test_a_refusal_is_recorded_not_silent(evidence):
    """An unrecorded refusal is indistinguishable from 'nothing to repair'."""
    from docpluck.telemetry import get_fallback_counters, reset_fallback_counters

    text, layout, sites = evidence
    site = next(s for s in sites if s["num"] == ".428")
    # Two textual twins with identical surroundings — genuinely undecidable.
    ambiguous = text + "\n\n" + text[
        max(0, text.find("b = .428") - 60): text.find("b = .428") + 40
    ]
    assert site  # anchor exists
    reset_fallback_counters()
    N.recover_dropped_minus_via_layout(ambiguous, layout)
    counters = get_fallback_counters()
    assert any(k.startswith("w0h_") for k in counters), (
        f"a pairing decision was made with no telemetry at all: {counters}"
    )


def test_unambiguous_documents_are_unchanged_by_the_new_pairing(evidence):
    """Behaviour preservation: on the source paper every site has exactly one
    textual candidate, so the identity check must not alter the outcome."""
    text, layout, sites = evidence
    out = N.recover_dropped_minus_via_layout(text, layout)
    for s in sites:
        assert f"= -{s['num']}" in out, f"{s['num']} was not repaired"


# ── W0m: the same defect, and it was the worse of the two ──────────────────
#
# W0h at least matched on the coefficient string. W0m counted β glyphs and then
# flipped the first N `b = <anything>` occurrences, WITHOUT requiring the
# coefficient to match — so a β proven on one page could promote a genuine
# unstandardized `b` on another. `b` is a real, distinct statistic; that is the
# entire reason the rule is layout-gated rather than a text rewrite.


def test_beta_sites_carry_the_coefficient_they_govern(evidence):
    _text, layout, _sites = evidence
    sites = N._layout_beta_coefficient_sites(layout)
    assert len(sites) >= 5, f"known positive did not fire: {sites}"
    coefs = {s["coef"] for s in sites}
    assert "" not in coefs, (
        "a site read no coefficient — the layout's leading sign is often the "
        "(cid:N) unmapped minus, which must be skipped, not treated as a stop"
    )
    assert coefs >= {".022", ".48", ".88", ".245", ".428"}


def test_beta_evidence_is_not_spent_on_an_unrelated_b_coefficient(evidence):
    """THE W0m REGRESSION. An unstandardized `b` the layout never proved must
    keep its own identity — relabelling it β silently reports one statistic as
    another."""
    text, layout, _sites = evidence
    decoy = "\n\nFor comparison the raw slope was b = 9.99, t(12) = 1.1, n.s.\n"
    out = N.recover_beta_via_layout(decoy + text, layout)
    assert "b = 9.99" in out, "a genuine unstandardized b was relabelled as beta"
    assert "β = 9.99" not in out


def test_beta_still_recovers_every_proven_site(evidence):
    text, layout, _sites = evidence
    out = N.recover_beta_via_layout(text, layout)
    assert out.count("β") >= 5, f"only {out.count(chr(946))} betas recovered"
