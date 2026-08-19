"""Real per-cell geometry for Camelot captures, behind a round-trip identity guard.

Register A1 / G6a. Until now every Camelot cell shipped ``(0.0, 0.0, 0.0, 0.0)``
(``camelot_extract``'s zero-bbox literal) while Camelot itself held real
coordinates for each one - the register's A-pattern: the library already computed
the number we then discarded.

WHY THIS IS GUARDED RATHER THAN JUST WIRED
------------------------------------------
Register G4 deferred this work because every known trap produces **wrong**
geometry rather than empty, and a wrong bbox is silently worse than none: it
answers, plausibly, and the answer is off by a page. The traps, all measured on
the render baseline, not reasoned about:

  T1  Camelot is bottom-up PDF space; ``chars_in_bbox`` is pdfplumber top-down.
  T2  Camelot pages are 1-indexed; ``LayoutDoc.pages`` is 0-indexed.
  T3  docpluck trims rows (running header / caption row / prose tail) BEFORE
      emitting cells, so the emitted ``r`` is not Camelot's df row index.
  T4  the whitespace path carries a zero table bbox.
  T5  **Camelot rotates a page whose TEXT is sideways** and then reports
      coordinates in that rotated frame, while pdfplumber reports the page
      unrotated. Measured on ``10.1001/jamanetworkopen.2023.39337`` p8:
      ``ct.rotation == 'anticlockwise'``, ``ct.pdf_size == (792.0, 612.0)`` and a
      table bbox reaching x=730.7 - off-page in pdfplumber's 612-wide frame,
      while pdfplumber reports ``rotation == 0``. Also on
      ``10.1017/s0007123424000024`` p6 (``clockwise``), whose converted boxes
      come out with a NEGATIVE top. **2 of the 8 papers probed**, so this is a
      class, not a curiosity.
  T6  **``_augment_lattice_with_stream_rows`` concatenates stream rows onto
      ``lattice_ct.df`` and never touches ``lattice_ct.cells``**, so an augmented
      table has more df rows than cell rows. Zipping them by index would give
      every augmented row the geometry of a different row.

**T5 and T6 are NOT in G4's list of four.** T5 was found by running this guard
against the corpus before trusting it; T6 by reading the augmentation the
register pointed at. That two more traps surfaced the moment anyone looked is the
whole argument for building the guard before the lookup.

THE GUARD, AND THE MEASUREMENT THAT SET IT
------------------------------------------
For every raw Camelot cell we convert its rectangle to pdfplumber space, ask
``chars_in_bbox`` what actually stands there, and score

    containment = |multiset(recovered) & multiset(cell text)| / |cell text|

Exact string equality is the WRONG predicate and the probe said so: Camelot
assigns a whole text object to ONE grid cell even when that object's glyphs
spill past the cell's column edges, so ``df.iloc[r, c]`` is regularly a superset
of what stands inside the rectangle. Measured over the render baseline, per
cell: **86.3% of cells score >= 0.95 under the correct transform, against 2.1%
under T1, 1.5% under T2 and 1.5% under T3** - so the predicate separates, and
the residual 14% is Camelot's text assignment, not our arithmetic.

Per cell that is not a clean discriminator; per TABLE it is - measured over 200
tables, the correct transform has a median pass fraction of **0.98** while
**every one of the 200 tables scores below 0.30 under each of the three traps**.
The gate is therefore the FRACTION of a table's verifiable cells that pass,
thresholded at ``TABLE_PASS_FRACTION`` - and it is ALL-OR-NOTHING per table, the
same discipline ``render._carries_statistical_content`` follows: a half-verified
grid would carry real bboxes on some cells and zeros on others with nothing to
tell them apart, which is a new defect whose gaps nobody can see.

**The verification is SAMPLED, the geometry is not.** Every cell gets its
rectangle (pure arithmetic, free); at most ``VERIFY_SAMPLE_CAP`` of them are
round-tripped, on a fixed stride so the verdict is reproducible run to run.
``chars_in_bbox`` is O(chars-on-page) per call, so full verification costs
78.9 ms/table and scales with grid size - a 397-cell table pays 397 scans, on the
SaaS service's per-request path. The cap makes the cost independent of table
size (40.0 ms/table) and **changed no verdict in 200 tables**. A stride, never a
random sample: a gate whose answer moves between runs is not a gate.

Re-run both measurements with ``tools/diag/cell_geometry_census.py``.

WHAT A VERIFIED BBOX MEANS (and what it does not)
-------------------------------------------------
It is the **grid rectangle** for that (row, column) in pdfplumber top-down
coordinates - the same convention ``tables/whitespace.py`` already emits, so the
two capture paths finally agree on one coordinate space. It is NOT a promise
that ``cell["text"]`` is exactly the text standing inside it; see the spill
above. For a consumer proving what the renderer put on the page - the fused-grid
detector of register G6h is the first - the RECTANGLE is the ground truth and
the chars inside it are the evidence.

A REFUSAL IS RECORDED, NEVER SILENT. ``camelot_cell_bboxes`` returns a reason
string on every path, and the caller both records a fallback and stamps
``Table["cell_geometry"]`` so a consumer can see which tables carry geometry and
which do not. A silent zero here would be indistinguishable from "this document
had no rotated pages", which is the instrument-describing zero this project has
now been burned by three times.
"""

