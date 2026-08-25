#!/usr/bin/env python3
"""How often does the standalone-page-number strip delete a PUBLISHED VALUE?

`normalize.py::_strip_standalone_page_numbers` deletes every line whose entire
content is a bare 1-3 digit integer:

    _PAGE_NUMBER_LINE_RE = re.compile(r"^(\\f*)[ \\t]*\\d{1,3}[ \\t]*$", re.MULTILINE)

A page number matches. So does a TABLE CELL holding a small whole number, which
is what pdftotext emits for a narrow numeric column: one cell per line. The rule
is therefore silently selective -- `-4`, `0.5` and `1000` survive; `0`, `4` and
`999` do not.

FOUND ON A REAL PAPER, NOT CONSTRUCTED. `10.1136/bmj-2024-080924` (BMJ),
supplementary appendix Table S1, row "Number of Advancement Maneuvers
(attempt #2)": the printed coefficient is `0`, its interval `(-1.5 to 1.5)` and
its p-value `0.999`. docpluck delivers the interval and the p-value with NO
coefficient -- the consumer receives a confidence interval attached to nothing,
which is worse than a wrong number because there is nothing to challenge.

This scan measures the DENOMINATOR, per the standing rule that one real paper
proves a shape EXISTS and says nothing about how often. It classifies every
matching line by its TYPOGRAPHIC position, never by what the number "ought" to
be:

  FURNITURE  the line sits at the extreme top or bottom of its page (a page
             number is drawn in the margin, so it is first or last on the page)
  INTERIOR   the line sits in the body of a page, surrounded by content -- the
             shape that cannot be a page number

INTERIOR sites are reported with their neighbours so a reader can see what the
deletion costs. Sites whose neighbourhood carries statistical content (an
interval, a p-value, another numeric cell) are counted separately, because those
are the ones that reach a meta-science consumer as a hole.

Usage:
    python tools/diag/page_number_strip_blast_radius.py [--baseline | --sample N]
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.diag._corpus import (  # noqa: E402
    CorpusUnavailable,
    baseline_corpus,
    coverage_line,
    sampled_corpus,
)

from docpluck.extract import extract_pdf  # noqa: E402
from docpluck.normalize import _PAGE_NUMBER_LINE_RE  # noqa: E402

# The SHIPPED pattern is imported, never retyped -- a scan that measures a copy
# of the rule measures the copy.
_BARE = re.compile(_PAGE_NUMBER_LINE_RE.pattern.replace("(\\f*)", "\\f*"))

# Neighbourhood evidence that a deleted bare integer sat among DATA. Kept
# deliberately narrow and typographic: a parenthesised or bracketed interval, a
# p-value, or another numeric cell standing alone.
_INTERVAL = re.compile(r"[\(\[]\s*-?\d[\d.,]*\s*(?:to|,|;|-|--|–)\s*-?\d[\d.,]*\s*[\)\]]")
_PVALUE = re.compile(r"(?<![A-Za-z])[pP]\s*[<>=≤≥]|^\s*[<>]?\s*0?\.\d+\s*$")
_NUMERIC_CELL = re.compile(r"^\s*[-−]?\d[\d.,]*\s*(?:\([^)]*\))?\s*$")

# How many non-blank lines at each end of a page count as the margin band. A
# page number can be preceded by a running footer, so 1 is too tight.
_EDGE_BAND = 2


def _pages(text: str) -> list[list[str]]:
    return [p.split("\n") for p in text.split("\f")]


def _classify_page(lines: list[str]) -> list[tuple[int, str, str]]:
    """Return (index, verdict, line) for every bare-integer line on one page."""
    nonblank = [i for i, ln in enumerate(lines) if ln.strip()]
    head = set(nonblank[:_EDGE_BAND])
    tail = set(nonblank[-_EDGE_BAND:])
    out = []
    for i, ln in enumerate(lines):
        if not _BARE.fullmatch(ln):
            continue
        out.append((i, "FURNITURE" if (i in head or i in tail) else "INTERIOR", ln))
    return out


def _neighbourhood(lines: list[str], i: int, radius: int = 6) -> list[str]:
    lo, hi = max(0, i - radius), min(len(lines), i + radius + 1)
    return [lines[j].strip() for j in range(lo, hi) if j != i and lines[j].strip()]


def _looks_like_data(neighbours: list[str]) -> bool:
    """True when the window carries a STATISTIC, not merely another number.

    Deliberately stricter than "a numeric neighbour": a numbered figure-step
    list (`01`, `02`, ...) also puts bare integers next to each other, and
    counting those inflates the number that matters. An interval or a p-value
    is what makes the deletion reach a meta-science consumer as a hole.
    """
    stat = sum(bool(_INTERVAL.search(ln) or _PVALUE.search(ln)) for ln in neighbours)
    cells = sum(bool(_NUMERIC_CELL.fullmatch(ln)) for ln in neighbours)
    return stat >= 1 and (stat + cells) >= 2


def main() -> int:
    # A diagnostic that dies on an un-encodable glyph reports NOTHING, which
    # reads exactly like a clean corpus. Real papers carry math-italic and
    # Greek codepoints the Windows console cannot encode.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass

    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--baseline", action="store_true", help="docpluck's render-baseline corpus")
    g.add_argument("--sample", type=int, metavar="N", help="N papers sampled from the repository")
    ap.add_argument("--seed", type=int, default=20260822)
    ap.add_argument("--show", type=int, default=8, help="max INTERIOR sites to print per paper")
    ap.add_argument("--pdf", action="append", default=[], help="scan an explicit PDF path")
    args = ap.parse_args()

    if args.pdf:
        papers = [(Path(p).stem, Path(p)) for p in args.pdf]
    else:
        try:
            papers = (
                sampled_corpus(args.sample, seed=args.seed)
                if args.sample
                else baseline_corpus()
            )
        except CorpusUnavailable as e:
            print(e, file=sys.stderr)
            return 2

    tot_furniture = tot_interior = tot_data = 0
    papers_with_interior = papers_with_data = 0

    for key, pdf in papers:
        try:
            raw = extract_pdf(pdf.read_bytes())
            raw = raw[0] if isinstance(raw, tuple) else raw
        except Exception as e:  # a paper we cannot read is reported, never skipped silently
            print(f"{key}: EXTRACT FAILED ({type(e).__name__}: {e})")
            continue

        furniture = interior = data = 0
        shown = 0
        for lines in _pages(raw):
            for i, verdict, ln in _classify_page(lines):
                if verdict == "FURNITURE":
                    furniture += 1
                    continue
                interior += 1
                nb = _neighbourhood(lines, i)
                is_data = _looks_like_data(nb)
                data += is_data
                if shown < args.show:
                    shown += 1
                    tag = "DATA" if is_data else "interior"
                    print(f"  {key} [{tag}] deleted {ln.strip()!r} | near: {nb[:4]}")

        tot_furniture += furniture
        tot_interior += interior
        tot_data += data
        papers_with_interior += interior > 0
        papers_with_data += data > 0
        print(f"{key}: furniture={furniture} interior={interior} data-adjacent={data}")

    n = len(papers)
    print()
    print(f"papers scanned            : {n}")
    print(f"page-number sites (furniture): {tot_furniture}")
    print(f"INTERIOR sites (not a page number): {tot_interior} in {papers_with_interior} papers")
    print(f"  of those, DATA-adjacent : {tot_data} in {papers_with_data} papers")
    if not args.pdf:
        print(coverage_line())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
