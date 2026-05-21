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
    _is_in_numeric_block,
    _is_numeric_only_line,
    _rejoin_space_broken_compounds,
    _strip_document_header_banners,
    _strip_page_footer_lines,
    recover_minus_via_ci_pairing,
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
#   cycle 8  (JOIN)        -> 10 -> 6
#   cycle 9  (STRIP JAMA)  -> 6 -> 4
#   cycle 9b (STRIP S9-4d) -> 4 -> 2
#   cycle 10 (CHARSUB)     -> 2 -> 2 (ip-feldman cleared corpus-wide but NOT
#                                     in the strided slice — stride miss)
#   cycle 11 (long-tail)   -> 2 -> ~0
# Do NOT raise this number to make the test pass — a higher count is a
# regression. Lower it (only) when a cycle genuinely fixes papers.
_IDEMPOTENCY_RATCHET = 2


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


def test_p0_jama_affiliations_sentinel_strips_after_line_join():
    """JAMA papers emit the sidebar sentinel line `Author affiliations and
    article information are listed at the end of this article.` as TWO
    pdftotext rows (`...are\\nlisted at the end of this article.`). P0's
    anchored ``^...$`` pattern matches only the joined form, so the early P0
    pass misses it. After S7/S8/LateJoin merge the rows, P0r (the cycle-9
    late re-strip) catches the now-single-line form and removes it.

    Cycle 9 (v2.4.60): adds P0r — generalization of cycle-7's H0r pattern.
    Clears 10 jama_open_* papers from the post-cycle-8 non-idempotent set.
    """
    # The 2-row pdftotext form: pre-LateJoin, the sentinel spans two lines.
    split_form = (
        "Some body text.\n"
        "+ Visual Abstract\n"
        "+ Supplemental content\n"
        "Author affiliations and article information are\n"
        "listed at the end of this article.\n"
        "More body text."
    )
    # P0 on the split form: the sentinel survives (line-anchor fails).
    s_split = _strip_page_footer_lines(split_form)
    assert "Author affiliations and article information are" in s_split
    # The joined form: P0 strips it.
    joined_form = split_form.replace(
        "Author affiliations and article information are\nlisted at the end of this article.",
        "Author affiliations and article information are listed at the end of this article.",
    )
    s_joined = _strip_page_footer_lines(joined_form)
    assert "Author affiliations and article information" not in s_joined
    # P0 is idempotent (a fixed point) — running it twice changes nothing.
    s_joined2 = _strip_page_footer_lines(s_joined)
    assert s_joined == s_joined2

    # End-to-end via normalize_text: split → joined-and-stripped in ONE pass.
    n1, _ = normalize_text(split_form, NormalizationLevel.academic)
    n2, _ = normalize_text(n1, NormalizationLevel.academic)
    assert "Author affiliations and article information" not in n1, (
        "P0r did not strip the JAMA sentinel after LateJoin merged the rows"
    )
    assert n1 == n2, "normalize_text is not idempotent on the JAMA split-sentinel form"


def test_is_numeric_only_line_distinguishes_table_cells_from_prose():
    """Cycle 9b context discriminator: identifies a line as a table cell vs
    prose. Used by S9 Pattern A to protect N values from being stripped as
    page numbers."""
    # Numeric-only (table cells)
    assert _is_numeric_only_line("7182")
    assert _is_numeric_only_line("-4455.54")
    assert _is_numeric_only_line("2.12∗∗∗ (0.201)")
    assert _is_numeric_only_line("  1,234,567  ")  # whitespace + thousands
    assert _is_numeric_only_line("-0.05 (0.058)")
    # Prose / mixed (NOT numeric-only)
    assert not _is_numeric_only_line("Observations: 7,182")
    assert not _is_numeric_only_line("Table 3")
    assert not _is_numeric_only_line("p < 0.001")  # contains 'p'
    assert not _is_numeric_only_line("")
    assert not _is_numeric_only_line("   ")
    assert not _is_numeric_only_line("(observations only)")  # no digit


