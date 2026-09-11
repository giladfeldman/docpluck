"""The render post-process chain must never delete a published quantity.

**The biggest finding of the 2026-08-14 audit, and it indicts that audit's own
framing.** All 111 `normalize.py` transformations were classified NOTATION vs
REPAIR and every numeric rule's firing sites counted across 297 English papers.
The same question was never asked of `render.py` — the channel that reaches the
user. Asked for the first time, it answered immediately.

MEASURED ON REAL PAPERS at v2.4.129, by `tools/diag/render_deletion_scan.py`:

    10.1017/s1930297500009189   an ENTIRE published-results sentence deleted
        "…(240 participants * 8 items), we found a strong relationship between
         comparative ability estimates and others' ability ratings (r(6) = 0.94,
         p < .001, 95% CI [0.71, .99]); and … (r(6) = 0.99, p < .001, 95% CI
         [0.96, .99]). Hotelling's (1940) t indicated these correlations to be
         different from each other (t(5) = 4.66, p = .006)."
        step: _suppress_inline_duplicate_table_captions
        mechanism: its "real prose" stop requires a line of >=80 chars ENDING
        in `.!?`, and pdftotext WRAPS body text, so a genuine sentence spans
        several lines and no single line qualifies. The walk consumed them as
        "cell-shaped continuation".

    10.1001/jamanetworkopen.2023.48333   a hazard ratio and its CI deleted
        "<td>1.31 (1.20-1.44)<br>JAMA Network Open. 2023;6(12):e2348333…</td>"
        step: _strip_phantom_camelot_tables, whose own docstring called itself
        "intentionally LOSSY". The phantom diagnosis reads the <th> (masthead
        text); it says nothing about whether the <tbody> holds measurements.

Two correlations, a Hotelling's *t*, three *p*-values and two confidence
intervals — the exact quantities docpluck exists to deliver — removed from a
meta-science pipeline with **no count, no key in `changes_made`, no log line**.
`render_pdf_to_markdown()` chains 54 `md = fn(md)` calls and returned a bare
`str`, so no consumer could even ask.

THE FIX (v2.4.130): `_carries_statistical_content` / `_run_carries_statistical_content`.
Delete FURNITURE, never DATA. A candidate deletion run holding any published
quantity is left ENTIRELY alone — not filtered down to its numeric lines,
because a half-suppressed table is a new defect whose gaps nobody can see.

See LESSONS.md L-032 and docs/SCOPE.md.
"""

from __future__ import annotations

from pathlib import Path

import pytest

# Camelot is not needed by this module's tests; skipping it keeps them fast.
# Declarative on purpose: this was `os.environ.setdefault(...)` at module scope,
# which executes during COLLECTION and was never undone, so importing this file
# disabled Camelot for the WHOLE pytest process and every real-PDF table test
# collected afterwards found no tables. `conftest._camelot_disabled_per_module`
# reads this flag and restores the prior value when the module finishes.
DISABLE_CAMELOT = True

from docpluck import render as R

from .conftest import pdf_available, pdf_path


# ── the discriminator: data vs furniture ────────────────────────────────


@pytest.mark.parametrize(
    "line",
    [
        "M = 4.52",
        "SD = 1.13",
        "N = 245",
        "t(87) = 2.01",
        "p < .001",
        "p = .006",
        "r(6) = 0.94",
        "-0.28",
        "0.87",
        "95% CI [0.12, 0.44]",
        "1.31 (1.20-1.44)",
        "= 4.66, p = .006).",
    ],
)
def test_a_published_quantity_is_recognised_as_data(line):
    assert R._carries_statistical_content(line), line


@pytest.mark.parametrize(
    "line",
    [
        # Every one of these is a REAL orphan cell label harvested from the
        # corpus papers the suppressors were built for — they must stay
        # deletable or the suppressors lose their purpose.
        "Target article",
        "Replication",
        "Study design",
        "Sample characteristics",
        "Positive",
        "Negative",
        "No of estimates",
        "Share of positives (%)",
        "Hypothesis",
        "Description",
    ],
)
def test_furniture_is_still_deletable(line):
    assert not R._carries_statistical_content(line), line


