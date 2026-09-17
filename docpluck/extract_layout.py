"""Layout-aware PDF extraction.

Internal-only for v1.6.0 — used by docpluck.sections.annotators.pdf and the
F0 footnote/header strip step in normalize. Public API surface (the shape of
LayoutDoc) is NOT promised externally; see TODO.md.
"""

from __future__ import annotations

import re
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
    # Which page indices actually carry geometry. ``None`` means "every page"
    # (the only state that existed before the page subset was added) and is
    # what every full
    # extraction returns. A tuple means this doc was built with
    # ``extract_pdf_layout(..., pages=...)``, and the pages OUTSIDE it are
    # PRESENT BUT EMPTY — correct ``width``/``height``, no spans, words, chars,
    # lines, rects or curves, and no text in ``raw_text``.
    #
    # Recorded rather than left implicit because a 72-page LayoutDoc whose 49
    # unrequested pages silently contain nothing is indistinguishable from a
    # document whose pages really are blank, and a consumer reading it as the
    # latter gets a wrong answer with no error. Check this field before treating
    # an empty page as evidence about the PDF.
    populated_pages: tuple[int, ...] | None = None


def extract_pdf_layout(
    pdf_bytes: bytes,
    *,
    pages: Iterable[int] | None = None,
) -> LayoutDoc:
    """Read a PDF with pdfplumber and return per-page layout + raw text.

    `raw_text` joins per-page text with `\f` separators (matching the
    pdftotext form-feed convention) so existing normalization page-detection
    keeps working. `page_offsets[i]` is the start offset of page i+1 in
    raw_text.

    Args:
        pages: optional 0-based page indices to populate. ``None`` (default)
            populates every page and returns exactly what this function has
            always returned. When a subset is given the returned doc still has
            ONE ENTRY PER PDF PAGE at its real index — so ``doc.pages[i]`` keeps
            meaning "page i" for every caller — but only the requested pages
            carry geometry; the rest are empty placeholders, and
            ``populated_pages`` records which is which. Indices outside
            ``[0, n_pages)`` are ignored rather than raising: callers derive
            page numbers from pdftotext's form feeds, which can disagree with
            pdfplumber's page count by one on a trailing form feed.

    Why the subset exists (measured 2026-09-17). ``extract_pdf`` runs this over
    the WHOLE document whenever its cheap text-only detectors flag any page for
    column correction, then corrects at most those pages. On a 72-page paper
    with 23 flagged pages that was 25.3 s of pdfplumber for 23 pages' worth of
    geometry, and ``p.chars`` — the per-page content-stream parse — is 81.9% of
    it. Reading only the flagged pages is the same work for the splice at
    roughly ``len(pages)/n_pages`` of the cost.
    """
    import pdfplumber  # type: ignore
    import io

    wanted: set[int] | None = None if pages is None else {int(i) for i in pages}

    out_pages: list[PageLayout] = []
    raw_chunks: list[str] = []
    offsets: list[int] = []
    cursor = 0

    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for i, p in enumerate(pdf.pages):
            populate = wanted is None or i in wanted
            # ``p.chars`` is the content-stream parse and everything else on the
            # page reuses it, so it is the whole saving: a skipped page must read
            # NOTHING but the page dict's own width/height.
            page_text = (p.extract_text() or "") if populate else ""
            offsets.append(cursor)
            if i > 0:
                # Form-feed page separator (matches pdftotext convention).
                raw_chunks.append("\f")
                cursor += 1
                offsets[-1] = cursor  # adjust to point AFTER the form feed
            raw_chunks.append(page_text)
            cursor += len(page_text)
            if populate:
                chars = p.chars or []
                out_pages.append(PageLayout(
                    page_index=i,
                    width=float(p.width),
                    height=float(p.height),
                    spans=tuple(_chars_to_spans(chars, page_index=i)),
                    lines=tuple(p.lines or ()),
                    rects=tuple(p.rects or ()),
                    curves=tuple(p.curves or ()),
                    chars=tuple(chars),
                    words=tuple(p.extract_words() or ()),
                ))
            else:
                out_pages.append(PageLayout(
                    page_index=i,
                    width=float(p.width),
                    height=float(p.height),
                    spans=(),
                ))

    return LayoutDoc(
        pages=tuple(out_pages),
        raw_text="".join(raw_chunks),
        page_offsets=tuple(offsets),
        populated_pages=(
            None if wanted is None
            else tuple(sorted(i for i in wanted if 0 <= i < len(out_pages)))
        ),
    )


