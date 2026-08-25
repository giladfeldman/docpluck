#!/usr/bin/env python3
r"""How many of pdftotext's PAGE BOUNDARIES does normalization destroy?

A page NUMBER is furniture; a page BOUNDARY is structure (LESSONS L-052,
NORMALIZATION_VERSION 1.9.57). v1.9.57 fixed ONE site that consumed the form
feed standing beside the thing it deleted -- `_strip_standalone_page_numbers`,
plus `_drop()` inside F0. This scan asks the question of the WHOLE pipeline,
because the same shape can occur in any rule that deletes a LINE:

    pdftotext emits the page break at the START of the new page's first line,
    so that line is "\fD.J. Leonard et al. / Journal ...". Python's `.strip()`
    and `.split()` treat U+000C as whitespace, so a rule that tests
    `line.strip() in <furniture set>` and then drops the line takes the page
    boundary with it -- silently, and with no key in `changes_made`.

Why it matters beyond tidiness: pdftotext's form feeds ARE the text channel's
page index. Measured over 30 sampled papers on 2026-08-22, `raw_text.count("\f")`
equals `pdfinfo`'s page count on **30 of 30**. So the form feeds are the cheap,
offset-preserving route to `Section.pages` -- which is `()` today on every
section of every format -- and every one destroyed is a page number a consumer
cannot give back to an author. Scimeto asked for `Section.pages` on 2026-08-21:
"Page numbers are how a finding becomes checkable by the author."

The scan reports, per paper: pdfinfo pages, raw form feeds, surviving form feeds
after `normalize_text(academic)`, and -- with `--attribute` -- the exact
`normalize.py` line that dropped each one, found by a line-level trace of the
pipeline variable rather than by reading the source.

Usage:
    python tools/diag/page_break_loss_scan.py --baseline
    python tools/diag/page_break_loss_scan.py --sample 30
    python tools/diag/page_break_loss_scan.py --sample 5 --attribute
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.diag._corpus import (  # noqa: E402
    CorpusUnavailable,
    baseline_corpus,
    coverage_line,
    sampled_corpus,
)

import docpluck.normalize as _norm  # noqa: E402
from docpluck.extract import extract_pdf  # noqa: E402
from docpluck.normalize import NormalizationLevel, normalize_text  # noqa: E402

FF = "\f"


def pdfinfo_pages(path: Path) -> int | None:
    """Ground-truth page count from poppler. `None` when pdfinfo is absent.

    poppler, never PyMuPDF -- the AGPL ban is a hard rule (LESSONS L-003).
    """
    try:
        out = subprocess.run(
            ["pdfinfo", str(path)], capture_output=True, text=True, timeout=60
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    for line in out.splitlines():
        if line.startswith("Pages:"):
            try:
                return int(line.split(":", 1)[1].strip())
            except ValueError:
                return None
    return None


def attribute_losses(raw: str) -> list[tuple[str, int, int, int]]:
    """Name the normalize.py LINE that dropped each form feed.

    Line-level trace of `_normalize_text`'s pipeline variable `t`, so the answer
    comes from what the code DID rather than from reading it -- the reason this
    class survived a release that believed it had fixed it is that reading found
    one site and there were three.

    Returns (function, normalize.py line number, count before, count after).
    """
    norm_file = _norm.__file__
    drops: list[tuple[str, int, int, int]] = []
    prev: dict[str, object] = {"line": None, "ff": None}

    def tracer(frame, event, arg):
        if frame.f_code.co_filename != norm_file:
            return None
        if event == "call":
            return tracer
        if event == "line":
            v = frame.f_locals.get("t")
            if isinstance(v, str):
                c = v.count(FF)
                before = prev["ff"]
                if isinstance(before, int) and c < before:
                    drops.append(
                        (frame.f_code.co_name, int(prev["line"] or 0), before, c)
                    )
                prev["ff"] = c
            prev["line"] = frame.f_lineno
        return tracer

    sys.settrace(tracer)
    try:
        normalize_text(raw, NormalizationLevel.academic)
    finally:
        sys.settrace(None)
    return drops


def main() -> int:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--baseline", action="store_true", help="the render baseline corpus")
    g.add_argument("--sample", type=int, metavar="N", help="N papers from the repository")
    ap.add_argument(
        "--attribute",
        action="store_true",
        help="trace which normalize.py line dropped each break (slow: ~40s/paper)",
    )
    args = ap.parse_args()

    try:
        papers = baseline_corpus() if args.baseline else sampled_corpus(args.sample)
    except CorpusUnavailable as exc:
        print(exc)
        return 2

    print(coverage_line())
    print()

    src = Path(_norm.__file__).read_text(encoding="utf-8").splitlines()
    rows = []
    sites: dict[tuple[str, int], int] = {}

    for key, path in papers:
        try:
            raw, _method = extract_pdf(path.read_bytes())
            out, _rep = normalize_text(raw, NormalizationLevel.academic)
        except Exception as exc:  # a paper that cannot be read is reported, not skipped
            print(f"  !! {key}: {type(exc).__name__}: {exc}")
            continue
        pages = pdfinfo_pages(path)
        rows.append((key, pages, raw.count(FF), out.count(FF)))
        if args.attribute:
            for fn, line, before, after in attribute_losses(raw):
                sites[(fn, line)] = sites.get((fn, line), 0) + (before - after)

    if not rows:
        print("no paper produced a measurement -- this is UNBOUNDED, not clean")
        return 2

    print(f"{'paper':<44} {'pdfinfo':>7} {'raw \\f':>7} {'kept':>5}  {'lost':>5}")
    for key, pages, raw_ff, keep_ff in sorted(rows, key=lambda r: r[3] - r[2]):
        pg = str(pages) if pages is not None else "?"
        print(f"{key[:44]:<44} {pg:>7} {raw_ff:>7} {keep_ff:>5}  {raw_ff - keep_ff:>5}")

    tot_raw = sum(r[2] for r in rows)
    tot_keep = sum(r[3] for r in rows)
    exact = sum(1 for r in rows if r[1] is not None and r[2] == r[1])
    with_pages = sum(1 for r in rows if r[1] is not None)
    all_gone = sum(1 for r in rows if r[2] and r[3] == 0)

    print()
    print(f"papers                                 : {len(rows)}")
    if with_pages:
        print(f"raw form feeds == pdfinfo page count   : {exact} / {with_pages}")
    print(f"form feeds  raw -> normalized          : {tot_raw} -> {tot_keep}"
          f"  ({tot_keep / tot_raw:.1%} survive)" if tot_raw else "")
    print(f"papers left with NO page boundary at all: {all_gone} / {len(rows)}")

    if args.attribute:
        print("\nWHERE THEY GO (normalize.py line -> form feeds dropped):")
        for (fn, line), n in sorted(sites.items(), key=lambda kv: -kv[1]):
            code = src[line - 1].strip()[:88] if 0 < line <= len(src) else "?"
            print(f"  {n:>4}  {fn}  normalize.py:{line}  | {code}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
