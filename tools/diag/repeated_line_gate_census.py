"""Census of the repeated-line page gate's decisions, arm by arm.

REGENERATES the separation the gate is tuned on. The previous separation
("33 candidates, no overlap") was computed on a page map that was wrong for
half of all page boundaries, so it is VOID and must not be carried forward.
This tool recomputes it against the corrected attribution.

It answers two questions the gate cannot answer about itself:

  1. Do running headers and table content still separate cleanly on
     `(distinct_pages, max_per_page)` once the pages are attributed correctly?
  2. Is the `count >= 20` watermark arm earning its place, or is it deleting
     table content? It was reported firing on `20 occurrences of a treatment
     -response row over 5 pages` and needs a real denominator either way.

MEASURE THE DENOMINATOR SEPARATELY FROM THE SHAPE. One paper proves a shape
exists; only a sample says how often. Every count printed here is per-corpus,
and the corpus is named in the output.

The gate logic is MIRRORED from `normalize.py`'s repeated-line strip rather
than imported, because the strip is inline inside `_normalize_text`. That is a
second definition of one rule, which this project has a standing rule against
-- so the mirror is asserted against the real thing by
`tests/test_repeated_line_gate_census_mirrors_the_rule.py`, and this docstring
is the pointer to that assertion. If the test is failing, trust the rule and
not this tool.

TWO LIMITS, STATED UP FRONT BECAUSE BOTH CAN MAKE THIS TOOL LOOK AUTHORITATIVE
WHEN IT IS NOT:

  1. IT READS THE INPUT TEXT, NOT WHAT THE GATE SEES. The real strip runs
     mid-pipeline, after roughly thirty steps have already rewritten and
     removed lines, so a candidate listed here may never reach the gate --
     it may have been taken by an earlier step, or its text may have changed.
     Measured 2026-08-28: of 7 candidates this tool scored as
     stats-carrying-and-strippable, 4 were absent from the final output
     because an EARLIER step removed them, not this gate.
  2. IT MIRRORS THE ARMS, NOT THE GUARDS. The real rule additionally skips a
     candidate on a parenthesised year, on caption-shaped prose, and on
     `_carries_statistical_content`. So the `carry_stats` column here is an
     UPPER BOUND on what the gate would take, never a list of losses.

The authoritative instrument for loss is the corpus differential -- run both
trees over the same pre-extracted raw text and diff the whitespace-collapsed
output. This tool explains the gate's REASONING; only the differential
establishes its EFFECT.

Usage
-----
    python tools/diag/repeated_line_gate_census.py <dir-of-.txt-or-.pdf> [--limit N]
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
import collections
import os
import sys

PAGE_BREAK = chr(12)

CANDIDATE_MIN = 15
CANDIDATE_MAX = 120
MIN_COUNT = 5
MIN_PAGES_FOR_FURNITURE = 5
WATERMARK_COUNT = 20


def page_attribution(lines: list[str]) -> list[int]:
    """The CORRECTED map: a leading form feed belongs to the line that follows."""
    pages, page = [], 1
    for line in lines:
        at = len(line) - len(line.lstrip())
        page += line.count(PAGE_BREAK, 0, at)
        pages.append(page)
        page += line.count(PAGE_BREAK, at)
    return pages


def old_page_attribution(lines: list[str]) -> list[int]:
    """The PRE-FIX map, kept so the two can be compared rather than asserted."""
    pages, page = [], 1
    for line in lines:
        pages.append(page)
        page += line.count(PAGE_BREAK)
    return pages


def census_one(text: str, use_old_map: bool = False):
    lines = text.split("\n")
    pages = (old_page_attribution if use_old_map else page_attribution)(lines)
    counts: dict[str, int] = {}
    line_pages: dict[str, list[int]] = {}
    for i, line in enumerate(lines):
        s = line.strip()
        if CANDIDATE_MIN <= len(s) <= CANDIDATE_MAX:
            counts[s] = counts.get(s, 0) + 1
            line_pages.setdefault(s, []).append(pages[i])

    paginated = sum(l.count(PAGE_BREAK) for l in lines) >= 2
    rows = []
    for s, c in counts.items():
        if c < MIN_COUNT:
            continue
        pg = line_pages[s]
        distinct = len(set(pg))
        per_page = max(collections.Counter(pg).values())
        if not paginated:
            arm, qualifies = "unpaginated", None
        elif distinct < MIN_PAGES_FOR_FURNITURE:
            arm, qualifies = "rejected:few_pages", False
        elif per_page == 1:
            arm, qualifies = "once_per_page", True
        elif c >= WATERMARK_COUNT:
            arm, qualifies = "watermark_count>=20", True
        else:
            arm, qualifies = "rejected:multi_per_page", False
        rows.append(
            {"line": s, "count": c, "distinct_pages": distinct,
             "max_per_page": per_page, "arm": arm, "qualifies": qualifies}
        )
    return rows, paginated


def _iter_texts(path: str, limit):
    names = sorted(os.listdir(path))
    txts = [n for n in names if n.lower().endswith(".txt")]
    if txts:
        for n in txts[:limit]:
            with open(os.path.join(path, n), encoding="utf-8") as fh:
                yield n, fh.read()
        return
    from docpluck.extract import extract_pdf
    for n in [x for x in names if x.lower().endswith(".pdf")][:limit]:
        with open(os.path.join(path, n), "rb") as fh:
            data = fh.read()
        try:
            text, _engine = extract_pdf(data)  # TUPLE -- unpack
        except Exception as exc:  # noqa: BLE001
            print(f"  FAIL {n}: {type(exc).__name__}", file=sys.stderr)
            continue
        if not isinstance(text, str) or len(text) < 10_000:
            continue
        yield n, text


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("corpus")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--show", type=int, default=25)
    args = ap.parse_args(argv)

    try:
        from docpluck.render import _carries_statistical_content
    except Exception:  # noqa: BLE001
        def _carries_statistical_content(_s):  # type: ignore[misc]
            return False

    by_arm = collections.Counter()
    watermark_rows, once_rows, rejected_rows = [], [], []
    papers = 0
    map_changed = 0

    for name, text in _iter_texts(args.corpus, args.limit):
        papers += 1
        rows, paginated = census_one(text)
        old_rows, _ = census_one(text, use_old_map=True)
        old_q = {r["line"]: r["qualifies"] for r in old_rows}
        for r in rows:
            by_arm[r["arm"]] += 1
            r["paper"] = name
            r["stats"] = _carries_statistical_content(r["line"])
            if old_q.get(r["line"]) != r["qualifies"]:
                map_changed += 1
            if r["arm"] == "watermark_count>=20":
                watermark_rows.append(r)
            elif r["arm"] == "once_per_page":
                once_rows.append(r)
            elif r["arm"].startswith("rejected"):
                rejected_rows.append(r)

    print(f"corpus: {args.corpus}")
    print(f"papers: {papers}")
    print()
    print("DECISIONS BY ARM")
    for arm, n in by_arm.most_common():
        print(f"  {arm:<26} {n:>5}")
    print(f"\ncandidates whose VERDICT CHANGED under the corrected page map: {map_changed}")
    print("  (the old separation was computed on the wrong map and is void)")

    print(f"\n--- SEPARATION: kept-as-furniture vs rejected ---")
    def band(rows, label):
        if not rows:
            print(f"  {label:<24} (none)")
            return
        dp = [r['distinct_pages'] for r in rows]
        pp = [r['max_per_page'] for r in rows]
        ct = [r['count'] for r in rows]
        ns = sum(1 for r in rows if r['stats'])
        print(f"  {label:<24} n={len(rows):<4} pages {min(dp)}-{max(dp)}  "
              f"per_page {min(pp)}-{max(pp)}  count {min(ct)}-{max(ct)}  carry_stats={ns}")
    band(once_rows, "STRIPPED once_per_page")
    band(watermark_rows, "STRIPPED watermark>=20")
    band(rejected_rows, "KEPT (rejected)")

    print(f"\n--- THE count>=20 ARM, every firing ({len(watermark_rows)}) ---")
    if not watermark_rows:
        print("  ZERO firings on this corpus. A zero is a claim about the")
        print("  INSTRUMENT until a known positive is shown to fire -- so this")
        print("  says the arm is unexercised here, NOT that it is safe.")
    for r in sorted(watermark_rows, key=lambda x: -x["count"])[: args.show]:
        flag = "  <-- CARRIES STATS" if r["stats"] else ""
        print(f"  [{r['count']:>3}x on {r['distinct_pages']:>2}p, {r['max_per_page']}/page] "
              f"{r['paper']}{flag}")
        print(f"        {r['line'][:120]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