class PartialLayoutError(ValueError):
    """A page-subset LayoutDoc was handed to something that needs the whole document."""


def require_full_layout(layout, *, who: str):
    """Refuse a page-subset ``LayoutDoc`` where a full-document one is meant.

    ``extract_pdf_layout(pages=...)`` returns a doc whose unrequested pages are
    present but EMPTY. That is exactly right for the column splice, which reads
    only the pages it asked for — and exactly wrong for table extraction, figure
    detection or the symbol-font scan, each of which sweeps every page and would
    report "no tables on page 40" when the truth is "page 40 was never read".

    The failure would be silent and plausible, which is the worst combination
    available, so the subset is refused at the boundary rather than trusted to
    stay where it was built. Returns ``layout`` unchanged when it is safe, so
    call sites can wrap in place.
    """
    if layout is None:
        return None
    populated = getattr(layout, "populated_pages", None)
    if populated is None:
        return layout
    total = len(getattr(layout, "pages", ()) or ())
    raise PartialLayoutError(
        f"{who} needs a full-document LayoutDoc, but was given one covering "
        f"{len(populated)} of {total} pages ({sorted(populated)[:8]}...). "
        f"Call extract_pdf_layout(pdf_bytes) without `pages=` for this path."
    )


def _join_chars_with_spaces(line: list[dict]) -> str:
    """Concatenate per-char ``text``, inserting a space where the horizontal
    gap between consecutive glyphs exceeds a font-relative threshold.

    pdfplumber's ``chars`` stream often omits the inter-word space glyph on
    tight-kerned PDFs (Cambridge journals, many two-column layouts), so a naive
    ``"".join(...)`` glues a whole line into one token ("CNSSpectrums",
    "Thebehavioralhealthcarecontinuum"). That silently destroys the text/body
    channel whenever the F0 layout path rebuilds body text from spans — the
    word boundaries are simply gone, even though the character count looks
    right. We re-introduce word boundaries the way pdftotext does: from the
    x-gap, keyed on a fraction of the glyph font size so the threshold scales
    across point sizes. ``0.20·size`` reproduces pdftotext/JATS spacing to
    within ~0.2% space-density on the Cambridge/PMC corpus.

    See LESSONS.md / memory ``feedback_pdfplumber_extract_words_unreliable``
    ("always carry a char-level absolute-x-gap fallback").
    """
    parts: list[str] = []
    prev: dict | None = None
    for c in line:
        t = c.get("text", "")
        if not t:
            continue
        if prev is not None and parts:
            gap = float(c.get("x0") or 0.0) - float(prev.get("x1") or 0.0)
            size = max(float(c.get("size") or 0.0),
                       float(prev.get("size") or 0.0)) or 10.0
            if gap > 0.20 * size and not t[0].isspace() \
                    and not parts[-1].endswith(" "):
                parts.append(" ")
        parts.append(t)
        prev = c
    return "".join(parts)


