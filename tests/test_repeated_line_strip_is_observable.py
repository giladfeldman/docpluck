"""The repeated-line strip deletes lines. Until 2026-08-22 it did so invisibly.

`_normalize_text` builds a `repeated` set of lines that occur >= 5 times with a
minimum gap of >= 20 lines (or >= 20 times at any spacing), and removes every
occurrence with a bare list comprehension:

    lines = [l for l in lines if l.strip() not in repeated]

No `_track`, no `changes_made` key, no log line. It is inline code rather than a
named function, which is why an audit that wrapped **every module-level function
in `normalize.py`** and separately patched **`NormalizationReport._track`** found
nothing at all while five lines went missing between two normalization passes.
That is rule 0g's blind spot stated exactly: instrumentation attracts audit, and
its absence repels it.

Measured on `ieee_access_5` when the step was first instrumented: **1,280
characters removed on pass 1 and a further 95 on pass 2** — a step doing that
much work with no telemetry.

This test pins the telemetry, not the behaviour. The behaviour has a known open
defect recorded beside the code and in `todo.md`: the gate is a POSITION metric,
so an earlier step removing lines can move a repeated line across the threshold
between passes. On `ieee_access_5` the line it then deletes is
`Performance metric` — a repeated table COLUMN HEADER, which
`_looks_like_running_header_or_footer` correctly refuses, and which this rule
takes on spacing alone.
"""

from __future__ import annotations

from docpluck.normalize import NormalizationLevel, normalize_text


def _doc(marker: str, n_blocks: int = 6, gap: int = 30) -> str:
    """`marker` repeated `n_blocks` times, `gap` lines apart — a running header."""
    block = "".join(f"body line {i}\n" for i in range(gap))
    return "".join(marker + "\n" + block for _ in range(n_blocks))


def test_the_repeated_line_strip_is_counted():
    text = _doc("Journal of Repeated Headers 2024")
    out, report = normalize_text(text, level=NormalizationLevel.academic)
    assert "Journal of Repeated Headers 2024" not in out, (
        "fixture no longer exercises the rule"
    )
    assert report.changes_made.get("repeated_lines_stripped"), (
        "a step that removed content recorded nothing in changes_made"
    )


def test_the_repeated_line_strip_names_itself_per_step():
    text = _doc("Journal of Repeated Headers 2024")
    _out, report = normalize_text(text, level=NormalizationLevel.academic)
    assert "P0q_repeated_line_strip" in report.changes_made_by_step, (
        "the per-rule breakdown cannot attribute this deletion to anything"
    )
    assert "P0q_repeated_line_strip" in report.steps_changed


def test_a_line_that_does_not_repeat_enough_is_left_alone():
    """Fewer than 5 occurrences is not a running header."""
    text = _doc("Only Three Times", n_blocks=3)
    out, report = normalize_text(text, level=NormalizationLevel.academic)
    assert "Only Three Times" in out
    assert "P0q_repeated_line_strip" not in report.changes_made_by_step
