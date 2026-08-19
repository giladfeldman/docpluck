"""How many SHIPPED tables carry verified per-cell geometry, and why do the rest not?

Register A1 / G6a. ``tables/cell_geometry.py`` refuses to emit geometry it cannot
verify, which is the right default and also the exact shape of a measurement that
can quietly describe the INSTRUMENT: a census reporting "0 refusals" over a
corpus holding no rotated page says nothing about rotated pages.

So this scan runs the PRODUCTION path (``extract_pdf_structured``) and reports,
over the tables docpluck actually ships:

  * how many carry ``cell_geometry == "verified:<fraction>"``,
  * every refusal reason with its count -- so a refusal class that grows is
    visible rather than inferred,
  * the distribution of verified fractions, so the ``TABLE_PASS_FRACTION``
    threshold can be re-argued against data instead of memory.

**Read the refusal counts as the finding, not the pass rate.** A high pass rate
over a corpus with no rotated pages and no prose-mis-captured-as-table would be
uninformative; the baseline has both, measured, which is why it is the corpus.

Usage:
    python tools/diag/cell_geometry_census.py                # 26-paper baseline
    python tools/diag/cell_geometry_census.py --sample 60    # wider denominator
"""

from __future__ import annotations

import argparse
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from tools.diag._corpus import baseline_corpus, coverage_line, sampled_corpus  # noqa: E402

from docpluck.extract_structured import extract_pdf_structured  # noqa: E402
from docpluck.tables.cell_geometry import TABLE_PASS_FRACTION  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", type=int, default=0,
                    help="sample N papers from the repository instead of the baseline")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--examples", type=int, default=10)
    args = ap.parse_args()

    papers = sampled_corpus(args.sample) if args.sample else baseline_corpus(limit=args.limit)
    print(coverage_line())
    print(f"threshold: TABLE_PASS_FRACTION = {TABLE_PASS_FRACTION}\n")

    reasons: Counter[str] = Counter()
    fractions: list[float] = []
    zero_bbox_on_verified = 0
    tables = 0
    examples: list[str] = []

    for key, path in papers:
        try:
            result = extract_pdf_structured(path.read_bytes())
        except Exception as exc:  # noqa: BLE001
            print(f"  !! {key}: {type(exc).__name__}: {exc}")
            continue
        for t in result.get("tables", []) or []:
            tables += 1
            reason = t.get("cell_geometry") or "absent"
            head = reason.split(":", 1)[0]
            reasons[head] += 1
            if head == "verified":
                try:
                    fractions.append(float(reason.split(":", 1)[1]))
                except (IndexError, ValueError):
                    pass
                # A verified table whose cells are all zeros would be the
                # all-clear that means nothing -- the instrument-zero this file
                # exists to make visible.
                cells = t.get("cells") or []
                if cells and all(tuple(c.get("bbox") or ()) == (0.0, 0.0, 0.0, 0.0) for c in cells):
                    zero_bbox_on_verified += 1
                    if len(examples) < args.examples:
                        examples.append(f"    ZERO-BBOX ON VERIFIED: {key} {t.get('id')} {t.get('label')}")
            elif len(examples) < args.examples:
                examples.append(f"    {head:28s} {key} {t.get('id')} p{t.get('page')} {reason}")

    print(f"shipped tables: {tables}\n")
    for reason, n in reasons.most_common():
        pct = 100.0 * n / tables if tables else 0.0
        print(f"  {reason:32s} {n:5d}  ({pct:5.1f}%)")

    if fractions:
        fractions.sort()
        n = len(fractions)
        q = lambda f: fractions[min(n - 1, int(f * n))]  # noqa: E731
        print(f"\nverified fractions: min={fractions[0]:.2f} p05={q(0.05):.2f} "
              f"median={q(0.5):.2f} mean={sum(fractions)/n:.2f}")

    if zero_bbox_on_verified:
        print(f"\n!! {zero_bbox_on_verified} table(s) reported VERIFIED but carry only zero bboxes "
              f"-- a false all-clear; the guard passed on geometry that is not there")

    if examples:
        print("\nexamples:")
        for e in examples:
            print(e)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
