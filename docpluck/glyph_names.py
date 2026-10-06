"""Glyph-name repair for fonts that carry no ToUnicode map (Linotype Pi families).

THE DEFECT (2026-10-05, reported by a downstream consumer, DOI 10.1037/xge0000057, JEP: General 2015)
    Some typesetters set operators and Greek letters in Linotype Pi fonts
    (Universal-GreekwithMathPi, MathematicalPi-One / -Six, Universal-NewswithCommPi).
    Those fonts have NO /ToUnicode map; their /Encoding is a /Differences array of
    Linotype glyph names (/H11005, /H9251, ...) that are not in the Adobe Glyph List.
    poppler cannot map them: Linux builds fall back to the raw byte (``=`` arrives as
    ``!``, ``<`` as ``'``, minus as ``&``); the Windows build reads the decimal digits
    as a hex code point (``=`` arrives as U+2AFD). Either way every statistic in the
    paper is unparseable (``F(2, 126) ! 4.04, p ! .02``).

THE REPAIR
    Not a rewrite of the extracted text (``!`` is also a real exclamation mark; nothing
    in the output says which is which). The evidence is in the PDF: the font's own
    glyph NAME. For a font with no ToUnicode and a /Differences name in the table
    below, a ToUnicode CMap is added to a copy of the PDF in memory, and every
    downstream tool (pdftotext, pdfplumber, Camelot) then decodes the glyph as the
    font declares it. This is Tier 2 (channel repair: our reader could not decode a
    name the file does declare), never a guess from surrounding words — the gate test
    "would the same evidence justify the output if every surrounding word were random
    garbage" passes, because the evidence is the glyph name alone.

    The result is independent of the poppler build and of poppler's data directory.

WHAT IS NOT MAPPED
    A glyph name that matches ``^H\\d{4,5}$`` but is not in the table is left exactly
    as the extractor emits it and REPORTED (:class:`GlyphNameReport.unmapped`), so a
    consumer can tell a reader the symbols are unreliable instead of silently
    receiving ``!`` for ``=``. The table lists ONLY glyphs verified against a 300 dpi
    raster of a real page; extending it by pattern (e.g. "Greek is Unicode + 8306")
    is a guess until each added glyph is seen drawn.

PROVENANCE of every row: 10.1037/xge0000057 (JEP: General 2015), 300 dpi page raster,
checked 2026-10-05 by the reporting consumer and re-confirmed against the raster here.
The journal prints partial eta-squared as eta^2 with a rho subscript; rho is emitted
AS PRINTED (U+03C1), never corrected to a Latin p.

NOT COVERED: a font whose glyph NAME is an Adobe Glyph List name but draws something
else (OurOwn-CJS code 193 is named /exclamdown and draws an arrow U+2192). That is a
font-specific override, not a name table, and is not done here.
"""

from __future__ import annotations

import hashlib
import io
import logging
import re
import threading
from collections import OrderedDict
from dataclasses import dataclass, field

# Glyph name -> character. Every row verified against a rendered page (see above).
LINOTYPE_PI_GLYPHS: dict[str, str] = {
    "H11005": "=",
    "H9251": "α",   # alpha
    "H11003": "×",  # multiplication sign
    "H9257": "η",   # eta
    "H9267": "ρ",   # rho (printed as the subscript of partial eta-squared)
    "H11002": "−",  # minus; normalize_text folds U+2212 to "-"
    "H11021": "<",
    "H11022": ">",
    "H9273": "χ",   # chi
    "H11001": "+",
    "H11349": "≤",  # <=  (MathematicalPi-One; 10.1001/jamanetworkopen.2023.21102 p4, 300 dpi: "very low CRF (<=25 mL/min/kg)")
    "H11350": "≥",  # >=  (same paper p7: "age, >=60 years")
    "H11569": "∗",  # asterisk operator (significance star)
    "H18546": "■",  # black square (end-of-article mark)
}

_H_NAME_RE = re.compile(r"^H\d{4,5}$")


@dataclass
class GlyphNameReport:
    """What the scan found. ``remapped``/``unmapped`` are per font.

    ``remapped``: ``{font: {glyph_name: char}}`` for glyphs the table decoded.
    ``unmapped``: ``[{"font", "glyph_names", "char_count"}]`` for H-named glyphs the
    table does not cover (left as the extractor emits them). ``char_count`` is the
    number of characters set in that font across the document, or None when it could
    not be counted.
    """

    remapped: dict[str, dict[str, str]] = field(default_factory=dict)
    unmapped: list[dict] = field(default_factory=list)

    @property
    def method_suffix(self) -> str:
        """Pieces appended to ``extract_pdf``'s method string ('' when nothing fired)."""
        out = ""
        if self.remapped:
            out += "+linotype_pi_remapped:" + ",".join(sorted(self.remapped))
        if self.unmapped:
            out += "+unmapped_glyph_fonts:" + ",".join(
                sorted(u["font"] for u in self.unmapped)
            )
        return out

    def __bool__(self) -> bool:
        return bool(self.remapped or self.unmapped)