from __future__ import annotations

import re
from collections import Counter
from typing import Any

from .bbox_utils import Bbox, chars_in_bbox

_WS_RE = re.compile(r"\s+")

# Per-cell predicate. Set at 0.95 rather than 1.0 because a handful of glyphs
# legitimately sit on a rectangle edge (a leading minus, a superscript marker)
# and midpoint containment puts them on the far side.
CELL_CONTAINMENT_OK: float = 0.95

# Per-table gate. See the module docstring for the measured distributions.
TABLE_PASS_FRACTION: float = 0.60

# Below this many verifiable cells the fraction is noise, so we refuse rather
# than bless geometry on the strength of two cells.
MIN_VERIFIABLE_CELLS: int = 4

# At most this many cells are round-tripped per table, on a fixed stride. Bounds
# the guard's cost at ~40 ms/table regardless of grid size; measured to change no
# verdict across 200 tables. See the module docstring.
VERIFY_SAMPLE_CAP: int = 40

# Camelot's own page size must agree with pdfplumber's, or the two are not
# describing the same frame (T5).
PAGE_SIZE_TOLERANCE_PT: float = 0.5

ZERO_BBOX: Bbox = (0.0, 0.0, 0.0, 0.0)


def _norm(text: str) -> str:
    return _WS_RE.sub("", text or "")


def _containment(recovered: str, want: str) -> float:
    """Fraction of ``want``'s characters that also stand in ``recovered``."""
    if not want:
        return 1.0
    overlap = Counter(recovered) & Counter(want)
    return sum(overlap.values()) / float(len(want))


def _recovered_text(layout: Any, page: int, bbox: Bbox) -> str:
    return _norm(
        "".join(c.get("text", "") for c in chars_in_bbox(layout, bbox=bbox, page=page))
    )


