"""A significance mark set on its own line rejoins the legend it opens.

10.1177/01461672251327169 Tables 1, 8, 9 and 10 (canary audit, 2026-10-31):
the page prints "*p < .05. **p < .01. ***p < .001." on one line, but the raised
"*" sits on its own baseline, so pdftotext emits it as a line of its own and
the note read "*" / "p < .05. ...". Over the 128-paper render sample the same
split appears 25 times in 12 papers (marks *, **, and the dagger).

The join fires only when the line holds nothing but 1-4 marks and the next line
opens a p-value legend ("p <", "p =", "p ≤", or the "p ," a lost "<" glyph
leaves); a lone mark followed by anything else is left where it is.
"""

from docpluck.normalize import NormalizationLevel, normalize_text


def _norm(text: str, level=NormalizationLevel.standard) -> str:
    out = normalize_text(text, level)
    return out[0] if isinstance(out, tuple) else out


def test_a_lone_mark_rejoins_its_p_value_legend():
    t = "Note. df = 592.\n*\np < .05. **p < .01. ***p < .001.\n"
    assert "*p < .05. **p < .01. ***p < .001." in _norm(t)


def test_a_dagger_and_a_double_mark_rejoin_too():
    assert "†p < .10. **p < .01." in _norm("Note: n = 225.\n†\np < .10. **p < .01.\n")
    assert "**p < .01." in _norm("Note. IAT = Implicit Association Test.\n**\np < .01.\n")


def test_the_join_holds_at_the_academic_level():
    t = "Note. Linear regression, N = 594.\n*\np < .05. **p < .01.\n"
    assert "*p < .05. **p < .01." in _norm(t, NormalizationLevel.academic)


def test_a_lone_mark_before_anything_else_stays_put():
    for nxt in ("Institute of Psychology, Cracow", "0.45", "Age"):
        t = f"Some text.\n*\n{nxt}\n"
        assert f"*{nxt}" not in _norm(t), nxt
