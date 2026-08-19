"""What do v2.4.134's three TEXT-LOSS fixes actually change, table by table?

Three capture-path changes landed together, each closing an `xfail(strict)` that
pinned gold-verified text loss:

    caption_clip   `detect._column_runs` clips a caption's char row to the COLUMN
                   RUN carrying it. A y-row on a two-column page also holds the
                   neighbouring column's body line, so min(x0)/max(x1) over the whole
                   row gave a caption bbox spanning both columns and the region built
                   from it swallowed that column's prose.
    row_cluster    `whitespace._cluster_into_rows` measures the y-gap to the row's
                   ANCHOR, not to the previous WORD. (A continuation re-merge was
                   built alongside it and DELETED before release because it chained
                   — see the register section J4. This line described it as shipped
                   for several hours after it was removed, which is the exact
                   stale-claim class this repo polices; caught by a reviewer.)
    prose_guard    `extract_structured` rejects a capture candidate that is running
                   body PROSE before `_pick_better_table` arbitrates on shape.

This project's history says a capture-path change is net-harmful unless it is gated
by a corpus-wide before/after. So: extract every corpus paper TWICE in one process —

    arm A   the shipped code
    arm B   all three changes neutralised at their call sites (a single-run
            `_column_runs`, the retired previous-word clustering, a
            `grid_is_body_prose` that never fires)

— and compare the only thing that matters: how much table CONTENT each caption ends
up with. `--isolate <name>` neutralises just one change, so a regression can be
attributed to the fix that caused it rather than to the release.

THIS IS A SCREEN, NOT AN ORACLE — and that correction is itself a finding. The first
version printed `VERDICT: FAIL - content regressed` whenever a table lost cells, and
on the 2026-08-19 run it flagged 5 tables. **Every one turned out to be an
improvement**, and the reasons are worth writing down because they are the reasons a
cell count cannot answer the question this tool is asking:

    10.1016/j.joep.2020.102350 T1   -2 cells: the running header `I. Ziano et al.`
                                    and the journal footer left the grid. FURNITURE.
    10.1016/j.jesp.2009.12.010 T3   4 cells -> 0, raw_text 148 -> 345. The 4 cells
                                    were fused (`4.603.804.80`) and missing a whole
                                    condition row; the fallback carries all 12 values.
    10.1177/01461672251327169 T3/T4 same shape: a fused 2-column rendering of a
                                    4-column table (`104594` is two numbers glued)
                                    replaced by text carrying twice as much.
    10.48550/arxiv.2406.11713  T5   18 cells -> 14: the 18 were half body prose
                                    interleaved with the table.

So a flag means **go and look**, never "this regressed". Cell count falls legitimately
when furniture is dropped, when content moves from `cells` to `raw_text`, and when a
fused grid is replaced by cleaner text. No counter separates those from a real loss —
that is what the AI-gold canary is for. The tool therefore reports FLAGGED tables and
exits non-zero so they cannot be skipped, and the adjudication goes in the register.

A ZERO IS A CLAIM ABOUT THE INSTRUMENT: if `arms_differ` is 0 the two arms are the
same code and the scan measured nothing, so it says so and exits non-zero.

WHAT THIS SCAN CANNOT SEE, stated so a PASS is not read as more than it is: it
compares cell COUNT and raw_text LENGTH, never cell CONTENT. A table that keeps all
70 of its cells while their text changes scores as unchanged here. Content correctness
is the AI-gold canary's job (`article-finder` `reading` view), not this tool's; this
tool answers exactly one question — did a capture-path change make table content
DISAPPEAR — and that is the question this project's history says a capture-path change
must answer before it ships.

Usage:
    python tools/diag/table_capture_guard_diff.py                    # baseline corpus
    python tools/diag/table_capture_guard_diff.py --sample 60        # wider denominator
    python tools/diag/table_capture_guard_diff.py --isolate row_cluster
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.diag._corpus import baseline_corpus, coverage_line, sampled_corpus  # noqa: E402
from tools.diag.row_cluster_census import _cluster_prev_word  # noqa: E402

from docpluck import extract_structured as ES  # noqa: E402
from docpluck.tables import detect as DET  # noqa: E402
from docpluck.tables import whitespace as WS  # noqa: E402

CHANGES = ("caption_clip", "row_cluster", "prose_guard")


def _neutralise(names: tuple[str, ...]) -> list[tuple[Any, str, Any]]:
    """Patch the named changes back to their pre-v2.4.134 behaviour. Returns undo info."""
    undo: list[tuple[Any, str, Any]] = []
    if "caption_clip" in names:
        undo.append((DET, "_column_runs", DET._column_runs))
        DET._column_runs = lambda row_chars: [list(row_chars)]
    if "row_cluster" in names:
        undo.append((WS, "_cluster_into_rows", WS._cluster_into_rows))
        WS._cluster_into_rows = _cluster_prev_word
    if "prose_guard" in names:
        undo.append((ES, "grid_is_body_prose", ES.grid_is_body_prose))
        ES.grid_is_body_prose = lambda cells: False
    return undo


def _restore(undo: list[tuple[Any, str, Any]]) -> None:
    for mod, name, orig in reversed(undo):
        setattr(mod, name, orig)


def _profile(pdf_bytes: bytes) -> dict[str, tuple[int, int, int]]:
    """{label: (populated_cells, len(raw_text), content_chars)} for one document.

    ``content_chars`` is the MAX of the two channels, not their sum: a Camelot table
    carries the same text in both, so summing would double-count it and make a move
    between channels look like a gain or a loss depending on which way it went.
    """
    out: dict[str, tuple[int, int, int]] = {}
    res = ES.extract_pdf_structured(pdf_bytes)
    for t in res.get("tables") or []:
        label = t.get("label") or f"?{t.get('id')}"
        texts = [(c.get("text") or "").strip() for c in (t.get("cells") or [])]
        cells = sum(1 for x in texts if x)
        raw = len((t.get("raw_text") or "").strip())
        out[label] = (cells, raw, max(len(" ".join(x for x in texts if x)), raw))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", type=int, default=None)
    ap.add_argument("--limit", type=int, default=None,
                    help="first N baseline papers only (smoke-test the harness)")
    ap.add_argument("--isolate", choices=CHANGES, default=None,
                    help="neutralise only this change in arm B")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    names = (args.isolate,) if args.isolate else CHANGES
    corpus = sampled_corpus(args.sample) if args.sample else baseline_corpus(args.limit)
    print(coverage_line())
    print(f"ARM B neutralises: {', '.join(names)}")
    print()

    papers = tables = 0
    cells_gained = cells_lost = 0
    tables_gained = 0
    content_lost = 0
    flagged: list[str] = []
    arms_differ = 0

    for key, pdf in corpus:
        try:
            data = pdf.read_bytes()
        except OSError:
            continue
        try:
            arm_a = _profile(data)
            undo = _neutralise(names)
            try:
                arm_b = _profile(data)
            finally:
                _restore(undo)
        except Exception as exc:
            print(f"  !! {key}: {type(exc).__name__}: {exc}")
            continue
        papers += 1
        if arm_a != arm_b:
            arms_differ += 1
        for label in sorted(set(arm_a) | set(arm_b)):
            tables += 1
            a_cells, a_raw, a_content = arm_a.get(label, (0, 0, 0))
            b_cells, b_raw, b_content = arm_b.get(label, (0, 0, 0))
            if a_cells > b_cells:
                cells_gained += a_cells - b_cells
                tables_gained += 1
                if args.verbose:
                    print(f"  + {key} {label}: cells {b_cells} -> {a_cells}, "
                          f"content {b_content} -> {a_content} chars")
            # FLAG, not verdict. See the module docstring: a cell count falls
            # legitimately when furniture is dropped, when content moves between
            # `cells` and `raw_text`, and when a fused grid is replaced by cleaner
            # text. Every flag is a table to OPEN.
            if a_cells < b_cells or a_content < b_content:
                cells_lost += max(0, b_cells - a_cells)
                content_lost += max(0, b_content - a_content)
                flagged.append(
                    f"  ? {key} {label}: cells {b_cells} -> {a_cells}, "
                    f"raw_text {b_raw} -> {a_raw}, content {b_content} -> {a_content} chars"
                )

    for line in flagged:
        print(line)
    print()
    print(f"papers extracted (both arms) : {papers}")
    print(f"captions compared            : {tables}")
    print(f"papers where the arms DIFFER : {arms_differ}")
    if arms_differ == 0:
        print("\nA ZERO HERE IS A CLAIM ABOUT THE INSTRUMENT: the two arms produced "
              "identical output on every paper, so either the patches did not take "
              "effect or this corpus contains no affected paper. This run proves "
              "nothing about the fixes.")
        return 1
    print(f"tables that GAINED cells     : {tables_gained}  (+{cells_gained} cells)")
    print(f"tables FLAGGED for inspection: {len(flagged)}  (-{cells_lost} cells, "
          f"-{content_lost} content chars)")
    if not flagged:
        print("\nCLEAN: no table lost cells or content anywhere in the corpus.")
        return 0
    print(
        "\nREVIEW REQUIRED: the flags above are tables to OPEN, not regressions. "
        "A cell count falls legitimately when page furniture leaves the grid, when "
        "content moves from `cells` to `raw_text`, and when a fused grid is replaced "
        "by cleaner text — see the module docstring for four measured examples of "
        "exactly that. Adjudicate each against the page and record the verdict; do "
        "NOT read this exit code as 'the change regressed'."
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
