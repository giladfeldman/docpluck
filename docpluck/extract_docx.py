"""
DOCX Text Extraction
=====================
Primary engine: mammoth (DOCX → HTML → text via html_to_text)

Why mammoth:
- `mammoth.convert_to_html()` preserves Shift+Enter soft breaks as <br> tags
  (critical for academic documents with poetry, equations, addresses, etc.)
- `mammoth.extract_raw_text()` loses intra-paragraph line breaks — do NOT use it
- python-docx only provides paragraph-level access, not enough structure
- docx2txt is effectively abandoned
- pypandoc requires a binary (pandoc) that's hard to deploy
- BSD-2 license, available in both Python (mammoth) and Node.js (mammoth.js)
- Battle-tested in Scimeto production since Dec 2025

Known limitations:
- ⚠ OMML equations (Office Math) are SILENTLY DROPPED, and this is the most
  serious known defect in this module. **The claim that used to stand here —
  "in practice this is rare in social science papers where stats are written
  as plain text" — was MEASURED FALSE on 2026-08-15** and is recorded rather
  than deleted, because it is why nobody looked for years.

  Measured over 26 real papers from CitationGuard's validation corpus:
      4 / 26 papers (15%) contain OMML
      ~45 non-empty math spans across them
      EVERY ONE is `ηp2`, `χ2` or `ρ` — precisely the effect-size and
      test-statistic symbols this library exists to deliver.

  Verified end to end on `28_ImageMemorability.docx` (8 of its 9 spans are
  `ηp2`):

      the document says   F(1,86) = 48.50, p < .001, ηp2 = .361.
      docpluck delivers   F(1,86) = 48.50, p < .001, = .361.

  The effect size's NAME is gone, leaving a bare `= .361` that no consumer
  can attribute to any statistic. **That is worse than a wrong number**: a
  wrong number can be challenged, an unlabelled one is structurally
  unidentifiable. It is the same defect class as the render-channel deletion
  fixed in v2.4.130 (LESSONS.md L-032), in the DOCX channel instead.

  `mammoth` has NO model of `m:oMath` at all — grepped, zero references — so
  it is not degrading gracefully, it is skipping unrecognized markup. The
  remedy is to read `m:t` runs from `word/document.xml` directly (OMML text
  is trivially extractable) or, at minimum, to emit a LOUD flag that math
  objects were present and dropped, so a consumer knows a label is missing
  rather than trusting a bare value. **Do not ship a silent drop.**
- Tracked changes: only deleted paragraphs are handled minimally.
- Memory: peak usage is ~3-5x file size. Not a concern for single-file
  processing but worth noting for very large documents.

Requires the `docx` optional dependency:
  pip install docpluck[docx]
"""
import io
import re
import zipfile

from .extract_html import html_to_text
from .telemetry import record_fallback


# DISPLAY math is wrapped in `m:oMathPara`, and mammoth skips THAT element too —
# so rewriting only the inner `m:oMath` leaves the replacement run stranded inside
# an element mammoth still discards, and the equation is deleted exactly as before.
# Measured 2026-08-15 (Fable review, reproduced): `42_StressExposureTraining.docx`,
# 1 of the 4 OMML papers in this fix's own corpus, defines `Excess Distance =
# (W-S)/S` inside an `m:oMathPara` and lost it. The outer alternative is listed
# FIRST so the whole paragraph object is replaced, not its inner equation.
_OMATH_RE = re.compile(
    rb"<m:oMathPara[ >].*?</m:oMathPara>|<m:oMath[ >].*?</m:oMath>", re.DOTALL
)
_OMATH_TEXT_RE = re.compile(rb"<m:t[^>]*>(.*?)</m:t>", re.DOTALL)
# Every `xmlns:*` declaration on the part's root element, reused verbatim when a
# matched fragment is re-parsed. Copying the real declarations (rather than
# guessing a list) is what makes the parse survive parts that carry `a:`, `pic:`,
# `mc:` and friends inside an equation.
_XMLNS_DECL_RE = re.compile(rb'\sxmlns:[A-Za-z0-9_.-]+="[^"]*"')
_ROOT_START_TAG_RE = re.compile(rb"<w:document\b[^>]*>")

_MATH_NS = "http://schemas.openxmlformats.org/officeDocument/2006/math"

