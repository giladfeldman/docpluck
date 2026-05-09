"""
docpluck.extract_structured — top-level structured PDF extraction.

Per [LESSONS L-006](../LESSONS.md#l-006), this module is pdfplumber-free.
Tables come from Camelot stream flavor; figures and captions are detected
purely from the pdftotext text channel via the regexes in
``docpluck.tables.captions``.

Pipeline:
    1. ``extract_pdf`` → linear pdftotext text + page count.
    2. ``find_caption_matches`` → "Table N" / "Figure N" caption lines on
       each page.
    3. ``extract_tables_camelot`` → cell-bearing tables from each page.
    4. Match each Camelot table to its same-page caption (label, caption text).
    5. Build :class:`Figure` dicts from caption matches that don't pair with
       any table.
    6. Optional placeholder mode replaces caption lines with
       ``[Label: caption]`` markers.
"""

from __future__ import annotations

import os
import re
from typing import Literal, Optional, TypedDict

from .extract import extract_pdf, count_pages
from .figures import Figure
from .tables import Cell, Table
from .tables.camelot_extract import extract_tables_camelot
from .tables.captions import CaptionMatch, find_caption_matches
from .tables.render import cells_to_html


TABLE_EXTRACTION_VERSION = "2.0.0"  # bumped: pdfplumber removed; Camelot is the table source

TableTextMode = Literal["raw", "placeholder"]


class StructuredResult(TypedDict):
    text: str
    method: str
    page_count: int
    tables: list[Table]
    figures: list[Figure]
    table_extraction_version: str


