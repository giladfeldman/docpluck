"""How often does `_cluster_into_rows` chain-merge a table into a smear?

`docpluck/tables/whitespace.py::_cluster_into_rows` starts a new row when a word's
`top` exceeds the PREVIOUS WORD's by the row threshold. Words are sorted by
`(top, x0)`, so in a wrapped or staggered block the running "previous top" creeps
forward in sub-threshold steps and the threshold is never crossed: an arbitrarily
tall band collapses into ONE row, which then fails every downstream grid guard on
its own "merits" and the whole table is dropped.

**THIS IS STILL THE SHIPPED RULE.** The anchor-relative candidate below closes the
smear and was NOT shipped, because it regresses `efendic_2022_affect` by 11
sign-flipped B-coefficients — see `_cluster_into_rows`' docstring. So the two arms
here are **shipped (previous-word)** vs **candidate (anchor-relative)**, and the
scan's job is to tell whoever picks this up again what the candidate would buy.

A ONE-PAPER case proves the shape EXISTS and says NOTHING about how often — the
2026-08-15 directive. This scan supplies the denominator: over a real corpus it
clusters every caption-anchored region BOTH ways and reports, per table, how many
rows each rule produces, the tallest row each leaves behind, and — the number that
actually matters — whether `whitespace_cells` ends up emitting a grid at all.

    SMEAR is counted when the OLD rule leaves a row spanning more than
    `--smear-factor` x the row threshold. That is the defect's own signature, not a
    proxy: the threshold is precisely the height the clustering claims a row cannot
    exceed.

The scan deliberately carries its own copy of the RETIRED previous-word rule
(`_cluster_prev_word`). That is not a "one concept, two tables" violation: the rule
no longer exists in the library, and a before/after diagnostic that cannot express
"before" measures nothing. It is pinned by `tests/test_row_cluster_census_baseline.py`
so it cannot silently drift into agreeing with the shipped rule.

Usage:
    python tools/diag/row_cluster_census.py                 # 26-paper baseline corpus
    python tools/diag/row_cluster_census.py --sample 80     # wider denominator
    python tools/diag/row_cluster_census.py --verbose       # per-table detail
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.diag._corpus import baseline_corpus, coverage_line, sampled_corpus  # noqa: E402

from docpluck.extract_layout import extract_pdf_layout  # noqa: E402
from docpluck.tables.bbox_utils import words_in_bbox  # noqa: E402
from docpluck.tables.captions import find_caption_matches  # noqa: E402
from docpluck.tables.detect import _region_for_caption  # noqa: E402
from docpluck.tables.whitespace import (  # noqa: E402
    BODY_HEIGHT_FALLBACK,
    ROW_GAP_FLOOR_PT,
    ROW_GAP_RATIO,
    whitespace_cells,
)


def _row_threshold(words: list[dict[str, Any]]) -> float:
    heights = sorted(max(w["bottom"] - w["top"], 0.0) for w in words)
    median_h = heights[len(heights) // 2] if heights else BODY_HEIGHT_FALLBACK
    return max(median_h * ROW_GAP_RATIO, ROW_GAP_FLOOR_PT)


def _cluster_prev_word(words: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    """The SHIPPED rule, re-implemented: gap measured to the previous WORD.

    Deliberately a copy rather than an import, so this scan keeps measuring the
    defect even after the library rule changes — a diagnostic whose baseline moves
    with the code cannot report a before/after at all.
    `tests/test_row_cluster_census_baseline.py` pins that it still exhibits the
    smear.
    """
    if not words:
        return []
    sorted_words = sorted(words, key=lambda w: (w["top"], w["x0"]))
    threshold = _row_threshold(sorted_words)
    rows: list[list[dict[str, Any]]] = []
    current = [sorted_words[0]]
    for w in sorted_words[1:]:
        if w["top"] - current[-1]["top"] > threshold:
            rows.append(current)
            current = [w]
        else:
            current.append(w)
    if current:
        rows.append(current)
    return rows


def _cluster_anchor(words: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    """The CANDIDATE rule: gap measured to the row's ANCHOR (its topmost word).

    Closes the smear. NOT shipped — it regresses `efendic_2022_affect`, separating
    each corrupt `2X.XX` B-coefficient from the CI proving it negative so 11
    published negative coefficients ship positive. Kept here so the next attempt can
    measure what it would buy before paying for it again.
    """
    if not words:
        return []
    sorted_words = sorted(words, key=lambda w: (w["top"], w["x0"]))
    threshold = _row_threshold(sorted_words)
    rows: list[list[dict[str, Any]]] = []
    current = [sorted_words[0]]
    anchor_top = sorted_words[0]["top"]
    for w in sorted_words[1:]:
        if w["top"] - anchor_top > threshold:
            rows.append(current)
            current = [w]
            anchor_top = w["top"]
        else:
            current.append(w)
    if current:
        rows.append(current)
    return rows


def _max_span(rows: list[list[dict[str, Any]]]) -> float:
    return max(
        (max(w["top"] for w in r) - min(w["top"] for w in r) for r in rows if r),
        default=0.0,
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", type=int, default=None,
                    help="sample N papers from the shared repository instead of the baseline")
    ap.add_argument("--smear-factor", type=float, default=2.0,
                    help="a row taller than this x the row threshold counts as a smear")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    corpus = sampled_corpus(args.sample) if args.sample else baseline_corpus()
    print(coverage_line())
    print()

    tables = smear_tables = 0
    smear_papers: set[str] = set()
    gained = lost = unchanged = 0
    gained_cells = lost_cells = 0

    for key, pdf in corpus:
        try:
            layout = extract_pdf_layout(pdf.read_bytes())
        except Exception as exc:  # a broken PDF is not a measurement
            print(f"  !! {key}: layout failed ({type(exc).__name__})")
            continue
        caps = [
            c for c in find_caption_matches(layout.raw_text, list(layout.page_offsets))
            if c.kind == "table"
        ]
        for cap in caps:
            region = _region_for_caption(layout, cap)
            if region is None:
                continue
            words = words_in_bbox(layout, bbox=region.bbox, page=region.page)
            if len(words) < 3:
                continue
            tables += 1
            threshold = _row_threshold(words)
            old_rows = _cluster_prev_word(words)
            new_rows = _cluster_anchor(words)
            old_span = _max_span(old_rows)
            is_smear = old_span > threshold * args.smear_factor
            if is_smear:
                smear_tables += 1
                smear_papers.add(key)
            n_cells = len(whitespace_cells(layout, region=region))
            if args.verbose and is_smear:
                print(
                    f"  {key} {cap.label}: rows {len(old_rows)}->{len(new_rows)} "
                    f"maxspan {old_span:.0f}->{_max_span(new_rows):.0f}pt "
                    f"(threshold {threshold:.1f}) cells_now={n_cells}"
                )
            if len(new_rows) > len(old_rows):
                gained += 1
                gained_cells += n_cells
            elif len(new_rows) < len(old_rows):
                lost += 1
                lost_cells += n_cells
            else:
                unchanged += 1

    print()
    print(f"caption-anchored regions examined : {tables}")
    if tables == 0:
        print("A ZERO HERE IS A CLAIM ABOUT THE INSTRUMENT: no region resolved at all, "
              "so this run measures nothing about the corpus.")
        return 1
    print(f"regions the SHIPPED rule smears    : {smear_tables} "
          f"({smear_tables / tables:.1%}) across {len(smear_papers)} papers")
    print(f"regions the CANDIDATE splits more  : {gained}  (cells now emitted: {gained_cells})")
    print(f"regions the CANDIDATE splits less  : {lost}   (cells now emitted: {lost_cells})")
    print(f"regions unchanged                 : {unchanged}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
