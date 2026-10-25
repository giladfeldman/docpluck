"""compute_quality_score sees statistics the font broke.

10.5465/amj.2016.1196 draws `=` in a font whose character map says `5`: the text reads
`F(1, 350) 5 27.7`, `F(2, 350) 5 298...`, `t(231) 5 0.54` -- all three of its
statistics, in fluent English prose. Before 2.4.154 the score was lexical only and this
paper scored like a clean one.
"""
from __future__ import annotations

from docpluck import NormalizationLevel, compute_quality_score, extract_pdf, normalize_text
from docpluck.testing import require_corpus_pdf


def _quality(rel: str) -> dict:
    t = extract_pdf(require_corpus_pdf(rel).read_bytes())
    t = t[0] if isinstance(t, tuple) else t
    return compute_quality_score(normalize_text(t, NormalizationLevel.academic)[0])


def test_operator_lost_paper_is_flagged():
    q = _quality("aom/amj_1.pdf")
    d = q["details"]
    assert d["statistics_without_operator"] >= 3 and d["statistics_damaged"], d
    assert q["confidence"] != "high", q


def test_clean_paper_is_not_flagged():
    q = _quality("apa/ip_feldman_2025_pspb.pdf")
    d = q["details"]
    assert d["statistics_with_operator"] >= 20 and not d["statistics_damaged"], d
    assert q["confidence"] == "high", q


def test_unit_signals():
    prose = "The study found that participants in the treatment condition reported more. " * 30
    base = compute_quality_score(prose)
    assert base["details"]["residual_control_chars"] == 0 and base["score"] == 100
    hit = compute_quality_score(prose + " F(1, 350) 5 27.7 and t(231) 5 0.54.")
    assert hit["details"]["statistics_damaged"] and hit["score"] <= 70, hit
    ok = compute_quality_score(prose + " F(1, 350) = 27.7 and t(231) = 0.54.")
    assert not ok["details"]["statistics_damaged"] and ok["score"] == 100, ok
    ctl = compute_quality_score(prose + "f emales\x01males")
    assert ctl["details"]["residual_control_chars"] == 1 and ctl["details"]["has_corruption_signal"]