# Containers whose children are one continuous expression: concatenating them is
# what recovers `ηp2` / `χ2` / `R2` — Word splits an equation into runs by
# formatting, so adjacent runs really are adjacent characters.
_CONCAT = {
    "oMath", "oMathPara", "r", "e", "num", "den", "deg", "sub", "sup", "lim",
    "fName",
}
# Elements that carry formatting properties, never text.
_PROPERTY_SUFFIX = "Pr"
_PROPERTY_NAMES = {
    "chr", "begChr", "endChr", "sepChr", "degHide", "type", "pos", "vertJc",
    "grow", "hideTop", "hideBot", "hideLeft", "hideRight", "count", "mcJc",
}
# An operand needs bracketing before a `/` when it is not a single atom.
_COMPOUND_OPERAND_RE = re.compile(r"[\s+\-*/^×÷−–—=<>,]")


def _local(tag: str) -> str:
    """Local name of an ElementTree tag (`{uri}f` -> `f`)."""
    return tag.rsplit("}", 1)[-1]


def _is_property(name: str) -> bool:
    return name.endswith(_PROPERTY_SUFFIX) or name in _PROPERTY_NAMES


def _paren(operand: str) -> str:
    """Bracket a fraction operand unless it is a single atom.

    `1/2` stays `1/2`; `(Absent-Present)/Absent` keeps the numerator's own
    grouping, which is the information a bare concatenation destroys.
    """
    operand = operand.strip()
    if not operand or not _COMPOUND_OPERAND_RE.search(operand):
        return operand
    if operand.startswith("(") and operand.endswith(")"):
        return operand
    return f"({operand})"


def _arg(el, want: str) -> str:
    """Linearize the first child with local name ``want`` (empty when absent)."""
    for child in el:
        if _local(child.tag) == want:
            return _linearize_omml(child)
    return ""


def _linearize_omml(el) -> str:
    """Render one OMML element as plain text WITHOUT inventing a value.

    The rule this function exists to enforce: **never fuse two numerals whose
    relationship we cannot name.** The first version of this module joined every
    `m:t` in document order with no separator, which is correct for a run of
    characters and catastrophic for a structured object — measured 2026-08-15
    (Fable review, reproduced synthetically and on the flagship paper):

        the document says   ratio = 1/2 of sample
        docpluck delivered  ratio = 12 of sample

        `28_ImageMemorability.docx` span 9, `(Absent-Present)/Absent×100`
        docpluck delivered  `[ Absent-PresentAbsent*100 ]`

    A fabricated `12` is worse than the deletion it replaced: the deletion left
    nothing to trust, while `12` is a plausible number a consumer will parse and
    publish. It does not announce itself, which is this project's worst class.

    So: structures we can name (`m:f`, `m:d`, `m:rad`, and the sub/superscript
    family) are linearized with their real operators, and any structure we CANNOT
    name joins its parts with a space — lossy, visibly so, and incapable of
    manufacturing a number.

    Sub/superscripts deliberately CONCATENATE (`ηp2`, `χ2`, `R2`): that is the
    convention pdftotext already produces for the same symbols, so the DOCX and
    PDF channels agree — `docs/SYMBOL_CONTRACT.md`, one concept one table.
    """
    name = _local(el.tag)
    if name == "t":
        return el.text or ""
    if _is_property(name):
        return ""

    if name in ("sSub", "sSup", "sSubSup"):
        # base, then subscript, then superscript — document order of the parts,
        # concatenated. `m:e` is the base.
        return _arg(el, "e") + _arg(el, "sub") + _arg(el, "sup")

    # An operator is only emitted when there is text on BOTH sides of it. A
    # structure with an empty operand (a bare fraction bar, an empty radical)
    # must not contribute a stray `/` or a fabricated `sqrt()` — the same
    # no-inventing rule as above, applied to the operators themselves.
    if name == "f":
        num, den = _arg(el, "num"), _arg(el, "den")
        if not num.strip() or not den.strip():
            return (num + den).strip()
        return f"{_paren(num)}/{_paren(den)}"

    if name == "rad":
        base = _arg(el, "e")
        deg = _arg(el, "deg").strip()
        if not base.strip():
            return deg
        return f"sqrt({base})" if not deg else f"root{deg}({base})"

    if name == "d":
        beg, end, sep = _delimiters(el)
        inner = [p for p in (
            _linearize_omml(c) for c in el if _local(c.tag) == "e"
        ) if p.strip()]
        if not inner:
            return ""
        return beg + sep.join(inner) + end

    parts = [p for p in (_linearize_omml(c) for c in el) if p]
    if name in _CONCAT:
        return "".join(parts)
    # An unmodelled structure (m:nary, m:limLow, m:m, m:eqArr, m:groupChr, …).
    # Space-join: we do not know the operator, so we refuse to imply one.
    return " ".join(parts)


