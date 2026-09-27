"""Regression test for the CI-UPPER-BOUND DETACHED-minus reattachment (B7 / GLYPH)
— and for the RETIREMENT of its inferential arm (2.4.146, d-a4ceab / DP-17).

Primary source, rasterized and read 2026-09-27 (``pdftoppm -png -r 300 -f 13
-l 13``), ``10.1080/02699931.2024.2434156`` (Chan & Feldman 2025) p13, Table 9,
Replication arm:

    2bi   r = -.73   [−0.78, − 0.67]   <- the page PRINTS a detached minus
    2bii  r = -.43   [−0.52, 0.33]     <- the page prints NO minus (authors' typo)

Table 8 on the same page prints the 2bii correlation correctly as
``−.43*** [−.52, −.33]``, which settles 2bii as the paper's own error.

* 2bi is a TYPOGRAPHIC repair: the dash is on the page, detached from its digit,
  and the comma already occupies the separator role, so it can only be the
  bound's sign. It is reattached and recorded.
* 2bii must PASS THROUGH as printed. Until 2.4.146 an estimate-containment rule
  (``recover_dropped_minus_ci_upper``) flipped it to ``−0.33`` because the
  estimate "fitted" the flipped interval better — an INFERENTIAL rewrite that
  fabricated a number the paper never printed and silently corrected the paper.
  Flagging that interval is ESCImate's / Scimeto's job, not docpluck's.

Earlier versions of this file (and of the rule's own comment) asserted that 2bii
"publishes −0.33"; that was a misreading of the page and is retracted here.
"""

from __future__ import annotations

import os

import pytest

from docpluck.extract_structured import extract_pdf_structured
from docpluck.normalize import recover_dropped_minus_ci_upper_in_text
from docpluck.tables.cell_cleaning import (
    _recover_ci_upper_in_grid_row,
    cells_grid_to_html,
)
from docpluck.normalize import recover_dropped_minus_ci_upper
from docpluck.tables.flatten import flatten_table

from docpluck.testing import require_corpus_pdf



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


def test_text_helper_passes_through_upper_bound_with_no_dash():
    # 2bii as printed: no dash before 0.33. Nothing on the page supports a
    # minus, so the text must come back byte-identical.
    s = "r = -.43[−0.52,  0.33]Signal"
    assert recover_dropped_minus_ci_upper_in_text(s) == s


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


def test_grid_row_helper_passes_through_upper_bound_with_no_dash():
    # 2bii as printed, separate-cell shape: no dash, so no rewrite.
    row = ["2bii", "/", "/", "/", "<.001", "r = -.43", "[−0.52,  0.33]", "Signal"]
    assert _recover_ci_upper_in_grid_row(row) == row


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
    assert "[−0.78, −0.67]" in html, html        # printed dash reattached
    assert "−0.33]" not in html, html             # no fabricated minus (DP-17)
    assert "0.33]" in html, html                  # 2bii passes through as printed
    assert "[0.34, 0.54]" in html, html          # positive CI untouched
    assert ",  0.67]" not in html


# ── Real-PDF regression test (rule 0d) ───────────────────────────────────────


