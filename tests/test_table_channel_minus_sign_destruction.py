r"""The table channel destroys minus signs, and the repair meant to stop it cannot fire.

Reproduced 2026-09-02 at docpluck 2.4.138 on `10.1016/j.joep.2020.102350`, verified
against the rasterized page rather than against another parser:

* p2 Table 1 prints ``Cramer's V = 0.067 [-0.108, 0.218]`` -- an interval that SPANS
  zero. docpluck emits ``[\x00 0.108, 0.218]``, which reads as one that EXCLUDES it.
* p4 Table 2 "Comparison of differences across conditions" prints
  ``199  -1  -31  -30  213  14  31  17``. docpluck emits the three signed values as
  ``\x00 1 / \x00 31 / \x00 30`` and the three unsigned values intact -- the row
  carries its own two-sided control.

``cell_cleaning`` ALREADY contains the repair, keyed on the literal marker
``(cid:0)``, and its own comment names ``"(cid:0) 31" is -31``. But Camelot emits a raw
NUL on this path and never that literal, so the repair is a no-op that has looked
correct for as long as it has existed.

These are recorded as STRICT expected failures: when the defect is fixed they become
XPASS, which `strict=True` reports as a FAILURE, so the fix cannot land without this
file being updated. That is a record of a known defect, not a weakened gate.

FIX SITE, and the trap it must clear: repair where the Camelot cell is first read,
BEFORE docpluck inserts its own ``\x00BR\x00`` / ``\x00SUP\x00`` sentinels. A naive
``\x00\s*(?=\d)`` applied inside ``_html_escape`` would rewrite the closing sentinel
of a folded header such as ``"Replication\x00BR\x0095% CI"``, losing the ``<br>`` and
inventing a minus that was never printed. See
docs/FINDINGS_2026-09-02_table_channel_destroys_minus_signs.md.
"""

from __future__ import annotations

import pytest

from docpluck.tables.cell_cleaning import _html_escape

NUL = "\x00"


def test_the_repair_works_on_the_literal_marker_it_was_written_for() -> None:
    """Control. Without this, the expected failures below could be read as
    'the repair is broken' rather than 'the repair never sees this input'."""
    assert _html_escape("(cid:0) 31") == "-31"
    assert _html_escape("(cid:0)0.108") == "-0.108"


@pytest.mark.xfail(strict=True, reason="Camelot emits a raw NUL; the repair keys on '(cid:0)'")
@pytest.mark.parametrize(
    "cell, expected",
    [
        (f"{NUL} 1", "-1"),
        (f"{NUL} 31", "-31"),
        (f"{NUL} 30", "-30"),
        (f"[{NUL} 0.108, 0.218]", "[-0.108, 0.218]"),
        (f"0.064<br>[{NUL} 0.122, 0.231]", "0.064<br>[-0.122, 0.231]"),
    ],
    ids=["diff--1", "diff--31", "diff--30", "ci-spans-zero", "ci-with-fold"],
)
def test_a_raw_nul_before_a_digit_is_a_destroyed_minus_sign(cell: str, expected: str) -> None:
    assert _html_escape(cell) == expected


def test_the_internal_sentinel_must_survive_any_such_fix() -> None:
    """The trap. `\x00` is also docpluck's own fold sentinel, and a folded header can
    put a DIGIT immediately after its closing NUL. A digit-lookahead repair applied at
    this layer would destroy the fold and fabricate a minus. This test must keep
    passing after the fix -- if it goes red, the fix was applied at the wrong layer."""
    assert _html_escape(f"Replication{NUL}BR{NUL}95% CI") == "Replication<br>95% CI"
    assert _html_escape(f"Separate{NUL}BR{NUL}Joint") == "Separate<br>Joint"
