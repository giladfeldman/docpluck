"""Two-origin evidence for an operator glyph the text layer mislabels as a digit.

THE DEFECT, ON A REAL PAGE
--------------------------
``10.5465/amj.2016.1196`` p15 prints ``(b = −0.04, SE = 0.06, t = −0.63,
p = .528)``. Every text extractor -- pdftotext, pdfplumber, a PDF viewer's copy
command -- reads ``(b 5 20.04, SE 5 0.06, t 5 20.63, p 5 .528)``. The paper
draws ``=``, ``−`` and ``<`` in a separate embedded font (``AdvOT463cc31e``)
whose character map labels them ``5``, ``2`` and ``,``. The file is internally
consistent and consistently wrong: this is the "file lie" tier of CLAUDE.md's
THREE TIERS, and ~190 minus signs in that one paper reach consumers as a
leading ``2`` -- a sign error in a published coefficient.

WHY A CORRECTION IS LICENSED HERE, AND ONLY HERE
------------------------------------------------
The tier rule forbids correcting a file lie on the file's own word, and forbids
linguistic evidence entirely. It licenses a correction when two signals of
DIFFERENT PHYSICAL ORIGIN agree (owner decision, 2026-09-27, option B):

  (A) DECLARED -- the font. A font whose entire repertoire is a handful of
      digit/punctuation codes, in a document whose digits otherwise come from a
      text font, is not a digit font. Census on the paper above: the body font
      draws 97,886 glyphs over 78 characters; ``AdvOT463cc31e`` draws 568 over
      5 (``'5'`` x336, ``'2'`` x190, ``','`` x37, ``'3'`` x4, ``';'`` x1).
  (B) RENDERED -- the ink. The glyph is rasterized from the PDF by poppler and
      its SHAPE is measured: a minus is one thin solid horizontal bar, an equals
      sign is two. A real ``2`` or ``5`` is a tall stroke figure and cannot pass
      either test. No number, word or sentence is consulted.

A pair (font, code) is PROVEN only when every sampled occurrence renders as the
same bar shape. Anything else -- ``<``, ``+``, a glyph whose raster is not a bar,
a sample that disagrees -- is UNRESOLVED and is never rewritten; it is reported so
a consumer can see it. The gate test ("replace every surrounding word with
garbage -- would the evidence still justify the output?") passes: both signals
are local to the glyph.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from .extract_layout import strip_font_subset_prefix

#: A font drawing more distinct non-space characters than this is a text font.
MAX_OPERATOR_FONT_REPERTOIRE = 6
#: The codes an operator font can hide behind: digits and ASCII punctuation.
_DECLARABLE = set("0123456789,.;:<>=+-/()")
#: The document must draw at least this many digits in OTHER fonts, so that a
#: digit from the suspect font is anomalous rather than the only digits there are.
MIN_BODY_DIGITS = 50
#: Occurrences rasterized per (font, code) pair; all must agree.
SAMPLES_PER_PAIR = 3
#: Render resolution for the shape test.
RASTER_DPI = 600
#: Ink touching the crop edge is a neighbour's only if it is this thin a fraction
#: of the box (amj p23 descender: 4 of 83 rows = 0.05).
EDGE_SLIVER_FRACTION = 0.15

MINUS = "−"
EQUALS = "="


@dataclass
class GlyphEvidence:
    """What the two-origin test established for one document."""

    #: (font name, declared code) -> the character the page draws, PROVEN.
    proven: dict[tuple[str, str], str] = field(default_factory=dict)
    #: (font name, declared code) -> why it stays as declared.
    unresolved: dict[tuple[str, str], str] = field(default_factory=dict)
    #: Token index, built on first use by `_prepared`; never part of the record.
    _index: Any = field(default=None, repr=False, compare=False)

    def as_dict(self) -> dict[str, Any]:
        return {
            "proven": {f"{f}|{c}": v for (f, c), v in sorted(self.proven.items())},
            "unresolved": {f"{f}|{c}": v for (f, c), v in sorted(self.unresolved.items())},
        }


def operator_font_candidates(layout: Any) -> dict[str, Counter]:
    """Fonts whose whole repertoire is a few digit/punctuation codes (signal A)."""
    per_font: dict[str, Counter] = {}
    for page in getattr(layout, "pages", ()) or ():
        for c in getattr(page, "chars", ()) or ():
            t = c.get("text") or ""
            if not t.strip():
                continue
            per_font.setdefault(c.get("fontname") or "", Counter())[t] += 1
    out: dict[str, Counter] = {}
    for font, rep in per_font.items():
        if not font or len(rep) > MAX_OPERATOR_FONT_REPERTOIRE:
            continue
        if not set(rep) <= _DECLARABLE or not any(ch.isdigit() for ch in rep):
            continue
        other_digits = sum(
            n for f, r in per_font.items() if f != font
            for ch, n in r.items() if ch.isdigit()
        )
        if other_digits >= MIN_BODY_DIGITS:
            out[font] = rep
    return out


def _read_pgm(path: str) -> tuple[int, int, bytes]:
    with open(path, "rb") as fh:
        data = fh.read()
    # P5 header: magic, width, height, maxval, each separated by whitespace.
    parts: list[bytes] = []
    i = 0
    while len(parts) < 4:
        while data[i:i + 1].isspace():
            i += 1
        if data[i:i + 1] == b"#":
            while data[i:i + 1] not in (b"\n", b""):
                i += 1
            continue
        j = i
        while not data[j:j + 1].isspace():
            j += 1
        parts.append(data[i:j])
        i = j
    if parts[0] != b"P5":
        raise ValueError("not a binary PGM")
    w, h = int(parts[1]), int(parts[2])
    return w, h, data[i + 1:i + 1 + w * h]


def classify_bar_shape(w: int, h: int, pixels: bytes) -> str | None:
    """``MINUS`` for one thin solid bar, ``EQUALS`` for two, else ``None``."""
    ink = [[pixels[y * w + x] < 128 for x in range(w)] for y in range(h)]
    rows = [any(r) for r in ink]
    bands: list[tuple[int, int]] = []
    y = 0
    while y < h:
        if rows[y]:
            s = y
            while y < h and rows[y]:
                y += 1
            bands.append((s, y))
        else:
            y += 1
    # A band touching the crop's top or bottom edge is a NEIGHBOURING LINE's ink
    # (a descender from above, an ascender from below) spilling into this glyph's
    # box -- measured on 10.5465/amj.2016.1196 p23, where a clean minus bar sat
    # under the tail of the line above. The glyph's own bar is interior.
    #
    # ONLY A SLIVER may be discarded. Measured 2026-09-27 on
    # 10.1038/s41598-023-50588-1 p4: genuine digits in a stacked fraction's
    # denominator touch both edges of their box, and dropping that ink left only
    # the fraction's rule -- a clean bar -- so `2` and `6` were "proven" minus
    # signs. A glyph's own figure is tall; a neighbour's descender is a sliver.
    kept = []
    for s, e in bands:
        if s > 0 and e < h:
            kept.append((s, e))
        elif (e - s) > EDGE_SLIVER_FRACTION * h:
            return None  # a figure filling the box: never a bar
    bands = kept
    if not bands or len(bands) > 2:
        return None
    widths = []
    for s, e in bands:
        cols = [x for x in range(w) if any(ink[yy][x] for yy in range(s, e))]
        x0, x1 = min(cols), max(cols) + 1
        width = x1 - x0
        if width <= 0 or (e - s) > 0.35 * width:
            return None  # not thin: a stroke figure, not a bar
        # solid: every ink row of the bar spans most of its width
        for yy in range(s, e):
            if sum(ink[yy][x0:x1]) < 0.8 * width:
                return None
        widths.append(width)
    if len(bands) == 1:
        return MINUS
    if min(widths) >= 0.8 * max(widths):
        return EQUALS
    return None


def _record_raster_failure(key: tuple[str, str], exc: BaseException) -> None:
    """A glyph whose raster failed stays unresolved, so it is not repaired: the
    output differs from a run where the raster worked. Recorded as an
    ``*_exception`` event, which ``extract_pdf_structured`` names in ``method``
    as ``glyph_raster_failed``
    (Sonnet review, 2026-10-01: this site used to record nothing)."""
    from .telemetry import record_fallback

    record_fallback("glyph_raster_exception", detail=f"{key[0]}:{type(exc).__name__}")


def _raster_shape(pdf_path: str, page: int, c: dict, workdir: str) -> str | None:
    scale = RASTER_DPI / 72.0
    x = int(float(c["x0"]) * scale)
    y = int(float(c["top"]) * scale)
    w = max(1, int((float(c["x1"]) - float(c["x0"])) * scale))
    h = max(1, int((float(c["bottom"]) - float(c["top"])) * scale))
    stem = os.path.join(workdir, f"g{page}_{x}_{y}")
    subprocess.run(
        ["pdftoppm", "-gray", "-r", str(RASTER_DPI), "-f", str(page), "-l", str(page),
         "-x", str(x), "-y", str(y), "-W", str(w), "-H", str(h), "-singlefile",
         pdf_path, stem],
        check=True, capture_output=True, timeout=60,
    )
    w, h, px = _read_pgm(stem + ".pgm")
    if c.get("upright") is False:
        # A glyph set sideways (a rotated table page) draws its bar VERTICALLY.
        # Transpose so the same bar test applies -- measured on
        # 10.5465/amj.2016.1196 p13, where all 53 unreadable samples of the
        # document were the non-upright glyphs of its landscape correlation table.
        px = bytes(px[y * w + x] for x in range(w) for y in range(h))
        w, h = h, w
    return classify_bar_shape(w, h, px)


def collect_glyph_evidence(pdf_bytes: bytes, layout: Any) -> GlyphEvidence:
    """Run both signals over one document. Never raises; failures are UNRESOLVED."""
    ev = GlyphEvidence()
    fonts = operator_font_candidates(layout)
    if not fonts:
        return ev
    if shutil.which("pdftoppm") is None:
        for font, rep in fonts.items():
            for code in rep:
                ev.unresolved[(strip_font_subset_prefix(font), code)] = "no_pdftoppm"
        return ev
    occ: dict[tuple[str, str], list[tuple[int, dict]]] = {}
    for pi, page in enumerate(getattr(layout, "pages", ()) or ()):
        for c in getattr(page, "chars", ()) or ():
            f = c.get("fontname") or ""
            if f in fonts and (c.get("text") or "").strip():
                occ.setdefault((f, c["text"]), []).append((pi + 1, c))
    with tempfile.TemporaryDirectory(prefix="docpluck_glyph_") as wd:
        fd, pdf_path = tempfile.mkstemp(suffix=".pdf", dir=wd)
        with os.fdopen(fd, "wb") as fh:
            fh.write(pdf_bytes)
        for (font, code), sites in sorted(occ.items()):
            key = (strip_font_subset_prefix(font), code)
            n = len(sites)
            picks = sorted({0, n // 2, n - 1})[:SAMPLES_PER_PAIR]
            shapes = []
            for k in picks:
                page, c = sites[k]
                try:
                    shapes.append(_raster_shape(pdf_path, page, c, wd))
                except Exception as exc:  # noqa: BLE001 - evidence missing, not a crash
                    shapes.append(None)
                    ev.unresolved[key] = f"raster_failed:{type(exc).__name__}"
                    _record_raster_failure(key, exc)
            if key in ev.unresolved:
                continue
            if shapes and shapes[0] is not None and all(s == shapes[0] for s in shapes):
                if _EMIT.get(shapes[0]) == code or shapes[0] == code:
                    continue  # the file already declares what it draws: nothing to do
                ev.proven[key] = shapes[0]
            else:
                ev.unresolved[key] = "raster_not_a_bar:" + ",".join(str(s) for s in shapes)
    return ev


# ── Applying the evidence ───────────────────────────────────────────────────
#
# The text channel (pdftotext) and the table channel (Camelot) carry no font, so
# a proven glyph has to be found in them by the WORD it sits in. The layout is
# re-tokenised from its own characters -- pdfplumber's ``words`` are unusable
# here: on a rotated page they read backwards (``48.0`` for a printed ``−.48``)
# and on a two-column page their order interleaves columns.
#
# A text token is rewritten only when EVERY layout token with the same string
# and compatible neighbours carries the proven glyph at the same positions. A
# genuine digit anywhere in that set makes the evidence ambiguous and the token
# is REFUSED -- left exactly as declared, and counted. Neighbours are compared
# only where both sides have one (a line end or a table-cell edge matches
# anything), which is what lets a table cell with no neighbours still resolve
# when its string is unique on the page.

#: What a proven glyph is emitted as. A minus goes out as ASCII hyphen-minus --
#: the project's one sanctioned Unicode->ASCII rewrite (LESSONS L-004), so a
#: corrected sign is indistinguishable from one the paper encoded correctly.
_EMIT = {MINUS: "-", EQUALS: "="}


def _layout_lines(page: Any, upright: bool, descending: bool = False) -> list[list[dict]]:
    chars = [c for c in (getattr(page, "chars", ()) or ())
             if bool(c.get("upright", True)) == upright]
    if not chars:
        return []
    # "across" is the reading axis, "down" the line axis.
    if upright:
        down = lambda c: float(c["top"])  # noqa: E731
        across = lambda c: float(c["x0"])  # noqa: E731
    else:
        down = lambda c: float(c["x0"])  # noqa: E731
        across = (lambda c: -float(c["top"])) if descending else (lambda c: float(c["top"]))  # noqa: E731
    lines: list[list[dict]] = []
    for c in sorted(chars, key=lambda c: (down(c), across(c))):
        size = float(c.get("size") or 8.0)
        if lines and abs(down(lines[-1][0]) - down(c)) < 0.5 * size:
            lines[-1].append(c)
        else:
            lines.append([c])
    out: list[list[dict]] = []
    for ln in lines:
        ln.sort(key=across)
        seg = [ln[0]]
        for a, b in zip(ln, ln[1:]):
            size = float(b.get("size") or 8.0)
            if abs(across(b) - across(a)) > 3.0 * size:  # column gutter
                out.append(seg)
                seg = []
            seg.append(b)
        out.append(seg)
    return out


def _tokens_of_line(line: list[dict], upright: bool) -> list[list[dict]]:
    toks: list[list[dict]] = []
    cur: list[dict] = []
    for i, c in enumerate(line):
        if not (c.get("text") or "").strip():
            if cur:
                toks.append(cur)
                cur = []
            continue
        if cur:
            p = cur[-1]
            size = float(c.get("size") or 8.0)
            if upright:
                gap = float(c["x0"]) - float(p["x1"])
            else:
                gap = min(abs(float(c["top"]) - float(p["bottom"])),
                          abs(float(p["top"]) - float(c["bottom"])))
            if gap > 0.2 * size:
                toks.append(cur)
                cur = []
        cur.append(c)
    if cur:
        toks.append(cur)
    return toks


TokenRecord = tuple  # (prev: str|None, next: str|None, fixes: tuple[(pos, emit), ...])


def layout_token_index(layout: Any, evidence: GlyphEvidence) -> dict[str, list[TokenRecord]]:
    """Every layout token that could be compared against a text token."""
    proven = {(f, c): _EMIT[v] for (f, c), v in evidence.proven.items()}
    index: dict[str, list[TokenRecord]] = {}
    if not proven:
        return index
    for page in getattr(layout, "pages", ()) or ():
        streams = [_layout_lines(page, True)]
        if any(not c.get("upright", True) for c in (getattr(page, "chars", ()) or ())):
            # Reading direction of sideways text is not recorded per character;
            # both orders are indexed and only the right one can ever match a
            # text token (a reversed number does not spell a real one).
            streams += [_layout_lines(page, False, False), _layout_lines(page, False, True)]
        for si, lines in enumerate(streams):
            upright = si == 0
            for line in lines:
                toks = _tokens_of_line(line, upright)
                strs = ["".join(ch["text"] for ch in t) for t in toks]
                for k, t in enumerate(toks):
                    fixes = tuple(
                        (pos, proven[(strip_font_subset_prefix(ch.get("fontname") or ""), ch["text"])])
                        for pos, ch in enumerate(t)
                        if (strip_font_subset_prefix(ch.get("fontname") or ""), ch["text"]) in proven
                    )
                    index.setdefault(strs[k], []).append((
                        strs[k - 1] if k > 0 else None,
                        strs[k + 1] if k + 1 < len(toks) else None,
                        fixes,
                    ))
    return index


def _compatible(a: str | None, b: str | None) -> bool:
    return a is None or b is None or a == b


def resolve_token(tok: str, prev: str | None, nxt: str | None,
                  index: dict[str, list[TokenRecord]]) -> tuple[str, str]:
    """``(new_token, outcome)`` with outcome ``fixed`` / ``refused`` / ``none``."""
    recs = [r for r in index.get(tok, ()) if _compatible(r[0], prev) and _compatible(r[1], nxt)]
    # The most specific evidence wins. A layout token with NO neighbours (a bare
    # `5` alone on a line) is compatible with every text context, so it must not
    # outvote tokens whose neighbours match exactly -- measured on
    # 10.5465/amj.2016.1196: 15 isolated genuine `5`s refused all 296 equals signs.
    for need in (2, 1):
        exact = [r for r in recs
                 if (r[0] is not None and r[0] == prev) + (r[1] is not None and r[1] == nxt) >= need]
        if exact:
            recs = exact
            break
    else:
        # NO neighbour matched anywhere. Wildcard-compatible records alone are not
        # evidence: when the two channels tokenise a genuine digit's surroundings
        # differently, its own layout record drops out and only isolated proven
        # glyphs elsewhere remain (Sonnet review, 2026-09-27). Fall back to the
        # WHOLE document: every layout instance of this string must agree.
        recs = list(index.get(tok, ()))
    if not recs or not any(r[2] for r in recs):
        return tok, ("refused" if not recs and tok in index else "none")
    fixes = {r[2] for r in recs}
    if len(fixes) != 1:
        return tok, "refused"
    chars = list(tok)
    for pos, emit in next(iter(fixes)):
        chars[pos] = emit
    return "".join(chars), "fixed"


def apply_to_text(text: str, index: dict[str, list[TokenRecord]],
                  codes: set[str]) -> tuple[str, int, int]:
    """Rewrite proven glyphs in free text. Returns ``(text, fixed, refused)``."""
    if not index or not text:
        return text, 0, 0
    import re
    spans = [(m.start(), m.end(), m.group()) for m in re.finditer(r"\S+", text)]
    edits: list[tuple[int, int, str]] = []
    fixed = refused = 0
    for k, (s, e, tok) in enumerate(spans):
        if not any(ch in codes for ch in tok):
            continue
        new, outcome = resolve_token(
            tok,
            spans[k - 1][2] if k > 0 else None,
            spans[k + 1][2] if k + 1 < len(spans) else None,
            index,
        )
        if outcome == "fixed" and new != tok:
            edits.append((s, e, new))
            fixed += 1
        elif outcome == "refused":
            refused += 1
    for s, e, new in reversed(edits):
        text = text[:s] + new + text[e:]
    return text, fixed, refused


def _prepared(layout: Any) -> tuple[dict[str, list[TokenRecord]], set[str]] | None:
    """The token index for a layout carrying proven evidence, built once."""
    ev = getattr(layout, "glyph_evidence", None) if layout is not None else None
    if ev is None or not ev.proven:
        return None
    if ev._index is None:
        ev._index = layout_token_index(layout, ev)
    return ev._index, {c for (_f, c) in ev.proven}


def apply_to_document_text(text: str, layout: Any) -> tuple[str, int, int]:
    """Text-channel entry point. ``(text, fixed, refused)``; a no-op without evidence."""
    prep = _prepared(layout)
    if prep is None:
        return text, 0, 0
    return apply_to_text(text, *prep)


def apply_to_cells(cells: list[dict], layout: Any) -> None:
    """Table-channel entry point. Rewrites cell text in place; counts go to telemetry.

    Neighbours are taken INSIDE the cell only -- a cell edge is not a word
    boundary the layout can see, so it matches anything.
    """
    prep = _prepared(layout)
    if prep is None:
        return
    import re
    from .telemetry import record_fallback
    index, codes = prep
    fixed = refused = 0
    for cell in cells:
        text = cell.get("text") or ""
        if not any(ch in codes for ch in text):
            continue
        spans = [(m.start(), m.end(), m.group()) for m in re.finditer(r"\S+", text)]
        edits = []
        for k, (s, e, tok) in enumerate(spans):
            if not any(ch in codes for ch in tok):
                continue
            new, outcome = resolve_token(
                tok,
                spans[k - 1][2] if k > 0 else None,
                spans[k + 1][2] if k + 1 < len(spans) else None,
                index,
            )
            if outcome == "fixed" and new != tok:
                edits.append((s, e, new))
            elif outcome == "refused":
                refused += 1
        for s, e, new in reversed(edits):
            text = text[:s] + new + text[e:]
        fixed += len(edits)
        cell["text"] = text
    if fixed:
        record_fallback("operator_glyph_recovered_in_table", detail=str(fixed))
    if refused:
        record_fallback("operator_glyph_refused_in_table", detail=str(refused))


__all__ = [
    "GlyphEvidence", "operator_font_candidates", "classify_bar_shape",
    "collect_glyph_evidence", "layout_token_index", "resolve_token",
    "apply_to_text", "apply_to_document_text", "apply_to_cells", "MINUS", "EQUALS",
]