def extract_pdf_structured(
    pdf_bytes: bytes,
    *,
    thorough: bool = False,
    table_text_mode: TableTextMode = "raw",
) -> StructuredResult:
    """Extract text + structured tables + figures from a PDF.

    Args:
        pdf_bytes: Raw PDF bytes.
        thorough: Currently unused — Camelot scans every page by default.
            Retained for backwards-compatible call signature.
        table_text_mode: ``"raw"`` (default; text identical to ``extract_pdf``)
            or ``"placeholder"`` (caption lines for tables/figures are replaced
            with ``[Label: caption]`` markers).

    Returns:
        StructuredResult dict.
    """
    raw_text, base_method = extract_pdf(pdf_bytes)
    page_count = count_pages(pdf_bytes)

    if raw_text.startswith("ERROR:"):
        return {
            "text": raw_text,
            "method": base_method,
            "page_count": page_count,
            "tables": [],
            "figures": [],
            "table_extraction_version": TABLE_EXTRACTION_VERSION,
        }

    method_pieces = [base_method]
    if thorough:
        method_pieces.append("thorough")
    # Preprocess: pdftotext sometimes splits captions like "Table 1: X" into
    # "T\n\n1: X". Join these so the caption regex matches consistently.
    # We work on a SHADOW string for caption detection only — raw_text returned
    # to callers is unmodified.
    rejoined = _join_split_captions(raw_text)
    page_offsets = _page_offsets(rejoined)
    captions_all = find_caption_matches(rejoined, page_offsets)
    # Dedupe by (kind, number): keep only the first occurrence — body-text
    # references like "see Table 1" can otherwise duplicate captions.
    seen_keys: set[tuple[str, int]] = set()
    captions: list[CaptionMatch] = []
    for c in captions_all:
        key = (c.kind, c.number)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        captions.append(c)
    # The captions' char_start/char_end refer to `rejoined`, not raw_text. For
    # placeholder mode we need positions in raw_text — build a translation map.
    # Since the rejoin only deletes whitespace runs, char positions in rejoined
    # are <= positions in raw_text. We translate by re-finding the caption line
    # in raw_text on demand.

    tables: list[Table] = []
    figures: list[Figure] = []

    # ---- Tables (Camelot) ----
    camelot_disabled = os.environ.get("DOCPLUCK_DISABLE_CAMELOT", "0") == "1"
    camelot_tables: list[Table] = []
    if not camelot_disabled:
        try:
            camelot_tables = extract_tables_camelot(pdf_bytes)
            if camelot_tables:
                method_pieces.append("camelot_stream")
        except Exception:
            method_pieces.append("camelot_failed")
            camelot_tables = []

    # Match Camelot tables to "Table N" caption lines on the same page.
    used_caption_ids: set[int] = set()
    table_captions = [c for c in captions if c.kind == "table"]

    # Filter Camelot's output to tables that have a same-page caption.
    # This anchors detection to caption signal (matching the pre-pdfplumber-removal
    # behavior of docpluck) and drops false-positive Camelot detections like
    # bibliographies or address blocks. Tables without captions are rare in APA
    # corpus and the existing tests are calibrated against caption-anchored counts.
    pages_with_table_caption = {c.page for c in table_captions}
    for ct in camelot_tables:
        if (ct.get("page") or 0) not in pages_with_table_caption:
            continue
        match = _find_caption_for_table(ct, table_captions, raw_text, used_caption_ids)
        if match is not None:
            used_caption_ids.add(id(match))
            ct["label"] = match.label
            ct["caption"] = _extract_caption_text(rejoined, match)
            tables.append(ct)

    # If a table caption had no Camelot match, emit an "isolated" Table dict so
    # downstream consumers still see something at that page.
    for cap in table_captions:
        if id(cap) in used_caption_ids:
            continue
        tables.append(_isolated_table_from_caption(cap, rejoined))

    # ---- Figures ----
    for cap in captions:
        if cap.kind != "figure":
            continue
        figures.append(_figure_from_caption(cap, rejoined))

    # ---- Placeholder mode ----
    text_out = (
        _apply_placeholder(raw_text, captions)
        if table_text_mode == "placeholder"
        else raw_text
    )

    # Sort tables/figures by page for stable output.
    tables.sort(key=lambda t: (t.get("page") or 0, t.get("label") or ""))
    figures.sort(key=lambda f: (f.get("page") or 0, f.get("label") or ""))

    return {
        "text": text_out,
        "method": "+".join(method_pieces),
        "page_count": page_count,
        "tables": tables,
        "figures": figures,
        "table_extraction_version": TABLE_EXTRACTION_VERSION,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _page_offsets(raw_text: str) -> list[int]:
    """Char offset where each 1-indexed page starts in raw_text. raw_text uses
    ``\\f`` (form feed) as page separator (pdftotext default)."""
    offsets = [0]
    for i, ch in enumerate(raw_text):
        if ch == "\f":
            offsets.append(i + 1)
    return offsets


_SPLIT_CAPTION_RE = re.compile(
    r"^(T|Table|Fig\.?|Figure)\s*\n\s*\n\s*(\d+(?:\.\d+)?)([\s.:\-—–]+)",
    re.MULTILINE | re.IGNORECASE,
)
_T_PREFIX_RE = re.compile(
    r"^T\s+(\d+(?:\.\d+)?)([\s.:\-—–])",
    re.MULTILINE,
)
_FIG_PREFIX_RE = re.compile(
    r"^Fig\.?\s+(\d+(?:\.\d+)?)([\s.:\-—–])",
    re.MULTILINE | re.IGNORECASE,
)


def _join_split_captions(text: str) -> str:
    """Rejoin captions pdftotext split across paragraphs.

    Patterns:
      - "T\\n\\n1: foo" → "Table 1: foo"
      - "Fig.\\n\\n2: bar" → "Figure 2: bar"
      - bare "T 1:" prefix → "Table 1:" (after the rejoin above)
    """
    text = _SPLIT_CAPTION_RE.sub(r"\1 \2\3", text)
    text = _T_PREFIX_RE.sub(r"Table \1\2", text)
    text = _FIG_PREFIX_RE.sub(r"Figure \1\2", text)
    return text


def _find_caption_for_table(
    camelot_table: Table,
    captions: list[CaptionMatch],
    raw_text: str,
    used_caption_ids: set[int],
) -> Optional[CaptionMatch]:
    """Pick the best ``Table N:`` caption on the same page as the camelot table.

    Strategy: among unused captions on the same page, prefer the one whose
    caption-line tokens appear most densely in the table's raw_text. If no
    captions are on the same page, return None.
    """
    page = camelot_table.get("page") or 0
    same_page = [c for c in captions if c.page == page and id(c) not in used_caption_ids]
    if not same_page:
        return None
    if len(same_page) == 1:
        return same_page[0]
    # Score each caption by token overlap with the camelot table content
    table_text = (camelot_table.get("raw_text") or "").lower()
    table_tokens = set(re.findall(r"[a-z]{3,}|\d+(?:\.\d+)?", table_text))
    best: Optional[tuple[int, int, CaptionMatch]] = None
    for c in same_page:
        cap_tokens = set(re.findall(r"[a-z]{3,}|\d+(?:\.\d+)?", c.line_text.lower()))
        score = len(cap_tokens & table_tokens)
        candidate = (-score, c.char_start, c)
        if best is None or candidate < best:
            best = candidate
    if best is None:
        return None
    return best[2]


def _extract_caption_text(raw_text: str, cap: CaptionMatch) -> str:
    """Pull the full caption (label + description) starting at the caption line.

    Captions are often line-wrapped by pdftotext, so a single ``\\n\\n``
    boundary can sit MID-SENTENCE. Walk past such breaks until we find one
    where the preceding text ends with a real sentence terminator
    (``.``/``!``/``?``) or we hit the 600-char hard cap.
    """
    start = cap.char_start
    # Hard cap — never read more than 600 chars from the caption start.
    hard_end = min(cap.char_end + 600, len(raw_text))
    pos = cap.char_end
    while pos < hard_end:
        nxt = raw_text.find("\n\n", pos)
        if nxt == -1 or nxt >= hard_end:
            break
        # Check the text just before this paragraph break.
        prev = raw_text[max(start, nxt - 40):nxt].rstrip()
        # If it ends with a sentence terminator OR is empty/very short, stop.
        if not prev or len(prev.split()) < 2:
            hard_end = nxt
            break
        if re.search(r"[.!?][\"'\)\]]?$", prev):
            hard_end = nxt
            break
        # Otherwise the caption continues — skip past this break and keep going.
        pos = nxt + 2
    snippet = raw_text[start:hard_end].replace("\n", " ").strip()
    # Collapse runs of any whitespace (including U+2002 EN SPACE, etc.) to a
    # single space; many APA PDFs use unusual spaces between label and caption.
    snippet = re.sub(r"\s+", " ", snippet)
    # Strip leading orphan punctuation that can occur when the rejoin produced
    # a partial caption (e.g., "Table 1. : Studies 1b and 3...").
    snippet = re.sub(r"^[\s.:\-—–]+", "", snippet)
    # Re-prefix the label if stripping ate it.
    if cap.label and not snippet.startswith(cap.label):
        snippet = f"{cap.label}. {snippet}".strip()
    if len(snippet) > 400:
        snippet = snippet[:400].rsplit(" ", 1)[0] + "…"
    return snippet


def _isolated_table_from_caption(cap: CaptionMatch, raw_text: str) -> Table:
    """Build an isolated (cellless) Table dict for a caption with no Camelot match."""
    return {
        "id": f"t{cap.number}",
        "label": cap.label,
        "page": cap.page,
        "bbox": (0.0, 0.0, 0.0, 0.0),
        "caption": _extract_caption_text(raw_text, cap),
        "footnote": None,
        "kind": "isolated",
        "rendering": "isolated",
        "confidence": None,
        "n_rows": None,
        "n_cols": None,
        "header_rows": None,
        "cells": [],
        "html": None,
        "raw_text": "",
    }


def _figure_from_caption(cap: CaptionMatch, raw_text: str) -> Figure:
    """Build a Figure dict from a caption match. bbox is unknown (zeros)."""
    return {
        "id": f"f{cap.number}",
        "label": cap.label,
        "page": cap.page,
        "bbox": (0.0, 0.0, 0.0, 0.0),
        "caption": _extract_caption_text(raw_text, cap),
    }


def _apply_placeholder(raw_text: str, captions: list[CaptionMatch]) -> str:
    """Replace each caption's line with ``[Label: caption]`` marker.

    Without pdfplumber we don't know the exact bbox of the table region; we
    mark only the caption line itself. The marker is shorter than the caption
    line so total text length doesn't grow.
    """
    if not captions:
        return raw_text
    items = sorted(
        ((c.char_start, c.char_end, c) for c in captions),
        key=lambda item: item[0],
        reverse=True,
    )
    out = raw_text
    for start, end, cap in items:
        snippet = _extract_caption_text(raw_text, cap)
        # Build "[Label: caption]" marker. Use the snippet (already cleaned).
        if cap.label and cap.label in snippet:
            desc = snippet[len(cap.label):].lstrip(" .:—–-,")
        else:
            desc = snippet
        marker = f"[{cap.label}: {desc[:120]}]" if desc else f"[{cap.label}]"
        out = out[:start] + marker + out[end:]
    return out


__all__ = [
    "TABLE_EXTRACTION_VERSION",
    "TableTextMode",
    "StructuredResult",
    "extract_pdf_structured",
]