@pytest.mark.skipif(
    os.environ.get("DOCPLUCK_DISABLE_CAMELOT", "0") == "1",
    reason="The hypothesis grid requires Camelot; disabled via "
    "DOCPLUCK_DISABLE_CAMELOT=1.",
)
def test_chan_feldman_hypothesis_table_ci_upper_signs_recovered():
    """2bi's printed detached minus is reattached; 2bii's upper bound passes through.

    RE-TARGETED 2026-08-04 (RC-T cycle 4). This test previously read the rows out of
    ``Table 8`` — which was wrong, and passed only because the caption→table pairing
    was itself wrong. The AI gold (article-finder ``reading`` view, the only ground
    truth per the project rule — never pdftotext) is unambiguous:

        Table 8. Control condition (Replication): Intercorrelations with confidence
                 intervals.          <- an M / SD / alpha / omega variable matrix
        Table 9. Summary of statistical tests and their interpretation.
                 | Hypothesis | ... |  <- 1a, 1b, 2a, 2bi, 2bii live HERE

    Cycle 4's own-caption exemption FIXED that pairing, so the hypothesis rows now
    resolve to Table 9 and this test follows the gold rather than the old defect.
    The recovered values are unchanged and still gold-exact: 2bi target
    ``[−0.78, −0.66]``, 2bi replication ``[−0.78, −0.67]``.

    Selection is by CONTENT (the table carrying the hypothesis rows), not by a
    hard-coded label, so a future pairing change surfaces as a real failure here
    instead of silently re-passing against whichever table happens to be labelled 8.
    """
    pdf = require_corpus_pdf("apa/chan_feldman_2025_cogemo.pdf")

    result = extract_pdf_structured(pdf.read_bytes())
    hypothesis_table = None
    for t in result["tables"]:
        if not (t.get("cells") or []):
            continue
        joined = " ".join((c.get("text") or "") for c in t["cells"])
        if "Hypothesis" in joined and "2bi" in joined:
            hypothesis_table = t
            break
    if hypothesis_table is None:
        pytest.skip("hypothesis grid has no Camelot cells in this environment")

    rows = flatten_table(hypothesis_table)
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

    # 2bii Replication: the page prints +0.33 (authors' typo). Pass through;
    # until 2.4.146 this was flipped to -0.33 (DP-17).
    rep_2bii = by_key.get("2bii (Replication)")
    assert rep_2bii is not None, "2bii (Replication) row not flattened"
    f = rep_2bii["fields"]
    assert f["CI_lower"] == pytest.approx(-0.52), f
    assert f["CI_upper"] == pytest.approx(0.33), f

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


def test_chan_feldman_rendered_markdown_prints_2bii_as_the_page_does():
    """End to end through the production renderer: the `<table>` channel and the
    text channel must both show 2bii's upper bound exactly as printed."""
    from docpluck.render import render_pdf_to_markdown

    pdf = require_corpus_pdf("apa/chan_feldman_2025_cogemo.pdf")
    md = render_pdf_to_markdown(pdf.read_bytes())
    # Scope to Table 9's rows: the abstract and prose legitimately print the
    # correct [-0.52, -0.33], so a whole-document search cannot tell them apart.
    rows = {}
    for tr in md.split("<tr>")[1:]:
        cells = [c.split("</td>")[0].strip() for c in tr.split("<td>")[1:]]
        if cells and cells[0] in ("2bi", "2bii"):
            rows[cells[0]] = cells
    assert "2bii" in rows and "2bi" in rows, "Table 9 hypothesis rows not rendered"
    ci_2bii = rows["2bii"][-2].replace(" ", "")
    ci_2bi = rows["2bi"][-2].replace(" ", "")
    assert ci_2bii == "[−0.52,0.33]", (
        f"2bii must pass through as printed; got {rows['2bii'][-2]!r} (DP-17)"
    )
    # The printed detached dash on 2bi is still reattached (typographic).
    assert ci_2bi == "[−0.78,−0.67]", rows["2bi"]


def test_inferential_ci_upper_rule_has_no_production_call_site():
    """`recover_dropped_minus_ci_upper` is kept as evidence but must stay unwired."""
    import pathlib
    import re as _re

    import docpluck

    root = pathlib.Path(docpluck.__file__).parent
    callers = []
    for py in root.rglob("*.py"):
        for i, line in enumerate(py.read_text(encoding="utf-8").splitlines(), 1):
            code = line.split("#", 1)[0]
            if _re.search(r"\brecover_dropped_minus_ci_upper\s*\(", code) and "def " not in code:
                callers.append(f"{py.relative_to(root)}:{i}")
    assert callers == [], f"inferential CI-upper rule re-wired at: {callers}"
