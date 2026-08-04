"""Regression test for W0n: p-threshold dropped decimal point (v2.4.118).

The run-3 Sonnet canary audit (2026-07-07) found ar_apa_j_jesp_2009_12_011
rendering `β = -.88, t(87) = 2.01, p < 05 (see Fig. 1)` — the threshold's
decimal point is gone. Diagnosis (2026-08-03): the '.' glyph is absent from
BOTH text channels (pdftotext emits nothing; the pdfplumber char stream reads
`p<05(see` while every healthy threshold on the same page carries an explicit
'.' char) — the same absent-glyph class as the painted-pixel `.245` minus, so
no layout gate is possible.

Fix (v2.4.118): `recover_p_threshold_dropped_decimal` — a pure text-shape
recovery. A dotless, leading-zero-free canonical threshold (05/01/001) after
`<`/`>`/`≤`/`≥` is never legitimate notation. Four guards: never `=`
(zero-padded IDs / exact p-values); canonical threshold set only (`005` is
ambiguous between corrupted `0.05` and corrupted `.005`); no longer-number
continuation; significance-clause context (comma-after-stat / paren / legend
marker / line start) so a prose subject ("the probability p < 0.5" losing its
dot) never fires. Wired into channel 1 (normalize_text) AND channel 3 (render
post-process).

Fails-at-HEAD evidence: the v2.4.117 render of the fixture (run-4 cycle-1
artifact) contains `p < 05 (see` — the first assertion below is red at HEAD.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("DOCPLUCK_DISABLE_CAMELOT", "1")

from docpluck.render import render_pdf_to_markdown

TEST_PDFS = Path(__file__).resolve().parents[1].parent / "PDFextractor" / "test-pdfs"


def test_ar_apa_p_threshold_decimal_recovered_real_pdf():
    """ar_apa's corrupt `p < 05` renders as `p < .05`; the paper's healthy
    thresholds are untouched."""
    pdf = TEST_PDFS / "apa" / "ar_apa_j_jesp_2009_12_011.pdf"
    if not pdf.exists():
        pytest.skip(f"fixture missing: {pdf}")
    md = render_pdf_to_markdown(pdf.read_bytes())
    assert "p < .05 (see" in md
    assert "p < 05" not in md
    # Healthy thresholds elsewhere in the paper stay byte-identical.
    assert "p < .001" in md
    assert "p < .068" in md  # non-canonical exact threshold, never touched
    assert "p < .025" in md


def test_p_threshold_recovery_shapes():
    """Canonical dotless shapes recover across operators and case."""
    from docpluck.normalize import recover_p_threshold_dropped_decimal as rec

    assert rec("t(87) = 2.01, p < 05 (see") == "t(87) = 2.01, p < .05 (see"
    assert rec("F(1, 88) = 7.49, p < 01.") == "F(1, 88) = 7.49, p < .01."
    assert rec("F(1, 88) = 13.14, p < 001. Consistent") == (
        "F(1, 88) = 13.14, p < .001. Consistent"
    )
    assert rec("(p > 05)") == "(p > .05)"
    assert rec("(p ≤ 05)") == "(p ≤ .05)"
    # Uppercase P (JAMA style) with a trailing-stat clause.
    assert rec("z = 2.1, P < 05,") == "z = 2.1, P < .05,"
    # Significance legend: line start and asterisk marker.
    assert rec("* p < 05. ** p < 01.") == "* p < .05. ** p < .01."
    assert rec("note\np < 05 level") == "note\np < .05 level"


def test_p_threshold_recovery_is_idempotent():
    from docpluck.normalize import recover_p_threshold_dropped_decimal as rec

    s = "t(87) = 2.01, p < 05 (see Fig. 1), * p < 05."
    once = rec(s)
    assert rec(once) == once


def test_p_threshold_guards_never_fire_on_legitimate_text():
    """The four guards: healthy dots, `=` operator, non-canonical digits,
    longer numbers, leading-zero variants, and prose subjects are untouched."""
    from docpluck.normalize import recover_p_threshold_dropped_decimal as rec

    for s in (
        # Healthy thresholds — dot present.
        "F(3, 90) = 6.62, p < .05. Again",
        "significant, p < 0.05, two-tailed",
        # `=` operator: exact p-values / zero-padded IDs are not provably corrupt.
        "participant p = 05 was excluded",
        "p = 01 in the log",
        # Non-canonical digit runs.
        "p < 10 in the marginal test",
        "n < 05 impossible but not a p",  # not a p before the operator
        "p < 052 items",
        # Decimal continuation — the digits belong to a longer number.
        "p < 05.3 units",
        # Leading-zero variants are ambiguous (0.05 vs .005) — left alone.
        "reported p < 005 threshold",
        "strict p < 0001 criterion",
        # Prose subject — no significance-clause context.
        "the probability p < 05 in our model",
        "whenever p < 05 we reject",
    ):
        assert rec(s) == s, s
