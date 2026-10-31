"""What does the caption_only rule-extent widening (``detect._caption_rule_extent``) do,
table by table?

Two arms in one process, per corpus paper:

    arm A   the shipped code
    arm B   ``_caption_rule_extent`` neutralised (returns None), i.e. the caption_only
            region stays at the caption's width and the search band's depth

Arm A records every region the rule actually changed. A paper where it changed no
region is identical in both arms by construction, so arm B runs only on papers with a
firing. For every table on a fired page the tool prints both arms' shape, content
status and the count of numeric tokens the table carries (cells, or raw_text when it
has no cells) -- a numeric token present in B and absent in A is content the change lost.

A SCREEN, NOT AN ORACLE: a changed table still has to be read against its page raster.
The numeric count scores content LOST only; content the wider region GAINED (prose or a
neighbouring table pulled in) and a different cell assignment show only as a changed
shape, so read every changed table, not just those with lost numbers.

Usage:  python tools/diag/caption_rule_extent_diff.py [--limit N | --sample N] [--workers N]
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.diag._corpus import baseline_corpus, coverage_line, sampled_corpus  # noqa: E402

_NUM = re.compile(r"[-−–]?\d*\.?\d+")


def _numbers(t: dict) -> Counter:
    cells = t.get("cells") or []
    text = " ".join(str(c.get("text", "")) for c in cells) if cells else (t.get("raw_text") or "")
    return Counter(m.replace("−", "-").replace("–", "-") for m in _NUM.findall(text))


def _summary(t: dict) -> str:
    return (f"{t.get('n_rows', 0)}x{t.get('n_cols', 0)} {t.get('content_status')} "
            f"nums={sum(_numbers(t).values())}")


def _run(item: tuple[str, str]) -> tuple[str, list[str], list[str]]:
    key, path = item
    import warnings
    warnings.filterwarnings("ignore")
    import docpluck.tables.detect as D
    from docpluck.extract_structured import extract_pdf_structured

    orig = D._caption_rule_extent
    fired: list[tuple[int, str]] = []
    cur: dict = {}

    orig_rfc = D._region_for_caption

    def rfc(layout, cap):
        cur["cap"] = cap
        return orig_rfc(layout, cap)

    def hooked(page_obj, caption_bbox, *, band_bottom):
        r = orig(page_obj, caption_bbox, band_bottom=band_bottom)
        # Any extent can change the region: wider, deeper (a narrower rule
        # family under a whitespace region), or rule_bounded alone.
        if r is not None:
            cap = cur.get("cap")
            fired.append((cap.page if cap else -1, cap.label if cap else "?"))
        return r

    pdf = Path(path).read_bytes()
    D._region_for_caption = rfc
    D._caption_rule_extent = hooked
    try:
        a = extract_pdf_structured(pdf)
    except Exception as exc:  # noqa: BLE001
        return key, [f"ERROR arm A {type(exc).__name__}: {exc}"], []
    finally:
        D._caption_rule_extent = orig
    if not fired:
        D._region_for_caption = orig_rfc
        return key, [], []
    D._caption_rule_extent = lambda *x, **k: None
    try:
        b = extract_pdf_structured(pdf)
    except Exception as exc:  # noqa: BLE001
        return key, [f"ERROR arm B {type(exc).__name__}: {exc}"], []
    finally:
        D._caption_rule_extent = orig
        D._region_for_caption = orig_rfc

    pages = {p for p, _ in fired}
    lines = [f"fired: {sorted(set(fired))}"]
    lost_lines: list[str] = []

    def by_label(r):
        return {(t.get("page"), t.get("label") or t.get("id")): t for t in r["tables"] if t.get("page") in pages}

    ta, tb = by_label(a), by_label(b)
    for k in sorted(set(ta) | set(tb), key=lambda x: (x[0] or 0, str(x[1]))):
        sa = _summary(ta[k]) if k in ta else "absent"
        sb = _summary(tb[k]) if k in tb else "absent"
        flag = "" if sa == sb else "  CHANGED"
        lines.append(f"  p{k[0]} {k[1]}: B[{sb}] -> A[{sa}]{flag}")
        if k in tb:
            lost = _numbers(tb[k]) - (_numbers(ta[k]) if k in ta else Counter())
            if lost:
                lost_lines.append(f"  p{k[0]} {k[1]} numbers in B not in A: {dict(lost)}")
    return key, lines, lost_lines


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--sample", type=int, default=None,
                    help="a seeded sample of the shared repository instead of the baseline")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")  # page text holds ligatures (U+FB03)
    corpus = sampled_corpus(args.sample) if args.sample else baseline_corpus(args.limit)
    print(coverage_line())
    n_fired = n_lost = 0
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        for key, lines, lost in ex.map(_run, [(k, str(p)) for k, p in corpus]):
            if lines:
                n_fired += 1
                print(key)
                for ln in lines + lost:
                    print(ln)
            if lost:
                n_lost += 1
            sys.stdout.flush()
    print(f"papers={len(corpus)} fired={n_fired} with_numbers_lost={n_lost}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
