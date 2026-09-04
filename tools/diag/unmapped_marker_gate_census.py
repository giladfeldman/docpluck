"""What does the grid-validity gate actually SEE, now that the marker changed spelling?

Backlog row: todo.md W-0015 (the correction section).
Findings:    docs/FINDINGS_2026-09-02_table_channel_destroys_minus_signs.md

`whitespace._whitespace_grid_is_clean` promises, in its own docstring, that "NO cell may
carry an unmapped-glyph marker ((cid:N) / U+FFFD) -- one occurrence condemns the grid."
Its marker pattern is

    _UNMAPPED_GLYPH_RE = re.compile(r"\\(cid:\\d+\\)|�")

and `camelot_extract.py:715` calls that gate on CAMELOT region-path cells, which under
Camelot 2.0 / playa carry a raw NUL rather than `(cid:N)`. So on that path the gate cannot
keep its own promise. This scan measures how much that costs, BEFORE anything is changed,
because widening the pattern changes which grids are ACCEPTED -- a capture-path change,
whose failure mode is a rejected grid falling back to a caption stub, i.e. TEXT LOSS.

WHAT IT COUNTS, per corpus paper, at the moment the gate runs:

    cells_seen          how many cells the gate judged at all (the denominator; without
                        it a zero below is a claim about whether the gate ran)
    already_matched     cells the gate DOES see today -- `(cid:N)` or U+FFFD present
    invisible_nul       cells carrying a raw NUL that the gate CANNOT see
    invisible_repairable  of those, ones W0r would have repaired anyway (a NUL before a
                        digit) -- these are NOT evidence for widening the pattern, since
                        the gate judges the repaired view and there is nothing left to
                        condemn
    invisible_residual  of those, ones W0r leaves alone -- a NUL mid-token, the
                        `[(cid:0)ra00m..er's,V` shape the gate exists to catch. **THIS is
                        the number that decides it.** Zero means widening the pattern is
                        inert today and safe to land for correctness alone; non-zero means
                        every site must be read before any grid is newly rejected.

A SHIPPED-OUTPUT ZERO CANNOT ANSWER THIS QUESTION, which is why this scan exists rather
than a grep of the rendered corpus: a grid the gate condemned never ships, so counting
markers in the .md measures survivors only.

A ZERO IS A CLAIM ABOUT THE INSTRUMENT. If `cells_seen` is 0 the gate never ran on this
corpus and every other count is meaningless, so the scan says so and exits non-zero.

Usage:
    python tools/diag/unmapped_marker_gate_census.py
    python tools/diag/unmapped_marker_gate_census.py --limit 5
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import time

# W-0011: without this insert, `import docpluck` in a tools/ script resolves to the
# INSTALLED release and every number printed would describe site-packages, not the tree.
_REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, _REPO)

import docpluck  # noqa: E402
from docpluck.tables import whitespace as _ws  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _corpus import baseline_corpus, coverage_line  # noqa: E402

NUL = "\x00"
_REPAIRABLE_RE = re.compile(r"(?:\(cid:0\)|\x00)[ \t]*(?=\d)")
# docpluck's own placeholders are NOT font markers. They should not exist this early in
# the pipeline, but counting them separately is cheaper than assuming they do not.
_PLACEHOLDER_RE = re.compile(r"\x00(?:BR|SUP|/SUP)\x00")


def _banner() -> None:
    print("docpluck module :", docpluck.__file__)
    if _REPO.lower() not in os.path.abspath(docpluck.__file__).lower():
        print("!! REFUSING: docpluck did not resolve to the working tree (W-0011).")
        raise SystemExit(2)
    print("docpluck version:", docpluck.__version__)
    print()


class Counts:
    def __init__(self) -> None:
        self.cells_seen = 0
        self.already_matched = 0
        self.invisible_repairable = 0
        self.invisible_residual = 0
        self.placeholder = 0
        self.samples: list[str] = []

    def observe(self, text: str) -> None:
        self.cells_seen += 1
        if _ws._UNMAPPED_GLYPH_RE.search(text):
            self.already_matched += 1
        placeholders = _PLACEHOLDER_RE.findall(text)
        if placeholders:
            self.placeholder += 1
        body = _PLACEHOLDER_RE.sub("", text)
        if NUL not in body:
            return
        if _REPAIRABLE_RE.search(body):
            self.invisible_repairable += 1
        else:
            self.invisible_residual += 1
            if len(self.samples) < 8:
                self.samples.append(text[:110])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()

    _banner()
    papers = baseline_corpus(limit=args.limit)
    print(coverage_line())
    print()

    total = Counts()
    original = _ws._whitespace_grid_is_clean

    def spy(cells, *a, **kw):
        # Judge the SAME text the gate judges -- its repaired view -- so this census
        # cannot disagree with the gate about what a cell says.
        try:
            rep = _ws._repaired_view(cells)
            for c in cells:
                total.observe(rep.get((c["r"], c["c"]), c.get("text") or ""))
        except Exception as exc:  # an instrument failure is NOT a zero
            print(f"    !! census hook failed: {type(exc).__name__}: {exc}")
        return original(cells, *a, **kw)

    _ws._whitespace_grid_is_clean = spy
    # The gate is imported INSIDE camelot_extract's function body, so patching the
    # module attribute is enough; there is no module-level alias holding the original.
    try:
        for key, path in papers:
            before = total.cells_seen
            t0 = time.time()
            from docpluck.render import render_pdf_to_markdown

            md = render_pdf_to_markdown(open(path, "rb").read())
            if isinstance(md, tuple):
                md = md[0]
            print(f"  {key:<44} cells_judged={total.cells_seen - before:<6} "
                  f"{time.time() - t0:5.1f}s")
    finally:
        _ws._whitespace_grid_is_clean = original

    print()
    print(f"cells the gate JUDGED                         : {total.cells_seen}")
    print(f"  cells it ALREADY sees ((cid:N) / U+FFFD)    : {total.already_matched}")
    print(f"  cells carrying a docpluck placeholder       : {total.placeholder}")
    print(f"  INVISIBLE raw NUL, repairable by W0r        : {total.invisible_repairable}")
    print(f"  INVISIBLE raw NUL, RESIDUAL (decides it)    : {total.invisible_residual}")
    for s in total.samples:
        print(f"      {s!r}")
    print()
    if total.cells_seen == 0:
        print("VERDICT: INSTRUMENT FAILURE - the gate never ran on this corpus, so every "
              "count above is meaningless. Do not read this as a clean result.")
        return 2
    if total.invisible_residual:
        print(f"VERDICT: {total.invisible_residual} cell(s) carry a marker the gate cannot "
              "see and W0r does not repair. READ EACH ONE before widening the pattern - "
              "widening it REJECTS those grids, and a rejected grid falls back to a stub.")
        return 1
    print("VERDICT: widening the pattern would be INERT on this corpus - no cell reaches "
          "the gate carrying an unrepairable NUL. Safe to land for correctness alone; it "
          "closes a promise the gate's own docstring makes and cannot currently keep.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