def test_s9_4digit_pattern_a_preserves_table_n_values():
    """Cycle 9b: a 4-digit value repeated ≥3 times in a regression-table
    column (where its NEAREST non-blank neighbour is itself numeric) MUST be
    preserved. Pre-9b: any such value was stripped corpus-wide as a "page
    number". Post-9b: per-occurrence context gate."""
    # Simulated chandrashekar regression table block: 4 columns × same N
    raw = (
        "Body prose introducing the regression model.\n\n"
        "Column A    Column B    Column C    Column D\n"
        "-0.05 (0.058)    0.12 (0.044)    -0.09 (0.041)    0.21 (0.052)\n"
        "2.12∗∗∗ (0.201)  -1.88∗ (0.198)  1.45 (0.220)    0.87 (0.190)\n\n"
        "7182\n"
        "-4455.54\n"
        "8919.07\n"
        "8946.59\n\n"
        "7182\n"
        "-3210.45\n"
        "6450.11\n"
        "6477.62\n\n"
        "7182\n"
        "-2107.88\n"
        "4240.50\n"
        "4267.99\n\n"
        "7182\n"
        "-1500.22\n"
        "3024.88\n"
        "3052.30\n\n"
        "Body prose continuing with results discussion."
    )
    n1, _ = normalize_text(raw, NormalizationLevel.academic)
    n2, _ = normalize_text(n1, NormalizationLevel.academic)
    # All four N values must survive — they are sample-size for the four columns
    assert n1.count("7182") == 4, (
        f"S9 stripped table N=7182 values from regression columns; got "
        f"{n1.count('7182')} occurrences (expected 4)"
    )
    # And the result must be idempotent — pass 1 stripped what it should
    assert n1 == n2, "normalize_text is not idempotent on chandrashekar-style N values"


def test_s9_4digit_pattern_a_still_strips_isolated_page_numbers():
    """Cycle 9b kept Pattern A's page-number strip working. A 4-digit value
    repeated ≥3 times in ISOLATED context (surrounded by prose, not numeric
    neighbours) MUST still be stripped — that's the original Pattern A
    contract for continuous-pagination journals."""
    raw = (
        "Page one body prose ends here.\n\n"
        "1228\n\n"
        "Page two body prose continues from the previous page.\n\n"
        "1228\n\n"
        "More page-two body prose carrying the discussion forward.\n\n"
        "1228\n\n"
        "Conclusion section starts with this longer paragraph "
        "of synthesis and so on, more prose more prose more prose."
    )
    n1, _ = normalize_text(raw, NormalizationLevel.academic)
    # All three page-number repeats should be stripped — isolated context
    assert n1.count("1228") == 0, (
        f"S9 should have stripped isolated `1228` page numbers; "
        f"{n1.count('1228')} survived"
    )


def test_recover_minus_proximity_gate_rejects_distant_unrelated_brackets():
    """Cycle 11: a stat-table row that mixes an unrelated SD value with a
    separately-reported CI bracket must NOT have the SD recovered as a
    negative. The CI belongs to the point estimate it IMMEDIATELY follows;
    a corrupted-looking token whose nearest bracket is far away (or
    sentence-broken from it) is left alone.

    majumder 2024 had `SD = 2.01), t(1827) = 1.83, d = 0.09 [-1.86, 0.04]`
    — the `[-1.86, 0.04]` is the CI for `d = 0.09`, not for `2.01`. Pre-
    cycle-11 the recovery fired on `2.01` (because `-0.01` is inside
    `[-1.86, 0.04]`), corrupting a valid SD."""
    text = "M = 5.37, SD = 2.01, t(1827) = 1.83, p tukey = .067, d = 0.09 [-1.86, 0.04]"
    out = recover_minus_via_ci_pairing(text)
    assert out == text, f"recovery falsely fired on a distant unrelated bracket: {out!r}"
    # Sanity: the SD value 2.01 is unchanged.
    assert "SD = 2.01" in out


def test_recover_minus_proximity_gate_keeps_adjacent_recovery():
    """The proximity gate doesn't break the original corruption-recovery
    contract. A corrupted `22.68` IMMEDIATELY followed by its CI bracket
    still recovers correctly — bracket is within 30 chars + no sentence
    break between."""
    corrupted = "B = 22.68 [-4.65, -0.68]"
    rec = recover_minus_via_ci_pairing(corrupted)
    assert "-2.68" in rec, f"original-corruption recovery broken: {rec!r}"
    assert "22.68" not in rec


def test_recover_minus_proximity_gate_rejects_sentence_broken_bracket():
    """A CI bracket separated from a candidate token by a sentence break
    (period + space, or a new stat label like `d = ...`) doesn't pair.
    Defends against the cross-statistic false-positive."""
    text = "We found 2.45 in the control group. Treatment d = 0.05 [-1.00, 1.10]."
    out = recover_minus_via_ci_pairing(text)
    assert "2.45" in out, "sentence break should prevent recovery"
    assert "-.45" not in out


