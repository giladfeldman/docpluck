"""What would a DOCUMENT-LEVEL numeric locale say about our corpus?

docpluck's separator rules are per-token. ESCImate's are gated on an
article-level fact, and their reasoning is the part worth stealing
(`effectcheck/R/parse.R::infer_numeric_locale`):

    the two conventions are MUTUALLY EXCLUSIVE -- if the comma is the decimal
    separator then thousands must be grouped with a period, space or
    apostrophe, and vice versa. So a single unambiguous token anywhere in the
    text settles how every ambiguous token in it should be read.

This script ports their evidence patterns verbatim (they are themselves
debugged -- see the exclusions below) and reports, per corpus paper, which
convention the DOCUMENT attests. It answers the only question that decides
whether docpluck should adopt the gate:

  * how many papers are decisively EUROPEAN (where our thousands strip is
    destroying decimals right now),
  * how many are CONFLICT (where every rule must step aside),
  * how many are decisively US or have no evidence (where today's behaviour
    is already correct and a gate would change nothing).

Three details in the patterns are load-bearing, each from one of their
regressions:
  - markers are OPERATOR-GUARDED; a bare `0,1` also matches coded variables,
    version numbers, ratios and lists (misfires on 5 of 10 realistic strings).
  - `\\d,\\d{1,2}` is NOT evidence: tight CI separators (`[0.57,0.73]`) produced
    a false CONFLICT on a real article whose six European signals were all CI
    commas.
  - a PLAIN space is excluded from the full-notation separator class: in
    English journals a space between digit groups separates two numbers far
    more often than it groups one (`403,669 107,081` was read as one European
    number and flipped the whole document).

Run:  python tools/diag/locale_inference_corpus_scan.py
"""

from __future__ import annotations

import glob
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
os.environ.setdefault("DOCPLUCK_DISABLE_CAMELOT", "1")

from docpluck.extract import extract_pdf  # noqa: E402

_OP = r"[=<>≤≥]\s*"

EUROPEAN = {
    "F1_full_notation": r"\d[.  '](\d{3}),\d",
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


def infer(text: str) -> tuple[str, int, int, dict]:
    ev = {}
    ne = nu = 0
    for name, pat in EUROPEAN.items():
        hits = re.findall(pat, text)
        if hits:
            ev[name] = len(hits)
            ne += len(hits)
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


_VIBE_ROOT = os.environ.get("VIBE_ROOT") or os.path.expanduser("~/Vibe")
CORPUS = os.path.join(_VIBE_ROOT, "MetaScienceTools", "PDFextractor", "test-pdfs")
if not os.path.isdir(CORPUS):
    sys.exit(f"FATAL: corpus dir not found: {CORPUS} (set VIBE_ROOT?)")
pdfs = sorted(glob.glob(os.path.join(CORPUS, "**", "*.pdf"), recursive=True))
if not pdfs:
    sys.exit("FATAL: 0 PDFs in corpus - refusing to report a false CLEAN")

print(f"inferring document locale for {len(pdfs)} corpus PDFs (raw text channel)...\n")
tally: dict[str, int] = {}
for p in sorted(pdfs):
    stem = os.path.splitext(os.path.basename(p))[0]
    try:
        with open(p, "rb") as fh:
            res = extract_pdf(fh.read())
        raw = res[0] if isinstance(res, tuple) else res
    except Exception as exc:  # pragma: no cover - diagnostic script
        print(f"  SKIP {stem}: {exc}")
        continue
    verdict, ne, nu, ev = infer(raw)
    tally[verdict] = tally.get(verdict, 0) + 1
    if verdict in ("decisive_eu", "conflict"):
        print(f"  {verdict.upper():12} {stem}  (eu={ne} us={nu})  {ev}")

print("\n--- tally ---")
for k in sorted(tally):
    print(f"  {k:12} {tally[k]}")
print(
    "\nA gate changes behaviour ONLY on decisive_eu and conflict papers.\n"
    "decisive_us / none keep today's output byte-for-byte."
)