# ── the orphan-cell suppressor ──────────────────────────────────────────


_STATS_RUN = """## Results

Table 3. Descriptive statistics by condition.

M = 4.52

SD = 1.13

N = 245

t(87) = 2.01

p < .001

The effect was robust across conditions.
"""

_FURNITURE_RUN = """Table 5. Comparison of target article versus replication.

Target article

Replication

Study design

Sample characteristics

Now the prose paragraph continues here with several stopwords in it.
"""


def test_orphan_suppressor_keeps_every_digit_of_a_statistical_run():
    out = R._suppress_orphan_table_cell_text(_STATS_RUN)
    before = sum(c.isdigit() for c in _STATS_RUN)
    assert sum(c.isdigit() for c in out) == before
    for tok in ("M = 4.52", "SD = 1.13", "N = 245", "t(87) = 2.01", "p < .001"):
        assert tok in out, tok


def test_orphan_suppressor_does_not_swallow_ADJACENT_PROSE():
    """The cascade, which is worse than the direct deletion.

    `_is_orphan_cell_paragraph` classifies an English sentence carrying fewer
    than 3 of its 20 stopwords as an orphan. "The effect was robust across
    conditions." has exactly 2 (`the`, `was`). Alone after a caption it
    survives, because the run needs >= 2 orphans; preceded by numeric cells the
    run is long enough and the sentence is swept out with them. So the presence
    of table data caused REAL PROSE to be deleted.
    """
    out = R._suppress_orphan_table_cell_text(_STATS_RUN)
    assert "The effect was robust across conditions." in out


def test_orphan_suppressor_still_suppresses_pure_furniture():
    """The guard must not neuter the rule it guards."""
    out = R._suppress_orphan_table_cell_text(_FURNITURE_RUN)
    assert "Target article" not in out
    assert "Study design" not in out
    assert "*Table 5. Comparison of target article versus replication.*" in out
    assert "Now the prose paragraph continues here" in out


def test_the_guard_is_LOAD_BEARING_not_decoration():
    """Break the guard and the defect must come back.

    A regression test that has never failed against the real defect is
    decoration (CLAUDE.md). Rather than reverting the module, this neutralises
    the discriminator the fix introduced — which is precisely the pre-fix
    behaviour, since before v2.4.130 nothing asked whether a line held a
    quantity — and asserts the numbers disappear again.
    """
    original = R._carries_statistical_content
    try:
        R._carries_statistical_content = lambda _line: False
        out = R._suppress_orphan_table_cell_text(_STATS_RUN)
    finally:
        R._carries_statistical_content = original

    assert "M = 4.52" not in out, (
        "with the guard disabled the statistics survived anyway — the guard is "
        "not what saves them, so this test proves nothing about it"
    )
    assert sum(c.isdigit() for c in out) < sum(c.isdigit() for c in _STATS_RUN)


# ── the duplicate-caption walk ──────────────────────────────────────────


def test_duplicate_caption_walk_stops_at_a_wrapped_prose_sentence():
    """The 10.1017/s1930297500009189 mechanism, reduced to its shape.

    The wrapped sentence's lines each end mid-clause (`,` and `).`), so the
    >=80-chars-ending-in-a-terminator stop never fires.
    """
    md = "\n".join([
        "### Table 2",
        "",
        "*Table 2. Correlations between ability estimates.*",
        "",
        "<table><tr><td>x</td></tr></table>",
        "",
        "Some body prose introduces the analysis here.",
        "",
        "*Table 2. Correlations between ability estimates.*",
        "we found a strong relationship between comparative ability "
        "estimates and others' ability ratings (r(6) = 0.94,",
        "= 4.66, p = .006).",
        "",
        "The discussion then continues.",
    ])
    out = R._suppress_inline_duplicate_table_captions(md)
    assert "r(6) = 0.94" in out
    assert "p = .006" in out