def camelot_cell_bboxes(
    ct: Any,
    *,
    layout: Any | None,
    page: int,
) -> tuple[list[list[Bbox]] | None, str]:
    """Verified per-cell geometry for one Camelot table, in pdfplumber coords.

    Args:
        ct: the Camelot ``Table``.
        layout: a ``LayoutDoc``, or ``None`` when the caller has none (the legacy
            auto-detect path). Without it there is nothing to verify against, so
            geometry is refused rather than emitted unverified.
        page: 1-indexed page number, as Camelot reports it.

    Returns:
        ``(matrix, reason)``. ``matrix[r][c]`` is the pdfplumber-space rectangle
        for Camelot's RAW df row ``r`` and column ``c`` - raw, i.e. before any of
        docpluck's row trimming, so the caller must map its trimmed row index
        back through the surviving-index list (T3). ``matrix`` is ``None`` when
        geometry is refused; ``reason`` is always non-empty and names the cause
        either way (``"verified:0.93"`` on success).
    """
    if layout is None:
        return None, "no_layout"

    rotation = getattr(ct, "rotation", "") or ""
    if rotation:
        # T5. Camelot read this page in a rotated frame; its coordinates and
        # pdfplumber's do not describe the same plane. The round-trip guard
        # below would catch it anyway, but naming the cause beats inferring it
        # from a low score.
        return None, f"camelot_rotated_page:{rotation}"

    pages = getattr(layout, "pages", None) or ()
    if not (1 <= page <= len(pages)):
        return None, f"page_out_of_range:{page}/{len(pages)}"
    page_obj = pages[page - 1]
    height = float(getattr(page_obj, "height", 0.0) or 0.0)
    width = float(getattr(page_obj, "width", 0.0) or 0.0)
    if height <= 0.0:
        return None, "layout_page_has_no_height"

    pdf_size = getattr(ct, "pdf_size", None)
    if pdf_size:
        try:
            cam_w, cam_h = float(pdf_size[0]), float(pdf_size[1])
        except (TypeError, ValueError, IndexError):
            cam_w = cam_h = -1.0
        if cam_w >= 0.0 and (
            abs(cam_w - width) > PAGE_SIZE_TOLERANCE_PT
            or abs(cam_h - height) > PAGE_SIZE_TOLERANCE_PT
        ):
            return None, (
                f"page_size_disagreement:camelot={cam_w:.0f}x{cam_h:.0f},"
                f"layout={width:.0f}x{height:.0f}"
            )

    try:
        df = ct.df
        n_rows, n_cols = len(df), len(df.columns)
        cam_cells = ct.cells
    except Exception as exc:  # noqa: BLE001 - a malformed table is a refusal, not a crash
        return None, f"camelot_table_exception:{type(exc).__name__}"
    if n_rows < 1 or n_cols < 1:
        return None, "camelot_table_empty"

    # T6. `_augment_lattice_with_stream_rows` pd.concat's stream rows onto
    # `lattice_ct.df` and leaves `lattice_ct.cells` at the lattice row count, so
    # for an augmented table the two are different lengths and index r means two
    # different rows depending which you ask. Refuse rather than hand the
    # augmented rows somebody else's rectangle.
    n_cell_rows = len(cam_cells)
    n_cell_cols = len(cam_cells[0]) if n_cell_rows else 0
    if n_cell_rows != n_rows or n_cell_cols < n_cols:
        return None, (
            f"grid_shape_mismatch:df={n_rows}x{n_cols},cells={n_cell_rows}x{n_cell_cols}"
        )

    # Pass 1 - build every rectangle. Pure arithmetic, so no reason to skip any.
    matrix: list[list[Bbox]] = []
    targets: list[tuple[Bbox, str]] = []
    for r in range(n_rows):
        row: list[Bbox] = []
        for c in range(n_cols):
            try:
                cell = cam_cells[r][c]
                x1, y1 = float(cell.x1), float(cell.y1)
                x2, y2 = float(cell.x2), float(cell.y2)
            except Exception:  # noqa: BLE001
                row.append(ZERO_BBOX)
                continue
            if x2 <= x1 or y2 <= y1:
                row.append(ZERO_BBOX)
                continue
            # T1: bottom-up (x1, y1) = bottom-left, (x2, y2) = top-right ->
            # pdfplumber top-down (x0, top, x1, bottom).
            bbox: Bbox = (x1, height - y2, x2, height - y1)
            row.append(bbox)
            want = _norm(str(df.iloc[r, c]))
            if len(want) >= 2:
                targets.append((bbox, want))
        matrix.append(row)

    if len(targets) < MIN_VERIFIABLE_CELLS:
        return None, f"too_few_verifiable_cells:{len(targets)}"

    # Pass 2 - round-trip a bounded, DETERMINISTIC sample. A fixed stride rather
    # than a random draw: a gate whose answer moves between runs is not a gate.
    stride = max(1, len(targets) // VERIFY_SAMPLE_CAP)
    sample = targets[::stride][:VERIFY_SAMPLE_CAP]
    passed = sum(
        1 for bbox, want in sample
        if _containment(_recovered_text(layout, page, bbox), want) >= CELL_CONTAINMENT_OK
    )
    fraction = passed / float(len(sample))
    if fraction < TABLE_PASS_FRACTION:
        return None, f"roundtrip_failed:{fraction:.2f}<{TABLE_PASS_FRACTION:.2f}"
    return matrix, f"verified:{fraction:.2f}"


__all__ = [
    "camelot_cell_bboxes",
    "CELL_CONTAINMENT_OK",
    "TABLE_PASS_FRACTION",
    "MIN_VERIFIABLE_CELLS",
    "VERIFY_SAMPLE_CAP",
    "PAGE_SIZE_TOLERANCE_PT",
    "ZERO_BBOX",
]
