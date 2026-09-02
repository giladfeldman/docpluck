"""Which codepoints does A5's transliteration table NOT cover?

A5 (`normalize.py`, "A5: Math symbol and Greek letter normalization") maps Greek
letters, superscript digits and subscript digits to the flat ASCII downstream
consumers parse. It is an ENUMERATION, and the question this project keeps
learning the hard way is *what is not on the list?*

The known instance (decision D6a): subscript LETTERS are unmapped while
subscript DIGITS are mapped, so `eta2p` survives normalization as `eta2` + a
literal U+209A and effectcheck's `(?:eta2p|...)` alternation misses it — the
effect size degrades from PASS (checked, 0.04) to OK (nothing was checked), with
no warning anywhere.

This scan finds the whole class instead of that one member. For every character
in each paper's raw text it asks: is this codepoint in a Unicode category A5
CLAIMS to handle (Greek letter / superscript form / subscript form) but does not
actually map? Every hit is a token that leaves docpluck as mixed ASCII+Unicode.

Two things it deliberately does NOT do:
  * it does not judge whether mapping a given codepoint is DESIRABLE — `pi` is a
    real question and this scan only supplies the frequency;
  * it does not read the rendered output. A5 is skipped under
    `preserve_math_glyphs=True`, so /render is out of scope by construction.

Run:  python tools/diag/glyph_map_gap_scan.py [--sample N] [--seed S]
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

import argparse
import os
import sys
import unicodedata
from collections import Counter

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
os.environ.setdefault("DOCPLUCK_DISABLE_CAMELOT", "1")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _corpus import baseline_corpus, coverage_line, sampled_corpus  # noqa: E402

from docpluck.extract import extract_pdf  # noqa: E402
from docpluck.normalize import NormalizationLevel, normalize_text  # noqa: E402

# The codepoint ranges A5's own comments claim as its domain. A character in
# one of these that SURVIVES academic normalization is by definition a gap in
# the table, not a design choice — nothing else in the pipeline maps them.
DOMAINS = {
    "greek": lambda c: "GREEK" in unicodedata.name(c, ""),
    "superscript": lambda c: "SUPERSCRIPT" in unicodedata.name(c, ""),
    "subscript": lambda c: "SUBSCRIPT" in unicodedata.name(c, ""),
    "modifier_letter": lambda c: unicodedata.category(c) == "Lm",
}


def classify(ch: str) -> str | None:
    for label, pred in DOMAINS.items():
        try:
            if pred(ch):
                return label
        except (TypeError, ValueError):
            continue
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", type=int, default=0,
                    help="seeded sample of the SHARED repository instead of "
                         "docpluck's own baseline corpus (which is 26 papers "
                         "and too narrow to measure frequency)")
    ap.add_argument("--seed", type=int, default=20260813)
    ap.add_argument("--examples", type=int, default=3,
                    help="context snippets to print per surviving codepoint")
    args = ap.parse_args()

    papers = (sampled_corpus(args.sample, args.seed) if args.sample
              else baseline_corpus())
    print(coverage_line())
    print(f"scanning {len(papers)} papers for codepoints A5 leaves unmapped...\n")

    survived: Counter[str] = Counter()
    papers_with: dict[str, set[str]] = {}
    examples: dict[str, list[str]] = {}
    read_failures = 0

    for key, path in papers:
        try:
            with open(path, "rb") as fh:
                res = extract_pdf(fh.read())
            raw = res[0] if isinstance(res, tuple) else res
        except Exception as exc:  # pragma: no cover - diagnostic script
            read_failures += 1
            print(f"  SKIP {key}: {type(exc).__name__}: {exc}")
            continue

        out, _ = normalize_text(raw, level=NormalizationLevel.academic)
        for i, ch in enumerate(out):
            if ord(ch) < 128:
                continue
            label = classify(ch)
            if label is None:
                continue
            name = unicodedata.name(ch, f"U+{ord(ch):04X}")
            tag = f"U+{ord(ch):04X} {name} [{label}]"
            survived[tag] += 1
            papers_with.setdefault(tag, set()).add(key)
            if len(examples.setdefault(tag, [])) < args.examples:
                examples[tag].append(repr(out[max(0, i - 30):i + 30]))

    print(f"\n=== codepoints SURVIVING academic normalization ({len(survived)} distinct) ===")
    if not survived:
        print("  none — A5's table is complete over this corpus.")
    for tag, n in survived.most_common():
        print(f"\n  {tag}")
        print(f"    {n} occurrences in {len(papers_with[tag])} of {len(papers)} papers")
        for ex in examples[tag]:
            print(f"      {ex}")

    if read_failures:
        print(f"\nNOTE: {read_failures} paper(s) could not be read — counts are "
              f"over {len(papers) - read_failures} papers, not {len(papers)}.")
    print(f"\n{coverage_line()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