# ── the phantom-table stripper ──────────────────────────────────────────


def test_phantom_stripper_keeps_a_table_whose_body_holds_a_measurement():
    """10.1001/jamanetworkopen.2023.48333 — a hazard ratio welded to masthead."""
    block = (
        "<table><thead><tr><th>JAMA Network Open | Public Health</th></tr></thead>"
        "<tbody><tr><td>1.31 (1.20-1.44)<br>JAMA Network Open. "
        "2023;6(12):e2348333</td></tr></tbody></table>\n"
    )
    out = R._strip_phantom_camelot_tables(block)
    assert "1.31 (1.20-1.44)" in out


def test_phantom_stripper_still_drops_a_genuinely_empty_phantom():
    """The guard must not neuter the rule: no measurement, still stripped."""
    block = (
        "<table><thead><tr><th>JAMA Network Open | Public Health</th></tr></thead>"
        "<tbody><tr><td>Discussion</td></tr></tbody></table>\n"
    )
    assert R._strip_phantom_camelot_tables(block).strip() == ""


# ── end to end, on the real papers ──────────────────────────────────────


_HOTELLING = "10.1017__s1930297500009189.pdf"


@pytest.mark.skipif(
    not pdf_available("articlerepo", _HOTELLING),
    reason=f"custodian has no {_HOTELLING}",
)
def test_hotelling_sentence_survives_the_whole_chain_real_pdf():
    """10.1017/s1930297500009189 — present before the chain, and now after it.

    Measured at v2.4.129: `r(6) = 0.94` before=1 after=0, `4.66` before=1
    after=0, `p = .006` before=1 after=0.
    """
    pdf = Path(pdf_path("articlerepo", _HOTELLING))
    md = R.render_pdf_to_markdown(pdf.read_bytes())
    for tok in ("r(6) = 0.94", "4.66", "p = .006"):
        assert tok in md, tok


# ── the report object: the channel can finally say what it did ──────────


def test_render_report_is_opt_in_and_output_identical():
    """Passing a report must not change a single byte of the markdown.

    The whole chain was rewritten from `md = fn(md)` to
    `md = _step(_report, "fn", fn, md)` in v2.4.130. That is 51 mechanical
    edits to the function that produces every rendered document, so the
    invariant worth pinning is not what the report says — it is that asking
    for the report changes nothing.
    """
    if not pdf_available("articlerepo", _HOTELLING):
        pytest.skip(f"custodian has no {_HOTELLING}")
    data = Path(pdf_path("articlerepo", _HOTELLING)).read_bytes()
    plain = R.render_pdf_to_markdown(data)
    report = R.RenderReport()
    with_report = R.render_pdf_to_markdown(data, _report=report)
    assert plain == with_report
    assert len(report.steps_applied) > 40, report.steps_applied
    assert set(report.steps_changed).issubset(set(report.steps_applied))


def test_render_report_names_the_step_that_removed_a_line():
    """Before v2.4.130 a deleted line left NO trace anywhere. Now it is named."""
    report = R.RenderReport()
    R._step(
        report,
        "_suppress_orphan_table_cell_text",
        R._suppress_orphan_table_cell_text,
        _FURNITURE_RUN,
    )
    assert "_suppress_orphan_table_cell_text" in report.steps_changed
    removed = {d["line"] for d in report.lines_removed}
    assert "Target article" in removed
    # ...and it is correctly classified as furniture, not as a lost statistic.
    assert report.statistics_removed == []


def test_render_report_flags_a_removed_statistic_as_such():
    """The report must be able to RAISE the alarm, not only stay quiet.

    A reporting field that has only ever been observed empty is untested. This
    drives a removal of a statistic-bearing line through `_track` directly and
    asserts it lands in `statistics_removed`, so the gate in
    `tools/diag/render_deletion_scan.py` and `/docpluck-qa` check 3c has a
    proven signal to key on.
    """
    report = R.RenderReport()
    report._track("_fake_step", "keep me\nM = 4.52\n", "keep me\n")
    assert [d["line"] for d in report.statistics_removed] == ["M = 4.52"]
    assert report.chars_delta < 0