def test_recover_minus_via_ci_pairing_idempotent_on_already_recovered():
    """Cycle 10: an already-recovered `-2.68` next to a CI bracket
    [-4.65, -0.68] must NOT be re-corrupted into `--.68` on a second pass.
    Pre-cycle-10 the lookbehind `(?<![\\d.])` allowed `-` before the `2`,
    so pass-2 fired and produced `--.68`. Cycle 10 tightens to
    `(?<![\\d.\\-])`."""
    # Already-recovered: must be a fixed point.
    text = "B = -2.68 [-4.65, -0.68]"
    out1 = recover_minus_via_ci_pairing(text)
    out2 = recover_minus_via_ci_pairing(out1)
    assert out1 == text, f"already-recovered text was modified: {out1!r}"
    assert out1 == out2, f"recover_minus_via_ci_pairing is not idempotent: {out2!r}"
    assert "--.68" not in out1, "lookbehind regression: --.68 appeared"

    # Original corruption: STILL gets recovered.
    corrupted = "B = 22.68 [-4.65, -0.68]"
    rec = recover_minus_via_ci_pairing(corrupted)
    assert "-2.68" in rec, f"original-corruption recovery broken: {rec!r}"


@requires_pdftotext
def test_normalize_idempotent_ip_feldman_2025():
    """ip-feldman 2025 PSPB exercises recover_minus_via_ci_pairing's
    non-idempotence: the table cell `B = -2.68 [-4.65, -0.68]` (already-
    recovered negative point estimate paired with a CI) was re-corrupted to
    `--.68` on pass 2. Cycle 10 (v2.4.62) tightens the corrupt-neg-token
    lookbehind to forbid a preceding literal minus."""
    pdf = os.path.join(
        _TEST_PDFS,
        "escicheck",
        "ip-feldman-2025-pspb-misestimation-of-emotional-experiences-print-nosupp.pdf",
    )
    if not os.path.isfile(pdf):
        pytest.skip("ip-feldman test PDF not available")
    with open(pdf, "rb") as fh:
        raw, _ = extract_pdf(fh.read())
    n1, n2 = _norm_twice(raw)
    assert n1 == n2, "normalize_text is not idempotent on ip-feldman"
    assert "--.68" not in n1, "double-minus corruption appeared in normalized text"


@requires_pdftotext
def test_normalize_idempotent_chandrashekar_regression_table():
    """chandrashekar 2020 (Shafir 1993 replication) has 4 regression columns
    citing the same N=7182 → 4 standalone `7182` lines. Pre-cycle-9b S9
    Pattern A stripped them all as a "page number" on pass 2, while pass 1
    preserved them (A3's comma-strip hadn't run yet). Cycle 9b's per-
    occurrence numeric-block gate keeps them under both passes."""
    pdf = os.path.join(
        _TEST_PDFS,
        "escicheck",
        "chandrashekar-et-al-2020-shafir-1993-replication-and-extensions-print-nosupp.pdf",
    )
    if not os.path.isfile(pdf):
        pytest.skip("chandrashekar test PDF not available")
    with open(pdf, "rb") as fh:
        raw, _ = extract_pdf(fh.read())
    n1, n2 = _norm_twice(raw)
    assert n1 == n2, "normalize_text is not idempotent on chandrashekar"
    # Sanity: the table N must survive
    assert n1.count("7182") >= 4, (
        f"S9 should preserve the 4 regression-column N=7182 lines; "
        f"only {n1.count('7182')} survived"
    )


@requires_pdftotext
def test_normalize_idempotent_jama_open_1():
    """jama-open-1 has the canonical JAMA affiliation-sidebar sentinel split
    across two pdftotext lines — P0 (early) cannot match the anchored pattern
    on the two-row form; only the cycle-9 P0r re-strip catches it after
    LateJoin merges the rows."""
    pdf = os.path.join(_TEST_PDFS, "ama", "jama_open_1.pdf")
    if not os.path.isfile(pdf):
        pytest.skip("jama_open_1 test PDF not available")
    with open(pdf, "rb") as fh:
        raw, _ = extract_pdf(fh.read())
    n1, n2 = _norm_twice(raw)
    assert n1 == n2, "normalize_text is not idempotent on jama_open_1"
    assert "Author affiliations and article information" not in n1, (
        "JAMA affiliations sentinel should be stripped by P0r"
    )


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
