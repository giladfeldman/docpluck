"""What do the 2026-11-11 table rules change, table by table?

Five rules, each with an "old behaviour" it can be switched back to in-process:

    tie        ``_find_caption_for_table`` breaks a word-overlap tie by the caption
               printed above the grid (old: earliest caption in the text)
    partial    ``_grid_covers_little_of_printed_table`` sets aside a grid holding
               under a quarter of the printed table's tokens (old: never)
    colbody    ``_column_body_text`` ends at the table note / the next numbered
               section heading (old: runs to the column's 640 pt bound)
    straddle   ``_attach_straddling_sign_cells`` joins a sign-above / digits-below
               cell into its row (old: rows kept as captured)
    letters    ``_mark_raised_letter_markers`` marks a raised footnote letter in a
               cell, ``errora`` -> ``error^a`` (old: left glued)

Arm A runs the shipped code and records, per rule, every call whose result differs
from the old behaviour (computed in the same call). A paper with no firing is
identical in both arms by construction; arm B (all five rules off) runs only on
papers with a firing. For every table on a fired page both arms' shape, content
status and numeric-token count are printed, plus the numbers present in B and
absent in A.

A SCREEN, NOT AN ORACLE: every CHANGED table still has to be read against its page.

Usage:  python tools/diag/table_pairing_completeness_diff.py [--manifest] [--limit N] [--workers N]
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.diag._corpus import baseline_corpus, coverage_line  # noqa: E402

_NUM = re.compile(r"[-−–]?\d*\.?\d+")


def _numbers(t: dict) -> Counter:
    cells = t.get("cells") or []
    text = " ".join(str(c.get("text", "")) for c in cells) if cells else (t.get("raw_text") or "")
    if t.get("html"):
        text += " " + re.sub(r"<[^>]+>", " ", t["html"])
    return Counter(m.replace("−", "-").replace("–", "-") for m in _NUM.findall(text))


def _summary(t: dict) -> str:
    return (f"{t.get('n_rows', 0)}x{t.get('n_cols', 0)} {t.get('content_status')} "
            f"raw={len(t.get('raw_text') or '')} nums={sum(_numbers(t).values())}")


def _run(item: tuple[str, str]) -> tuple[str, list[str], list[str]]:
    key, path = item
    import warnings
    warnings.filterwarnings("ignore")
    import docpluck.extract_structured as E
    import docpluck.tables.cell_cleaning as CC

    fired: list[tuple[str, int, str]] = []
    o_find, o_partial, o_colbody, o_straddle = (
        E._find_caption_for_table, E._grid_covers_little_of_printed_table,
        E._column_body_text, CC._attach_straddling_sign_cells,
    )
    o_head, o_cut = E._MULTILEVEL_SECTION_HEADING_RE, E._cut_after_note_paragraph
    o_letters = CC._mark_raised_letter_markers

    def letters(cells, layout):
        before = [c.get("text") for c in cells]
        o_letters(cells, layout)
        for b, c in zip(before, cells):
            if b != c.get("text"):
                fired.append(("letters", 0, f"{b!r}->{c.get('text')!r}"))
    never = re.compile(r"(?!x)x")

    def find(ct, caps, used, layout_doc=None):
        new = o_find(ct, caps, used, layout_doc=layout_doc)
        if new is not o_find(ct, caps, used, layout_doc=None):
            fired.append(("tie", ct.get("page") or 0, new.label if new else "?"))
        return new

    def partial(td, body):
        r = o_partial(td, body)
        if r:
            fired.append(("partial", td.get("page") or 0, str(td.get("label") or td.get("id"))))
        return r

    def colbody(layout_doc, cap, **kw):
        new = o_colbody(layout_doc, cap, **kw)
        E._MULTILEVEL_SECTION_HEADING_RE, E._cut_after_note_paragraph = never, (lambda x: x)
        try:
            old = o_colbody(layout_doc, cap, **kw)
        finally:
            E._MULTILEVEL_SECTION_HEADING_RE, E._cut_after_note_paragraph = o_head, o_cut
        if new != old:
            fired.append(("colbody", cap.page, cap.label or "?"))
        return new

    def straddle(rows):
        new = o_straddle(rows)
        if new != [list(r) for r in rows]:
            fired.append(("straddle", 0, "?"))
        return new

    def arm_on():
        E._find_caption_for_table, E._grid_covers_little_of_printed_table = find, partial
        E._column_body_text, CC._attach_straddling_sign_cells = colbody, straddle
        CC._mark_raised_letter_markers = letters

    def arm_off():
        E._find_caption_for_table = lambda ct, caps, used, layout_doc=None: o_find(ct, caps, used)
        E._grid_covers_little_of_printed_table = lambda td, body: False
        E._column_body_text = lambda *a, **k: (_old_colbody(a, k))
        CC._attach_straddling_sign_cells = lambda rows: [list(r) for r in rows]
        CC._mark_raised_letter_markers = lambda cells, layout: None

    def _old_colbody(a, k):
        E._MULTILEVEL_SECTION_HEADING_RE, E._cut_after_note_paragraph = never, (lambda x: x)
        try:
            return o_colbody(*a, **k)
        finally:
            E._MULTILEVEL_SECTION_HEADING_RE, E._cut_after_note_paragraph = o_head, o_cut

    def restore():
        E._find_caption_for_table, E._grid_covers_little_of_printed_table = o_find, o_partial
        E._column_body_text, CC._attach_straddling_sign_cells = o_colbody, o_straddle
        CC._mark_raised_letter_markers = o_letters

    pdf = Path(path).read_bytes()
    arm_on()
    try:
        a = E.extract_pdf_structured(pdf)
    except Exception as exc:  # noqa: BLE001
        return key, [f"ERROR arm A {type(exc).__name__}: {exc}"], []
    finally:
        restore()
    if not fired:
        return key, [], []
    arm_off()
    try:
        b = E.extract_pdf_structured(pdf)
    except Exception as exc:  # noqa: BLE001
        return key, [f"ERROR arm B {type(exc).__name__}: {exc}"], []
    finally:
        restore()

    lines = [f"fired: {sorted(set(fired))}"]
    lost_lines: list[str] = []

    def by_label(r):
        return {(t.get("page"), t.get("label") or t.get("id")): t for t in r["tables"]}

    ta, tb = by_label(a), by_label(b)
    for k in sorted(set(ta) | set(tb), key=lambda x: (x[0] or 0, str(x[1]))):
        ra, rb = ta.get(k), tb.get(k)
        if ra is not None and rb is not None and (
            ra.get("cells"), ra.get("raw_text"), ra.get("html")
        ) == (rb.get("cells"), rb.get("raw_text"), rb.get("html")):
            continue
        sa = _summary(ra) if ra is not None else "absent"
        sb = _summary(rb) if rb is not None else "absent"
        lines.append(f"  CHANGED p{k[0]} {k[1]}: B[{sb}] -> A[{sa}]")
        if rb is not None:
            lost = _numbers(rb) - (_numbers(ra) if ra is not None else Counter())
            if lost:
                lost_lines.append(f"  p{k[0]} {k[1]} numbers in B not in A: {dict(lost)}")
    return key, lines, lost_lines


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--keys", default="",
                    help="comma-separated manifest keys (file stems) to run, e.g. the papers a previous run fired on")
    ap.add_argument("--manifest", action="store_true",
                    help="every paper of the test manifest (docpluck.testing.corpus), not the baseline")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    if args.manifest or args.keys:
        from docpluck.testing.corpus import corpus_pdfs
        corpus = [(p.stem, p) for p in corpus_pdfs()]
        if args.keys:
            wanted = set(args.keys.split(","))
            corpus = [(k, p) for k, p in corpus if k in wanted]
        corpus = corpus[: args.limit]
    else:
        corpus = baseline_corpus(args.limit)
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
