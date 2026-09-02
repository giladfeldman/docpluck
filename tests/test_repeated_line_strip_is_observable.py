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

These tests pin the telemetry AND the all-or-nothing promise.

⚠️ HISTORICAL, CORRECTED 2026-08-29 — the paragraph that stood here described
the gate as a POSITION metric (`min(gaps) >= 20`) with an open idempotency
defect on `ieee_access_5`'s table column header `Performance metric`. That was
true when it was written and is no longer: v1.9.60 replaced the line-index
proxy with a PAGE-DISTRIBUTION gate, and v1.9.61 corrected that gate's page
attribution. It is kept as a dated record rather than deleted, because a stale
measurement read as current is this project's most expensive recurring mistake.
"""

from __future__ import annotations

from docpluck.normalize import NormalizationLevel, normalize_text


def _doc(marker: str, n_blocks: int = 6, gap: int = 30) -> str:
    """`marker` repeated `n_blocks` times, `gap` lines apart — a running header."""
    block = "".join(f"body line {i}\n" for i in range(gap))
    return "".join(marker + "\n" + block for _ in range(n_blocks))


def test_the_repeated_line_strip_deduplicates_and_counts_every_copy_it_took():
    """The strip DEDUPLICATES — it removes N−1 copies and spares one.

    ⚠️ THIS TEST USED TO ASSERT ``marker not in out`` — TOTAL removal — and
    that contract is the exact shape that shipped an article with no title.
    **DO NOT "FIX" A FAILURE HERE BY RESTORING TOTAL DELETION.**

    On `10.1001/jamanetworkopen.2023.39337` the title *"Effect of
    Time-Restricted Eating on Weight Loss in Adults With Type 2 Diabetes"* is
    ALSO the running head, so it occurs 13 times: twelve headers and the page-1
    title block. Under the old contract the strip took all thirteen and the
    paper was delivered with no title. CLAUDE.md rule 0g: deduplication is
    legitimate only when a copy demonstrably survives, otherwise it is a
    deletion wearing a dedup's name.

    Contract rewritten 2026-08-29 for normalization 1.9.62. Sibling of
    `tests/test_normalization.py::TestS9_HeaderFooter`, which pins the same
    promise on the paginated arm; this fixture carries no form feed and so
    exercises the UNPAGINATED fallback.
    """
    marker = "Journal of Repeated Headers 2024"
    text = _doc(marker)
    assert text.count(marker) == 6, "fixture no longer exercises the rule"
    out, report = normalize_text(text, level=NormalizationLevel.academic)

    assert out.count(marker) == 1, (
        "exactly one copy must survive — 0 is the all-or-nothing deletion "
        "rule 0g forbids, 6 means the dedup did not fire at all"
    )
    surviving = [ln for ln in out.split("\n") if ln.strip()]
    assert surviving[0].strip() == marker, (
        "the survivor must be the FIRST copy in document order"
    )
    assert report.changes_made.get("repeated_lines_stripped"), (
        "a step that removed content recorded nothing in changes_made"
    )


def test_the_strip_reports_the_exact_number_of_copies_taken_and_spared():
    """`changes_made` holds a CHARACTER DELTA under a count-shaped name.

    Measured 2026-08-29: on this 6-copy fixture `repeated_lines_stripped` is
    **165**, which is 5 × len("Journal of Repeated Headers 2024\\n") — the five
    deleted copies in characters, not the number 5. The name says "lines" and
    the value counts characters, so a consumer reading it as a count is wrong
    by a factor of the line length.

    The exact counts DO exist, in the per-line telemetry v1.9.61 added, and
    that is what a consumer should read. This test pins both facts so the
    mislabelling cannot be mistaken for a count and the real counts cannot
    silently disappear.
    """
    marker = "Journal of Repeated Headers 2024"
    out, report = normalize_text(_doc(marker), level=NormalizationLevel.academic)

    assert report.changes_made["repeated_lines_stripped"] == 5 * (len(marker) + 1), (
        "the key is a character delta; if this became a true count, update the "
        "docstring above and tell consumers — the name has always implied one"
    )

    taken = {k: v for k, v in report.fallbacks.items()
             if k.startswith("repeated_line_stripped:")}
    assert sum(taken.values()) == 5, (
        f"5 copies were removed; per-line telemetry reports {taken}"
    )
    assert report.fallbacks.get("repeated_line_last_copy_kept") == 1, (
        "rule 0g's spared copy must be announced, not merely performed — "
        "a line in `repeated_line_stripped:*` and absent from this key is the "
        "signature of the title-deletion defect"
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
