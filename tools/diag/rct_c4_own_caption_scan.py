"""Guard-diff for the RC-T cycle-4 own-caption exemption in ``_whitespace_grid_is_clean``.

The cycle-4 fix exempts a caption-anchored region's OWN caption (a ``Table N.`` cell in
the grid's leading rows) from the caption-absorption reject, because
``detect._region_for_caption`` includes the caption in the region by construction.

This scan runs the OLD and NEW guard over every table region of every corpus PDF and
reports, per caption, whether the verdict CHANGED. The fix is only safe if every change
is REJECT->ACCEPT (a recovered grid) and never ACCEPT->REJECT, and if each newly-accepted
grid's leading caption really is its OWN (number matches the anchoring caption) rather
than a neighbour's.

Usage:  py -3 tools/diag/rct_c4_own_caption_scan.py [--limit N]
"""
from __future__ import annotations

import argparse
import glob
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from docpluck.extract_layout import extract_pdf_layout
from docpluck.tables.captions import find_caption_matches
from docpluck.tables.detect import _region_for_caption
import docpluck.tables.whitespace as ws


def _old_guard(cells, *, allow_categorical: bool = False) -> bool:
    """The PRE-cycle-4 guard: ANY caption label anywhere condemns the grid.

    Reproduces only the OLD CAPTION RULE here; everything downstream of it is
    delegated to the real (current) guard, so this diff isolates exactly the one
    rule cycle 4 changed. Delegation is safe because the caption rule is a pure
    veto that runs before any other check — if no cell carries a caption label,
    old and new are identical by construction.
    """
    if not cells:
        return False
    for c in cells:
        if ws._CAPTION_LABEL_RE.search(c.get("text") or ""):
            return False
    # No caption label survived, so the own-caption exemption is a no-op here and
    # the current guard reproduces the old downstream behaviour exactly.
    return ws._whitespace_grid_is_clean(cells, allow_categorical=allow_categorical)


def _grid_for(layout, region):
    """Rebuild the pre-guard cell grid exactly as whitespace_cells does."""
    words = ws.words_in_bbox(layout, bbox=region.bbox, page=region.page)
    if len(words) < ws.WHITESPACE_MIN_ROWS:
        return None
    rows = ws._cluster_into_rows(words)
    if len(rows) < ws.WHITESPACE_MIN_ROWS:
        return None
    colxs = ws._find_stable_column_boundaries(rows, bbox=region.bbox)
    if len(colxs) >= 3:
        join = lambda inc: " ".join(w.get("text", "") for w in inc)
    else:
        items = [c for c in ws.chars_in_bbox(layout, bbox=region.bbox, page=region.page)
                 if (c.get("text", "") or "").strip()]
        if len(items) < ws.WHITESPACE_MIN_ROWS:
            return None
        rows = ws._cluster_into_rows(items)
        if len(rows) < ws.WHITESPACE_MIN_ROWS:
            return None
        colxs = ws._find_stable_column_boundaries(
            rows, bbox=region.bbox,
            gap_pt=ws.CHAR_COLUMN_GAP_PT, bucket_pt=ws.CHAR_BOUNDARY_BUCKET_PT,
        )
        if len(colxs) < 3:
            return None
        join = ws._join_chars
    cells = []
    for r, rw in enumerate(rows):
        if not rw:
            continue
        rt = min(w["top"] for w in rw)
        rb = max(w["bottom"] for w in rw)
        for c, (xl, xr) in enumerate(zip(colxs[:-1], colxs[1:])):
            inc = sorted([w for w in rw if xl <= (w["x0"] + w["x1"]) / 2 <= xr],
                         key=lambda w: w["x0"])
            cells.append({
                "r": r, "c": c, "rowspan": 1, "colspan": 1,
                "text": ws._normalize_cell_text(join(inc)),
                "is_header": r == 0, "bbox": (xl, rt, xr, rb),
            })
    return ws._trim_trailing_prose_rows(cells)


_NUM_RE = re.compile(r"\b(?:Table|TABLE)\s+(\d+)\s*[.:]")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--corpus", default="../PDFextractor/test-pdfs")
    args = ap.parse_args()

    pdfs = sorted(glob.glob(os.path.join(args.corpus, "**", "*.pdf"), recursive=True))
    if args.limit:
        pdfs = pdfs[: args.limit]
    print(f"scanning {len(pdfs)} PDFs")

    recovered = regressed = same = 0
    suspicious: list[str] = []
    for path in pdfs:
        stem = os.path.basename(path)
        try:
            layout = extract_pdf_layout(open(path, "rb").read())
            caps = [c for c in find_caption_matches(layout.raw_text, list(layout.page_offsets))
                    if c.kind == "table"]
        except Exception as exc:
            print(f"  !! {stem}: {type(exc).__name__}: {exc}")
            continue
        for cap in caps:
            try:
                region = _region_for_caption(layout, cap)
            except Exception:
                continue
            if region is None:
                continue
            cells = _grid_for(layout, region)
            if not cells:
                continue
            old = _old_guard(cells)
            new = ws._whitespace_grid_is_clean(cells, own_caption_number=cap.number)
            if old == new:
                same += 1
                continue
            if new and not old:
                recovered += 1
                # The newly-accepted grid's leading caption must be its OWN.
                lead = ""
                for c in sorted(cells, key=lambda c: (c["r"], c["c"])):
                    if ws._CAPTION_LABEL_RE.search(c.get("text") or ""):
                        lead = c.get("text") or ""
                        break
                m = _NUM_RE.search(lead)
                if m and cap.number is not None and int(m.group(1)) != cap.number:
                    suspicious.append(
                        f"{stem} T{cap.number}: newly accepted but leading caption is "
                        f"Table {m.group(1)} — FOREIGN, investigate"
                    )
                print(f"  RECOVER {stem} T{cap.number}: {len(cells)} cells  lead={lead[:50]!r}")
            else:
                regressed += 1
                print(f"  !! REGRESS {stem} T{cap.number}: was accepted, now rejected")

    print(f"\nunchanged={same} recovered={recovered} regressed={regressed}")
    if suspicious:
        print("\nSUSPICIOUS (foreign caption newly accepted):")
        for s in suspicious:
            print("  " + s)
    return 1 if (regressed or suspicious) else 0


if __name__ == "__main__":
    raise SystemExit(main())
