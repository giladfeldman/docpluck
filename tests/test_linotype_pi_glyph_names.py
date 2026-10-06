"""Linotype Pi glyph names (/H11005 ...) in fonts with no ToUnicode map.

Defect 2026-10-05 (downstream consumer report, DOI 10.1037/xge0000057): the PDF sets operators in a font
whose /Differences are Linotype names poppler cannot map, so `F(2, 126) = 4.04` came out
as `F(2, 126) ! 4.04` (Linux poppler) or `F(2, 126) U+2AFD 4.04` (Windows poppler).

The PDFs here are built byte by byte: no paper, publication text or corpus file lives in
this repository (article-finder is the sole custodian). The fonts are the 14 standard
fonts, un-embedded, which is all pdftotext needs to read the text layer.
"""

import re

from docpluck.extract import extract_pdf
from docpluck.glyph_names import LINOTYPE_PI_GLYPHS, repair_glyph_names


def _pdf(fonts: dict[str, str], content: str, extra: list[str] | None = None) -> bytes:
    """One-page PDF. ``fonts``: resource name -> font dictionary body."""
    objs: list[str] = []
    objs.append("<< /Type /Catalog /Pages 2 0 R >>")
    objs.append("<< /Type /Pages /Kids [3 0 R] /Count 1 >>")
    font_refs = " ".join(f"/{n} {5 + i} 0 R" for i, n in enumerate(fonts))
    objs.append(
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        f"/Contents 4 0 R /Resources << /Font << {font_refs} >> >> >>"
    )
    objs.append(f"<< /Length {len(content)} >>\nstream\n{content}\nendstream")
    objs.extend(fonts.values())
    objs.extend(extra or [])
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, body in enumerate(objs, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n{body}\nendobj\n".encode("latin-1")
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += (
        f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n"
    ).encode()
    return bytes(out)


_PLAIN = "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>"


def _pi(names: str) -> str:
    return (
        "<< /Type /Font /Subtype /Type1 /BaseFont /ABCDEF+Universal-GreekwithMathPi "
        "/FirstChar 33 /LastChar 33 /Widths [600] /FontDescriptor << /Type /FontDescriptor "
        "/FontName /ABCDEF+Universal-GreekwithMathPi /Flags 4 /FontBBox [0 0 1000 1000] "
        "/ItalicAngle 0 /Ascent 800 /Descent -200 /CapHeight 700 /StemV 80 >> "
        "/Encoding << /Type /Encoding /BaseEncoding /WinAnsiEncoding "
        f"/Differences [33 {names}] >> >>"
    )


def _squash(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


# Codes 33.. (!"#$%&'()*) map to the names in the order listed, as in the real font.
_CONTENT = (
    "BT /F1 12 Tf 72 700 Td (F\\(2, 126\\) ) Tj /F2 12 Tf (!) Tj /F1 12 Tf ( 4.04, p ) Tj "
    "/F2 12 Tf (!) Tj /F1 12 Tf ( .02, t\\(126\\) ) Tj /F2 12 Tf (!) Tj (&) Tj "
    "/F1 12 Tf (3.07, p ) Tj /F2 12 Tf (') Tj /F1 12 Tf ( .01!) Tj ET"
)
_NAMES = "/H11005 /H9251 /H11003 /H9257 /H9267 /H11002 /H11021"


def test_linotype_names_decode_as_the_font_declares_them():
    pdf = _pdf({"F1": _PLAIN, "F2": _pi(_NAMES)}, _CONTENT)
    text, method = extract_pdf(pdf)
    flat = _squash(text)
    assert "F(2, 126) = 4.04, p = .02, t(126) =" in flat
    assert "−3.07, p < .01" in flat
    # The ordinary Helvetica "!" at the end is a real exclamation mark: untouched.
    assert flat.endswith(".01!")
    assert "+linotype_pi_remapped:ABCDEF+Universal-GreekwithMathPi" in method
    assert "unmapped_glyph_fonts" not in method


def test_ordinary_pdf_is_byte_identical_and_never_rewritten():
    pdf = _pdf({"F1": _PLAIN}, "BT /F1 12 Tf 72 700 Td (p ! x = 1 & y) Tj ET")
    fixed, report = repair_glyph_names(pdf)
    assert fixed is pdf  # the very same object: no copy, no rewrite
    assert not report
    text, method = extract_pdf(pdf)
    assert method == "pdftotext_default"
    assert _squash(text).replace(" ", "") == "p!x=1&y"


def test_font_that_already_has_to_unicode_is_left_alone():
    cmap = (
        "/CIDInit /ProcSet findresource begin 12 dict begin begincmap "
        "1 begincodespacerange <00> <FF> endcodespacerange "
        "1 beginbfchar <21> <0058> endbfchar endcmap end end"
    )
    # Font objects are 5 and 6; the CMap stream is object 7.
    pdf = _pdf(
        {"F1": _PLAIN, "F2": _pi("/H11005").replace(">> >>", ">> /ToUnicode 7 0 R >>")},
        "BT /F2 12 Tf 72 700 Td (!) Tj ET",
        extra=[f"<< /Length {len(cmap)} >>\nstream\n{cmap}\nendstream"],
    )
    fixed, report = repair_glyph_names(pdf)
    assert fixed is pdf and not report
    text, _ = extract_pdf(pdf)
    assert _squash(text) == "X"  # the font's own map wins

def test_unmapped_linotype_glyphs_are_reported_never_silent():
    # /H12345 is H-shaped but not in the verified table: reported, not guessed.
    pdf = _pdf({"F1": _PLAIN, "F2": _pi("/H12345")}, "BT /F2 12 Tf 72 700 Td (!!) Tj ET")
    fixed, report = repair_glyph_names(pdf)
    assert fixed is pdf  # nothing to map, nothing rewritten
    assert report.unmapped == [
        {"font": "ABCDEF+Universal-GreekwithMathPi", "glyph_names": ["H12345"], "char_count": 2}
    ]
    _, method = extract_pdf(pdf)
    assert "+unmapped_glyph_fonts:ABCDEF+Universal-GreekwithMathPi" in method


def test_table_rows_are_the_verified_set():
    # Pinned so an addition is a deliberate, raster-verified edit (see module docstring).
    assert LINOTYPE_PI_GLYPHS == {
        "H11005": "=", "H9251": "α", "H11003": "×", "H9257": "η",
        "H9267": "ρ", "H11002": "−", "H11021": "<", "H11022": ">",
        "H9273": "χ", "H11001": "+", "H11349": "≤", "H11350": "≥",
        "H11569": "∗", "H18546": "■",
    }


def test_unmapped_glyph_detail_reaches_the_fallback_record():
    from docpluck import telemetry
    pdf = _pdf({"F1": _PLAIN, "F2": _pi("/H12345")}, "BT /F2 12 Tf 72 700 Td (!!) Tj ET")
    telemetry._FALLBACK_DETAILS.pop("unmapped_glyph_font", None)
    extract_pdf(pdf)
    assert "ABCDEF+Universal-GreekwithMathPi:H12345:chars=2" in telemetry._FALLBACK_DETAILS["unmapped_glyph_font"]


def test_a_failed_repair_is_recorded_every_time_and_never_cached(monkeypatch):
    from docpluck import glyph_names, telemetry
    pdf = _pdf({"F1": _PLAIN, "F2": _pi(_NAMES)}, _CONTENT)
    glyph_names._CACHE.clear()
    monkeypatch.setattr(glyph_names, "_candidate_fonts", lambda r: (_ for _ in ()).throw(RuntimeError("x")))
    telemetry._FALLBACK_COUNTERS.pop("glyph_name_repair_exception", None)
    glyph_names.repair_glyph_names(pdf)
    glyph_names.repair_glyph_names(pdf)
    assert telemetry._FALLBACK_COUNTERS["glyph_name_repair_exception"] == 2
    assert not glyph_names._CACHE


def test_pypdf_trailer_size_warning_is_not_printed(caplog):
    import logging
    from docpluck import glyph_names
    glyph_names._CACHE.clear()
    rec = logging.LogRecord("pypdf._writer", logging.WARNING, __file__, 1,
                            "Object count %(a)d exceeds defined trailer size %(b)d", ({"a": 3, "b": 2},), None)
    assert all(f.filter(rec) is False for f in logging.getLogger("pypdf._writer").filters
               if isinstance(f, glyph_names._TrailerSizeFilter))
    assert any(isinstance(f, glyph_names._TrailerSizeFilter) for f in logging.getLogger("pypdf._writer").filters)
