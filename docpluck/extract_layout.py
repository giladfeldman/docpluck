"""Layout-aware PDF extraction.

Internal-only for v1.6.0 — used by docpluck.sections.annotators.pdf and the
F0 footnote/header strip step in normalize. Public API surface (the shape of
LayoutDoc) is NOT promised externally; see TODO.md.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class TextSpan:
    text: str
    page_index: int          # 0-based
    x0: float
    y0: float
    x1: float
    y1: float
    font_size: float
    font_name: str
    bold: bool


@dataclass(frozen=True)
class PageLayout:
    page_index: int          # 0-based
    width: float
    height: float
    spans: tuple[TextSpan, ...]
    # v2.0 geometric primitives (added for table/figure extraction).
    # These mirror pdfplumber's native per-page collections, frozen as
    # immutable tuples of plain dicts so the dataclass stays hashable.
    lines: tuple[dict, ...] = ()
    rects: tuple[dict, ...] = ()
    curves: tuple[dict, ...] = ()
    chars: tuple[dict, ...] = ()
    words: tuple[dict, ...] = ()


@dataclass(frozen=True)
class LayoutDoc:
    pages: tuple[PageLayout, ...]
    raw_text: str
    page_offsets: tuple[int, ...]   # char offset of each page in raw_text


def extract_pdf_layout(pdf_bytes: bytes) -> LayoutDoc:
    """Read a PDF with pdfplumber and return per-page layout + raw text.

    `raw_text` joins per-page text with `\\f` separators (matching the
    pdftotext form-feed convention) so existing normalization page-detection
    keeps working. `page_offsets[i]` is the start offset of page i+1 in
    raw_text.
    """
    import pdfplumber  # type: ignore
    import io

    pages: list[PageLayout] = []
    raw_chunks: list[str] = []
    offsets: list[int] = []
    cursor = 0

    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for i, p in enumerate(pdf.pages):
            spans = tuple(_chars_to_spans(p.chars or [], page_index=i))
            page_text = p.extract_text() or ""
            offsets.append(cursor)
            if i > 0:
                # Form-feed page separator (matches pdftotext convention).
                raw_chunks.append("\f")
                cursor += 1
                offsets[-1] = cursor  # adjust to point AFTER the form feed
            raw_chunks.append(page_text)
            cursor += len(page_text)
            pages.append(PageLayout(
                page_index=i,
                width=float(p.width),
                height=float(p.height),
                spans=spans,
                lines=tuple(p.lines or ()),
                rects=tuple(p.rects or ()),
                curves=tuple(p.curves or ()),
                chars=tuple(p.chars or ()),
                words=tuple(p.extract_words() or ()),
            ))

    return LayoutDoc(
        pages=tuple(pages),
        raw_text="".join(raw_chunks),
        page_offsets=tuple(offsets),
    )


def _chars_to_spans(chars: Iterable[dict], *, page_index: int) -> Iterable[TextSpan]:
    """Cluster pdfplumber per-character dicts into per-line text spans.

    Heuristic: chars with the same fontname + fontsize on close y-coords
    (within 1pt) get joined into a span; gaps in x of >2× space-width
    split into separate spans.
    """
    if not chars:
        return []
    # Sort by (y0 descending — reading order top-to-bottom in PDF coords —
    # then x0 ascending).
    chars_sorted = sorted(
        chars, key=lambda c: (-(c.get("y0") or 0.0), c.get("x0") or 0.0)
    )
    lines: list[list[dict]] = []
    current: list[dict] = []
    last_y: float | None = None
    for ch in chars_sorted:
        y = float(ch.get("y0") or 0.0)
        if last_y is None or abs(y - last_y) <= 1.0:
            current.append(ch)
            last_y = y
        else:
            if current:
                lines.append(current)
            current = [ch]
            last_y = y
    if current:
        lines.append(current)

    spans: list[TextSpan] = []
    for line in lines:
        line.sort(key=lambda c: c.get("x0") or 0.0)
        text = "".join(c.get("text", "") for c in line)
        if not text.strip():
            continue
        font_sizes = [float(c.get("size") or 0.0) for c in line if c.get("size")]
        font_size = max(set(font_sizes), key=font_sizes.count) if font_sizes else 0.0
        font_names = [str(c.get("fontname") or "") for c in line]
        font_name = max(set(font_names), key=font_names.count) if font_names else ""
        bold = "Bold" in font_name or "bold" in font_name
        x0 = min(float(c.get("x0") or 0.0) for c in line)
        x1 = max(float(c.get("x1") or 0.0) for c in line)
        y0 = min(float(c.get("y0") or 0.0) for c in line)
        y1 = max(float(c.get("y1") or 0.0) for c in line)
        spans.append(TextSpan(
            text=text, page_index=page_index,
            x0=x0, y0=y0, x1=x1, y1=y1,
            font_size=font_size, font_name=font_name, bold=bold,
        ))
    return spans
