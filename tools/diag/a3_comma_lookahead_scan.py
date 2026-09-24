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
      python tools/diag/a3_comma_lookahead_scan.py --workers 8
      python tools/diag/a3_comma_lookahead_scan.py --specimen v2.4.126 --specimen . --workers 12

``--specimen`` selects WHICH copy of docpluck is measured (a directory holding a
``docpluck/`` package, or a git ref checked out as a temporary worktree outside
the repo); each one is an ARM, and every arm prints the path it actually
imported and refuses to run if that differs from the request. The paper set is
the same for every arm. See ``_corpus.run_arms``. docpluck is imported only
inside :func:`measure_paper` for that reason: a spawned worker re-runs this
module's top level before it binds its specimen.
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
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
os.environ.setdefault("DOCPLUCK_DISABLE_CAMELOT", "1")

# The paper set comes from the article custodian's committed manifest, never
# from a directory glob: a glob's denominator is its own numerator, so a corpus
# that has silently shrunk still reports 100% and every count below is divided
# by the wrong N. `docpluck_corpus()` raises rather than returning a short list.
from _corpus import (
    add_specimen_arguments,
    artifact_path,
    docpluck_corpus,
    run_arms,
)

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


def measure_paper(p: str) -> dict:
    """Measure one paper with whichever docpluck this process has bound."""
    from docpluck.extract import extract_pdf
    from docpluck.normalize import NormalizationLevel, normalize_text

    stem = os.path.splitext(os.path.basename(p))[0]
    try:
        with open(p, "rb") as fh:
            res = extract_pdf(fh.read())
        raw = res[0] if isinstance(res, tuple) else res
        rep = normalize_text(raw, level=NormalizationLevel.academic)
        text = rep.text if hasattr(rep, "text") else rep[0]
    except Exception as exc:  # noqa: BLE001  # pragma: no cover - a paper that fails is printed as SKIP
        return {"stem": stem, "skipped": str(exc)}

    # SHIPPED fires are measured on the text BEFORE normalization (A3 has
    # already consumed them in `text`), after A3a's generic thousands strip so
    # the two rules are seen in their real order.
    pre = _A3A_GENERIC.sub(lambda m: m.group(0).replace(",", ""), raw)
    shipped = [
        pre[max(0, m.start() - 55): m.end() + 30].replace("\n", "\\n")
        for m in SHIPPED.finditer(pre)
    ]

    hits1 = list(W1.finditer(text))
    hits2 = list(W2.finditer(text))
    w1_sites = []
    for m in hits1:
        ctx = text[max(0, m.start() - 60): m.end() + 40].replace("\n", "\\n")
        tag = "W1+W2" if any(h.start() == m.start() for h in hits2) else "W1only"
        w1_sites.append((tag, ctx))
    return {
        "stem": stem,
        "skipped": None,
        "shipped_sites": shipped,
        "w1": len(hits1),
        "w2": len(hits2),
        "w1_sites": w1_sites,
    }


def report(results: list[dict]) -> dict:
    """Print one arm's findings exactly as the single-process scan always did."""
    shipped_sites: list[tuple[str, str]] = []
    w1_total = w2_total = 0
    w1_papers: list[tuple[str, int, int]] = []
    scanned = 0
    for r in results:
        if r["skipped"] is not None:
            print(f"  SKIP {r['stem']}: {r['skipped']}")
            continue
        scanned += 1
        shipped_sites.extend((r["stem"], ctx) for ctx in r["shipped_sites"])
        if not r["w1"]:
            continue
        # `w2_total` accumulates only for papers that also have a W1 hit. A W2
        # site is always a W1 site (its lookahead is a strict subset), so the
        # gate loses nothing; it is kept so the totals match earlier runs.
        w1_total += r["w1"]
        w2_total += r["w2"]
        w1_papers.append((r["stem"], r["w1"], r["w2"]))
        print(f"  {r['stem']}: W1={r['w1']} W2={r['w2']}")
        for tag, ctx in r["w1_sites"]:
            print(f"      [{tag}] ...{ctx}...")

    print(f"\n=== what the SHIPPED A3 converts on this corpus ({len(shipped_sites)} sites) ===")
    for stem, ctx in shipped_sites:
        print(f"  {stem}: ...{ctx}...")

    shipped_papers = len({stem for stem, _ in shipped_sites})
    w2_papers = sum(1 for _, _, n2 in w1_papers if n2)
    print(f"\nscanned {scanned} PDFs.")
    print(f"papers with any candidate site: {len(w1_papers)}")
    print(f"W1 (bare comma)      total sites: {w1_total}")
    print(f"W2 (comma+space)     total sites: {w2_total}")
    print(f"W2 papers: {w2_papers}")
    print(f"SHIPPED A3 sites: {len(shipped_sites)} in {shipped_papers} papers")
    print("\nClassify every site above by hand before changing A3: a site is a TRUE")
    print("positive only if the token is a European DECIMAL; an enumeration, a")
    print("citation-superscript run or a df pair is a FALSE positive.")
    return {
        "scanned": scanned,
        "skipped": [(r["stem"], r["skipped"]) for r in results if r["skipped"] is not None],
        "papers_with_candidate": len(w1_papers),
        "w1_total": w1_total,
        "w2_total": w2_total,
        "w2_papers": w2_papers,
        "shipped_sites_total": len(shipped_sites),
        "shipped_papers": shipped_papers,
        "per_paper": w1_papers,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    add_specimen_arguments(parser)
    args = parser.parse_args()

    pdfs = [str(p) for p in docpluck_corpus()]
    if not pdfs:
        sys.exit("FATAL: 0 PDFs in corpus - refusing to report a false CLEAN")

    print(f"scanning {len(pdfs)} corpus PDFs (post-normalize) ...\n")
    arms = run_arms(measure_paper, pdfs, args.specimen, args.workers)
    for arm in arms:
        if len(arms) > 1:
            print(f"\n{'=' * 72}\nARM {arm.label}\n{'=' * 72}")
        print(arm.specimen_line() + "\n")
        summary = report(arm.results)
        if args.json:
            out = artifact_path("a3_comma_lookahead_scan", arm)
            record = {
                "scan": "a3_comma_lookahead_scan",
                "specimen_request": arm.request,
                "specimen_resolved": str(arm.resolved),
                "specimen_commit": arm.commit,
                "specimen_version": arm.version,
                "corpus_n": len(pdfs),
                **summary,
            }
            out.write_text(json.dumps(record, indent=1), encoding="utf-8")
            print(f"\nrecord: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