def _delimiters(el) -> tuple[str, str, str]:
    """`(`, `)`, `,` unless ``m:dPr`` states otherwise (OMML's own defaults)."""
    beg, end, sep = "(", ")", ","
    for pr in el:
        if _local(pr.tag) != "dPr":
            continue
        for child in pr:
            val = child.get(f"{{{_MATH_NS}}}val")
            if val is None:
                continue
            local = _local(child.tag)
            if local == "begChr":
                beg = val
            elif local == "endChr":
                end = val
            elif local == "sepChr":
                sep = val
    return beg, end, sep


def _omml_fragment_text(fragment: bytes, xmlns: bytes) -> str | None:
    """Linearize one matched OMML fragment, or ``None`` if it cannot be parsed.

    ``None`` is a signal to leave the fragment exactly as it was: a file we
    cannot parse must extract no worse than it did before.
    """
    import xml.etree.ElementTree as ET

    try:
        root = ET.fromstring(b"<docpluckOmmlWrap" + xmlns + b">" + fragment + b"</docpluckOmmlWrap>")
    except ET.ParseError:
        return None
    return "".join(_linearize_omml(child) for child in root)


def _inline_omml_runs(docx_bytes: bytes) -> bytes:
    """Replace every OMML equation with a plain run carrying its own text.

    **This fixes silent deletion of published statistics, measured on real
    papers (2026-08-15).** `mammoth` has no model of `m:oMath` — grepped, zero
    references — so it skips the element as unrecognised markup and the
    statistic's NAME disappears:

        the document says   F(1,86) = 48.50, p < .001, ηp2 = .361.
        docpluck delivered  F(1,86) = 48.50, p < .001, = .361.

    A bare `= .361` cannot be attributed to any statistic by any consumer,
    which is **worse than a wrong number**: a wrong number can be challenged,
    an unlabelled one is structurally unidentifiable. Same defect class as the
    render-channel deletion fixed in v2.4.130 (LESSONS.md L-032), in the DOCX
    channel.

    The module docstring used to say OMML was "rare in social science papers".
    Measured over 26 real papers: **4 (15%) contain OMML, ~45 non-empty spans,
    and every one is `ηp2`, `χ2` or `ρ`** — exactly the symbols this library
    exists to deliver.

    METHOD — why rewrite the XML rather than post-process the HTML. The
    equation's POSITION is the information at risk: `= .361` is only
    interpretable if its label sits immediately before it. Splicing recovered
    symbols back into converted HTML would require re-deriving that position;
    substituting a plain `w:r`/`w:t` run in place of the `m:oMath` element
    keeps mammoth's own layout handling and cannot drift. Ordinary Word
    superscript/subscript formatting is NOT involved here (`w:vertAlign` is a
    separate, unaffected mechanism), so this touches only true equation
    objects.

    Deliberately conservative:

    * OMML that yields no text (a pure graphic, a bare fraction bar) is left
      exactly as it was, so nothing that mammoth handles today changes.
    * A file with no `m:oMath` is returned UNCHANGED and unrepacked — the
      common case pays nothing.
    * Any failure to read or rewrite the zip returns the original bytes. A
      malformed DOCX must still extract as well as it did before.
    """
    # NOTE — do NOT early-exit on `b"<m:oMath" not in docx_bytes`. A DOCX is a
    # ZIP, so `docx_bytes` is COMPRESSED and the marker never appears in it; the
    # first version of this function did exactly that and was a silent no-op on
    # every file, while its tests-of-intent looked fine. The cheap check has to
    # happen AFTER decompressing `word/document.xml`. ("A capability nothing
    # invokes is not shipped" — CLAUDE.md.)
    try:
        src = io.BytesIO(docx_bytes)
        with zipfile.ZipFile(src) as zin:
            names = zin.namelist()
            if "word/document.xml" not in names:
                return docx_bytes
            doc_xml = zin.read("word/document.xml")
            if b"<m:oMath" not in doc_xml:
                return docx_bytes  # the common case pays only one decompress
            parts = {n: zin.read(n) for n in names}
            infos = {i.filename: i for i in zin.infolist()}

        # Reuse the part's OWN namespace declarations so a fragment carrying any
        # prefix the document declares still parses.
        root_tag = _ROOT_START_TAG_RE.search(doc_xml)
        xmlns = b"".join(_XMLNS_DECL_RE.findall(root_tag.group(0))) if root_tag else b""
        if b'xmlns:m="' not in xmlns:
            xmlns += b' xmlns:m="' + _MATH_NS.encode() + b'"'

        def _sub(m: "re.Match[bytes]") -> bytes:
            fragment = m.group(0)
            text = _omml_fragment_text(fragment, xmlns)
            if text is None:
                # Unparseable — fall back to the flat `m:t` concatenation rather
                # than to deletion. Lossy for structured math, never worse than
                # the pre-v2.4.131 behaviour. These bytes are already XML-escaped
                # as they stand in the source, so they are spliced verbatim.
                payload = b"".join(_OMATH_TEXT_RE.findall(fragment))
            else:
                if not text.strip():
                    return fragment  # no text to recover — leave it alone
                payload = (
                    text.replace("&", "&amp;")
                    .replace("<", "&lt;")
                    .replace(">", "&gt;")
                ).encode("utf-8")
            if not payload.strip():
                return fragment
            return b"<w:r><w:t xml:space=\"preserve\">" + payload + b"</w:t></w:r>"

        patched, n = _OMATH_RE.subn(_sub, parts["word/document.xml"])
        if not n:
            return docx_bytes
        parts["word/document.xml"] = patched

        out = io.BytesIO()
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zout:
            for name in names:
                zout.writestr(infos[name], parts[name])
        return out.getvalue()
    except Exception as exc:  # defensive; never make extraction worse
        # RECORD IT. Returning the unpatched bytes hands mammoth exactly the
        # input it silently deletes equations from — i.e. this except block
        # reproduces the pre-v2.4.131 defect the whole function exists to fix,
        # and it did so with no signal of any kind. "Never make extraction
        # worse" is the right fallback; doing it invisibly is not, because a
        # silently-reverted repair is indistinguishable from a document that
        # never needed one. That is the same shape as the finding that created
        # this function: mammoth WAS reporting the deletion and nobody read it.
        record_fallback("docx_omml_inline_exception", detail=type(exc).__name__)
        return docx_bytes