def _differences(font) -> dict[int, str]:
    """code -> glyph name from a simple font's /Encoding /Differences ({} if none)."""
    enc = font.get("/Encoding")
    enc = enc.get_object() if enc is not None else None
    diffs = enc.get("/Differences") if hasattr(enc, "get") else None
    if not diffs:
        return {}
    out: dict[int, str] = {}
    code = 0
    for item in diffs:
        item = item.get_object() if hasattr(item, "get_object") else item
        if isinstance(item, (int, float)) and not isinstance(item, bool):
            code = int(item)
        else:
            out[code] = str(item).lstrip("/")
            code += 1
    return out


def _iter_fonts(resources, seen: set, depth: int = 0):
    """Yield every distinct font dictionary reachable from a /Resources dict,
    including fonts used only inside Form XObjects."""
    if resources is None or depth > 4:
        return
    resources = resources.get_object()
    fonts = resources.get("/Font")
    if fonts is not None:
        for _, ref in fonts.get_object().items():
            fobj = ref.get_object()
            key = getattr(ref, "idnum", None) or id(fobj)
            if key in seen:
                continue
            seen.add(key)
            yield fobj
    xobjs = resources.get("/XObject")
    if xobjs is not None:
        for _, ref in xobjs.get_object().items():
            xo = ref.get_object()
            key = ("x", getattr(ref, "idnum", None) or id(xo))
            if key in seen:
                continue
            seen.add(key)
            if xo.get("/Subtype") == "/Form":
                yield from _iter_fonts(xo.get("/Resources"), seen, depth + 1)


def _candidate_fonts(reader):
    """(font object, base font name, code->H-name map) for every simple font that has
    no ToUnicode and at least one H-named /Differences glyph."""
    seen: set = set()
    for page in reader.pages:
        for font in _iter_fonts(page.get("/Resources"), seen):
            if "/ToUnicode" in font:
                continue
            h = {c: n for c, n in _differences(font).items() if _H_NAME_RE.match(n)}
            if h:
                yield font, str(font.get("/BaseFont", "?")).lstrip("/"), h


def _to_unicode_cmap(pairs: dict[int, str]) -> bytes:
    rows = "\n".join(
        "<%02X> <%s>" % (code, "".join("%04X" % ord(c) for c in ch))
        for code, ch in sorted(pairs.items())
    )
    return (
        "/CIDInit /ProcSet findresource begin 12 dict begin begincmap\n"
        "/CIDSystemInfo << /Registry (Adobe) /Ordering (UCS) /Supplement 0 >> def\n"
        "/CMapName /Adobe-Identity-UCS def /CMapType 2 def\n"
        "1 begincodespacerange <00> <FF> endcodespacerange\n"
        f"{len(pairs)} beginbfchar\n{rows}\nendbfchar\n"
        "endcmap CMapName currentdict /CMap defineresource pop end end\n"
    ).encode("ascii")


def _pages_using(reader, base_fonts: set[str]) -> set[int]:
    """0-based indices of the pages whose resources reach a font in ``base_fonts``.
    Counting characters parses a page's whole content stream (28 s over a 2.5 MB
    paper), so only these pages are ever parsed."""
    pages: set[int] = set()
    for i, page in enumerate(reader.pages):
        for font in _iter_fonts(page.get("/Resources"), set()):
            if str(font.get("/BaseFont", "?")).lstrip("/") in base_fonts:
                pages.add(i)
                break
    return pages


def _count_chars(reader, pdf_bytes: bytes, base_fonts: set[str]) -> dict[str, int | None]:
    """Characters set per base font (pdfplumber, only on pages that use one).
    None for all on any failure."""
    try:
        import pdfplumber

        counts = {f: 0 for f in base_fonts}
        wanted = _pages_using(reader, base_fonts)
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for i, page in enumerate(pdf.pages):
                if i not in wanted:
                    continue
                for ch in page.chars:
                    name = str(ch.get("fontname", "")).lstrip("/")
                    if name in counts:
                        counts[name] += 1
        return counts
    except Exception as exc:
        from .telemetry import record_fallback

        record_fallback("glyph_name_char_count_exception", detail=type(exc).__name__)
        return {f: None for f in base_fonts}


