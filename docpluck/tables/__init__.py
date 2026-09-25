"""
docpluck.tables — table detection + structuring for academic PDFs.

See an internal design doc for the design.

Public types: Cell, Table, TableKind, TableRendering.
"""

from __future__ import annotations

from typing import Literal, Optional, TypedDict


TableKind = Literal["structured", "isolated"]
# "markup" (v2.4.139) is the DOCX path: the grid was READ from `w:tbl`, not
# inferred from glyph positions. It is a new member of the union, never a
# renaming of an existing one -- a PDF table's `rendering` is unchanged. Kept
# distinct rather than reusing "lattice" because "lattice" names a Camelot
# flavor, and labelling a markup read as a Camelot capture would be an
# unlabelled engine substitution: a consumer thresholding on capture quality
# would silently include tables that have none to report.
TableRendering = Literal["lattice", "whitespace", "isolated", "markup"]

# How sure docpluck is that this is a CAPTIONED table (2026-09-24).
#   "matched"               -- paired with a detected "Table N" caption.
#   "none_found"            -- no caption, but the table itself is certain: the
#                              file DECLARES it (a DOCX `w:tbl`).
#   "uncaptioned_candidate" -- a PDF grid Camelot found on a page where no
#                              caption matched it. KEPT rather than discarded
#                              (owner directive: retain and label, never drop
#                              uncertain content) but NOT verified to be a
#                              table: it may be a title block or prose laid out
#                              in columns. `label` and `caption` are None.
CaptionStatus = Literal["matched", "none_found", "uncaptioned_candidate"]

# What the table's CONTENT is, as opposed to its caption (2026-09-25). One string,
# following the `cell_geometry` precedent of "<state>" or "<state>:<reason>":
#   "cells"                 -- a grid was captured (`cells` is non-empty).
#   "raw_text"              -- no grid, but the text that follows the caption was
#                              captured as a flat list (`raw_text`).
#   "not_captured:<reason>" -- the caption is real and the table is KEPT (owner
#                              directive: retain and label, never drop), but
#                              nothing under it is the table's content. `cells`
#                              is empty and `raw_text` is "". The reasons:
#       rotated_table         the caption is drawn sideways (a 90-degree text
#                             matrix): the table is printed rotated, and nothing
#                             that followed the caption was drawn as part of it
#                             -- only upright lines (running header, page
#                             number, body prose), sideways margin banners or
#                             watermarks recurring on most pages, or the
#                             caption's own title again; all are dropped.
#       page_furniture_only   everything after the caption was page-break
#                             furniture: the next page's running header plus a
#                             page marker (`_raw_text_is_page_furniture_only`).
#       body_prose_overshoot  everything after the caption was body prose that
#                             belongs to the surrounding section.
#       no_text_after_caption nothing at all followed the caption.
# Before this field an empty capture and a furniture-only capture were both
# indistinguishable from a table that had been read: 10.1038/s41467-024-45528-0
# Table 4 shipped `raw_text="Article"` (the page's running header) as its content.
CONTENT_NOT_CAPTURED = "not_captured"


def content_status_for(cells, raw_text, not_captured_reason: str = "no_text_after_caption") -> str:
    """The ``content_status`` a table with these cells and raw text carries."""
    if cells:
        return "cells"
    if (raw_text or "").strip():
        return "raw_text"
    return f"{CONTENT_NOT_CAPTURED}:{not_captured_reason}"



class Cell(TypedDict):
    r: int
    c: int
    rowspan: int
    # DOCX: the span the file declares. PDF: 1, except a super-header label
    # ("Target article", "Replication") whose span the page states with rules
    # (`tables/arm_spans.py`); that cell sits at its arm's first column and
    # carries the printed span. Camelot itself never recovers a span.
    colspan: int
    text: str
    is_header: bool
    bbox: tuple[float, float, float, float]


class Table(TypedDict):
    id: str
    label: Optional[str]
    page: int
    bbox: tuple[float, float, float, float]
    caption: Optional[str]
    footnote: Optional[str]
    kind: TableKind
    rendering: TableRendering
    # Composite capture-quality score in [0, 1], Camelot's own formula
    # `(accuracy/100) * (1 - whitespace/100)` applied to the grid docpluck
    # ships. `None` on paths that have no capture-quality signal at all (the
    # whitespace fallback and the isolated path).
    confidence: Optional[float]
    # The COMPONENTS of `confidence`, so a consumer can reconstruct any
    # threshold and can see which half moved. Before v2.4.133 `confidence` was
    # `accuracy/100` alone, so an 80%-empty capture scored 0.95; shipping only
    # the composite would repeat that mistake in a new place.
    accuracy: Optional[float]        # Camelot's 0-100 structural accuracy
    whitespace: Optional[float]      # 0-100, share of empty slots WE emit
    # Which Camelot parser won this page ("stream" / "lattice"), or None when
    # the table did not come from Camelot. `rendering` cannot carry this: it is
    # hardcoded per capture path, so a lattice capture was indistinguishable
    # from a stream one — an unlabelled engine substitution.
    camelot_flavor: Optional[str]
    n_rows: Optional[int]
    n_cols: Optional[int]
    header_rows: Optional[int]
    cells: list[Cell]
    html: Optional[str]
    raw_text: str
    # Whether `cells[].bbox` carries REAL per-cell geometry, and if not, why.
    # `"verified:<fraction>"` when the round-trip identity guard passed and every
    # cell rectangle is a genuine pdfplumber-space box; otherwise
    # `"<reason>"` naming the refusal (`no_layout`, `camelot_rotated_page:...`,
    # `grid_shape_mismatch:...`, `roundtrip_failed:...`). Never absent and never
    # silent: a zero bbox with no reason is indistinguishable from a document
    # that simply had no rotated pages. See `docpluck/tables/cell_geometry.py`.
    cell_geometry: Optional[str]
    # See `CaptionStatus`. Never absent: an unlabelled table with no status
    # would be indistinguishable from a labelling bug.
    caption_status: CaptionStatus
    # See `content_status_for` above. Never absent: a table with no cells and no
    # text must say WHY, or it reads as a table that was simply empty.
    content_status: str


__all__ = [
    "CONTENT_NOT_CAPTURED", "CaptionStatus", "Cell", "Table", "TableKind",
    "TableRendering", "content_status_for",
]