def test_a_deletion_MERGED_WITH_A_REWRITE_is_still_reported():
    """The false NEGATIVE that a first version of `removed_lines` had.

    `_suppress_orphan_table_cell_text` italicises the caption (a rewrite) and
    drops the orphan rows beneath it (deletions) in ONE contiguous change, so
    difflib emits a single `replace` opcode covering both. A version that
    inspected only `delete` opcodes reported ZERO removals for four real ones.

    That direction matters more than the false positives the function was
    written to remove: `statistics_removed` is what consumers are told to
    check, and a field that silently under-reports is the exact failure this
    whole release is about.
    """
    report = R.RenderReport()
    R._step(
        report,
        "_suppress_orphan_table_cell_text",
        R._suppress_orphan_table_cell_text,
        _FURNITURE_RUN,
    )
    removed = {d["line"] for d in report.lines_removed}
    assert {"Target article", "Replication", "Study design"} <= removed


def test_a_pure_REWRITE_is_never_reported_as_a_removal():
    """The other direction — a gate that cries wolf gets ignored.

    `recover_corrupted_minus_signs` turning `[20.21, 0.04]` into
    `[-0.21, 0.04]` is a repair docpluck is entitled to make. An early `_track`
    used a substring test and reported 55 of these as deleted statistics on one
    corpus paper, while the scan reported none.
    """
    report = R.RenderReport()
    report._track("_fake_rewrite", "[20.21, 0.04]\n", "[-0.21, 0.04]\n")
    assert report.lines_removed == []
    assert report.statistics_removed == []


@pytest.mark.parametrize(
    "line", ["245", "12", "1,182", "(45)", "67%", "-3", "F(2, 42) = 5"]
)
def test_a_BARE_COUNT_is_data_too(line):
    """A table of COUNTS carries no decimal, no percent and no `label =` syntax.

    Found by an adversarial review (codex, 2026-08-14) and reproduced: `245` and
    `12` alone on their lines scored as FURNITURE under the first version of the
    guard, so a counts table sitting in a post-caption orphan run was still
    deletable — the exact shape this guard exists for, in the one flavour it
    could not see. `F(2, 42) = 5` was missed for a different reason: the
    labelled-statistic arm required `SYMBOL =` and did not allow the bracket.

    The asymmetry settles the tie: a false "this is data" costs one retained
    furniture line; a false "this is furniture" costs a published statistic.
    """
    assert R._carries_statistical_content(line), line


@pytest.mark.parametrize(
    "line",
    [
        "Target article", "Replication", "Study design", "Sample characteristics",
        "Positive", "Negative", "No of estimates", "Hypothesis", "Description",
        "1. Degree of apology", "Note: see text",
    ],
)
def test_widening_to_bare_counts_did_not_swallow_the_furniture_class(line):
    """The suppressors must keep working, or the guard has neutered the rule."""
    assert not R._carries_statistical_content(line), line