def _repair(pdf_bytes: bytes) -> tuple[bytes, GlyphNameReport, bool]:
    """``(bytes, report, ok)``; ``ok`` is False when the attempt raised (never cached)."""
    report = GlyphNameReport()
    try:
        import pypdf

        reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
        found = list(_candidate_fonts(reader))
        if not found:
            return pdf_bytes, report, True

        patch: list[tuple[str, dict[int, str]]] = []
        unmapped_names: dict[str, set[str]] = {}
        for _font, base, h in found:
            known = {c: LINOTYPE_PI_GLYPHS[n] for c, n in h.items() if n in LINOTYPE_PI_GLYPHS}
            if known:
                report.remapped.setdefault(base, {}).update(
                    {h[c]: ch for c, ch in known.items()}
                )
                patch.append((base, known))
            lost = {n for c, n in h.items() if n not in LINOTYPE_PI_GLYPHS}
            if lost:
                unmapped_names.setdefault(base, set()).update(lost)

        if unmapped_names:
            counts = _count_chars(reader, pdf_bytes, set(unmapped_names))
            for base, names in sorted(unmapped_names.items()):
                report.unmapped.append(
                    {
                        "font": base,
                        "glyph_names": sorted(names),
                        "char_count": counts.get(base),
                    }
                )

        if not patch:
            return pdf_bytes, report, True

        from pypdf import PdfWriter
        from pypdf.generic import DecodedStreamObject, NameObject

        writer = PdfWriter(clone_from=reader)
        applied = {(base, tuple(sorted(p.items()))) for base, p in patch}
        for _font, base, h in _candidate_fonts(writer):
            known = {c: LINOTYPE_PI_GLYPHS[n] for c, n in h.items() if n in LINOTYPE_PI_GLYPHS}
            if not known or (base, tuple(sorted(known.items()))) not in applied:
                continue
            stream = DecodedStreamObject()
            stream.set_data(_to_unicode_cmap(known))
            _font[NameObject("/ToUnicode")] = writer._add_object(stream)
        buf = io.BytesIO()
        writer.write(buf)
        return buf.getvalue(), report, True
    except Exception as exc:  # never lose the extraction over a repair attempt
        from .telemetry import record_fallback

        record_fallback("glyph_name_repair_exception", detail=type(exc).__name__)
        return pdf_bytes, GlyphNameReport(), False


_CACHE: "OrderedDict[tuple[int, str], tuple[bytes | None, GlyphNameReport]]" = OrderedDict()
_CACHE_MAX = 4
# The service runs extraction in a threadpool; move_to_end / popitem on a key another
# thread just evicted raises KeyError, so every cache touch holds this lock. The repair
# itself runs outside it (two threads may repair the same new document once each).
_CACHE_LOCK = threading.Lock()


class _TrailerSizeFilter(logging.Filter):
    """pypdf logs "Object count N exceeds defined trailer size M" for any PDF whose
    trailer under-counts its objects (the Linotype-Pi paper has 321 vs 319). It is a
    harmless header quirk that poppler and pdfplumber read past; it would otherwise
    print on stderr for every repaired document."""

    def filter(self, record: logging.LogRecord) -> bool:
        return "exceeds defined trailer size" not in record.getMessage()


for _name in ("pypdf._reader", "pypdf._writer"):  # the writer emits it on write()
    logging.getLogger(_name).addFilter(_TrailerSizeFilter())


def repair_glyph_names(pdf_bytes: bytes) -> tuple[bytes, GlyphNameReport]:
    """Return ``(pdf_bytes_to_read, report)``.

    For a PDF with no affected font the SAME bytes object comes back and the report is
    falsy, so every extraction of an ordinary PDF is byte-identical to before. The
    last few results are memoised by content hash because text, layout, table and
    structured extraction each call this with the same document. A repair that RAISED
    is never memoised: it is recorded (``glyph_name_repair_exception``) on every call,
    so a later request still sees the failure instead of an unrecorded clean pass.
    """
    key = (len(pdf_bytes), hashlib.sha1(pdf_bytes).hexdigest())
    with _CACHE_LOCK:
        hit = _CACHE.get(key)
        if hit is not None:
            _CACHE.move_to_end(key)
    if hit is not None:
        return (pdf_bytes if hit[0] is None else hit[0]), hit[1]
    fixed, report, ok = _repair(pdf_bytes)
    if ok:
        with _CACHE_LOCK:
            # An unchanged document is cached as None so the memo never pins its bytes.
            _CACHE[key] = (None if fixed is pdf_bytes else fixed, report)
            _CACHE.move_to_end(key)
            while len(_CACHE) > _CACHE_MAX:
                _CACHE.popitem(last=False)
    return fixed, report