def _chars_to_spans(chars: Iterable[dict], *, page_index: int) -> Iterable[TextSpan]:
    """Cluster pdfplumber per-character dicts into per-line text spans.

    Heuristic: chars are grouped into lines by close y-coords (within 1pt);
    within a line, ``_join_chars_with_spaces`` re-inserts inter-word spaces
    from the x-gap (pdfplumber's char stream drops the space glyph on
    tight-kerned PDFs — see that helper). One span == one line; columns are
    NOT split here, so a line spanning two columns is merged (a known residual
    handled downstream by the text channel's reading-order logic).
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
        text = _join_chars_with_spaces(line)
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


# ── Mis-mapped symbol fonts: DETECT and REPORT, do not repair ──────────────
#
# Some publisher font pipelines embed a symbol face whose glyph program is
# baked wrong, so pdftotext and pdfplumber both decode a symbol as an ordinary
# Latin character. Confirmed by rasterizing the page (10.5465-style AOM paper,
# `aom/amj-1` p11): the page prints
#
#     processes (alpha = .93), we created a 4-item scale
#
# and the text layer delivers `a5(.93)` — the Greek alpha drawn by a font whose
# ENTIRE whole-document repertoire is `D a b x` (the Adobe-Symbol Greek
# mapping: Delta alpha beta xi), and the `=` supplied by another narrow face.
# So a Cronbach's alpha of .93 reaches every consumer with both its NAME and its
# OPERATOR destroyed — structurally worse than a wrong number, because an
# unlabelled value cannot be challenged.
#
# WHY THIS DETECTS AND DOES NOT REPAIR. Measured over the 152-paper corpus, 15
# papers (10%) carry a narrow inline ASCII font whose letters are all
# Symbol-Greek preimages — but inspecting them shows they are NOT one class:
#
#   ar-apa-j-jesp-2009-12-010   AdvPSMP10   'b' x13        -> already W0m (beta)
#   aom/amj-1, aom/amd-2        AdvPS7DA6   'Dabx'         -> the alpha class
#   chen-et-al-2021-spps        AdvP4C4E74  '(cid:2)(cid:3)1/4' x416 -> a third thing
#
# A blanket Latin->Greek rewrite over that mixture would repair one class and
# corrupt the others, which is precisely the failure v2.4.131 shipped (a fix
# that fabricated numbers being worse than the deletion it replaced). Per
# docpluck's own contract — extract and normalize, never silently repair, and
# TELL the consumer what we could not resolve — the honest action available
# today is to make the corruption VISIBLE rather than silent. The detection
# reaches consumers through `StructuredResult["fallbacks"]`.
#
# The repair remains open work; see docs/OVERHAUL_REGISTER.md G1/G6b.

# The Adobe Symbol font's Latin->Greek glyph mapping. A font whose whole
# repertoire lies inside these preimages is a Symbol face being read as Latin.
_SYMBOL_GREEK_PREIMAGES = frozenset("abgdezhqiklmnxoprstufcyjw"
                                    "ABGDEZHQIKLMNXOPRSTUFCYJW")
_NARROW_REPERTOIRE_MAX = 6
_NARROW_MIN_GLYPHS = 8

_SUBSET_PREFIX_RE = re.compile(r"^[A-Z]{6}\+")
# Style suffixes publishers append to ONE family: MyriadPro-Regular / -It /
# -Semibold / -LightIt are the same face styled, not a separate font.
_STYLE_SUFFIX_RE = re.compile(
    r"[-,._]?(regular|roman|book|italic|it|oblique|obl|semibold|bold|bd|light|"
    r"medium|md|black|heavy|condensed|cond)+$",
    re.IGNORECASE,
)
# Short style codes after a separator: AdvTimes-i, Foo.B, Bar_bi. Only after a
# separator, so a hash-named face like `AdvOT3a8a92a3` is untouched.
_SHORT_STYLE_RE = re.compile(r"[-,._](i|b|o|bi|ib|bo|ri)$", re.IGNORECASE)
# TeX ships one cut per optical size: `CMR5` is a 5pt cut of `CMR10`.
_SIZE_SUFFIX_RE = re.compile(r"^([A-Za-z]+)(\d{1,2})$")


def strip_font_subset_prefix(fontname: str) -> str:
    """Drop the 6-letter subset prefix Type-1/CFF subsets carry (``ABCDEF+Font``)."""
    return _SUBSET_PREFIX_RE.sub("", fontname or "")


def _family_stem(name: str) -> str:
    return _STYLE_SUFFIX_RE.sub("", _SHORT_STYLE_RE.sub("", name or ""))


def fonts_are_same_family(a: str, b: str) -> bool:
    """True when two font names differ only by a STYLE suffix.

    **Negative filter only.** "Shared family root" was refuted as a *positive*
    discriminator — Elsevier's `AdvTT…` faces are opaque hashes, so a shared root
    either misses the known positive or fires on everything. The converse still
    holds: when two names share a stem and differ only by a recognised style
    word, the switch is ordinary styling, not a font substitution.

    Single definition, used by both the library detector
    (:func:`detect_symbol_font_corruption`) and
    ``tools/diag/glyph_font_discontinuity_scan.py``. It was duplicated once
    before, which is the exact shape of the one-concept-one-table rule's failure
    mode; the scan now imports it from here.
    """
    sa, sb = _family_stem(a), _family_stem(b)
    return bool(sa) and sa == sb


def font_size_variant_base(font: str) -> str | None:
    """``CMR5`` -> ``CMR``; ``None`` when the name is not a TeX optical-size cut.

    Deliberately narrow — a purely alphabetic stem plus 1-2 digits. Targets the
    TeX convention specifically and cannot fire on a hash name.
    """
    m = _SIZE_SUFFIX_RE.match(font or "")
    return m.group(1) if m else None


def detect_symbol_font_corruption(layout) -> dict[str, int]:
    """Fonts in this document that look like mis-decoded symbol faces.

    Returns ``{font_name: glyph_count}``. Empty when nothing qualifies.

    A font qualifies when, across the WHOLE document, it draws at least
    ``_NARROW_MIN_GLYPHS`` glyphs, has at most ``_NARROW_REPERTOIRE_MAX``
    distinct characters, every character is ASCII, and every LETTER it draws is
    a Symbol-font Greek preimage. A real text font in a 12-page paper draws
    50-90 distinct characters; three is not a text font.

    ## Two exclusions, both measured against real false positives

    The repertoire test alone has a false-positive surface a post-fix review
    named directly: ``_SYMBOL_GREEK_PREIMAGES`` covers 25 of the 26 lowercase
    letters, so a SUBSET FACE that happens to draw only statistical italics —
    ``{'p': 20, 't': 5}`` under ``Times-Italic`` — satisfies every condition and
    is reported as corruption. Since the report is what tells a consumer which
    document to distrust, a false positive there spends the consumer's trust on
    nothing.

    So a narrow font is excluded when the document ALSO carries:

      * the same family styled (:func:`fonts_are_same_family`) — italic *p* and
        *n* beside the roman body face is ordinary statistical notation
        (measured: 58 inline `MyriadPro-*It` hits on `bmc-med-3`);
      * the same TeX optical-size base (:func:`font_size_variant_base`) —
        ``CMR5``/``CMR6`` are narrow only because the document sets few
        characters at 5pt, and ``CMR10`` is right there (measured: 86 inline hits
        on `ieee-access-7`).

    Both conditions are the ones ``tools/diag/glyph_font_discontinuity_scan.py``
    already validated against known NEGATIVES, imported from here rather than
    re-implemented.

    Purely typographic — it reads what the renderer emitted and never reasons
    about what a number ought to be.
    """
    from collections import Counter

    pages = getattr(layout, "pages", None)
    if not pages:
        return {}
    per_font: dict[str, Counter] = {}
    for page in pages:
        for ch in (getattr(page, "chars", None) or ()):
            name = strip_font_subset_prefix(str(ch.get("fontname") or ""))
            per_font.setdefault(name, Counter())[str(ch.get("text") or "")] += 1

    all_fonts = list(per_font)
    out: dict[str, int] = {}
    for font, counts in per_font.items():
        total = sum(counts.values())
        if total < _NARROW_MIN_GLYPHS or len(counts) > _NARROW_REPERTOIRE_MAX:
            continue
        chars = "".join(k for k in counts if k)
        if not chars or any(ord(c) > 127 for c in chars):
            continue          # already-correct symbols decode fine
        letters = [c for c in chars if c.isalpha()]
        if not letters or any(c not in _SYMBOL_GREEK_PREIMAGES for c in letters):
            continue
        base = font_size_variant_base(font)
        if any(
            other != font
            and (
                fonts_are_same_family(other, font)
                or (base is not None and font_size_variant_base(other) == base)
            )
            for other in all_fonts
        ):
            continue          # ordinary styling / optical-size cut, not a symbol face
        out[font] = total
    return out
