"""Regression test for the CI-UPPER-BOUND dropped-minus recovery (B7 / GLYPH).

The W0g (``recover_dropped_minus_via_ci_pairing``) and W0h
(``recover_dropped_minus_via_layout``) recoveries in ``normalize.py`` repair a
*coefficient* token proven negative by its confidence-interval bracket — but
they TRUST the bracket. A minus dropped from the bracket's OWN upper bound is
therefore invisible to them.

On tight-kerned PDFs that draw the U+2212 minus in a dedicated symbol font,
pdftotext / Camelot can drop (or detach into a stray en-dash) the leading minus
of a CI's UPPER bound while keeping the lower bound's minus. A genuinely
negative interval ``[-0.78, -0.66]`` is then extracted as ``[-0.78, 0.67]`` — a
sign flip that inverts the interval. Confirmed on Table 8 of
``chan_feldman_2025_cogemo`` (Cognition & Emotion 2025), the Replication column:

    gold (AI-multimodal `reading` view)   →   flatten_table@HEAD (pre-fix)
    2bi  r = -0.73, 95% CI [-0.78, -0.66]  →  95% CI [-0.78, 0.67]  (detached en-dash)
    2bii r = -0.43, 95% CI [-0.52, -0.33]  →  95% CI [-0.52, 0.33]  (minus fully dropped)

The sibling Target-article row 2bi (``[-0.78, -0.66]``) extracts correctly —
both bounds keep their U+2212 — and must STAY correct (no over-flip).

``flatten_table`` parses the CI cell lexically (comma / en-dash branch) before
any sign invariant is applied, so the positive upper bound survives. The fix
(``recover_dropped_minus_ci_upper``) applies the estimate-containment invariant
docpluck already uses for hyphen-glued CIs (``_resolve_hyphen_ci``): when the
row's point estimate is negative and the parsed CI straddles zero
(``lo < 0 < hi``), and negating the upper bound yields an interval that is
monotonic, contains the estimate, AND centres it far better than the as-parsed
interval, the positive upper bound is the dropped-minus victim and is flipped.

Ground truth for the expected CIs is the AI-multimodal `reading` gold in the
shared article repository, per CLAUDE.md's ground-truth hard rule — NEVER
pdftotext (which is the source of the corruption this test exists to fix).

Keyed on the numeric STRUCTURAL SIGNATURE, never on paper/font identity. A
LEGITIMATE zero-straddling null CI (``d = -0.02, 95% CI [-0.19, 0.15]`` — a real
result in this same paper) is self-guarded: its estimate sits too near zero, so
negating the positive bound would EXCLUDE the estimate and the flip is refused.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from docpluck.extract_structured import extract_pdf_structured
from docpluck.normalize import recover_dropped_minus_ci_upper_in_text
from docpluck.tables.cell_cleaning import (
    _recover_ci_upper_in_grid_row,
    cells_grid_to_html,
)
from docpluck.tables.flatten import flatten_table, recover_dropped_minus_ci_upper

TEST_PDFS = Path(__file__).resolve().parents[1].parent / "PDFextractor" / "test-pdfs"


# ── Unit tests on recover_dropped_minus_ci_upper (synthetic, no Camelot) ─────


def test_flips_clear_dropped_minus_on_upper_bound():
    # est=-0.73, parsed CI [-0.78, 0.67] → upper bound's minus was dropped.
    assert recover_dropped_minus_ci_upper(-0.73, -0.78, 0.67) == pytest.approx(-0.67)


def test_flips_second_real_row():
    assert recover_dropped_minus_ci_upper(-0.43, -0.52, 0.33) == pytest.approx(-0.33)


def test_flips_generic_clearly_negative_interval():
    assert recover_dropped_minus_ci_upper(-0.50, -0.60, 0.40) == pytest.approx(-0.40)


def test_does_not_flip_legitimate_null_ci():
    # Real null result in chan_feldman: d = -0.02, 95% CI [-0.19, 0.15]. The
    # estimate is near zero — negating 0.15 → -0.15 would EXCLUDE -0.02, so the
    # flip must be refused (a genuine zero-straddling interval).
    assert recover_dropped_minus_ci_upper(-0.02, -0.19, 0.15) is None
    assert recover_dropped_minus_ci_upper(-0.04, -0.21, 0.13) is None


def test_does_not_flip_wide_straddling_ci_centred_on_estimate():
    # A genuinely wide CI whose estimate sits near the middle is NOT a
    # dropped-minus victim.
    assert recover_dropped_minus_ci_upper(-0.10, -0.30, 0.25) is None
    assert recover_dropped_minus_ci_upper(-0.05, -0.40, 0.35) is None


def test_does_not_flip_positive_estimate():
    assert recover_dropped_minus_ci_upper(0.45, 0.34, 0.54) is None


def test_does_not_touch_already_correct_negative_interval():
    # hi already negative → no straddle → signature does not fire.
    assert recover_dropped_minus_ci_upper(-0.73, -0.78, -0.66) is None
    assert recover_dropped_minus_ci_upper(-0.50, -0.60, -0.40) is None


def test_boundary_estimate_is_conservative_no_flip():
    # est exactly at the flipped upper bound is ambiguous → leave it (the
    # strict off-centre inequality refuses a boundary case).
    assert recover_dropped_minus_ci_upper(-0.40, -0.50, 0.40) is None
    assert recover_dropped_minus_ci_upper(-0.25, -0.50, 0.25) is None


# ── Channel: same-cell estimate+CI (cell_cleaning._html_escape text helper) ──


def test_text_helper_flips_detached_endash_upper_bound():
    # The mashed-cell shape: estimate and CI in one cell with a detached en-dash.
    s = "-.73***\x00BR\x00[−0.78,  –  0.67] (−0.72)"
    out = recover_dropped_minus_ci_upper_in_text(s)
    assert "[−0.78, −0.67]" in out, out


def test_text_helper_flips_fully_dropped_upper_bound():
    s = "r = -.43[−0.52,  0.33]Signal"
    out = recover_dropped_minus_ci_upper_in_text(s)
    assert "[−0.52, −0.33]" in out, out


def test_text_helper_leaves_null_ci_and_positive_r():
    # Real null result (estimate near zero) and a positive correlation: untouched.
    assert recover_dropped_minus_ci_upper_in_text(
        "-.02\x00BR\x00[−0.19,  0.15]"
    ) == "-.02\x00BR\x00[−0.19,  0.15]"
    assert recover_dropped_minus_ci_upper_in_text(
        ".45***\x00BR\x00[.35,  .54]"
    ) == ".45***\x00BR\x00[.35,  .54]"


def test_text_helper_leaves_already_correct_attached_minus():
    s = "-.73***\x00BR\x00[−0.78,  −0.67] (−0.72)"
    assert recover_dropped_minus_ci_upper_in_text(s) == s


# ── Channel: separate estimate/CI cells (cells_grid_to_html row helper) ──────


def test_grid_row_helper_flips_separate_cell_ci():
    # Region-driven grid shape: estimate and CI in adjacent cells.
    row = ["2bi", "<.001", "r = -.73", "[−0.78, −0.66]",
           "<.001", "r = -.73", "[−0.78,  –  0.67]", "Signal"]
    out = _recover_ci_upper_in_grid_row(row)
    assert out[6] == "[−0.78, −0.67]", out
    assert out[3] == "[−0.78, −0.66]", out  # already-correct sibling untouched


def test_grid_row_helper_leaves_positive_and_null():
    row = ["2a", "<.001", "r = .45", "[0.34, 0.54]"]
    assert _recover_ci_upper_in_grid_row(row) == row
    null_row = ["6", "9.06", ".03", "[−.09,  .15]", "−.11", "[−.23,  .01]"]
    assert _recover_ci_upper_in_grid_row(null_row) == null_row


def test_cells_grid_to_html_recovers_separate_cell_ci_upper():
    # End-to-end through the HTML renderer: a correlation grid where the upper
    # bound's minus is dropped in a separate cell.
    grid = [
        ["Hypothesis", "p", "Effect size", "CI"],
        ["2bi", "<.001", "r = -.73", "[−0.78,  –  0.67]"],
        ["2bii", "<.001", "r = -.43", "[−0.52,  0.33]"],
        ["2a", "<.001", "r = .45", "[0.34, 0.54]"],
    ]
    html = cells_grid_to_html(grid)
    assert "[−0.78, −0.67]" in html, html
    assert "[−0.52, −0.33]" in html, html
    assert "[0.34, 0.54]" in html, html          # positive CI untouched
    assert ",  0.67]" not in html and ",  0.33]" not in html


# ── Real-PDF regression test (rule 0d) ───────────────────────────────────────


@pytest.mark.skipif(
    os.environ.get("DOCPLUCK_DISABLE_CAMELOT", "0") == "1",
    reason="Table 8's structured grid requires Camelot; disabled via "
    "DOCPLUCK_DISABLE_CAMELOT=1.",
)
def test_chan_feldman_table8_ci_upper_signs_recovered():
    pdf = TEST_PDFS / "apa" / "chan_feldman_2025_cogemo.pdf"
    if not pdf.exists():
        pytest.skip(f"fixture missing: {pdf}")

    result = extract_pdf_structured(pdf.read_bytes())
    t8 = next((t for t in result["tables"] if t.get("label") == "Table 8"), None)
    if t8 is None or not (t8.get("cells") or []):
        pytest.skip("Table 8 has no Camelot cells in this environment")

    rows = flatten_table(t8)
    # Index flattened rows by (row-label, arm) via the sentence prefix.
    by_key: dict[str, dict] = {}
    for fr in rows:
        s = fr.get("sentence") or ""
        for key in ("2bi (Replication)", "2bii (Replication)",
                    "2bi (Target article)"):
            if s.startswith(key):
                by_key[key] = fr

    # 2bi Replication: dropped-minus (detached en-dash) on the upper bound.
    rep_2bi = by_key.get("2bi (Replication)")
    assert rep_2bi is not None, "2bi (Replication) row not flattened"
    f = rep_2bi["fields"]
    assert f["CI_lower"] == pytest.approx(-0.78), f
    assert f["CI_upper"] == pytest.approx(-0.67), f  # was +0.67 pre-fix
    assert "0.67]" in rep_2bi["sentence"] and ", 0.67]" not in rep_2bi["sentence"], (
        "sentence still shows a positive upper bound: " + rep_2bi["sentence"]
    )

    # 2bii Replication: minus fully dropped on the upper bound.
    rep_2bii = by_key.get("2bii (Replication)")
    assert rep_2bii is not None, "2bii (Replication) row not flattened"
    f = rep_2bii["fields"]
    assert f["CI_lower"] == pytest.approx(-0.52), f
    assert f["CI_upper"] == pytest.approx(-0.33), f  # was +0.33 pre-fix

    # Sibling Target-article 2bi already extracts correctly — must STAY correct.
    tgt_2bi = by_key.get("2bi (Target article)")
    if tgt_2bi is not None:
        f = tgt_2bi["fields"]
        assert f["CI_lower"] == pytest.approx(-0.78), f
        assert f["CI_upper"] == pytest.approx(-0.66), f

    # No positive-correlation row (1a/1b/2a) may have had its upper bound flipped
    # negative — those CIs are genuinely positive.
    for fr in rows:
        s = fr.get("sentence") or ""
        if s.startswith(("1a", "1b", "2a")):
            up = (fr.get("fields") or {}).get("CI_upper")
            if up is not None:
                assert up > 0, f"positive-r row over-flipped to negative CI: {s}"