def test_phantom_stripper_is_NOT_vetoed_by_a_lone_digit():
    """The two situations that look alike and are not.

    `_suppress_orphan_table_cell_text` must treat a bare `245` as DATA — a
    counts table is nothing but bare integers, and the linearized cells are the
    only surviving copy. `_strip_phantom_camelot_tables` must NOT, because its
    input is already diagnosed as a Camelot mis-capture (masthead or absorbed
    prose in the `<th>`), so a lone digit inside it is wreckage.

    Measured on `10.1525/collabra.90203` Table 7: a degenerate prose grid whose
    only `<td>` numeral is `4` stopped being stripped when the bare-count arm
    was added, and `test_maier_t7_prose_header_not_in_any_table` caught it. That
    is a pre-existing regression test doing exactly its job against a change
    made four steps away from it.
    """
    lone = (
        "<table><thead><tr><th>JAMA Network Open | Public Health</th></tr></thead>"
        "<tbody><tr><td>4</td></tr></tbody></table>\n"
    )
    assert R._strip_phantom_camelot_tables(lone).strip() == ""
    # ...while a real measurement still vetoes the strip.
    real = (
        "<table><thead><tr><th>JAMA Network Open | Public Health</th></tr></thead>"
        "<tbody><tr><td>1.31 (1.20-1.44)</td></tr></tbody></table>\n"
    )
    assert "1.31 (1.20-1.44)" in R._strip_phantom_camelot_tables(real)
    # And the orphan-cell path keeps counting a bare integer as data.
    assert R._carries_statistical_content("245") is True
    assert R._carries_statistical_content("245", bare_number_counts=False) is False


# ── The INSTRUMENT is a shipped component and nothing tested it ────────────────
#
# Found 2026-08-15 by an independent review (Fable 5) and reproduced: after
# v2.4.130 rewrote the chain as `md = _step(_report, "name", fn, md)`, the
# release gate `tools/diag/render_deletion_scan.py` derived its step list with
# `^\s*md = (\w+)\(` and got exactly
#     ['_render_sections_to_markdown', '_step', '_rescue_title_from_layout']
# then bailed on `_step` because its first positional argument is the report,
# never a `str`. It instrumented ZERO of the 53 deleting steps and reported
# "26/26 papers, 0 deletions".
#
# The guard-test discipline in this file was never applied to the thing that
# certifies it. These three tests close that: they are the load-bearing tests
# for the gate, not for the guards.


def _scan():
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "diag"))
    import render_deletion_scan  # noqa: PLC0415

    return render_deletion_scan


def test_the_gate_sees_the_whole_chain_not_three_names():
    """A refactor of the call shape must turn this RED, not silently green.

    THE ASSERTION IS AGREEMENT BETWEEN TWO DERIVATIONS, NOT A MAGIC NUMBER
    (changed 2026-09-08). It used to read `len(names) >= 50`, and that floor could
    only ever be wrong in one of two ways: too low to catch a real blinding, or
    tripped by a DELIBERATE retirement. It was the second — retiring `W0g` took the
    chain from 50 to 49 and turned this red, and "lower the floor by one" is the
    move this project forbids, so the gate was made to express what it actually
    means instead. `f169c3d` had already removed three steps without re-basing it,
    which is how a fixed floor rots: it sat at exactly 50 against a chain of 50.

    The two derivations are independent in the way that matters. The gate reads the
    `_step` call's own string literal out of `render_pdf_to_markdown`'s source via
    `inspect`; this test greps the whole module for the call shape. The 2026-08-15
    failure was precisely a CALL-SHAPE change that the gate's regex stopped matching
    while the calls were all still there — it saw 3 where 53 existed — and that
    failure makes these two numbers disagree loudly instead of drifting quietly.
    """
    import re as _re
    from pathlib import Path as _Path

    names = _scan()._chain_step_names()

    src = _Path(__file__).resolve().parents[1] / "docpluck" / "render.py"
    # `_step\(` and NOT `_step\(_report,`: one call site in the chain wraps its
    # arguments onto the following line, so requiring `_report` on the same line
    # undercounts by exactly one and manufactures a disagreement out of formatting.
    call_sites = len(_re.findall(r"^\s*md = _step\(", src.read_text(encoding="utf-8"), _re.M))

    # An absolute floor STILL, because both derivations could collapse together if
    # `_step` itself were renamed, and two agreeing zeros must never read as a pass.
    # It is deliberately far below the live count so an ordinary retirement does not
    # trip it, and far above the 3 the 2026-08-15 defect produced.
    assert call_sites >= 30, (
        f"only {call_sites} `_step` call sites in render.py — the chain cannot have "
        "shrunk this far legitimately; either the call shape changed or this test's "
        "pattern is stale, and a zero here must never read as a clean corpus."
    )
    assert len(names) == call_sites, (
        f"the gate sees {len(names)} steps but render.py has {call_sites} `_step` call "
        f"sites. The gate instruments only what it can name, so a shortfall means it "
        f"is silently skipping steps — the exact defect of 2026-08-15, where it saw 3 "
        f"of 53 and reported '26/26 papers, 0 deletions'. Names seen: {names}"
    )
    assert "_step" not in names, "`_step` is the wrapper, not a step"
    assert "_rescue_title_from_layout" in names, (
        "the title rescue DELETES and must be instrumented"
    )


