"""Put back a minus sign that Camelot's text layer dropped.

THE DEFECT, ON A REAL PAGE
--------------------------
``10.1098/rsos.140072`` p7, Table 3. The minus signs are drawn in the MathTime
symbol font (``MTSY``). pdftotext and pdfplumber read each one as U+2212; the
text lines Camelot builds for its grid do not contain them, so the grid printed
``submission | 0.03 | 0.02 | 1.93`` where the page prints ``-0.03 ... -1.93`` --
a published negative estimate and t-ratio delivered as positive. Measured over
the 101-PDF manifest on 2026-10-14 (every Camelot text line on every page that
carries a minus-like glyph): 55 lines in 6 papers, every one a TeX / MathTime
symbol font (``MTSY``, ``MTSYN``, ``CMSY10``, ``AdvPS``).

THE EVIDENCE IS TYPOGRAPHIC
---------------------------
A glyph is restored only when the page's own text layer (the layout channel,
pdfplumber) holds a minus-like character that

* lies directly left of a Camelot text line (its right edge within
  ``ADJACENT_PT`` of the line's left edge) and on that line's baseline;
* is inside NO Camelot text line, i.e. Camelot's parser lost it;
* leads a number (the text line starts with a digit or ``.digit``).

The character inserted is the one the page carries, unchanged. Nothing is
inferred from the values; a sign the page does not print is never added. This
is a channel repair -- our own extraction step lost the glyph -- not a repair
of the paper.

Upright pages only: Camelot reports a sideways page in a rotated frame (cell
geometry trap T5), so a rotated table is left as it was.
"""

from __future__ import annotations

from typing import Any

MINUS_LIKE = frozenset({"−", "-", "–", "—"})
ADJACENT_PT = 1.5
PAGE_SIZE_TOLERANCE_PT = 2.0


def _text(tl: Any) -> str:
    try:
        return (tl.get_text() or "").strip()
    except Exception:
        return ""


def _index(v: float, spans: list, *, descending: bool) -> int | None:
    for i, (a, b) in enumerate(spans):
        lo, hi = (float(b), float(a)) if descending else (float(a), float(b))
        if lo <= v <= hi:
            return i
    return None


def restore_dropped_signs(ct: Any, layout: Any) -> int:
    """Insert into ``ct.df`` every minus glyph the page prints before a cell's
    number that Camelot dropped. Returns how many were restored; never raises."""
    try:
        return _restore(ct, layout)
    except Exception:
        return 0


def _restore(ct: Any, layout: Any) -> int:
    if layout is None or getattr(ct, "rotation", ""):
        return 0
    pages = getattr(layout, "pages", None) or ()
    try:
        page = int(ct.page)
    except (TypeError, ValueError, AttributeError):
        return 0
    if not (1 <= page <= len(pages)):
        return 0
    page_obj = pages[page - 1]
    height = float(getattr(page_obj, "height", 0.0) or 0.0)
    width = float(getattr(page_obj, "width", 0.0) or 0.0)
    pdf_size = getattr(ct, "pdf_size", None)
    if height <= 0.0 or not pdf_size:
        return 0
    if (abs(float(pdf_size[0]) - width) > PAGE_SIZE_TOLERANCE_PT
            or abs(float(pdf_size[1]) - height) > PAGE_SIZE_TOLERANCE_PT):
        return 0
    signs = [c for c in (getattr(page_obj, "chars", None) or ()) if c.get("text") in MINUS_LIKE]
    if not signs:
        return 0
    lines = [tl for tl in (getattr(ct, "textlines", None) or ()) if _text(tl)]
    cols = list(getattr(ct, "cols", None) or ())
    rows = list(getattr(ct, "rows", None) or ())
    df = ct.df
    restored = 0
    for c in signs:
        cx = (float(c["x0"]) + float(c["x1"])) / 2.0
        cy = height - (float(c["top"]) + float(c["bottom"])) / 2.0  # bottom-up
        if any(tl.x0 - 0.5 <= cx <= tl.x1 + 0.5 and tl.y0 - 0.5 <= cy <= tl.y1 + 0.5 for tl in lines):
            continue  # Camelot holds this glyph
        lead = [
            tl for tl in lines
            if abs(float(c["x1"]) - tl.x0) <= ADJACENT_PT and tl.y0 - 1.0 <= cy <= tl.y1 + 1.0
        ]
        if len(lead) != 1:
            continue
        tl = lead[0]
        text = _text(tl)
        if not (text[0].isdigit() or (text[0] == "." and text[1:2].isdigit())):
            continue
        ci = _index((tl.x0 + tl.x1) / 2.0, cols, descending=False)
        ri = _index((tl.y0 + tl.y1) / 2.0, rows, descending=True)
        if ci is None or ri is None or ri >= len(df) or ci >= len(df.columns):
            continue
        cell = str(df.iloc[ri, ci])
        pos = cell.find(text)
        if pos < 0 or (pos > 0 and cell[pos - 1] in MINUS_LIKE):
            continue
        df.iloc[ri, ci] = cell[:pos] + c["text"] + cell[pos:]
        restored += 1
    return restored
