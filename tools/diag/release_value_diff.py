"""What does this tree change for CONSUMERS, value by value, against a released tag?

The gate the 2026-11-13 plan review asked for (G12 + extracted-value diff). A
row COUNT per paper passes when 12 rows are lost and 12 spurious ones appear,
and a render diff does not say which statistic moved. ESCImate saw the
2.4.153 -> 2.4.156 row changes before we did (letter 2026-10-30). This lists,
per paper, between two specimens (a tag and this tree by default):

* tables      -- (label, caption_status, rows x cols) added / removed / reshaped
* rows        -- flattened records keyed (table label, row label, column key),
                 every value added, removed or changed
* statistics  -- p / N / t / F / r / d / CI / df tokens parsed from the
                 NORMALIZED text (academic level), as multisets: a token that
                 vanished, appeared, or changed count
* status      -- tables_status / method pieces

Usage (from the repo root):

    python tools/diag/release_value_diff.py --base v2.4.159 [--limit N] [--workers 6]
        [--cache DIR] [--json OUT]

Exit 0 always for a completed run: this is an instrument that lists changes for a
human (and the page raster) to judge; a change is not a failure. It exits 2 when
the corpus could not be resolved, and prints the COVERAGE line every scan owes.

The per-paper dump of each specimen is cached under ``--cache`` (default: a
folder in the system temp dir, NEVER the repo: the dumps carry article text)
keyed by the specimen's resolved commit, so the base arm is computed once.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _corpus  # noqa: E402

_STAT = re.compile(
    r"(?<![A-Za-z])("
    r"[pP]\s*[<=>≤≥]\s*-?\.?\d[\d.]*"
    r"|[Nn]\s*=\s*\d[\d,]*"
    r"|[tF]\s*\(\s*\d[\d.,\s]*\)\s*=\s*-?\d[\d.]*"
    r"|χ2\s*\([^)]{1,20}\)\s*=\s*\d[\d.]*|chi2\s*\([^)]{1,20}\)\s*=\s*\d[\d.]*"
    r"|[rdgβ]\s*=\s*-?\.?\d[\d.]*"
    r"|(?:95|90|99)%\s*CI\s*[\[(]\s*-?\.?\d[\d.]*\s*,\s*-?\.?\d[\d.]*\s*[\])]"
    r")"
)


def _norm_tok(s: str) -> str:
    return re.sub(r"\s+", "", s)


# Bump when dump_paper records something new, so a cached dump made by an
# older tool is not compared against a newer one (2: normalization events).
DUMP_SCHEMA = 2


def dump_paper(path_str: str) -> dict:
    """Module-level so run_arms can pickle it; imports docpluck INSIDE."""
    import copy

    import docpluck
    from docpluck import (
        NormalizationLevel,
        extract_pdf_structured,
        flatten_tables_for_paper,
        normalize_text,
    )

    p = Path(path_str)
    out: dict = {"paper": p.name, "docpluck": docpluck.__file__}
    try:
        b = p.read_bytes()
        s = extract_pdf_structured(b)
        tables = []
        for t in s.get("tables") or []:
            cells = t.get("cells") or []
            nr = 1 + max((c.get("r", 0) for c in cells), default=-1)
            nc = 1 + max((c.get("c", 0) for c in cells), default=-1)
            tables.append({
                "label": t.get("label") or t.get("id"),
                "status": t.get("caption_status"),
                "page": t.get("page"),
                "shape": [nr, nc],
                "cells": sorted(str(c.get("text", "")) for c in cells),
            })
        rows = []
        for r in flatten_tables_for_paper(copy.deepcopy(s.get("tables") or [])):
            d = r if isinstance(r, dict) else getattr(r, "__dict__", {})
            fields = d.get("fields") or {}
            label = d.get("table_label") or d.get("label") or d.get("table_id")
            rl = d.get("row_label") or ""
            for k, v in (fields.items() if isinstance(fields, dict) else []):
                rows.append([str(label), str(rl), str(k), str(v)])
            if not fields:
                rows.append([str(label), str(rl), "<no fields>", ""])
        # Normalization's own events (a refused join, a removed line) are
        # recorded in a scope of their own, or no firing count reaches us.
        try:
            from docpluck.telemetry import fallback_scope
        except ImportError:  # a specimen older than the telemetry module
            fallback_scope = None
        if fallback_scope is not None:
            with fallback_scope() as nfb:
                text, _rep = normalize_text(s.get("text") or "", NormalizationLevel.academic)
            norm_fb = {f"normalize:{k}": v for k, v in nfb.counters.items()}
        else:
            text, _rep = normalize_text(s.get("text") or "", NormalizationLevel.academic)
            norm_fb = {}
        stats = Counter(_norm_tok(m.group(1)) for m in _STAT.finditer(text))
        out.update({
            "tables": tables,
            "rows": rows,
            "stats": dict(stats),
            "tables_status": s.get("tables_status"),
            "method": s.get("method"),
            "fallbacks": {**(s.get("fallbacks") or {}), **norm_fb},
            "text_sha": hashlib.sha256(text.encode("utf-8")).hexdigest()[:16],
        })
    except Exception as exc:  # an instrument must report, not die, per paper
        out["error"] = f"{type(exc).__name__}: {exc}"[:300]
    return out


def _diff_paper(a: dict, b: dict) -> dict:
    d: dict = {}
    if a.get("error") or b.get("error"):
        if a.get("error") != b.get("error"):
            d["error"] = [a.get("error"), b.get("error")]
        return d
    ta = {(t["label"], t["page"]): t for t in a["tables"]}
    tb = {(t["label"], t["page"]): t for t in b["tables"]}
    tab = []
    for k in sorted(set(ta) | set(tb), key=str):
        x, y = ta.get(k), tb.get(k)
        if x is None:
            tab.append(f"+ {k[0]} p{k[1]} {y['status']} {y['shape']}")
        elif y is None:
            tab.append(f"- {k[0]} p{k[1]} {x['status']} {x['shape']}")
        elif (x["shape"], x["status"], x["cells"]) != (y["shape"], y["status"], y["cells"]):
            lost = Counter(x["cells"]) - Counter(y["cells"])
            got = Counter(y["cells"]) - Counter(x["cells"])
            tab.append(f"~ {k[0]} p{k[1]} {x['status']}->{y['status']} "
                       f"{x['shape']}->{y['shape']} cells -{sum(lost.values())} "
                       f"+{sum(got.values())} e.g. -{list(lost)[:3]} +{list(got)[:3]}")
    if tab:
        d["tables"] = tab
    ra = Counter(tuple(r) for r in a["rows"])
    rb = Counter(tuple(r) for r in b["rows"])
    if ra != rb:
        d["rows_lost"] = [list(r) for r in (ra - rb)][:40]
        d["rows_gained"] = [list(r) for r in (rb - ra)][:40]
        d["rows_count"] = [sum(ra.values()), sum(rb.values())]
    sa, sb = Counter(a["stats"]), Counter(b["stats"])
    if sa != sb:
        d["stats_lost"] = dict(sa - sb)
        d["stats_gained"] = dict(sb - sa)
    if a.get("tables_status") != b.get("tables_status"):
        d["tables_status"] = [a.get("tables_status"), b.get("tables_status")]
    if a.get("text_sha") != b.get("text_sha"):
        d["text_changed"] = True
    return d


def _cached_arm(request: str, papers: list[Path], cache: Path, workers: int) -> list[dict]:
    """Dump every paper with one specimen; reuse a cached dump of a CLEAN commit."""
    is_tree = Path(request).resolve() == Path(_corpus._REPO_ROOT).resolve()
    if is_tree:
        dirty = _corpus._repo_git("status", "--porcelain", "--", "docpluck").stdout.strip()
        sha = _corpus._repo_git("rev-parse", "HEAD").stdout.strip()
        if dirty:
            # An uncommitted tree is cached under a hash of its library content,
            # so a crash after a 40-minute dump does not cost the dump.
            h = hashlib.sha256(sha.encode())
            for p in sorted(Path(_corpus._REPO_ROOT, "docpluck").rglob("*.py")):
                h.update(str(p.relative_to(_corpus._REPO_ROOT)).encode())
                h.update(p.read_bytes())
            sha = "tree-" + h.hexdigest()[:24]
    else:
        sha = _corpus._repo_git("rev-parse", f"{request}^{{commit}}").stdout.strip() or None
    f = cache / f"{sha}.dump{DUMP_SCHEMA}.json" if sha else None
    if f and f.exists():
        data = json.loads(f.read_text(encoding="utf-8"))
        if [d["paper"] for d in data] == [p.name for p in papers]:
            print(f"arm {request}: cached dump {f.name}")
            return data
    arms = _corpus.run_arms(dump_paper, [str(p) for p in papers], [request], workers=workers)
    print(f"arm {request}: imported {arms[0].resolved} version {arms[0].version}")
    data = arms[0].results
    if f:
        f.write_text(json.dumps(data), encoding="utf-8")
    return data


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--base", required=True, help="git ref of the released specimen, e.g. v2.4.159")
    ap.add_argument("--head", default=".", help="specimen to compare (default this tree)")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--cache", default=os.path.join(tempfile.gettempdir(), "docpluck_value_diff"))
    ap.add_argument("--json", help="write the full diff here (outside the repo)")
    args = ap.parse_args(argv)

    papers = _corpus.docpluck_corpus()
    if args.limit:
        papers = papers[: args.limit]
    print(_corpus.coverage_line())
    print(f"COVERAGE (this scan): {len(papers)} papers from docpluck_corpus()"
          + (f", first {args.limit} only" if args.limit else ""))
    cache = Path(args.cache)
    cache.mkdir(parents=True, exist_ok=True)
    base = _cached_arm(args.base, papers, cache, args.workers)
    head = _cached_arm(_corpus._REPO_ROOT if args.head == "." else args.head, papers, cache, args.workers)

    # Windows consoles default to cp1252; article text is not.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    report = {}
    for a, b in zip(base, head):
        d = _diff_paper(a, b)
        if d:
            report[a["paper"]] = d
    if args.json:
        Path(args.json).write_text(json.dumps(report, indent=1), encoding="utf-8")
    # A key the base release did not have changes every paper; say it once.
    new_status = Counter(d.pop("tables_status")[1] for d in report.values()
                         if (d.get("tables_status") or [0])[0] is None and "tables_status" in d)
    if new_status:
        print(f"tables_status is new in head (base has none): {dict(new_status)}")
    report = {k: d for k, d in report.items() if d}
    n_err = sum(1 for x in head if x.get("error"))
    print(f"papers {len(papers)}; changed {len(report)}; head errors {n_err}")
    # Firing counts per fallback event, base vs head: a new rule ships with
    # how often it fires on the corpus (CLAUDE.md three-tiers rule).
    fa, fh = Counter(), Counter()
    for x in base:
        fa.update(x.get("fallbacks") or {})
    for x in head:
        fh.update(x.get("fallbacks") or {})
    moved = {e: (fa.get(e, 0), fh.get(e, 0)) for e in set(fa) | set(fh) if fa.get(e, 0) != fh.get(e, 0)}
    if moved:
        print("fallback firings that moved (base -> head; base pre-dates the field if all 0):")
        for e, (x, y) in sorted(moved.items()):
            print(f"  {e}: {x} -> {y}")
    for paper, d in report.items():
        print(f"\n## {paper}")
        for k, v in d.items():
            if k == "tables":
                for line in v:
                    print("  " + line)
            elif k in ("rows_lost", "rows_gained"):
                print(f"  {k} ({len(v)} shown): {v[:6]}")
            else:
                print(f"  {k}: {v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