def test_the_gate_actually_records_a_deletion_driven_through_the_real_step():
    """Drive a statistic-deleting step through production's `_step` and assert
    the scan's instrumentation catches it. Without this, 'zero deletions' is a
    claim about the instrument (CLAUDE.md, 2026-08-15)."""
    scan = _scan()
    record: dict = {}
    originals = scan._instrument(record)
    try:
        before = "Some prose line that stays.\nM = 4.52, SD = 1.13, N = 245\nMore prose."
        after = "Some prose line that stays.\nMore prose."
        R._step(None, "_a_deleting_step", lambda md: after, before)
    finally:
        scan._uninstrument(originals)

    assert "_a_deleting_step" in record, (
        "the gate did not see a deletion that went through the real `_step`"
    )
    assert any("4.52" in ln for ln in record["_a_deleting_step"])


def test_the_gate_reports_nothing_for_a_legitimate_rewrite():
    """The other direction: an instrument that cries wolf gets switched off."""
    scan = _scan()
    record: dict = {}
    originals = scan._instrument(record)
    try:
        R._step(
            None, "_a_rewriting_step", lambda md: "[-0.21, 0.04]\n", "[20.21, 0.04]\n"
        )
    finally:
        scan._uninstrument(originals)
    assert record == {}, f"a pure rewrite was reported as a deletion: {record}"


def test_a_statistic_in_a_header_cell_vetoes_the_phantom_strip():
    """`<th>` as well as `<td>`.

    The Camelot mis-capture that produces a phantom table is exactly what puts
    body content into a header cell, so inspecting only `<td>` left the half of
    the table most likely to be corrupted unguarded (2026-08-15, Fable review).
    """
    block = (
        "<table><tr><th>HR 1.31 (1.20-1.44)</th></tr>"
        "<tr><td>some prose wreckage</td></tr></table>"
    )
    assert R._carries_statistical_content("HR 1.31 (1.20-1.44)")
    kept = R._strip_phantom_camelot_tables(block)
    assert "1.31" in kept, "a hazard ratio in a <th> was stripped with the block"


# ── The gate's first REAL run found 93 lines; two were instrument defects ─────
#
# With the gate fixed (see above), its first genuine pass over the 26-paper
# baseline reported 11 papers losing content — where the vacuous version had
# reported 0. Triaging that output exposed two comparison defects in
# `removed_lines` itself, both of which had been invisible for exactly as long
# as the gate had been blind. A scan that cries wolf gets ignored, so these are
# pinned as their own cases.


def test_an_indented_rewrite_is_not_a_removal():
    """Stripped-to-stripped comparison.

    `removed_lines` compared a STRIPPED source line against UNSTRIPPED output
    candidates, so indentation counted against similarity: `<td>20.09</td>` vs
    `    <td>-0.09</td>` scores 0.80 and fails the 0.9 cutoff. An ordinary W0d
    rewrite inside an indented table was therefore reported as 26 deleted
    statistics on `10.1177/19485506211056761`.
    """
    before = "    <td>20.09</td>\n    <td>21.15</td>"
    after = "    <td>-0.09</td>\n    <td>-1.15</td>"
    assert R.removed_lines(before, after) == []


