"""The FUSED-GRID detector the text-only census could not build (register G6h).

``tools/diag/fused_cell_census.py`` measures how often Camelot glues two published
values into one cell (``104594`` = sample sizes 104 and 594) and says plainly that
every number it prints is a FLOOR, because the commonest fusion -- two plain
integers -- is indistinguishable from a genuine six-digit number IN TEXT ALONE.
Its own conclusion:

    a shippable detector needs the LAYOUT channel (pdfplumber char x-gaps proving
    the gap Camelot swallowed), which is register G6a and deliberately open.

G6a CLOSED in v2.4.135: ``Table["cell_geometry"]`` now says whether ``cells[].bbox``
is a real pdfplumber-space rectangle, and 91.6% of shipped cells carry one. This
scan is what that unblocks.

THE EVIDENCE AXIS (CLAUDE.md rule 0h). The signal is TYPOGRAPHIC: a horizontal
gap the renderer actually emitted, INSIDE the cell's own verified rectangle, at a
position where ``cell["text"]`` carries no separator. It is not "this number looks
too long" -- that would be INFERENTIAL and is the consumer's job.

WHY THE GATE MATTERS. On a refused table every rectangle is ``(0,0,0,0)``, so
``chars_in_bbox`` returns nothing and the detector would report zero fusions while
measuring nothing at all -- the instrument-describing zero this repo has been
burned by three times. Cells without a real box are counted as SKIPPED and
printed, never silently folded into the denominator.

THIS IS A MEASUREMENT, NOT A REPAIR. It exists to put a real denominator under
the shape before any rule ships (CLAUDE.md: "MEASURE THE DENOMINATOR SEPARATELY
FROM THE SHAPE").

Usage::

    python tools/diag/fused_cell_geometry_scan.py                 # 26-paper baseline
    python tools/diag/fused_cell_geometry_scan.py --sample 60
    python tools/diag/fused_cell_geometry_scan.py --examples 40
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.diag._corpus import baseline_corpus, coverage_line, sampled_corpus  # noqa: E402

from docpluck.extract_layout import extract_pdf_layout  # noqa: E402
from docpluck.extract_structured import extract_pdf_structured  # noqa: E402
from docpluck.tables.bbox_utils import chars_in_bbox  # noqa: E402

# A gap this many EMs wide (em == the char's own font size) is a column gutter
# rather than inter-letter tracking. The band is reported by section B on every
# run so the threshold can be re-checked against the corpus it is applied to,
# instead of being trusted because it is written down here.
FUSION_GAP_EM: float = 0.75

# Below this the cell is too short for a gap to mean anything.
MIN_CHARS: int = 4


def _lines(chars: list[dict]) -> list[list[dict]]:
    """Group a cell's chars into baselines, then sort each left to right.

    A cell can hold several rendered lines, and a gap measured ACROSS a line
    break is meaningless: the next line restarts at the left edge, so
    ``next.x0 - prev.x1`` is a large negative number that says nothing about
    horizontal spacing.
    """
    by_top: dict[int, list[dict]] = {}
    for c in chars:
        by_top.setdefault(round(c["top"]), []).append(c)
    return [sorted(v, key=lambda c: c["x0"]) for _, v in sorted(by_top.items())]


def _gaps_in_line(line: list[dict]) -> list[tuple[float, str, str, float]]:
    """``(gap_in_ems, left_char, right_char, gap_pts)`` for each adjacent pair."""
    out = []
    for a, b in zip(line, line[1:]):
        size = max(a.get("size") or 0.0, b.get("size") or 0.0)
        if size <= 0:
            continue
        gap = b["x0"] - a["x1"]
        out.append((gap / size, a["text"], b["text"], gap))
    return out


def _norm(s: str) -> str:
    return "".join(s.split())


def fused_sites(cell_text: str, chars: list[dict]) -> list[dict] | None:
    """Gaps inside the rectangle that the cell's TEXT does not record.

    Returns ``None`` when the finding cannot be ATTRIBUTED to this cell, and a
    (possibly empty) list when it can. The caller must count the two separately:
    a ``None`` is a refusal, not a clean cell.

    WHY THE ATTRIBUTION CHECK IS THE WHOLE RULE. ``cell_geometry``'s docstring
    is explicit that a verified rectangle is the GRID RECTANGLE and *not* a
    promise that ``cell["text"]`` is exactly the text standing inside it. The
    first draft of this scan ignored that and measured gaps between whatever
    ``chars_in_bbox`` returned, so a wide header rectangle that also covers its
    neighbour produced gaps of **17.3 em** and three confident "fusions" on
    ``10.1001/jamanetworkopen.2023.39337`` Table 3 (``'TRE'``, ``'Baseline'``,
    ``'11 h 55 min'``) -- every one of them a gap BETWEEN two cells, which is a
    column gutter doing exactly its job.

    So a gap only counts when the glyphs in the rectangle ARE the cell's text:
    concatenated in reading order, ignoring whitespace, they must equal the
    cell text ignoring whitespace. Anything else is unattributable and refused.
    """
    if len(chars) < MIN_CHARS:
        return None
    lines = _lines(chars)
    recovered = _norm("".join(c["text"] for line in lines for c in line))
    if not recovered or recovered != _norm(cell_text):
        return None
    sites = []
    for line in lines:
        for em, left, right, pts in _gaps_in_line(line):
            if em < FUSION_GAP_EM:
                continue
            if left.isspace() or right.isspace():
                continue
            sites.append(
                {"gap_em": round(em, 2), "gap_pts": round(pts, 1),
                 "left": left, "right": right}
            )
    return sites


def _distribution(samples: list[float]) -> str:
    if not samples:
        return "no gaps sampled"
    samples = sorted(samples)

    def q(p: float) -> float:
        return samples[min(len(samples) - 1, int(p * len(samples)))]

    return (f"n={len(samples)} p50={q(.50):.2f} p90={q(.90):.2f} "
            f"p99={q(.99):.2f} max={samples[-1]:.2f} (ems)")


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--sample", type=int, default=0,
                    help="Sample N papers from the article repository instead "
                         "of the 26-paper render baseline.")
    ap.add_argument("--seed", type=int, default=20260820)
    ap.add_argument("--examples", type=int, default=25)
    args = ap.parse_args()

    corpus = (sampled_corpus(args.sample, seed=args.seed) if args.sample
              else baseline_corpus())
    print(coverage_line())
    print()

    tables_total = tables_gated = 0
    cells_total = cells_measured = cells_skipped_no_box = 0
    cells_unattributable = 0
    fused_cells = 0
    geometry_states: Counter[str] = Counter()
    all_gaps: list[float] = []
    examples: list[str] = []
    errors = 0

    for key, pdf_path in corpus:
        try:
            pdf = pdf_path.read_bytes()
            layout = extract_pdf_layout(pdf)
            res = extract_pdf_structured(pdf, _layout_doc=layout)
        except Exception as exc:  # noqa: BLE001
            errors += 1
            print(f"  ! {key}: {type(exc).__name__}: {exc}")
            continue

        for t in res.get("tables", []):
            tables_total += 1
            geom = t.get("cell_geometry") or "unset"
            geometry_states[geom.split(":")[0]] += 1
            # GATE. Only a table whose rectangles were round-trip verified (or
            # are real by construction on the whitespace path) can speak here.
            if not (geom.startswith("verified") or geom == "whitespace_native"):
                continue
            tables_gated += 1
            for cell in t.get("cells", []):
                cells_total += 1
                bbox = cell.get("bbox")
                text = cell.get("text") or ""
                if not bbox or tuple(bbox) == (0.0, 0.0, 0.0, 0.0) or not text.strip():
                    cells_skipped_no_box += 1
                    continue
                try:
                    chars = chars_in_bbox(layout, bbox=tuple(bbox), page=t["page"])
                except Exception:  # noqa: BLE001
                    cells_skipped_no_box += 1
                    continue
                sites = fused_sites(text, chars)
                if sites is None:
                    cells_unattributable += 1
                    continue
                cells_measured += 1
                for line in _lines(chars):
                    all_gaps += [g[0] for g in _gaps_in_line(line)]
                if sites:
                    fused_cells += 1
                    if len(examples) < args.examples:
                        widest = max(sites, key=lambda s: s["gap_em"])
                        examples.append(
                            f"  {key} p{t['page']} {t.get('label') or '?'}: "
                            f"{text[:46]!r}  gap {widest['gap_em']}em "
                            f"({widest['gap_pts']}pt) between "
                            f"{widest['left']!r}|{widest['right']!r}"
                        )

    print("=" * 72)
    print("A. COVERAGE -- what could actually be measured")
    print(f"   tables seen                          {tables_total}")
    print(f"   tables with verified geometry        {tables_gated}")
    for state, n in geometry_states.most_common():
        print(f"       {n:5d}  {state}")
    print(f"   cells in gated tables                {cells_total}")
    print(f"   ...measured                          {cells_measured}")
    print(f"   ...skipped (zero box / empty)        {cells_skipped_no_box}")
    print(f"   ...refused, glyphs != cell text      {cells_unattributable}")
    print()
    print("B. THE GAP DISTRIBUTION -- where the threshold sits")
    print(f"   intra-cell adjacent-char gaps: {_distribution(all_gaps)}")
    print(f"   threshold FUSION_GAP_EM = {FUSION_GAP_EM}")
    print()
    print("C. FUSED CELLS -- a renderer gap the cell text does not record")
    pct = (100.0 * fused_cells / cells_measured) if cells_measured else 0.0
    print(f"   cells flagged                        {fused_cells}  ({pct:.2f}% of measured)")
    if examples:
        print("\n   examples:")
        for e in examples:
            print(e)
    if errors:
        print(f"\n   {errors} paper(s) failed to extract and are excluded.")
    if cells_measured == 0:
        print("\n   *** ZERO CELLS MEASURED -- this is a statement about the")
        print("       INSTRUMENT, not the corpus. Do not quote the count above.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
