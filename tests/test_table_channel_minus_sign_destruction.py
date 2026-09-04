r"""The table channel destroyed minus signs, because the repair could not fire. FIXED.

Reproduced 2026-09-02 at docpluck 2.4.138 on `10.1016/j.joep.2020.102350`, verified
against the RASTERIZED PAGE rather than against another parser:

* p2 Table 1 prints ``Cramer's V = 0.067 [-0.108, 0.218]`` -- an interval that SPANS
  zero. docpluck emitted ``[\x00 0.108, 0.218]``, which reads as one that EXCLUDES it.
* p4 Table 2 "Comparison of differences across conditions" prints
  ``199  -1  -31  -30  213  14  31  17``. docpluck emitted the three signed values as
  ``\x00 1 / \x00 31 / \x00 30`` and the three unsigned values intact -- the row
  carries its own two-sided control.

ROOT CAUSE. ``cell_cleaning`` already held the repair, keyed on the literal ``(cid:0)``
pdfminer.six emits for an unmappable glyph. **Camelot 2.0.0 does not use pdfminer.six**
-- it reads text through ``playa.miner``, whose ``Font.decode`` falls back to an
identity map, so the same character code 0 arrives as a raw NUL. Measured on the same
file: Camelot page 4 stream -> 21 cells carry ``\x00`` and 0 carry ``(cid:0)``;
pdfplumber (pdfminer.six) -> 0 NULs and 31 ``(cid:0)``. The repair became a
green-shaped no-op the day the table backend changed, and nothing failed.

FIXED in v2.4.139 by ``recover_unmapped_glyph_minus``, which recovers BOTH spellings --
a repair keyed on one library's spelling of "I could not decode this" is one dependency
bump away from silently doing nothing again.

THE TRAP THE FIX HAD TO CLEAR, pinned below and load-bearing: ``\x00`` is also
docpluck's own placeholder character, ``clean_cell_text`` runs a second time from
``_html_escape`` once those placeholders exist, and a folded header puts a DIGIT right
after a closing placeholder NUL (``"Replication\x00BR\x0095% CI"``). A naive
``\x00\s*(?=\d)`` would destroy the fold AND invent a minus that was never printed --
data loss turned into data FABRICATION. If the placeholder tests below go red, the fix
was applied at the wrong layer.

Full write-up: docs/FINDINGS_2026-09-02_table_channel_destroys_minus_signs.md (W-0015).
"""

from __future__ import annotations

import pytest

from docpluck.tables.cell_cleaning import (
    _MERGE_SEPARATOR,
    _SUP_CLOSE,
    _SUP_OPEN,
    _html_escape,
    clean_cell_text,
    recover_unmapped_glyph_minus,
)

NUL = "\x00"


def test_the_repair_works_on_the_literal_marker_it_was_written_for() -> None:
    """Control. Without this, the cases below could be read as 'the repair is broken'
    rather than 'the repair never saw this input'. pdfminer.six still emits this
    spelling -- pdfplumber produced 31 of them on the very paper where Camelot
    produced none -- so it must keep working alongside the raw-NUL arm."""
    assert _html_escape("(cid:0) 31") == "-31"
    assert _html_escape("(cid:0)0.108") == "-0.108"


@pytest.mark.parametrize(
    "cell, expected",
    [
        (f"{NUL} 1", "-1"),
        (f"{NUL} 31", "-31"),
        (f"{NUL} 30", "-30"),
        (f"[{NUL} 0.108, 0.218]", "[-0.108, 0.218]"),
        (f"0.064{_MERGE_SEPARATOR}[{NUL} 0.122, 0.231]", "0.064<br>[-0.122, 0.231]"),
    ],
    ids=["diff--1", "diff--31", "diff--30", "ci-spans-zero", "ci-with-fold"],
)
def test_a_raw_nul_before_a_digit_is_a_destroyed_minus_sign(cell: str, expected: str) -> None:
    """Every case here is a cell Camelot actually emitted for
    `10.1016/j.joep.2020.102350`, and every expected value was read off the
    rasterized page."""
    assert _html_escape(cell) == expected


def test_both_spellings_of_the_same_unmapped_glyph_agree() -> None:
    """One concept, one answer. The two readers spell "I could not decode this"
    differently; docpluck must not give two different values for the same cell."""
    for magnitude in ("1", "31", "0.108"):
        assert _html_escape(f"{NUL} {magnitude}") == _html_escape(f"(cid:0) {magnitude}")


def test_the_internal_sentinel_must_survive_any_such_fix() -> None:
    """The trap. `\x00` is also docpluck's own fold placeholder, and a folded header
    can put a DIGIT immediately after its closing NUL. A digit-lookahead repair applied
    without placeholder protection would destroy the fold and fabricate a minus. These
    must keep passing -- if they go red, the fix was applied at the wrong layer."""
    assert _html_escape(f"Replication{NUL}BR{NUL}95% CI") == "Replication<br>95% CI"
    assert _html_escape(f"Separate{NUL}BR{NUL}Joint") == "Separate<br>Joint"
    assert _html_escape(f"0.31{_SUP_OPEN}*{_SUP_CLOSE}") == "0.31<sup>*</sup>"
    # The exact string the backlog recorded as what a naive fix would corrupt
    # (todo.md W-0016 part B: "'Age\x00BR\x0031' -> 'Age\x00BR-31'", destroying the
    # fold and injecting a minus never printed).
    assert _html_escape(f"Age{NUL}BR{NUL}31") == "Age<br>31"