def test_a_line_merged_into_a_longer_one_is_not_a_removal():
    """A REFLOW is not a deletion, and no similarity ratio can see it.

    The caption-join family merges a wrapped line into its neighbour. The text
    is present verbatim in the output, just not as its own line — and a short
    line compared against the long line containing it scores far below any
    useful cutoff, so 25 caption joins were reported as content loss.
    """
    before = "Figure 1. The effect of\ntreatment on outcome."
    after = "Figure 1. The effect of treatment on outcome."
    assert R.removed_lines(before, after) == []


def test_a_numbered_reference_block_is_not_an_author_affiliation():
    """IEEE/numbered bibliographies were being stripped as affiliation blocks.

    Found by the render-deletion gate on its FIRST genuine run (2026-08-15) —
    the gate had been instrumenting nothing, so this was invisible for as long
    as the guard had existed. Reproduced on `10.48550/arxiv.2406.11713`: seven
    reference entries deleted, because both arms of the citation guard were
    APA-shaped and a numbered entry carries neither a parenthesised year nor a
    `Surname, A.` opener.
    """
    refs = [
        '[5] A. Ramesh, P. Dhariwal, and M. Chen, "Hierarchical text-conditional '
        'image generation with clip latents", ArXiv preprint, 2022. 2',
        '[21] P. Dhariwal and A. Nichol, "Diffusion models beat gans on image '
        'synthesis", CoRR, arXiv:2105.05233, 2021. 2',
        '[23] A. Jolicoeur-Martineau, K. Li, and I. Mitliagkas, "Gotta go fast '
        'when generating data with score-based models", 2021. 3',
    ]
    for line in refs:
        assert R._is_affiliation_line(line) is False, f"reference read as affiliation: {line[:60]}"

    # ...and the guard must not have been widened into uselessness.
    for line in [
        "Department of Psychology, University of Hong Kong, Hong Kong",
        "School of Business, Renmin University of China, Beijing, China",
    ]:
        assert R._is_affiliation_line(line) is True, f"real affiliation missed: {line}"


def test_a_caption_overhang_is_deduplicated_not_deleted():
    """The superset branch dropped an inline caption LONGER than the block copy.

    The module's own docstring promises the opposite — "an inline run that
    EXCEEDS the block caption is left untouched so no caption text can be lost"
    — and the FIG-3c-2 branch, added later, discarded the difference.

    Measured on `10.1109/access.2025.3645087` Figure 5 by the render-deletion
    gate the moment it could see anything: the inline copy ran 121 characters
    longer and the tail — a methods parameter, "…at a time step of 20 PN time
    steps per unit time per 1 ODE time interval." — appeared NOWHERE in the
    output. L-032: dedup is legitimate only when a copy demonstrably survives,
    and here the surviving copy was strictly smaller.

    The survivor is now EXTENDED with the overhang before the copy is dropped,
    so the drop is a real deduplication.
    """
    text = "\n".join([
        "### Figure 5",
        "",
        "*Figure 5: Comparison of rounding methods on simulated data. The legend "
        "applies to all figures.*",
        "",
        "## Results",
        "",
        "Figure 5: Comparison of rounding methods on simulated data. The legend "
        "applies to all figures. All comparisons used a time step of 20 units.",
        "",
    ])
    out = R._suppress_inline_duplicate_figure_captions(text)
    assert "a time step of 20 units" in out, "the caption overhang was deleted"
    assert out.count("Comparison of rounding methods") == 1, "the copy was not deduplicated"


def test_a_line_extended_in_place_is_not_a_removal():
    """`*A*` -> `*A B*` keeps every character of `A`.

    The closing emphasis marker defeats a raw substring test, and the length
    change pushes the pair below the 0.9 similarity cutoff — so an EXTENSION
    read as a deletion. Found while triaging the caption fix above.
    """
    before = "*Figure 5: a long caption here about several things*"
    after = "*Figure 5: a long caption here about several things and more text.*"
    assert R.removed_lines(before, after) == []
