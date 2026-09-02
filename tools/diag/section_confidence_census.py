#!/usr/bin/env python3
"""Does `Section.confidence` carry information, or is it a constant with three names?

Scimeto measured **17 of 17** detected `references` sections at `confidence=high`
and `detected_via=heading_match` -- including one whose span was a
data-availability statement, not a reference list -- and concluded: *"The field
carries no discriminating information at the moment, so a consumer cannot use it
to gate on."* (`INBOX_FROM_SCIMETO_2026-08-21b_flatten_typing_and_sections.md`
§2, 2026-08-21.)

That is a claim about ONE label over 18 papers. This scan measures the
denominator, per the standing rule that one observation proves a shape exists and
says nothing about how often. It reports, over a real corpus:

  - the distribution of `confidence` over every emitted section;
  - the distribution over the subset a consumer actually gates on
    (`references`, `methods`, `results`, `discussion`);
  - the joint distribution with `detected_via`, because the two are computed
    from the same `BlockHint` and may be the same signal twice;
  - how many PAPERS emit more than one distinct confidence value at all -- a
    field that never varies WITHIN a document cannot rank that document's
    sections, whatever its corpus-level spread.

A field that turns out not to discriminate is not automatically a defect; it is
a documentation obligation, and a reason to give consumers something that does.

Usage:
    python tools/diag/section_confidence_census.py --baseline
    python tools/diag/section_confidence_census.py --sample 40
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.diag._corpus import (  # noqa: E402
    CorpusUnavailable,
    baseline_corpus,
    coverage_line,
    sampled_corpus,
)

from docpluck.sections import extract_sections  # noqa: E402

# The labels a consumer gates on: the ones that decide what text gets parsed.
GATED = ("references", "methods", "results", "discussion", "abstract", "introduction")


def main() -> int:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--baseline", action="store_true")
    g.add_argument("--sample", type=int, metavar="N")
    args = ap.parse_args()

    try:
        papers = baseline_corpus() if args.baseline else sampled_corpus(args.sample)
    except CorpusUnavailable as exc:
        print(exc)
        return 2

    print(coverage_line())
    print()

    overall: Counter[str] = Counter()
    gated: Counter[str] = Counter()
    joint: Counter[tuple[str, str]] = Counter()
    per_paper_variety: Counter[int] = Counter()
    papers_scanned = 0

    for key, path in papers:
        try:
            doc = extract_sections(file_bytes=path.read_bytes())
        except Exception as exc:
            print(f"  !! {key}: {type(exc).__name__}: {exc}")
            continue
        papers_scanned += 1
        seen: set[str] = set()
        for s in doc.sections:
            c = s.confidence.value
            overall[c] += 1
            joint[(c, s.detected_via.value)] += 1
            seen.add(c)
            if s.canonical_label.value in GATED:
                gated[c] += 1
        per_paper_variety[len(seen)] += 1

    if not papers_scanned:
        print("no paper produced a measurement -- this is UNBOUNDED, not clean")
        return 2

    total = sum(overall.values())
    print(f"papers scanned : {papers_scanned}")
    print(f"sections       : {total}\n")

    print("confidence, ALL sections:")
    for c, n in overall.most_common():
        print(f"  {c:<8} {n:>6}  {n / total:6.1%}")

    gt = sum(gated.values())
    print(f"\nconfidence, sections a consumer GATES on ({', '.join(GATED)}): {gt}")
    for c, n in gated.most_common():
        print(f"  {c:<8} {n:>6}  {n / gt:6.1%}" if gt else f"  {c:<8} {n:>6}")

    print("\njoint (confidence, detected_via):")
    for (c, v), n in joint.most_common():
        print(f"  {c:<8} {v:<24} {n:>6}")

    print("\ndistinct confidence values WITHIN one paper:")
    for k in sorted(per_paper_variety):
        print(f"  {k} value(s): {per_paper_variety[k]} papers")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
