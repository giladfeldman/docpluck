"""Which CONTEXT CUES actually discriminate a comma between digits? Measure them.

A comma between digits has at least four meanings — thousands separator,
decimal separator, list/pair separator, structural (an identifier). ESCImate's
`.NUM_STRUCTURAL_PATTERNS` names several candidate cues and states one as its
PRIMARY discriminator:

    a genuine grouped number has every group after the first exactly three
    digits ("1,000,000"); a list does not ("Figures 6,7,8"). Of 35 bare chains
    in the validation set, that single width test classifies 34 correctly.

That is a measurable claim, and this script measures it — and every other cue —
on docpluck's own 101-PDF corpus, so a cue is adopted on evidence rather than
on the fact that another project found it useful.

Every `\\d\\s*,\\s*\\d` occurrence in the raw text of every corpus paper is
bucketed by the cue that would classify it:

  GLUE_LEFT      the digits are glued to a word, a sentence period or '%'
                 (a Vancouver citation superscript: 'controls.7,8')
  OPERATOR       an operator immediately precedes ('d = 0,45') - a VALUE
  IDENTIFIER     inside a DOI or URL
  HEADNOUN       a head noun precedes ('Experiments 1,2', 'items 1,5')
  BRACKET_TUPLE  the whole bracket content is an integer tuple ('(52,272)')
  STAT_BRACKET   a short label is glued to the bracket ('t(1,197)', 'F(7,140)')
  CHAIN3         three or more comma-separated groups
  PAIR_SPACED    a bare two-element pair with a leading space ('Frank 1,2')
  OTHER          none of the above

and, for the numeric shapes, by the WIDTH test (every group after the first
exactly three digits => a grouped number).

Run:  python tools/diag/comma_signal_evaluation.py [--dump N]
"""

from __future__ import annotations

import collections
import glob
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
os.environ.setdefault("DOCPLUCK_DISABLE_CAMELOT", "1")

from docpluck.extract import extract_pdf  # noqa: E402

DUMP = 6
if "--dump" in sys.argv:
    DUMP = int(sys.argv[sys.argv.index("--dump") + 1])

OCCURRENCE = re.compile(r"\d(?:\s*,\s*\d+)+")
HEAD_NOUNS = re.compile(
    r"(?i)\b(?:experiments?|stud(?:y|ies)|tables?|figures?|items?|conditions?|"
    r"sections?|appendi(?:x|ces)|models?|groups?|anchors?|levels?|phases?|"
    r"blocks?|waves?|panels?|steps?|ids?|trials?|runs?|sites?|cohorts?|rounds?|"
    r"sessions?|clusters?|chapters?|equations?|refs?|references?|questions?|"
    r"scales?)\s+$"
)
IDENT = re.compile(r"(?i)(?:doi|https?|www)\S*$")
OPERATOR = re.compile(r"[=<>≤≥]\s*[-–−+]?\s*$")
STAT_LABEL = re.compile(r"[A-Za-z]{1,4}\d?\s*[\[(]$")


def width_says_grouped(token: str) -> bool:
    groups = [g.strip() for g in token.split(",")]
    return len(groups) > 1 and all(len(g) == 3 for g in groups[1:])


def classify(text: str, m: re.Match) -> str:
    lo, hi = m.start(), m.end()
    before = text[max(0, lo - 40):lo]
    after = text[hi:hi + 2]
    if IDENT.search(before):
        return "IDENTIFIER"
    if before.endswith((".", "%")) and len(before) > 1 and (before[-2].isalpha() or before[-1] == "%"):
        return "GLUE_LEFT"
    if before and (before[-1].isalpha()):
        return "GLUE_LEFT"
    if OPERATOR.search(before):
        return "OPERATOR"
    if STAT_LABEL.search(before):
        return "STAT_BRACKET"
    if before.endswith(("(", "[")) and after[:1] in (")", "]"):
        return "BRACKET_TUPLE"
    if HEAD_NOUNS.search(before):
        return "HEADNOUN"
    if m.group(0).count(",") >= 2:
        return "CHAIN3"
    if before.endswith((" ", "\n", "\t")):
        return "PAIR_SPACED"
    return "OTHER"


_VIBE_ROOT = os.environ.get("VIBE_ROOT") or os.path.expanduser("~/Vibe")
CORPUS = os.path.join(_VIBE_ROOT, "MetaScienceTools", "PDFextractor", "test-pdfs")
if not os.path.isdir(CORPUS):
    sys.exit(f"FATAL: corpus dir not found: {CORPUS} (set VIBE_ROOT?)")
pdfs = sorted(glob.glob(os.path.join(CORPUS, "**", "*.pdf"), recursive=True))
if not pdfs:
    sys.exit("FATAL: 0 PDFs in corpus - refusing to report a false CLEAN")

buckets: dict[str, int] = collections.Counter()
width_by_bucket: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
samples: dict[str, list[str]] = collections.defaultdict(list)
scanned = 0

print(f"evaluating comma-between-digits cues over {len(pdfs)} corpus PDFs...\n")
for p in pdfs:
    stem = os.path.splitext(os.path.basename(p))[0]
    try:
        with open(p, "rb") as fh:
            res = extract_pdf(fh.read())
        raw = res[0] if isinstance(res, tuple) else res
    except Exception as exc:  # pragma: no cover - diagnostic script
        print(f"  SKIP {stem}: {exc}")
        continue
    scanned += 1
    for m in OCCURRENCE.finditer(raw):
        b = classify(raw, m)
        buckets[b] += 1
        width_by_bucket[b]["grouped" if width_says_grouped(m.group(0)) else "list"] += 1
        if len(samples[b]) < DUMP:
            ctx = raw[max(0, m.start() - 45):m.end() + 25].replace("\n", "\\n")
            samples[b].append(f"{stem}: ...{ctx}...")

total = sum(buckets.values())
print(f"scanned {scanned} PDFs, {total} occurrences of digit-comma-digit\n")
print(f"{'bucket':15} {'n':>6}  {'%':>5}   width says grouped / list")
for b, n in buckets.most_common():
    w = width_by_bucket[b]
    print(f"{b:15} {n:6}  {100*n/total:5.1f}   {w['grouped']:5} / {w['list']:5}")

print("\n--- samples per bucket ---")
for b, _ in buckets.most_common():
    print(f"\n[{b}]")
    for s in samples[b]:
        print(f"   {s}")
