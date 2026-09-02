"""Corpus measurement: A3a's df-bracket guard only recognises ONE label shape.

A3a strips thousands separators from any ``[1-9]\\d{0,2}(?:,\\d{3})+`` token. Its
guard against destroying a degrees-of-freedom pair is a single negative
lookbehind::

    (?<![A-Z][\\(\\[])

i.e. it protects a bracket introduced by exactly one UPPERCASE letter. Measured
on the shipped pipeline (2.4.126), these are what actually happens:

    F(7,140) = 2.31      ->  F(7, 140) = 2.31     protected
    chi2(2,420) = 5.1    ->  chi2(2420) = 5.1     df PAIR destroyed
    X²(2,420)  = 5.1     ->  chi2(2420) = 5.1     (Greek transliterated first)
    f(3,120)   = 4.4     ->  f(3120)    = 4.4     lowercase label
    F1(2,140)  = 3.3     ->  F1(2140)   = 3.3     subscripted label
    t(1,197)   = 2.31    ->  t(1197)    = 2.31    single df - right answer,
                                                  wrong reason; the in-source
                                                  comment claims this case is
                                                  guarded, and it is not.

A destroyed df pair is a WRONG NUMBER, not a missing one: `2420` is a plausible
single df, so nothing downstream can tell it apart from a real one.

This scan counts, over the corpus, how often a comma-thousands token sits inside
a bracket whose label is NOT a single uppercase letter - i.e. how often the
guard is bypassed on real text - and prints each site for classification.

Run:  python tools/diag/a3a_df_bracket_guard_scan.py
"""

from __future__ import annotations

# --- repo-root import guard (do not remove) ---------------------------------
# Python puts THIS SCRIPT'S OWN DIRECTORY on sys.path[0] -- never the current
# working directory -- so a script under tools/ or scripts/ has no route to the
# repo root and a bare ``import docpluck`` silently resolves to whatever copy is
# INSTALLED.  Measured 2026-09-01: 16 of 34 importers here loaded site-packages
# 2.4.137 while this tree was 2.4.138, including the 26-paper baseline gate --
# so a fix could be verified all night against a library it had not touched.
# Keyed on the pyproject.toml marker rather than a parents[N] count, so it
# survives the file being moved.  Pinned by
# tests/test_harness_scripts_import_the_working_tree.py.
import sys as _sys
from pathlib import Path as _Path

for _root in _Path(__file__).resolve().parents:
    if (_root / "pyproject.toml").is_file():
        if str(_root) not in _sys.path:
            _sys.path.insert(0, str(_root))
        break
# --- end repo-root import guard ---------------------------------------------

import glob
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
os.environ.setdefault("DOCPLUCK_DISABLE_CAMELOT", "1")

from docpluck.extract import extract_pdf  # noqa: E402

_VIBE_ROOT = os.environ.get("VIBE_ROOT") or os.path.expanduser("~/Vibe")
CORPUS = os.path.join(_VIBE_ROOT, "MetaScienceTools", "PDFextractor", "test-pdfs")
if not os.path.isdir(CORPUS):
    sys.exit(f"FATAL: corpus dir not found: {CORPUS} (set VIBE_ROOT?)")
pdfs = sorted(glob.glob(os.path.join(CORPUS, "**", "*.pdf"), recursive=True))
if not pdfs:
    sys.exit("FATAL: 0 PDFs in corpus - refusing to report a false CLEAN")

# A thousands-shaped token immediately after an opening bracket, where the
# character before the bracket is NOT a single uppercase letter (the shape the
# shipped guard fails to protect). Captures the label tail for classification.
UNGUARDED = re.compile(r"(?<![A-Z])([A-Za-z0-9²₁-₉]{0,6})([\(\[])([1-9]\d{0,2},\d{3})(?=[\)\],;\s])")
GUARDED = re.compile(r"[A-Z][\(\[][1-9]\d{0,2},\d{3}(?=[\)\],;\s])")

print(f"scanning {len(pdfs)} corpus PDFs (raw text channel) ...\n")
total_unguarded = total_guarded = scanned = 0
papers: list[tuple[str, int]] = []

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
    total_guarded += len(GUARDED.findall(raw))
    hits = list(UNGUARDED.finditer(raw))
    if not hits:
        continue
    total_unguarded += len(hits)
    papers.append((stem, len(hits)))
    print(f"  {stem}: {len(hits)} unguarded bracket site(s)")
    for m in hits:
        ctx = raw[max(0, m.start() - 50): m.end() + 30].replace("\n", "\\n")
        print(f"      ...{ctx}...")

print(f"\nscanned {scanned} PDFs.")
print(f"guarded  (single uppercase label) sites: {total_guarded}")
print(f"UNGUARDED sites: {total_unguarded} across {len(papers)} paper(s)")
print("\nA site is a real defect only if the bracket is a df PAIR; a single df")
print("with a genuine thousands separator (t(1,197)) is stripped correctly.")
