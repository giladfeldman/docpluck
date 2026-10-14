"""W0t: a line-end fragment the text still prints hyphenated licenses no glued copy (d-d68442).

The licence rule is "one layout line-end fragment `A-` per glued text site". A fragment
pdftotext did NOT dehyphenate (the text still reads `well-` / `being`) produced no glued
copy, so before this guard it was a free licence: a glued `wellbeing` from anywhere else --
a printed `well being` whose space pdftotext dropped -- could take it and come out
`well-being`, a hyphen the paper never printed there (consult round 2, finding 7).
No corpus case was found (measured 2026-10-14, see CHANGELOG); this pins the guard.
"""
from __future__ import annotations

from types import SimpleNamespace

from docpluck.normalize import recover_semantic_hyphens_via_layout


def _layout(*words: str):
    return SimpleNamespace(pages=[SimpleNamespace(words=[{"text": w} for w in words])])


def test_kept_fragment_does_not_license_a_dropped_space():
    text = ("The scale measures well-being across groups. Its items ask about well-\n"
            "being at work. A third paper reports wellbeing scores.\n")
    lay = _layout("The", "scale", "measures", "well-being", "well-", "being", "well", "being")
    c = [0]
    out = recover_semantic_hyphens_via_layout(text, lay, c)
    assert "reports wellbeing scores" in out and c[0] == 0, out


def test_a_used_fragment_still_licenses_its_glued_copy():
    text = "The scale measures well-being across groups. We report wellbeing at work.\n"
    lay = _layout("The", "scale", "measures", "well-being", "well-", "being")
    c = [0]
    out = recover_semantic_hyphens_via_layout(text, lay, c)
    assert "report well-being at work" in out and c[0] == 1, out
