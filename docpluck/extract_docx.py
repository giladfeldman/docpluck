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
- OMML equations (Office Math) are silently dropped. Papers with inline
  stats inside equation objects will lose those values. In practice this is
  rare in social science papers where stats are written as plain text.
- Tracked changes: only deleted paragraphs are handled minimally.
- Memory: peak usage is ~3-5x file size. Not a concern for single-file
  processing but worth noting for very large documents.

Requires the `docx` optional dependency:
  pip install docpluck[docx]
"""
import io

from .extract_html import html_to_text


def extract_docx(docx_bytes: bytes, *, sections: list[str] | None = None) -> tuple[str, str]:
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

    result = mammoth.convert_to_html(io.BytesIO(docx_bytes))
    html = result.value
    text = html_to_text(html)

    if sections is not None:
        from .sections import extract_sections
        doc = extract_sections(docx_bytes)
        return doc.text_for(*sections), "mammoth"

    return text, "mammoth"
