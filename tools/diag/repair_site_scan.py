"""Where does each REPAIR rule actually fire, in ENGLISH articles, in the wild?

The separation-of-duties directive (user, 2026-08-13) splits every rewriting step
into two kinds:

    NOTATION  canonicalising a FORM the paper printed correctly
              (Greek -> ASCII, U+2212 -> '-', superscript -> caret)
    REPAIR    correcting a MISTAKE

and then splits REPAIR again by *whose* mistake it was:

    docpluck's   the extraction channel lost or mangled something the page prints
                 -> ours to fix, the source is intact underneath
    the paper's  the page prints the error
                 -> PASS THROUGH. Silently repairing it launders a real defect
                    into a meta-science pipeline: the consumer then validates a
                    number the paper never printed, and the author never learns.

Deciding which one a rule serves needs two things this scan supplies and no
amount of reasoning can: **the real sites where the rule fires**, and **the paper
each came from**, so the page can be rasterized and read. It answers, per rule:

    how many English papers does it touch?  how many sites?  which ones?

A rule with zero sites over a real corpus is a rule with no observed input — a
DELETE candidate regardless of how defensible it looks (rule A3d was built on a
constructed string and a 600-paper hunt found 0 occurrences in 0 papers).

Attribution is by ``NormalizationReport.steps_changed`` rather than by a copy of
each rule's regex: **one concept, one table.** A scan carrying its own copy of
the pattern it measures drifts from the shipped rule and reports a number about
code that does not run (CLAUDE.md, 2026-08-13).

STATED LIMIT, so nobody reads more into the counts than they carry: the scan
normalizes **line by line**, so cross-line steps (F0 footnote/running-header,
W0l's wrapped-interaction arm) are under-counted here. It is a measurement of the
single-line numeric and glyph rules, which is what the directive is about.

The locale question itself is CLOSED: docpluck serves English papers in US
numeric convention and passes European numbers through unconverted (v2.4.129,
`docs/SCOPE.md`). `english_only_locale_scan.py` retired with that feature; its
language filter moved to `_language.py`.

ENGLISH ONLY, and the exclusions are printed. Non-English evidence does not
transfer to the English separator question and will actively mislead — the
bilingual SciELO trap of 2026-08-13.

Run:  python tools/diag/repair_site_scan.py [--sample N] [--seed S]
                                            [--rules A3,A3c,A3d,W0n]
                                            [--max-sites 25]
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
import re
import sys
from collections import Counter, defaultdict

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
os.environ.setdefault("DOCPLUCK_DISABLE_CAMELOT", "1")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _corpus import baseline_corpus, coverage_line, sampled_corpus  # noqa: E402
from _language import detect_language  # noqa: E402

from docpluck.extract import extract_pdf  # noqa: E402
from docpluck.normalize import NormalizationLevel, normalize_text  # noqa: E402

# The steps this scan reports on by default: every rule the directive puts in
# question because it rewrites a NUMBER rather than a notation.
DEFAULT_RULES = "A2,A3,A3a,A3b,A3c,A3d,A4,W0n"

_STEP_ID_RE = re.compile(r"^([A-Z]\d[a-z]?[a-z]?)_")


def step_id(step_name: str) -> str:
    """`A3c_leading_zero_decimal_recovery` -> `A3c`."""
    m = _STEP_ID_RE.match(step_name)
    return m.group(1) if m else step_name


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", type=int, default=0)
    ap.add_argument("--seed", type=int, default=20260813)
    ap.add_argument("--rules", default=DEFAULT_RULES)
    ap.add_argument("--max-sites", type=int, default=25)
    args = ap.parse_args()

    wanted = {r.strip() for r in args.rules.split(",") if r.strip()}

    papers = (sampled_corpus(args.sample, args.seed) if args.sample
              else baseline_corpus())
    print(coverage_line())
    print(f"scanning {len(papers)} papers; ENGLISH-language articles only")
    print(f"rules: {', '.join(sorted(wanted))}\n")

    sites: dict[str, list[tuple[str, str, str]]] = defaultdict(list)
    papers_touched: dict[str, set[str]] = defaultdict(set)
    langs: Counter[str] = Counter()
    excluded: list[str] = []
    english = 0
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

        lang, _counts = detect_language(raw)
        langs[lang] += 1
        if lang != "english":
            excluded.append(f"{lang:16} {key}")
            continue
        english += 1

        for line in raw.splitlines():
            if not line.strip():
                continue
            try:
                out, rep = normalize_text(line, NormalizationLevel.academic)
            except Exception:  # pragma: no cover - diagnostic script
                continue
            if out == line:
                continue
            for name in rep.steps_changed:
                sid = step_id(name)
                if sid not in wanted:
                    continue
                sites[sid].append((key, line.strip(), out.strip()))
                papers_touched[sid].add(key)

    print("=== language distribution (ALL scanned) ===")
    for lang, n in langs.most_common():
        print(f"  {lang:18} {n}")
    print(f"\n=== EXCLUDED as non-English ({len(excluded)}) ===")
    for e in excluded[:30]:
        print(f"    {e}")
    if len(excluded) > 30:
        print(f"    ... and {len(excluded) - 30} more")

    print(f"\n=== FIRING RATE over {english} ENGLISH papers ===")
    print(f"  {'rule':6} {'papers':>7} {'sites':>7}")
    for sid in sorted(wanted):
        print(f"  {sid:6} {len(papers_touched[sid]):>7} {len(sites[sid]):>7}")

    for sid in sorted(wanted):
        hits = sites[sid]
        print(f"\n=== {sid} — {len(hits)} site(s) in {len(papers_touched[sid])} paper(s) ===")
        if not hits:
            print("    NO SITES. A rule with no observed input in real English")
            print("    articles is a DELETE candidate: it is pure false-positive")
            print("    surface for no measured benefit.")
            continue
        for key, before, after in hits[: args.max_sites]:
            print(f"    {key}")
            print(f"      -  {before[:200]}")
            print(f"      +  {after[:200]}")
        if len(hits) > args.max_sites:
            print(f"    ... and {len(hits) - args.max_sites} more site(s) "
                  f"(raise --max-sites to see them)")

    if failures:
        print(f"\nNOTE: {failures} paper(s) unreadable — counts are over "
              f"{len(papers) - failures} papers, not {len(papers)}.")
    print("\nEvery site above is a candidate for the ONLY test that decides "
          "ownership:\n  rasterize the page and look. "
          "`pdftoppm -png -r 300 -f N -l N doc.pdf out/p`\n"
          "Never adjudicate an extraction defect with the extractors under "
          "suspicion.")
    print(f"\n{coverage_line()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
