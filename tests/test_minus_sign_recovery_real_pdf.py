"""Regression test for the '2'-for-U+2212 minus-sign corruption (cycle 6, v2.4.38).

The APA Phase-5d sweep found efendic_2022_affect rendered every negative
statistic with the U+2212 minus sign turned into the digit '2': the abstract
read `r = 2.74 [20.92, 20.30]` for `r = −.74 [−0.92, −0.30]`, and every CI in
the body and tables was likewise sign-corrupted (29 confidence intervals).
Diagnosis: a font quirk makes pdftotext map U+2212 to '2'.

Fix (v2.4.38): `normalize.py::recover_corrupted_minus_signs` (W0b step, also
applied to table cells via `cell_cleaning._html_escape`). Two self-gating,
context-safe rules:
  - descending CI bracket `[A, B]` (A > B is impossible) recovered when the
    leading '2' of a decimal bound reads as '−' and the interval becomes
    ascending;
  - `r = 2.<digits>` — a Pearson r cannot exceed 1.
An ascending CI / a plausible correlation is never touched.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

os.environ.setdefault("DOCPLUCK_DISABLE_CAMELOT", "1")

from docpluck.normalize import (
    recover_corrupted_minus_signs,
    recover_dropped_minus_via_ci_pairing,
    recover_minus_via_ci_pairing,
)
from docpluck.render import render_pdf_to_markdown

TEST_PDFS = Path(__file__).resolve().parents[1].parent / "PDFextractor" / "test-pdfs"

# A corrupt `2`-for-minus CI is one whose literal bounds DESCEND — impossible
# for a real interval, so the leading `2`s are mis-mapped minus signs
# (`[20.92, 20.30]` = `[-0.92, -0.30]`). The bare shape `[2X.XX, 2X.XX]` is NOT
# sufficient: `[2.42, 2.69]` ascends and the AI gold confirms efendic Table 5's
# is a GENUINELY POSITIVE interval (Direction high-vs-low, estimate 2.56).
# Matching it here asserted a wrong published number into existence — the
# reason the "column-consensus" recovery was rejected (2026-08-04). Only
# per-record evidence (descending bounds, or W0d containment) proves a flip.
_CORRUPT_CI_PAIR_RE = re.compile(r"\[(2\d?\.\d+), ?(2\d?\.\d+)\]")


def _corrupt_descending_cis(md: str) -> list[str]:
    """Every `[2X.XX, 2X.XX]` CI in ``md`` whose literal bounds DESCEND."""
    return [
        m.group(0)
        for m in _CORRUPT_CI_PAIR_RE.finditer(md)
        if float(m.group(1)) > float(m.group(2))
    ]


# ── Unit tests on recover_corrupted_minus_signs ─────────────────────────

def test_recovers_descending_ci_both_bounds():
    assert recover_corrupted_minus_signs("[20.92, 20.30]") == "[-0.92, -0.30]"


def test_recovers_descending_ci_one_bound():
    # Lower bound corrupt, upper bound genuinely positive.
    assert recover_corrupted_minus_signs("[20.08, 0.35]") == "[-0.08, 0.35]"


def test_recovers_descending_ci_above_one():
    assert recover_corrupted_minus_signs("[21.27, 21.03]") == "[-1.27, -1.03]"


def test_ascending_ci_untouched():
    # A genuine ascending interval — must NOT be converted.
    assert recover_corrupted_minus_signs("[2.42, 2.69]") == "[2.42, 2.69]"
    assert recover_corrupted_minus_signs("[0.22, 0.75]") == "[0.22, 0.75]"


def test_already_negative_ci_untouched():
    assert recover_corrupted_minus_signs("[-0.92, -0.30]") == "[-0.92, -0.30]"


def test_integer_bracket_untouched():
    # Citation list or integer pair — no decimal bound, never converted.
    assert recover_corrupted_minus_signs("[25, 3]") == "[25, 3]"


def test_recovers_implausible_correlation():
    assert recover_corrupted_minus_signs("r = 2.74") == "r = -.74"
    assert recover_corrupted_minus_signs("r(10) = 2.87") == "r(10) = -.87"


def test_plausible_correlation_untouched():
    assert recover_corrupted_minus_signs("r = 0.74") == "r = 0.74"


# ── Unit tests on recover_minus_via_ci_pairing (cycle 8, v2.4.40) ───────
# A standalone '2X.XX' point estimate (no bracket of its own) is recovered
# only when the SAME record carries a CI it must lie inside — a structural
# invariant of statistics. A genuine literal 2X.XX is never touched.

def test_ci_pairing_recovers_table_row_estimate():
    row = "<tr><td>Intercept</td><td>20.26</td><td>0.10</td><td>[-0.45, -0.06]</td></tr>"
    assert "<td>-0.26</td>" in recover_minus_via_ci_pairing(row)


def test_ci_pairing_recovers_above_one():
    row = "<tr><td>PMA</td><td>21.15</td><td>0.06</td><td>[-1.27, -1.03]</td></tr>"
    assert "<td>-1.15</td>" in recover_minus_via_ci_pairing(row)


def test_ci_pairing_recovers_multiline_html_row_across_se_cell():
    """Camelot emits each <td> on its own line, so the SE cell sits between the
    B-column estimate and the CI cell — pushing the char-gap past the 30-char
    bare-bracket cap and defeating W0d in the Camelot HTML-table channel (the
    production default), even though the no-Camelot unstructured-table channel
    recovered it. In an HTML table row the columns are structurally paired, so
    the estimate MUST recover regardless of the intervening SE cell. This is the
    exact efendic Table 2 Intercept row rendered with Camelot ON."""
    row = (
        "<tr>\n"
        "      <td>Intercept</td>\n"
        "      <td>20.09</td>\n"
        "      <td>-0.06</td>\n"
        "      <td>[-0.21, 0.04]</td>\n"
        "      <td>.185</td>\n"
        "    </tr>"
    )
    out = recover_minus_via_ci_pairing(row)
    assert "<td>-0.09</td>" in out, out
    assert "20.09" not in out


def test_ci_pairing_multiline_html_row_leaves_genuine_positive():
    """The genuine Direction row (2.56 ∈ [2.42, 2.69]) must be left alone even
    with the relaxed HTML-row gap — the containment invariant still guards it
    (recovered -0.56 ∉ [2.42, 2.69], literal 2.56 ∈)."""
    row = (
        "<tr>\n"
        "      <td>Direction (high vs.low)</td>\n"
        "      <td>2.56</td>\n"
        "      <td>0.07</td>\n"
        "      <td>[2.42, 2.69]</td>\n"
        "      <td>&lt;.001</td>\n"
        "    </tr>"
    )
    assert recover_minus_via_ci_pairing(row) == row


def test_ci_pairing_prose_line_keeps_strict_gap():
    """The relaxed gap must apply ONLY to HTML table rows. A prose text line
    (no <td>) keeps the strict 30-char bare-bracket cap so the majumder
    false-positive stays blocked: the bare CI [-1.86, 0.04] belongs to `d`,
    not to the far-away corrupt-looking `2.01`, and must NOT flip 2.01."""
    line = "M = 5.37, SD = 2.01, t(1827) = 1.83, p tukey = .067, d = 0.09 [-1.86, 0.04]"
    assert recover_minus_via_ci_pairing(line) == line


def test_ci_pairing_bare_bracket_rejects_across_independent_stat():
    """A bare CI never pairs back ACROSS an independent test statistic, even
    inside the 30-char gap. Pre-existing FP (v2.4.102): the tight-spaced variant
    `M = 5.37, SD = 2.01, t(1827)=1.83, d = 0.09 [-1.86, 0.04]` is only 25 chars
    from `2.01` to the bracket, so the gap cap alone let `SD = 2.01` recover to
    `-.01` — but the CI belongs to `d`, and `t`/`d` intervene, so it must be
    rejected by the independent-stat guard."""
    line = "M = 5.37, SD = 2.01, t(1827)=1.83, d = 0.09 [-1.86, 0.04]"
    assert recover_minus_via_ci_pairing(line) == line


def test_ci_pairing_recovers_body_line():
    line = "High only mediation: Mposterior = 20.54, SD=0.04, CI = [-0.61, -0.47];"
    assert "Mposterior = -0.54" in recover_minus_via_ci_pairing(line)


def test_ci_pairing_leaves_positive_estimate():
    row = "<tr><td>Attribute</td><td>0.55</td><td>0.06</td><td>[0.43, 0.67]</td></tr>"
    assert recover_minus_via_ci_pairing(row) == row


def test_ci_pairing_leaves_literal_mean_inside_its_ci():
    # A genuine mean (e.g. age 23.45) sitting INSIDE its own CI must never be
    # "recovered" — the literal value is consistent with the bracket.
    row = "<tr><td>Age</td><td>23.45</td><td>[22.10, 24.80]</td></tr>"
    assert recover_minus_via_ci_pairing(row) == row


def test_ci_pairing_leaves_token_without_bracket():
    # No CI in the record — genuinely ambiguous, must not be touched.
    assert recover_minus_via_ci_pairing("Mchange = 20.14, (0.05)") == "Mchange = 20.14, (0.05)"


def test_ci_pairing_leaves_token_outside_any_ci():
    # 25.0 de-corrupts to -5.0 which is not inside [2.0, 3.0]; untouched.
    assert recover_minus_via_ci_pairing("value 25.0 CI [2.0, 3.0]") == "value 25.0 CI [2.0, 3.0]"


# ── Real-PDF regression test ────────────────────────────────────────────

def test_efendic_no_corrupt_minus_in_render():
    pdf = TEST_PDFS / "apa" / "efendic_2022_affect.pdf"
    if not pdf.exists():
        pytest.skip(f"fixture missing: {pdf}")
    md = render_pdf_to_markdown(pdf.read_bytes())
    bad_cis = _corrupt_descending_cis(md)
    assert not bad_cis, f"corrupt (descending '2'-prefixed) CIs remain: {bad_cis[:5]}"
    assert not re.search(r"\br = 2\.\d", md), "'r = 2.X' corrupted correlation remains"
    # The headline abstract effect size must read correctly.
    assert "r = -.74" in md


def test_efendic_table_point_estimates_recovered_via_ci():
    """Every negative B-coefficient that pairs with a CI must read as a
    recovered negative, not the corrupted '2X.XX' literal. Mode-agnostic:
    tables emit as <td> HTML (Camelot) or as unstructured-table lines, and
    the CI-pairing recovery reaches the point estimate in either mode."""
    pdf = TEST_PDFS / "apa" / "efendic_2022_affect.pdf"
    if not pdf.exists():
        pytest.skip(f"fixture missing: {pdf}")
    md = render_pdf_to_markdown(pdf.read_bytes())
    # Mediation estimate recovered in body prose (confirmed vs AI gold).
    assert "Mposterior = -0.54" in md
    # Distinctive corrupt point-estimate forms must be gone (recovered).
    assert "21.34" not in md  # Table 3, Direction x Attribute -> -1.34
    assert "21.05" not in md  # Table 4, PMA -> -1.05
    # Idempotence: the render already applies the CI-pairing recovery, so a
    # second pass must be a no-op -- proving no CI-paired corrupt estimate
    # survived. (The body `Mchange` / contrast-coding residuals carry no CI
    # and are documented escalations -- the pass leaves them untouched.)
    assert recover_minus_via_ci_pairing(md) == md


def test_efendic_table_estimates_recovered_with_camelot_on():
    """The production render path uses Camelot, which emits each table cell on
    its own line inside a multi-line <tr>. Before this fix the SE cell between
    the B-column estimate and the CI cell pushed the char-gap past the 30-char
    bare-bracket cap, so W0d recovered the estimate in the DISABLE_CAMELOT
    unstructured-table channel but left every negative B-coefficient corrupt as
    '2X.XX' in the Camelot HTML-table channel. Every <tr> carrying a corrupt
    '2X.XX' estimate also carries its CI in the same row, so all are
    structurally recoverable. The genuine positive (2.56 in [2.42, 2.69]) stays.
    """
    pdf = TEST_PDFS / "apa" / "efendic_2022_affect.pdf"
    if not pdf.exists():
        pytest.skip(f"fixture missing: {pdf}")
    md = render_pdf_to_markdown(pdf.read_bytes())  # Camelot ON (production default)
    # No corrupt '2X.XX' B-column estimate cell may survive whose row carries a
    # CI it must lie inside.
    from docpluck.normalize import (
        _CI_PAIR_BRACKET_RE,
        _CORRUPT_NEG_TOKEN_RE,
        _TABLE_ROW_RE,
    )
    surviving = []
    for m in _TABLE_ROW_RE.finditer(md):
        row = m.group(0)
        if not _CI_PAIR_BRACKET_RE.search(row):
            continue
        lo_hi = [
            (float(g1), float(g2))
            for g1, g2 in _CI_PAIR_BRACKET_RE.findall(row)
        ]
        for tok in _CORRUPT_NEG_TOKEN_RE.finditer(row):
            # inside a bracket span? skip (it's a CI bound, not an estimate)
            if any(bm.start() <= tok.start() < bm.end() for bm in _CI_PAIR_BRACKET_RE.finditer(row)):
                continue
            frac = tok.group(1)
            recovered = float("-" + frac)
            literal = float("2" + frac)
            # only count as a defect when the recovered value fits a CI and the
            # literal does not (a genuine positive like 2.56 in [2.42,2.69] is
            # correctly left and is NOT a defect).
            for lo, hi in lo_hi:
                if (lo - 0.005) <= recovered <= (hi + 0.005) and not (
                    (lo - 0.005) <= literal <= (hi + 0.005)
                ):
                    surviving.append(tok.group(0))
                    break
    assert not surviving, (
        f"{len(surviving)} corrupt '2X.XX' B-estimate cells survived in Camelot "
        f"HTML tables despite a CI in the same row: {surviving[:8]}"
    )


# ── A3: dropped-minus SE-over-recovery guard (v2.4.104) ─────────────────────
# recover_dropped_minus_via_ci_pairing flips a bare positive to negative when the
# paired CI proves the minus was dropped. But in a "B | SE | CI" table row the CI
# describes the B estimate, and the SE (standard error) legitimately falls OUTSIDE
# B's CI — so the recovery wrongly flipped the SE to negative (SE cannot be
# negative). The guard: don't flip a bare-positive token in a <td> row when a
# signed-negative number (the already-recovered estimate) precedes it.


def test_dropped_minus_leaves_se_column_positive_in_table_row():
    # efendic Table 2 Intercept: B recovered to -0.09 (by W0d, upstream), SE=0.06,
    # CI=[-0.21, 0.04]. -0.06 is inside the CI but 0.06 is not — yet 0.06 is the
    # SE and must stay positive.
    row = (
        "<tr>\n<td>Intercept</td>\n<td>-0.09</td>\n<td>0.06</td>\n"
        "<td>[-0.21, 0.04]</td>\n<td>.185</td>\n</tr>"
    )
    out = recover_dropped_minus_via_ci_pairing(row)
    assert "<td>0.06</td>" in out, out
    assert "<td>-0.06</td>" not in out


def test_dropped_minus_still_recovers_first_estimate_in_table_row():
    # A genuinely dropped-minus B (the FIRST numeric column, no preceding negative)
    # must still flip: X=.09 with CI=[-0.21, -0.04] → -.09.
    row = "<tr>\n<td>X</td>\n<td>.09</td>\n<td>[-0.21, -0.04]</td>\n</tr>"
    out = recover_dropped_minus_via_ci_pairing(row)
    assert "<td>-.09</td>" in out, out


def test_dropped_minus_body_prose_unaffected_by_se_guard():
    # The SE guard is scoped to <td> table rows; a body-prose dropped-minus
    # estimate must still recover (the guard's "<td" check leaves prose alone).
    line = "the simple slope was b = .022 [-0.05, -0.01]"
    assert recover_dropped_minus_via_ci_pairing(line) == "the simple slope was b = -.022 [-0.05, -0.01]"


def test_efendic_se_columns_all_positive_with_camelot_on():
    """Every SE (standard-error) column value in efendic's regression tables must
    render positive — a standard error is non-negative. Before the A3 guard the
    dropped-minus recovery flipped SE cells that fell inside the B estimate's CI
    (e.g. Intercept SE 0.06 → -0.06)."""
    pdf = TEST_PDFS / "apa" / "efendic_2022_affect.pdf"
    if not pdf.exists():
        pytest.skip(f"fixture missing: {pdf}")
    md = render_pdf_to_markdown(pdf.read_bytes())  # Camelot ON
    # In each 5-column regression row (pred | B | SE | CI | p), the SE (3rd cell,
    # 2nd numeric) must not be a bare negative decimal.
    row_re = re.compile(
        r"<tr>\s*<td>[^<]*</td>\s*<td>[^<]*</td>\s*<td>(-0?\.\d+)</td>\s*<td>\[",
        re.DOTALL,
    )
    negative_se = row_re.findall(md)
    assert not negative_se, f"SE column rendered negative (SE cannot be < 0): {negative_se[:6]}"


# ── v2.4.119: column-structure minus recovery in raw_text table fallbacks ────
#
# A raw_text fallback linearizes each table COLUMN as its own run of lines, so
# neither of W0b/W0d's per-record rules can reach two shapes. Both were exposed
# by the v2.4.119 caption-tail walk, which recovers leading rows the previous
# walk silently dropped (efendic Table 3/5).


def test_ascending_positive_ci_is_never_flipped():
    """REGRESSION GUARD (2026-08-04): a `2`-prefixed CI whose bounds ASCEND is
    NOT provably corrupt, and must be left alone.

    A rejected "column-consensus" recovery flipped efendic Table 5's
    `[2.42, 2.69]` to `[-0.42, -0.69]` on the reasoning that its CI column
    already held recovered negatives. The AI gold confirms `[2.42, 2.69]` is a
    GENUINELY POSITIVE interval (the Direction high-vs-low contrast, estimate
    2.56) — the recovery manufactured a wrong published number. Column
    membership is not evidence for a sign flip; only per-record containment is.
    """
    from docpluck.normalize import recover_corrupted_minus_signs as rec

    col = "\n".join(
        ["[20.21, 0.04]", "[21.15, 21.03]", "[2.42, 2.69]", "[20.40, 20.13]"]
    )
    out = rec(col).split("\n")
    # The genuinely-corrupt descending brackets still recover...
    assert out[0] == "[-0.21, 0.04]"
    assert out[1] == "[-1.15, -1.03]"
    assert out[3] == "[-0.40, -0.13]"
    # ...and the genuine positive interval is untouched.
    assert out[2] == "[2.42, 2.69]"


def test_estimate_column_recovered_by_positional_ci_pairing():
    """W0b-est: the estimate column is separated from its CI column by the SE
    column, so W0d's proximity window cannot pair them. Positional pairing
    recovers each corrupt estimate whose fixed reading lands inside its CI —
    and leaves the SE column and genuine positives alone."""
    from docpluck.normalize import recover_corrupted_minus_signs as rec

    block = "\n".join(
        ["20.26", "20.21", "20.95", "21.15", "0.55", "0.14", "20.16", "21.34", "0.13"]
        + ["0.10", "0.03", "0.03", "0.06", "0.06", "0.05", "0.06", "0.12", "0.11"]
        + ["[-0.45, -0.06]", "[-0.27, -0.15]", "[-1.01, -0.89]", "[-1.27, -1.03]",
           "[0.43, 0.67]", "[0.04, 0.25]", "[-0.27, -0.05]", "[-1.58, -1.10]",
           "[-0.08, 0.35]"]
    )
    out = rec(block).split("\n")
    assert out[:9] == ["-0.26", "-0.21", "-0.95", "-1.15", "0.55", "0.14",
                       "-0.16", "-1.34", "0.13"], out[:9]
    # SE column must stay positive (it is a different column from the estimate).
    assert out[9:18] == ["0.10", "0.03", "0.03", "0.06", "0.06", "0.05",
                         "0.06", "0.12", "0.11"], out[9:18]


def test_estimate_column_pairing_leaves_genuine_positives():
    """FP guard: a table whose estimates are genuinely positive and whose CIs
    contain them is never rewritten (the containment test gates every fix)."""
    from docpluck.normalize import recover_corrupted_minus_signs as rec

    block = "\n".join(
        ["2.42", "3.10", "1.05"] + ["0.10", "0.20", "0.30"]
        + ["[2.20, 2.60]", "[3.00, 3.30]", "[1.00, 1.10]"]
    )
    assert rec(block) == block


# ── W0d non-negative-CI guard: an F-statistic is never negative (v2.4.123) ──

def test_f_statistic_not_flipped_against_a_nonnegative_ci():
    """W0d must not pair an estimate with a CI that cannot contain a negative.

    Found 2026-08-04 by the run-5 canary audit on maier_2023_collabra Table 9.
    The row is `Target article | 1, 114 | 2.00 | .16 | N/A | .02 | [.00, .09]`:
    an F-statistic of 2.00, its p, its partial-eta-squared .02, and the CI OF
    THE ETA-SQUARED. W0d read the leading `2` of `2.00` as a corrupted minus and
    flipped it to `-.00`, because `-.00` falls inside `[.00, .09]` while `2.00`
    does not — the containment invariant fires, but on the WRONG statistic's CI.

    The rendered output then carried **F = -.00**, which is impossible (F is a
    ratio of sums of squares and is non-negative by construction). Both text
    channels confirm the source reads `2.00`; docpluck manufactured the sign.

    The guard: a CI whose LOWER bound is >= 0 is an entirely non-negative
    interval, so no negative value can lie inside it. If the "recovery" is only
    accepted because the flipped value hits such an interval, the pairing is
    wrong by construction and must be refused.
    """
    from docpluck.normalize import recover_minus_via_ci_pairing as rec

    row = (
        "<tr><td>Target article</td><td>1, 114</td><td>2.00</td><td>.16</td>"
        "<td>N/A</td><td>.02</td><td>[.00, .09]</td></tr>"
    )
    assert rec(row) == row, f"F-statistic wrongly flipped negative: {rec(row)!r}"
    assert "-.00" not in rec(row)


def test_nonnegative_ci_guard_leaves_genuine_recoveries_armed():
    """The guard must not disarm W0d where the CI genuinely admits a negative.

    Both rows below carry a CI whose lower bound is < 0, so a negative estimate
    is admissible and the containment invariant remains meaningful.
    """
    from docpluck.normalize import recover_minus_via_ci_pairing as rec

    # efendic-shaped: intercept 20.09 -> -0.09, CI straddles zero
    straddling = "<tr><td>Intercept</td><td>20.09</td><td>0.06</td><td>[-0.21, 0.04]</td></tr>"
    assert "-0.09" in rec(straddling)

    # wholly-negative CI: 20.42 -> -0.42
    negative = "<tr><td>Direction</td><td>20.42</td><td>0.11</td><td>[-0.63, -0.21]</td></tr>"
    assert "-0.42" in rec(negative)