def extract_docx(
    docx_bytes: bytes,
    *,
    sections: list[str] | None = None,
    max_input_bytes: int | None = None,
) -> tuple[str, str]:
    """Extract text from DOCX file bytes.

    Converts the DOCX to HTML via mammoth (preserving soft breaks and block
    structure), then runs it through html_to_text() for the final plain-text
    output. This two-step pipeline is what makes soft-break preservation work.

    Args:
        docx_bytes: Raw DOCX file content as bytes.
        sections: Optional list of section labels (e.g. ``["abstract",
            "methods"]``) to filter the output. When provided, ``extract_sections``
            is called and only the requested sections are returned concatenated
            in document order. Pass ``None`` (default) to return the full text.
        max_input_bytes: Optional hard cap for input size. When set and
            ``len(docx_bytes)`` exceeds it, a ValueError is raised.

    Returns:
        A tuple of (text, method) where:
          - text: Extracted plain text with block/inline-aware formatting.
            When ``sections`` is not None, only text from the requested
            sections is included.
          - method: Always "mammoth".

    Raises:
        ValueError: If the DOCX is malformed (mammoth raises — we re-raise).
        ImportError: If mammoth is not installed.

    Requires:
        mammoth (install with `pip install docpluck[docx]`).

    Example:
        with open("paper.docx", "rb") as f:
            text, method = extract_docx(f.read())

        # Filter to abstract only:
        with open("paper.docx", "rb") as f:
            text, method = extract_docx(f.read(), sections=["abstract"])
    """
    # Lazy import so the core library works without mammoth installed
    import mammoth

    if max_input_bytes is not None and len(docx_bytes) > max_input_bytes:
        raise ValueError(
            f"DOCX input exceeds max_input_bytes: {len(docx_bytes)} > {max_input_bytes}"
        )

    # v2.4.131: inline OMML before mammoth sees the file. `mammoth` has NO model
    # of `m:oMath` and silently skips it, deleting the NAME of a statistic and
    # leaving a bare `= .361` behind. See `_inline_omml_runs`.
    docx_bytes = _inline_omml_runs(docx_bytes)

    result = mammoth.convert_to_html(io.BytesIO(docx_bytes))
    html = result.value
    text = html_to_text(html)

    if sections is not None:
        from .sections import extract_sections
        doc = extract_sections(docx_bytes)
        return doc.text_for(*sections), "mammoth"

    return text, "mammoth"
