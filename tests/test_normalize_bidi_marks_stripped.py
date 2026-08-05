"""S6 must strip Unicode BIDI FORMAT marks (U+200E / U+200F / U+2060 / U+FEFF).

Regression guard for a defect found in run 7 (2026-08-05) via the xiao_2021_crsp
canary: an invisible LEFT-TO-RIGHT MARK survived normalization into the rendered
markdown, immediately after a citation's closing paren
(``Connolly, Reb, and Kausel (2013)<U+200E>``).

Why it matters beyond cosmetics: an invisible character inside rendered output
breaks *string equality and search* for every downstream consumer. A citation
checker comparing ``(2013)`` against ``(2013)‎`` sees a mismatch it cannot
see on screen -- and docpluck's output feeds exactly such consumers (citelink,
CitationGuard). It is the same failure class the U+00AD soft-hyphen strip on
``normalize.py`` was added for ("invisible, breaks search").

The S6 invisible-character block already strips U+200B/C/D and U+FEFF but
skipped U+200E/U+200F -- an omission in a sequence, not a decision.

Written BEFORE the fix and watched FAILING at unfixed HEAD (v2.4.124), per the
portfolio rule that a test authored after the fix proves nothing.
"""

from __future__ import annotations

import pytest

from docpluck.normalize import normalize_text, NormalizationLevel


BIDI_MARKS = [
    ("‎", "LEFT-TO-RIGHT MARK"),
    ("‏", "RIGHT-TO-LEFT MARK"),
    ("⁠", "WORD JOINER"),
]


@pytest.mark.parametrize("mark,name", BIDI_MARKS)
@pytest.mark.parametrize("level", [NormalizationLevel.standard, NormalizationLevel.academic])
def test_bidi_mark_stripped(mark: str, name: str, level: NormalizationLevel) -> None:
    """No invisible BIDI/join format char may survive normalization."""
    text = f"See Connolly, Reb, and Kausel (2013){mark} and others."
    out, _report = normalize_text(text, level)
    assert mark not in out, f"{name} survived normalization at {level}"
    # The visible text must be untouched -- stripping must not eat content.
    assert "Kausel (2013) and others." in out


def test_bidi_strip_preserves_surrounding_text_exactly() -> None:
    """Stripping the mark must be the ONLY change to the line."""
    clean = "See Connolly, Reb, and Kausel (2013) and others."
    dirty = "See Connolly, Reb, and Kausel (2013)‎ and others."
    out_clean, _ = normalize_text(clean, NormalizationLevel.academic)
    out_dirty, _ = normalize_text(dirty, NormalizationLevel.academic)
    assert out_dirty == out_clean


def test_bidi_strip_is_idempotent() -> None:
    """A second pass must be a no-op (normalize_text idempotency contract)."""
    text = "Kausel (2013)‎ and‏ others⁠."
    once, _ = normalize_text(text, NormalizationLevel.academic)
    twice, _ = normalize_text(once, NormalizationLevel.academic)
    assert once == twice


def test_zero_width_and_bom_still_stripped() -> None:
    """The pre-existing invisible-char strips must keep working (no regression)."""
    text = "alpha​beta‌gamma‍delta﻿epsilon"
    out, _ = normalize_text(text, NormalizationLevel.academic)
    for ch in ("​", "‌", "‍", "﻿"):
        assert ch not in out
    assert "alphabetagammadeltaepsilon" in out
