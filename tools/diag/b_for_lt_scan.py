"""How often is a bare `b` standing in a statistic's OPERATOR SLOT, and is it ever legitimate?

RASTER-VERIFIED PREMISE (2026-08-14). `10.1016/j.jesp.2016.11.001` page 4 PRINTS
`p < 0.001` in font `BFDKFC+AdvTT94c8263f.I` — the same broken-ToUnicode AdvTT
family implicated in W0n — and our text layer yields `p b 0.001`. The page is
correct and our extraction is not, so under the separation-of-duties directive
this is **OURS to fix** (the one exception: a defect docpluck's own pipeline
introduced, where the source is intact underneath).

**It is not fixed.** No rule handles it. The 2026-08-14 handoff recorded "that
one is ours (`W0c` owns it) and stays", which is FALSE:
`recover_corrupted_lt_operator` recovers `<`-as-BACKSLASH only. The claim was
copied forward unverified — the L-027 failure mode in miniature.

WHY A SCAN BEFORE A FIX. `b` is a REAL statistical symbol (an unstandardized
regression coefficient), which makes this far more collision-prone than the
backslash W0c keys on. A backslash never legitimately touches a numeral in
extracted academic text; a `b` does, constantly. So the discriminator cannot be
"a b near a number" — it has to be **the operator SLOT**: a statistic symbol,
then `b`, then a value, with no operator anywhere between them. `b` is never an
operator, and a statistic always has one between its symbol and its value.

This scan measures both sides over English-language corpus papers:

    HITS   `p b 0.001`  — the corruption shape, `b` in the operator slot
    NEAR   `b = 0.23`, `b(24) = 1.9`, `beta`, `b1` — legitimate `b` uses that
           the signature must NOT touch

A fix ships only if HITS are real (spot-rasterized) and NEAR is untouched.

ENGLISH ONLY, exclusions printed. See `docs/SCOPE.md`.

Run:  python tools/diag/b_for_lt_scan.py [--sample N] [--limit N]
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _corpus  # noqa: E402
from _language import detect_language  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from docpluck.extract import extract_pdf  # noqa: E402

# The corruption: a statistic symbol, whitespace, a bare `b`, whitespace, a
# value — and NO operator between symbol and value, because `b` took its place.
_STAT_SYMBOL = r"(?:[pPtFrRzZdgFQ]|chi2|eta2|BF|OR|RR|HR|SE|SD|CI)"
_B_IN_OPERATOR_SLOT = re.compile(
    r"\b" + _STAT_SYMBOL + r"\s+b\s+(?=[.\d])[-+]?\d*\.?\d+"
)

# Legitimate `b` uses that must survive untouched.
_LEGIT_B = re.compile(
    r"\bb\s*[=<>]\s*[-+]?[\d.]"      # b = 0.23   (a coefficient)
    r"|\bb\d"                          # b1, b2     (indexed coefficients)
    r"|\bbeta\b"                       # spelled out
    r"|\bb\s*\("                      # b(24) = …
)


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--sample", type=int, default=0)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--seed", type=int, default=20260814)
    args = ap.parse_args()

    corpus = (
        _corpus.sampled_corpus(args.sample, seed=args.seed)
        if args.sample
        else _corpus.baseline_corpus(limit=args.limit or None)
    )
    print(_corpus.coverage_line())
    print(f"SCANNING {len(corpus)} papers for `b` in a statistic's operator slot\n")

    hit_papers: Counter[str] = Counter()
    legit_papers: Counter[str] = Counter()
    skipped: list[str] = []
    errors: list[str] = []
    total_hits = 0
    total_legit = 0

    for key, pdf_path in corpus:
        if pdf_path is None or not pdf_path.exists():
            errors.append(key)
            continue
        try:
            # extract_pdf returns (text, engine) — the engine label matters
            # here, because the corruption is font-driven and pdfplumber's
            # fallback may not reproduce it.
            text, _engine = extract_pdf(pdf_path.read_bytes())
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{key}: {type(exc).__name__}")
            continue
        if text.startswith("ERROR:"):
            errors.append(f"{key}: {text[:60]}")
            continue
        lang, _ = detect_language(text)
        if lang != "english":
            skipped.append(f"{key} [{lang}]")
            continue

        hits = _B_IN_OPERATOR_SLOT.findall(text)
        legit = _LEGIT_B.findall(text)
        total_legit += len(legit)
        if legit:
            legit_papers[key] = len(legit)
        if not hits:
            continue
        hit_papers[key] = len(hits)
        total_hits += len(hits)
        print(f"-- {key}  ({len(hits)} hit(s))")
        for m in _B_IN_OPERATOR_SLOT.finditer(text):
            lo = max(0, m.start() - 60)
            print(f"     …{text[lo:m.end() + 40]}…".replace("\n", " "))
        print()

    print("=" * 72)
    print(f"PAPERS SCANNED           {len(corpus) - len(skipped) - len(errors)}")
    print(f"PAPERS WITH THE SHAPE    {len(hit_papers)}")
    print(f"TOTAL HITS               {total_hits}")
    print(f"LEGITIMATE `b` USES      {total_legit} across {len(legit_papers)} papers")
    print("   (a coefficient `b = 0.23`, `b1`, `beta`, `b(24)` — the signature")
    print("    must not touch any of these; that is why it keys on the SLOT)")
    if skipped:
        print(f"SKIPPED (non-English)    {len(skipped)}: {', '.join(skipped[:5])}")
    if errors:
        print(f"ERRORS                   {len(errors)}: {', '.join(errors[:5])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
