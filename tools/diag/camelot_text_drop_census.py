"""How much printed text inside a delivered Camelot grid reaches NO cell?

Word-preservation census over the tables docpluck actually ships from Camelot.

WHY THIS EXISTS (measured 2026-09-25, 10.1136/bmjopen-2022-066361 p5 Table 2):
Camelot's stream parser groups textlines into rows by ``y0`` within
``row_tol=2``. Two header lines that share a TOP edge but whose bottoms differ by
more than 2 pt (one carries a subscript: ``Imatinib+vitamin D3``) become two row
groups, and ``_join_rows`` puts the shared boundary at
``(min_y0(upper) + max_y1(lower)) / 2`` -- which, for a one-line upper group
whose top equals the lower group's top, is bit-for-bit that line's own
``y_mid``. ``get_table_index`` then requires STRICT ``y_bot < y_mid < y_top`` on
both sides, so the line belongs to no row and Camelot 2.0.0 discards it
(``return [], 1.0``). Camelot 0.11.0 used the same strict test but a DIFFERENT
``_join_rows`` (boundaries at the midpoint between adjacent rows' mean
``y_mid``), which cannot put a boundary on a one-line row's own centre: swapping
the 0.11.0 ``_join_rows`` into 2.0.0 restores ``Imatinib+placebo`` on the
specimen. The regression is the ``_join_rows`` rewrite, not the vectorised
``get_table_index`` (which is bit-identical to the old loop).

The scan runs the PRODUCTION path (``extract_pdf_structured``) and reports, for
every Camelot grid docpluck delivers:

  * ``unassigned``  -- textlines ``get_table_index`` placed in no row (the
                       mechanism above), read from a spy on the real call;
  * ``col_miss``    -- textlines placed in a row but no column (Camelot writes
                       them into the last column: misplaced, not lost);
  * ``lost_words``  -- pdfplumber page words whose centre lies inside the grid's
                       area and whose text appears in NO cell of Camelot's grid.
                       This is the mechanism-independent measurement: it counts
                       loss from any cause, not only the one we know about.

TWO-SIDED. ``--self-test`` runs the known positive (the specimen above, through
the full production path) and an instrument control on ``lost_words`` itself
(the same word against a cell list that contains it / does not), and exits 1
unless the census reports >0, 0 and 1 respectively.

Usage:
    python tools/diag/camelot_text_drop_census.py --self-test
    python tools/diag/camelot_text_drop_census.py --out census.jsonl
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import unicodedata
from pathlib import Path

_REPO_ROOT = str(Path(__file__).resolve().parents[2])
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import docpluck

SPECIMEN = "vancouver/bmj_open_1.pdf"  # 10.1136/bmjopen-2022-066361

# What this run applied. Printed at start and written to every record, so an
# arm can never be mistaken for the other one.
TREATMENT = {"tie_fix": True}


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKC", s).casefold()
    return "".join(ch for ch in s if ch.isalnum())


def lost_words(page_words, bbox, grid):
    """Words whose centre is inside ``bbox`` (PDF coords, bottom-up, (x0,y0,x1,y1))
    and whose normalised text appears in no cell, nor in the row-major or
    column-major concatenation of the grid.

    The concatenations matter: pdfplumber fuses a tightly-set line into ONE
    "word" that Camelot legitimately splits across adjacent cells (measured on
    ama/jama_open_4 p6, a footnote line spanning a 6-column grid); per-cell
    matching alone reports that as a loss. A word Camelot genuinely dropped is
    absent from every reading.

    ``grid`` is a list of rows of cell strings; ``page_words`` are pdfplumber
    words already converted to PDF coords ``(text, x0, y0, x1, y1)``."""
    x0, y0, x1, y1 = bbox
    cells = [_norm(c) for row in grid for c in row if c]
    ncols = max((len(r) for r in grid), default=0)
    cells.append("".join(_norm(c) for row in grid for c in row))
    cells.append("".join(_norm(row[j]) for j in range(ncols) for row in grid if j < len(row)))
    out = []
    for text, wx0, wy0, wx1, wy1 in page_words:
        cx, cy = (wx0 + wx1) / 2, (wy0 + wy1) / 2
        if not (x0 <= cx <= x1 and y0 <= cy <= y1):
            continue
        n = _norm(text)
        if not n:
            continue
        # pdfplumber spells bottom-to-top rotated words BACKWARDS (",ssol" for
        # "loss,"); Camelot's vertical textlines do not. Accept either reading.
        rev = n[::-1]
        if not any(n in c or rev in c for c in cells):
            out.append((text, round(wx0, 1), round(wy0, 1), round(wx1, 1), round(wy1, 1)))
    return out


class _Spy:
    """Record every Camelot table converted by docpluck and every textline its
    ``get_table_index`` refused, WITHOUT changing either result."""

    def __init__(self):
        import camelot.parsers.base as pb

        from docpluck.tables import camelot_extract as ce

        self.pb, self.ce = pb, ce
        self.orig_gti = pb.get_table_index
        self.orig_to_dict = ce._camelot_table_to_dict
        self.records = []

        def gti(table, t, direction, **kw):
            res = self.orig_gti(table, t, direction, **kw)
            indices = res[0]
            txt = t.get_text().strip()
            if txt:
                if not indices:
                    # ``tie``: the line's centre sits EXACTLY on a row boundary --
                    # the _join_rows mechanism -- as opposed to outside every row.
                    y_mid = (t.y0 + t.y1) * 0.5
                    tie = any(bot == y_mid for _top, bot in table.rows)
                    table.__dict__.setdefault("_dp_unassigned", []).append(
                        (txt, round(t.x0, 1), round(t.y0, 1), round(t.x1, 1), round(t.y1, 1), tie))
                elif any(ix[1] == -1 for ix in indices):
                    table.__dict__.setdefault("_dp_colmiss", []).append(txt)
            return res

        def to_dict(ct, idx, **kw):
            td = self.orig_to_dict(ct, idx, **kw)
            self.records.append((ct, td, kw.get("id_prefix", "camelot_t")))
            return td

        self.gti, self.to_dict = gti, to_dict

    def __enter__(self):
        self.pb.get_table_index = self.gti
        self.ce._camelot_table_to_dict = self.to_dict
        return self

    def __exit__(self, *exc):
        self.pb.get_table_index = self.orig_gti
        self.ce._camelot_table_to_dict = self.orig_to_dict


def _page_words(pdf_path, cache):
    import pdfplumber

    if "pdf" not in cache:
        cache["pdf"] = pdfplumber.open(str(pdf_path))

    def get(pno: int):
        if pno not in cache:
            page = cache["pdf"].pages[pno - 1]
            h = float(page.height)
            cache[pno] = [
                (w["text"], float(w["x0"]), h - float(w["bottom"]), float(w["x1"]), h - float(w["top"]))
                for w in page.extract_words(keep_blank_chars=False, use_text_flow=False)
            ]
        return cache[pno]

    return get


def census_paper(pdf_path: Path, name: str):
    from docpluck.extract_structured import extract_pdf_structured

    pdf_bytes = pdf_path.read_bytes()
    # When the tree carries the boundary-tie fix, install its wrapper FIRST so
    # the spy wraps it and records what survives the fix, not what Camelot
    # alone would have done. On a tree without it this is a no-op.
    if TREATMENT["tie_fix"]:
        try:
            from docpluck.tables import camelot_row_ties
            camelot_row_ties._install()
        except ImportError:
            TREATMENT["tie_fix"] = "absent-from-tree"
    with _Spy() as spy:
        result = extract_pdf_structured(pdf_bytes)
    fb = result.get("fallbacks", {}) if isinstance(result, dict) else {}
    tie_assigned = fb.get("camelot_row_boundary_tie_assigned", 0)
    final_tables = result.get("tables", []) if isinstance(result, dict) else []
    final_cells_ids = {id(t.get("cells")) for t in final_tables}
    cache: dict = {}
    words_of = _page_words(pdf_path, cache)
    rows = []
    try:
        for ct, td, prefix in spy.records:
            grid = [[str(v) for v in row] for row in ct.df.values.tolist()]
            pno = int(ct.page)
            lw = lost_words(words_of(pno), ct._bbox, grid)
            un = ct.__dict__.get("_dp_unassigned", [])
            # a lost word explained by the no-row mechanism lies inside an unassigned textline
            def _in_un(w, un=un):
                cx, cy = (w[1] + w[3]) / 2, (w[2] + w[4]) / 2
                return any(u[1] - 0.5 <= cx <= u[3] + 0.5 and u[2] - 0.5 <= cy <= u[4] + 0.5 for u in un)
            rows.append({
                "paper": name,
                "page": pno,
                "flavor": getattr(ct, "flavor", None),
                "path": prefix,
                "shape": list(ct.df.shape),
                "converted": td is not None,
                "delivered": td is not None and id(td.get("cells")) in final_cells_ids,
                "label": (td or {}).get("label"),
                "unassigned": un,
                "col_miss": ct.__dict__.get("_dp_colmiss", []),
                "lost_words": lw,
                "lost_by_no_row": sum(1 for w in lw if _in_un(w)),
                "paper_tie_assigned": tie_assigned,
                "bbox": [round(v, 2) for v in ct._bbox],
                "grid": grid,
                "treatment": dict(TREATMENT),
            })
    finally:
        if "pdf" in cache:
            cache["pdf"].close()
    return rows


def self_test() -> int:
    """Known positive must report >0 lost words and >0 unassigned; a known
    negative (the missing text written back into a cell) must report 0."""
    import contextlib

    from docpluck.tables import camelot_extract as ce
    from docpluck.testing.corpus import require_corpus_pdf

    p = require_corpus_pdf(SPECIMEN)
    # Arm 1 -- Camelot alone (fix neutralised): the census must SEE the loss.
    real_scope = getattr(ce, "boundary_tie_scope", None)
    TREATMENT["tie_fix"] = False
    if real_scope is not None:
        ce.boundary_tie_scope = contextlib.nullcontext
    try:
        rows = census_paper(p, SPECIMEN)
    finally:
        if real_scope is not None:
            ce.boundary_tie_scope = real_scope
    hit = [r for r in rows if r["page"] == 5 and any("placebo" in u[0] for u in r["unassigned"])]
    pos_ok = bool(hit) and any(any("placebo" in w[0].lower() for w in r["lost_words"]) for r in hit)
    print(f"POSITIVE  {SPECIMEN} p5, no fix: grids with the placebo line unassigned={len(hit)}; "
          f"lost={[[w[0] for w in r['lost_words']] for r in hit]}")
    # Arm 2 -- with the fix (when the tree has it): the same census must see it RECOVERED.
    if real_scope is not None:
        TREATMENT["tie_fix"] = True
        rows2 = census_paper(p, SPECIMEN)
        still = [r for r in rows2 if r["page"] == 5
                 and any("placebo" in w[0].lower() for w in r["lost_words"])]
        print(f"FIXED     {SPECIMEN} p5, with fix: grids still losing the placebo line={len(still)} (want 0); "
              f"tie assignments counted={rows2[0]['paper_tie_assigned'] if rows2 else 0}")
        pos_ok = pos_ok and not still
    # Negative control: same page words, a cell list that DOES contain the text.
    neg_words = [("Imatinib+placebo", 370.0, 195.0, 446.0, 204.0)]
    neg = lost_words(neg_words, (40, 37, 555, 209), [["", "Imatinib+placebo group (n=31)"]])
    neg_pos = lost_words(neg_words, (40, 37, 555, 209), [["", "Imatinib+vitamin D3"]])
    print(f"NEGATIVE  text present in a cell -> lost={len(neg)} (want 0); absent -> lost={len(neg_pos)} (want 1)")
    ok = pos_ok and len(neg) == 0 and len(neg_pos) == 1
    print("SELF-TEST", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--out", default=None)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--no-tie-fix", action="store_true",
                    help="BEFORE arm: neutralise camelot_row_ties.boundary_tie_scope")
    args = ap.parse_args()
    if args.no_tie_fix:
        import contextlib

        from docpluck.tables import camelot_extract as ce
        if hasattr(ce, "boundary_tie_scope"):
            ce.boundary_tie_scope = contextlib.nullcontext
        TREATMENT["tie_fix"] = False
    print(f"TREATMENT {TREATMENT}")
    print(f"docpluck imported from {docpluck.__file__} ({docpluck.__version__})")
    import camelot
    print(f"camelot imported from {camelot.__file__} ({camelot.__version__})")
    if args.self_test:
        return self_test()

    from docpluck.testing.corpus import corpus_names, require_corpus_pdf

    names = corpus_names()[: args.limit] if args.limit else corpus_names()
    print(f"COVERAGE: {len(names)} manifest papers (docpluck.testing.corpus MANIFEST)")
    out = open(args.out, "w", encoding="utf-8") if args.out else None  # noqa: SIM115 - closed below
    tot = {"papers": 0, "errors": 0, "delivered": 0, "delivered_with_loss": 0,
           "lost_words": 0, "lost_by_no_row": 0, "unassigned_lines": 0, "unassigned_ties": 0,
           "papers_with_loss": set(), "papers_with_no_row": set()}
    for i, name in enumerate(names, 1):
        t0 = time.time()
        try:
            rows = census_paper(require_corpus_pdf(name), name)
        except Exception as exc:  # noqa: BLE001 - recorded per paper, never silent
            tot["errors"] += 1
            print(f"[{i}/{len(names)}] {name} ERROR {type(exc).__name__}: {exc}", flush=True)
            if out:
                out.write(json.dumps({"paper": name, "error": f"{type(exc).__name__}: {exc}"}) + "\n")
            continue
        tot["papers"] += 1
        d = [r for r in rows if r["delivered"]]
        for r in d:
            tot["delivered"] += 1
            if r["lost_words"]:
                tot["delivered_with_loss"] += 1
                tot["papers_with_loss"].add(name)
            tot["lost_words"] += len(r["lost_words"])
            tot["lost_by_no_row"] += r["lost_by_no_row"]
            tot["unassigned_lines"] += len(r["unassigned"])
            tot["unassigned_ties"] += sum(1 for u in r["unassigned"] if u[5])
            if r["unassigned"]:
                tot["papers_with_no_row"].add(name)
        if out:
            for r in rows:
                out.write(json.dumps(r) + "\n")
            out.flush()
        print(f"[{i}/{len(names)}] {name} grids={len(rows)} delivered={len(d)} "
              f"lost={sum(len(r['lost_words']) for r in d)} no_row_lines={sum(len(r['unassigned']) for r in d)} "
              f"({time.time() - t0:.0f}s)", flush=True)
    print("TOTALS", {k: (len(v) if isinstance(v, set) else v) for k, v in tot.items()})
    if out:
        out.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
