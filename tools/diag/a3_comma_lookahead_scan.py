"""Corpus measurement for the ESCImate A3-lookahead divergence (2026-08-09).

ESCImate reports that docpluck's A3 lookahead ``(?=\\s|[;)\\]]|\\.(?!\\d)|$)``
omits ``,``, so a European decimal followed by a LIST comma is left unconverted:

    t(28) = 2,21, d = 0,45   ->   t(28) = 2,21, d = 0.45      (2,21 unchanged)

Confirmed locally. This script measures the two things the fix decision needs,
on the 101-PDF corpus, over ALREADY-NORMALIZED text (so every site printed is
one the shipped pipeline leaves behind today):

  A. TP candidates - sites the widening would newly convert.
  B. FP risk       - the same sites, classified by the following character,
                     because "1,2, and 3" (an enumeration with one missing
                     space) is the shape that would break.

Two candidate widenings are measured separately:

  W1 = ESCImate's proposal: admit a bare ``,`` into the lookahead.
  W2 = narrower: admit ``,`` ONLY when followed by whitespace (a list comma in
       running prose always is; a digit-run separator "1,2,3" never is).

Run:  python tools/diag/a3_comma_lookahead_scan.py
"""

from __future__ import annotations

import glob
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
os.environ.setdefault("DOCPLUCK_DISABLE_CAMELOT", "1")

from docpluck.extract import extract_pdf  # noqa: E402
from docpluck.normalize import NormalizationLevel, normalize_text  # noqa: E402

_VIBE_ROOT = os.environ.get("VIBE_ROOT") or os.path.expanduser("~/Vibe")
CORPUS = os.path.join(_VIBE_ROOT, "MetaScienceTools", "PDFextractor", "test-pdfs")
if not os.path.isdir(CORPUS):
    sys.exit(f"FATAL: corpus dir not found: {CORPUS} (set VIBE_ROOT?)")
pdfs = sorted(glob.glob(os.path.join(CORPUS, "**", "*.pdf"), recursive=True))
if not pdfs:
    sys.exit("FATAL: 0 PDFs in corpus - refusing to report a false CLEAN")

# Same lookbehind as shipped A3; only the trailing lookahead differs.
_LB = r"(?<![a-zA-Z,0-9\[\(])"
W1 = re.compile(_LB + r"(\d),(\d{1,3})(?=,)")          # bare list comma
W2 = re.compile(_LB + r"(\d),(\d{1,3})(?=,[ \t\n])")   # list comma + whitespace

# The SHIPPED rule, so the same scan reports what A3 converts on this corpus
# TODAY. ESCImate's conformance corpus (cases list-experiments, list-table,
# list-items, list-coded-binary) says several of those are enumerations, i.e.
# false positives that predate any widening: "Experiments 1,2 showed" already
# becomes "Experiments 1.2 showed".
SHIPPED = re.compile(_LB + r"(\d),(\d{1,3})(?=\s|[;)\]]|\.(?!\d)|$)")

_A3A_GENERIC = re.compile(r"(?<![A-Z][\(\[])\b[1-9]\d{0,2}(?:,\d{3})+(?=[\s,;.)\]:]|$)")

print(f"scanning {len(pdfs)} corpus PDFs (post-normalize) ...\n")

shipped_sites: list[tuple[str, str]] = []
w1_total = w2_total = 0
w1_papers: list[tuple[str, int, int]] = []
scanned = 0

for p in pdfs:
    stem = os.path.splitext(os.path.basename(p))[0]
    try:
        with open(p, "rb") as fh:
            res = extract_pdf(fh.read())
        raw = res[0] if isinstance(res, tuple) else res
        rep = normalize_text(raw, level=NormalizationLevel.academic)
        text = rep.text if hasattr(rep, "text") else rep[0]
    except Exception as exc:  # pragma: no cover - diagnostic script
        print(f"  SKIP {stem}: {exc}")
        continue
    scanned += 1

    # SHIPPED fires are measured on the text BEFORE normalization (A3 has
    # already consumed them in `text`), after A3a's generic thousands strip so
    # the two rules are seen in their real order.
    pre = _A3A_GENERIC.sub(lambda m: m.group(0).replace(",", ""), raw)
    for m in SHIPPED.finditer(pre):
        shipped_sites.append((stem, pre[max(0, m.start() - 55): m.end() + 30].replace("\n", "\\n")))

    hits1 = list(W1.finditer(text))
    hits2 = list(W2.finditer(text))
    if not hits1:
        continue
    w1_total += len(hits1)
    w2_total += len(hits2)
    w1_papers.append((stem, len(hits1), len(hits2)))
    print(f"  {stem}: W1={len(hits1)} W2={len(hits2)}")
    for m in hits1:
        ctx = text[max(0, m.start() - 60): m.end() + 40].replace("\n", "\\n")
        tag = "W1+W2" if any(h.start() == m.start() for h in hits2) else "W1only"
        print(f"      [{tag}] ...{ctx}...")

print(f"\n=== what the SHIPPED A3 converts on this corpus ({len(shipped_sites)} sites) ===")
for stem, ctx in shipped_sites:
    print(f"  {stem}: ...{ctx}...")

print(f"\nscanned {scanned} PDFs.")
print(f"papers with any candidate site: {len(w1_papers)}")
print(f"W1 (bare comma)      total sites: {w1_total}")
print(f"W2 (comma+space)     total sites: {w2_total}")
print("\nClassify every site above by hand before changing A3: a site is a TRUE")
print("positive only if the token is a European DECIMAL; an enumeration, a")
print("citation-superscript run or a df pair is a FALSE positive.")
