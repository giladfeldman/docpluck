"""How often does a table cell GLUE two published numbers into one?

Camelot's column segmentation sometimes swallows a real inter-column gap, so two
values printed side by side arrive as a single token with no separator:

    10.1177/01461672251327169 T3   '104594'        sample sizes 104 and 594
    10.1016/j.jesp.2009.12.010 T3  '4.603.804.80'  4.60, 3.80, 4.80
    10.48550/arxiv.2406.11713 T5   '5.210.40Ours0.55 (*)'

This is the WRONG-NUMBER class: a consumer parses `104594` as a sample size the paper
never printed, and nothing about the output announces the fusion. By this project's
ranking that is worse than a deletion, which is why it needs a denominator before
anyone argues about priority — **one paper proves the shape exists and says nothing
about how often** (the 2026-08-15 directive).

WHAT THIS SCAN IS AND IS NOT. It is a PREVALENCE MEASUREMENT, not a repair and not a
detector fit for shipping. The signatures below are deliberately high-precision and
therefore UNDERCOUNT: the commonest fusion — two plain integers, `104` + `594` ->
`104594` — is indistinguishable from a genuine six-digit number in text alone, so it
is NOT counted here at all. Read every number this prints as a FLOOR.

That undercount is the finding, not a limitation to apologise for: it is the argument
that a shippable detector needs the LAYOUT channel (pdfplumber char x-gaps proving the
gap Camelot swallowed), which is register G6a and deliberately open.

Signatures, each requiring evidence no legitimate value would carry:

    MULTIDOT   a numeric token with >=2 decimal points and >=8 characters
               (`4.603.804.80`). Length excludes version strings like `1.2.3`.
    DIGIT_WORD a digit immediately followed by a capitalised word, then a digit
               (`0.40Ours0.55`) - a value, a label and a value with no separator.
    SENT_DIGIT a sentence-ending letter immediately followed by a numbered list item
               (`argument1. Received`) - two list cells glued.

Usage:
    python tools/diag/fused_cell_census.py                # 26-paper baseline
    python tools/diag/fused_cell_census.py --sample 60    # wider denominator
    python tools/diag/fused_cell_census.py --examples 40
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.diag._corpus import baseline_corpus, coverage_line, sampled_corpus  # noqa: E402

from docpluck.extract_structured import extract_pdf_structured  # noqa: E402

# >=2 decimal points inside one numeric run, at least 8 chars long.
_MULTIDOT = re.compile(r"(?<!\d)\d{1,4}(?:\.\d{1,4}){2,}(?!\d)")
# A number, then a capitalised word glued to it, then another number.
_DIGIT_WORD = re.compile(r"\d[A-Z][a-z]{2,}\d")
# `...argument1. Received` — a letter, then a list number, then `. ` and a capital.
_SENT_DIGIT = re.compile(r"[a-z]\d{1,2}\.\s+[A-Z]")

# A dotted DATE (`2026.08.11`, `11.08.2026`) satisfies MULTIDOT and is not a fusion.
# Excluded so the headline number is trustworthy — a measurement tool that overcounts
# is as useless as one that undercounts, and this one already undercounts by design.
_DATE_LIKE = re.compile(
    r"^(?:(?:19|20)\d{2}\.\d{1,2}\.\d{1,2}|\d{1,2}\.\d{1,2}\.(?:19|20)\d{2})$"
)

_SIGNATURES = (
    ("MULTIDOT", _MULTIDOT, 8),
    ("DIGIT_WORD", _DIGIT_WORD, 0),
    ("SENT_DIGIT", _SENT_DIGIT, 0),
)


def _hits(text: str) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for name, rx, min_len in _SIGNATURES:
        for m in rx.finditer(text):
            frag = m.group(0)
            if len(frag) < min_len:
                continue
            if name == "MULTIDOT" and _DATE_LIKE.match(frag):
                continue
            out.append((name, frag))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", type=int, default=None)
    ap.add_argument("--examples", type=int, default=25)
    args = ap.parse_args()

    corpus = sampled_corpus(args.sample) if args.sample else baseline_corpus()
    print(coverage_line())
    print("NOTE: high-precision signatures only. Two plain integers fused (`104`+`594`)")
    print("      are NOT detectable in text alone and are NOT counted. Numbers are a FLOOR.")
    print()

    papers = tables = cells = 0
    hit_cells = 0
    by_sig: Counter[str] = Counter()
    papers_hit: set[str] = set()
    tables_hit: set[tuple[str, str]] = set()
    examples: list[str] = []

    for key, pdf in corpus:
        try:
            result = extract_pdf_structured(pdf.read_bytes())
        except Exception as exc:
            print(f"  !! {key}: {type(exc).__name__}")
            continue
        papers += 1
        for t in result.get("tables") or []:
            tables += 1
            label = t.get("label") or str(t.get("id"))
            for c in t.get("cells") or []:
                text = (c.get("text") or "").strip()
                if not text:
                    continue
                cells += 1
                hits = _hits(text)
                if not hits:
                    continue
                hit_cells += 1
                papers_hit.add(key)
                tables_hit.add((key, label))
                for name, frag in hits:
                    by_sig[name] += 1
                if len(examples) < args.examples:
                    examples.append(
                        f"  {key} {label} r{c.get('r')}c{c.get('c')} "
                        f"[{hits[0][0]}] {text[:70]!r}"
                    )

    for line in examples:
        print(line)
    print()
    print(f"papers extracted        : {papers}")
    print(f"tables                  : {tables}")
    print(f"populated cells         : {cells}")
    if cells == 0:
        print("\nA ZERO HERE IS A CLAIM ABOUT THE INSTRUMENT: no populated cell was seen "
              "at all, so this run says nothing about fusion.")
        return 1
    print(f"cells with a fused token: {hit_cells} ({hit_cells / cells:.2%})")
    print(f"tables affected         : {len(tables_hit)} of {tables}")
    print(f"papers affected         : {len(papers_hit)} of {papers}")
    print(f"by signature            : {dict(by_sig)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