def test_a_placeholder_between_two_destroyed_minuses_is_not_swallowed() -> None:
    """A merged cell joins two NUL-carrying values with the fold placeholder, so the
    string reads `\x00 1` + `\x00BR\x00` + `\x00 31`. A generic `\x00[^\x00]*\x00`
    "placeholder span" matches `"\x00 1\x00"` here and would protect a REAL minus from
    repair -- which is why the fix matches the placeholders by exact spelling."""
    assert _html_escape(f"{NUL} 1{_MERGE_SEPARATOR}{NUL} 31") == "-1<br>-31"


def test_the_code_zero_slot_is_not_a_minus_in_every_font() -> None:
    """The false-positive class a single-paper diagnosis could not have shown, and the
    reason this rule is gated rather than a bare substitution.

    `10.1017/s1930297500007956` uses the same unmappable code-0 slot for an EXTENSIBLE
    OPENING PARENTHESIS, with code 1 as its closing partner. RASTERIZED at 170dpi and
    read: p17 prints ``y_i ~ Gaussian((mu1, mu2), [ ... ]^-1)``. The ungated rule fires
    25 times on that paper and every one MANUFACTURES a minus sign that is not on the
    page -- data loss traded for data fabrication, which this project treats as worse.

    Two independent signals separate the classes across every affected paper in a
    200-paper sample: the delimiter paper's 33 NULs are matched exactly by 33 code-1
    partners, and not one of its sites sits on the same line as its digits, because an
    extensible delimiter is its own layout element while a minus is glued to its number.
    """
    partnered = f"uniform {NUL} 0, 10\x01"
    assert recover_unmapped_glyph_minus(partnered) == partnered
    across_a_newline = f"Gaussian {NUL}\n0, 10"
    assert recover_unmapped_glyph_minus(across_a_newline) == across_a_newline


def test_the_minus_papers_carry_no_partner_code_two_sided() -> None:
    """The control for the test above. If the partner-code guard also blocked the real
    minus cases, it would be trading one silent loss for another -- so the cases that
    MUST still repair are asserted beside the case that must not."""
    assert recover_unmapped_glyph_minus(f"t(81.58) = {NUL} 2.19") == "t(81.58) = -2.19"
    assert recover_unmapped_glyph_minus(f"{NUL}74.27") == "-74.27"


def test_a_nul_that_is_not_before_a_digit_is_left_alone() -> None:
    """The glyph in an unmapped slot is only known where the evidence says so. Before a
    digit in a stat table it is U+2212; elsewhere it is unknown, and inventing one is
    the hypothetical this project forbids. Leaving it visible also keeps it detectable
    downstream, where a silently deleted character would not be."""
    assert recover_unmapped_glyph_minus(f"Cram{NUL}er's V") == f"Cram{NUL}er's V"
    assert recover_unmapped_glyph_minus(f"{NUL} n.s.") == f"{NUL} n.s."


def test_u_fffd_is_a_different_marker_and_must_not_get_this_treatment() -> None:
    """U+FFFD is the other spelling of "undecodable", and it lands in the OPERATOR slot,
    not the sign slot -- so this rule must never be "generalised" to cover it.

    Measured: 1 of 200 sampled papers carries it, `10.1371/journal.pone.0288438`, 11
    sites, every one an operator. RASTERIZED at 160dpi and read, page 7, where the SAME
    codepoint is two DIFFERENT operators on one page: "Significance level was p <= .05"
    (U+2264) and "anything >=1.5 arm's length was considered unreachable" (U+2265). No
    single substitution is right even within one document, and choosing between them from
    context would be inferential -- the consumer's job.

    Note what W0r's own shape would do if U+FFFD were added to it: `p�0.05` is a
    marker directly before a digit, so it would become `p-0.05` -- a comparison operator
    silently replaced by a minus sign.
    """
    for cell in ("p�0.05", "� 3 years", "�1.5 arm's length"):
        assert recover_unmapped_glyph_minus(cell) == cell


def test_the_repair_is_idempotent() -> None:
    """`clean_cell_text` runs twice on a constructed cell -- once from `repair_cells`
    at capture, once again from `_html_escape` -- so a non-idempotent repair would
    apply itself to its own output."""
    for cell in (f"{NUL} 31", f"[{NUL} 0.108, 0.218]", "(cid:0)0.1",
                 f"Replication{NUL}BR{NUL}95% CI", f"{NUL} 1{_MERGE_SEPARATOR}{NUL} 31"):
        once = clean_cell_text(cell)
        assert clean_cell_text(once) == once
