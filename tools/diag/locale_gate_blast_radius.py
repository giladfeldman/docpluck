"""What would a LOCALE GATE actually change, per paper, per rule?

Decision D5 / "Option A" proposes gating docpluck's separator rules on a
document-level numeric-locale verdict. Two independent design reviews (codex and
an adversarial Sonnet pass, 2026-08-13) agreed the AGGRESSIVE form manufactures
wrong numbers, and both raised a question only measurement can answer:

  * codex: suppressing A3c under `decisive_us` loses a genuine continental value
    in a mostly-US paper that embeds one imported table ("p < 0,001").
  * Sonnet: the corpus's only two genuine European decimals (leading-zero hazard
    ratios) sit in papers with NO European verdict, so a `decisive_eu`-only
    conversion would never reach them.

Both are claims about FREQUENCY. This scan counts, per paper:

  verdict            the document-level locale on the RAW text
  a3_sites           where the shipped operator-gated A3 fires
  a3c_sites          where the shipped ungated A3c fires  (the suppression risk)
  a3a_generic_sites  where A3a's UNLABELLED generic thousands-strip fires
                     (the only genuinely ambiguous, irreversible guess, and the
                      one rule a EU verdict would have to invert)
  mixed_rows         a single line carrying BOTH an A3c-convertible cell and an
                     unconverted `\\d,\\d\\d` neighbour — defect 8's real shape

The point is the CROSS-TABULATION: a rule whose sites all sit in `decisive_us`
papers is safe to gate on `decisive_us`; a rule whose sites sit in `none` papers
cannot be gated on a verdict at all, because there is no verdict to gate on.

Run:  python tools/diag/locale_gate_blast_radius.py [--sample N] [--seed S]
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from collections import Counter, defaultdict

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
os.environ.setdefault("DOCPLUCK_DISABLE_CAMELOT", "1")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _corpus import baseline_corpus, coverage_line, sampled_corpus  # noqa: E402

from docpluck.extract import extract_pdf  # noqa: E402

# ── the locale evidence rule ─────────────────────────────────────────────
# Ported from effectcheck's `infer_numeric_locale`. The separator class in
# F1 is `.`, U+00A0 NO-BREAK SPACE, U+202F NARROW NO-BREAK SPACE and `'` —
# a PLAIN space is deliberately absent, because `403,669 107,081` in an
# English table would otherwise read as one European number and flip the
# document. Codex's 2026-08-13 review flagged this as a regression; checked
# against the source, the exclusion is intact and the finding was REFUTED.
# It is spelled with explicit escapes here so the class can never again be
# misread (or mis-transcribed into a review document) as a plain space.
_OP = r"[=<>≤≥]\s*"
_SEP = "[.  ']"

EUROPEAN = {
    "F1_full_notation": r"\d" + _SEP + r"(\d{3}),\d",
    "E2_leading_comma": _OP + r",\d{2,}",
    "E3_zero_comma": _OP + r"0,\d",
    "E4_four_decimals": r"\d,\d{4,}",
    "E5_sci_notation": r"\d,\d+[eE][-+]?\d",
}
US = {
    "F2_full_notation": r"\d,\d{3}\.\d",
    "U2_leading_dot": _OP + r"\.\d{2,}",
    "U3_zero_dot": _OP + r"0\.\d",
    "U4_two_groups": r"\d,\d{3},\d{3}",
}

# E4 fires on machine-learning TENSOR SHAPES — `(70,64472)` is a matrix
# dimension, not a European decimal — and produced the corpus's single
# "conflict" verdict on an IEEE paper. A bracket-delimited pair is never a
# decimal, so E4 is measured both raw and bracket-guarded.
_E4_BRACKETED = re.compile(r"[(\[]\s*\d+,\d{4,}\s*[)\]]")

# ── the shipped rules, copied verbatim so the scan reports what SHIPS ────
_A3_VALUE_OPERATOR = r"([=<>]=?|[≤≥])"
A3_RE = re.compile(
    _A3_VALUE_OPERATOR + r"(\s*[-–−+]?\s*)(\d{1,4}),(\d{1,2})"
    r"(?=[\s;)\]%]|,(?!\d)|\.(?!\d)|$)"
)
A3C_RE = re.compile(r"\b0,(\d{2,4})(?=[\s)\];,.:]|$)")
# A bare digit-comma-digit that A3 does NOT convert (no operator in front).
BARE_DDD_RE = re.compile(r"(?<![\d.,])(\d{1,4}),(\d{1,2})(?![\d])")


def infer(text: str) -> tuple[str, int, int, dict]:
    ev: dict[str, int] = {}
    ne = nu = 0
    for name, pat in EUROPEAN.items():
        hits = re.findall(pat, text)
        if name == "E4_four_decimals":
            # count only NON-bracketed hits as evidence
            bracketed = len(_E4_BRACKETED.findall(text))
            n = max(0, len(hits) - bracketed)
            if bracketed:
                ev["E4_bracketed_excluded"] = bracketed
        else:
            n = len(hits)
        if n:
            ev[name] = n
            ne += n
    for name, pat in US.items():
        hits = re.findall(pat, text)
        if hits:
            ev[name] = len(hits)
            nu += len(hits)
    if ne == 0 and nu == 0:
        return "none", ne, nu, ev
    if ne > 0 and nu > 0 and min(ne, nu) / max(ne, nu) > 0.2:
        return "conflict", ne, nu, ev
    return ("decisive_eu" if ne > nu else "decisive_us"), ne, nu, ev


def mixed_rows(text: str) -> list[str]:
    """Lines where A3c converts one cell and a neighbour stays unconverted.

    Defect 8's actual shape: `Estimate | 1,23 | SE | 0,45` emits `0.45` beside
    `1,23`, so one flattened table row carries two numeric conventions.
    """
    out = []
    for line in text.splitlines():
        if not A3C_RE.search(line):
            continue
        rest = A3C_RE.sub("", line)
        if BARE_DDD_RE.search(rest) and not A3_RE.search(line):
            out.append(line.strip()[:160])
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", type=int, default=0)
    ap.add_argument("--seed", type=int, default=20260813)
    ap.add_argument("--examples", type=int, default=4)
    args = ap.parse_args()

    papers = (sampled_corpus(args.sample, args.seed) if args.sample
              else baseline_corpus())
    print(coverage_line())
    print(f"measuring locale-gate blast radius over {len(papers)} papers...\n")

    verdicts: Counter[str] = Counter()
    # rule -> verdict -> (papers, sites)
    by_rule: dict[str, dict[str, list[int]]] = {
        r: defaultdict(lambda: [0, 0]) for r in ("A3", "A3c", "A3a_generic", "mixed_rows")
    }
    examples: dict[str, list[str]] = defaultdict(list)
    failures = 0

    for key, path in papers:
        try:
            with open(path, "rb") as fh:
                res = extract_pdf(fh.read())
            raw = res[0] if isinstance(res, tuple) else res
        except Exception as exc:  # pragma: no cover - diagnostic script
            failures += 1
            print(f"  SKIP {key}: {type(exc).__name__}: {exc}")
            continue

        verdict, ne, nu, ev = infer(raw)
        verdicts[verdict] += 1

        counts = {
            "A3": len(A3_RE.findall(raw)),
            "A3c": len(A3C_RE.findall(raw)),
            "A3a_generic": len(re.findall(r"(?<![\d.,])\d{1,3},\d{3}(?![\d,])", raw)),
            "mixed_rows": len(mixed_rows(raw)),
        }
        for rule, n in counts.items():
            if n:
                by_rule[rule][verdict][0] += 1
                by_rule[rule][verdict][1] += n

        if verdict in ("decisive_eu", "conflict"):
            print(f"  {verdict.upper():12} {key}  (eu={ne} us={nu})  {ev}")
        for row in mixed_rows(raw)[: args.examples]:
            if len(examples["mixed"]) < args.examples * 3:
                examples["mixed"].append(f"[{verdict}] {key}: {row!r}")
        if verdict == "decisive_us":
            for m in A3C_RE.finditer(raw):
                if len(examples["a3c_in_us"]) < args.examples * 3:
                    s = max(0, m.start() - 45)
                    examples["a3c_in_us"].append(f"{key}: {raw[s:m.end()+25]!r}")

    print("\n=== document-locale verdicts ===")
    for v, n in verdicts.most_common():
        print(f"  {v:14} {n}")

    print("\n=== where each rule FIRES, cross-tabulated by verdict ===")
    print("    (a rule whose sites sit in `none` papers CANNOT be locale-gated —")
    print("     there is no verdict to gate on)")
    for rule in ("A3", "A3c", "A3a_generic", "mixed_rows"):
        print(f"\n  {rule}")
        tab = by_rule[rule]
        if not tab:
            print("    never fires on this corpus")
            continue
        for v in sorted(tab):
            papers_n, sites = tab[v]
            print(f"    {v:14} {sites:5} sites in {papers_n:3} papers")

    if examples["a3c_in_us"]:
        print("\n=== A3c sites inside decisive_US papers ===")
        print("    (SUPPRESSING A3c under decisive_us would stop converting these)")
        for e in examples["a3c_in_us"]:
            print(f"    {e}")

    if examples["mixed"]:
        print("\n=== defect-8 mixed rows (A3c converts, neighbour does not) ===")
        for e in examples["mixed"]:
            print(f"    {e}")
    else:
        print("\n=== defect-8 mixed rows: NONE FOUND on this corpus ===")

    if failures:
        print(f"\nNOTE: {failures} paper(s) unreadable — counts are over "
              f"{len(papers) - failures} papers, not {len(papers)}.")
    print(f"\n{coverage_line()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
