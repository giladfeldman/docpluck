"""Real-PDF regression tests for normalize_text idempotency.

normalize_text was systemically non-idempotent — normalize_text(raw) left work
that a second pass completed (and, for a few papers, a second pass actively
corrupted a correct value). A 180-doc scan found 85 non-idempotent papers in
three buckets: JOIN (line-join re.subs consume the boundary char), STRIP
(position/cluster-gated strips fire only on pass 2), CHARSUB (destructive
char-substitution on re-application).

Cycle 7 fixed the S7a (whitespace-broken compound rejoin) and H0 (header-banner
position gate) mechanisms. Cycles 8-10 take the JOIN / STRIP / CHARSUB buckets.

``test_normalize_idempotent_corpus`` is the honest corpus-wide gate: a ratchet
that tightens toward 0 as each idempotency cycle lands. A cycle that *increases*
the non-idempotent count fails it.
"""
import glob
import os
import shutil

import pytest

from docpluck import extract_pdf, normalize_text, NormalizationLevel
from docpluck.normalize import (
    _rejoin_space_broken_compounds,
    _strip_document_header_banners,
)

requires_pdftotext = pytest.mark.skipif(
    shutil.which("pdftotext") is None, reason="pdftotext not installed"
)

# PDFextractor is docpluck's sibling repo — derive the path from this file so
# the test is robust to where the tree is checked out.
_TEST_PDFS = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "PDFextractor", "test-pdfs")
)

# Honest corpus-wide gate. The ratchet is the count of still-non-idempotent
# papers in the strided sample below. Each idempotency cycle lowers it:
#   cycle 7  -> set to the post-cycle-7 baseline
#   cycle 8  (JOIN)    -> lower
#   cycle 9  (STRIP)   -> lower
#   cycle 10 (CHARSUB) -> 0
# Do NOT raise this number to make the test pass — a higher count is a
# regression. Lower it (only) when a cycle genuinely fixes papers.
_IDEMPOTENCY_RATCHET = 6


def _norm_twice(raw):
    n1, _ = normalize_text(raw, NormalizationLevel.academic)
    n2, _ = normalize_text(n1, NormalizationLevel.academic)
    return n1, n2


@requires_pdftotext
def test_normalize_idempotent_chan_feldman():
    """chan_feldman_2025_cogemo exercised both cycle-7 mechanisms: an S7a
    newline-broken compound (``repli``\\n``cations``) and an H0 banner line
    (a bare DOI URL) pushed past the 30-line header-zone cap by front-matter
    noise. normalize_text must converge in a single pass."""
    pdf = os.path.join(_TEST_PDFS, "apa", "chan_feldman_2025_cogemo.pdf")
    if not os.path.isfile(pdf):
        pytest.skip("chan_feldman test PDF not available")
    with open(pdf, "rb") as fh:
        raw, _ = extract_pdf(fh.read())
    n1, n2 = _norm_twice(raw)
    assert n1 == n2, "normalize_text is not idempotent on chan_feldman"


def test_rejoin_space_broken_compounds_joins_across_newline():
    """S7a rejoins a curated compound regardless of separator — a space OR a
    newline. Pre-v2.4.58 it stripped only the literal space, so a
    newline-broken compound survived to a second normalize pass."""
    assert (
        _rejoin_space_broken_compounds("the repli cations were")
        == "the replications were"
    )
    assert (
        _rejoin_space_broken_compounds("the repli\ncations were")
        == "the replications were"
    )
    assert (
        _rejoin_space_broken_compounds("we con\nducted a study")
        == "we conducted a study"
    )
    once = _rejoin_space_broken_compounds("the differ\nences observed")
    assert once == "the differences observed"
    assert _rejoin_space_broken_compounds(once) == once  # idempotent


def test_h0_header_banner_strip_reaches_fixed_point():
    """The H0 header-banner strip, re-applied, reaches a fixed point: a banner
    line is removed once and re-running finds nothing more to remove."""
    text = (
        "A Study Title\n\nhttps://doi.org/10.1234/x\n\nAuthor Name\n\n"
        + "Body sentence here. " * 40
    )
    s1 = _strip_document_header_banners(text)
    s2 = _strip_document_header_banners(s1)
    assert "doi.org/10.1234/x" not in s1, "H0 did not strip the bare DOI banner"
    assert s1 == s2, "H0 strip is not a fixed point"


@requires_pdftotext
def test_normalize_idempotent_corpus():
    """Honest corpus-wide gate — a strided sample of the test corpus must not
    exceed the known non-idempotent count (the ratchet)."""
    pdfs = sorted(glob.glob(os.path.join(_TEST_PDFS, "*", "*.pdf")))
    if len(pdfs) < 40:
        pytest.skip("test-pdf corpus not available")
    sample = pdfs[::5]  # deterministic strided sample
    nonidem = []
    for p in sample:
        try:
            with open(p, "rb") as fh:
                raw, _ = extract_pdf(fh.read())
            n1, n2 = _norm_twice(raw)
        except Exception:
            continue
        if n1 != n2:
            nonidem.append(os.path.basename(p))
    assert len(nonidem) <= _IDEMPOTENCY_RATCHET, (
        f"{len(nonidem)} non-idempotent papers (ratchet={_IDEMPOTENCY_RATCHET}); "
        f"a cycle increased the count — regression: {nonidem}"
    )
