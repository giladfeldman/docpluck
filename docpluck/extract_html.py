"""
HTML Text Extraction
=====================
Tree-walk HTML parser that preserves block/inline structure for clean text extraction.

Ported from Scimeto's extractTextFromHtmlString() which has been in production
since Dec 2025. Battle-tested on thousands of academic articles from PLoS, MDPI,
Springer, Elsevier, and Wiley.

Key design decisions:
- Block elements get newlines before/after (paragraphs, headings, list items, table cells)
- Inline elements get spaces before/after to prevent word merging
- script/style/meta/etc stripped before walk
- Uses lxml parser (fastest, good error recovery for machine-generated publisher HTML)
- Custom tree-walk (not BeautifulSoup's get_text) because get_text cannot distinguish
  block from inline elements — maintainer confirmed this will not be implemented
  (see https://bugs.launchpad.net/bugs/1768330)

The inline spacing is critical: without it, "<a>Chan</a><a>ORCID</a>" becomes
"ChanORCID" instead of "Chan ORCID". This was a real bug in Scimeto that went
undetected for weeks before being fixed.

Requires the `html` optional dependency:
  pip install docpluck[html]
"""
import re
from typing import Any


BLOCK_ELEMENTS = frozenset({
    'p', 'div', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'li', 'tr', 'td', 'th',
    'header', 'footer', 'section', 'article', 'blockquote', 'address',
    'dl', 'dt', 'dd', 'fieldset', 'legend', 'table', 'pre', 'hr', 'main', 'nav', 'aside'
})

IGNORED_TAGS = frozenset({
    'script', 'style', 'meta', 'link', 'head', 'noscript', 'svg', 'object', 'embed', 'iframe'
})

# Inline elements that wrap a run with ZERO visual gap to its neighbours, so a
# space around them would invent a word boundary the document does not have.
#
# The generic inline rule below pads every inline element with a space. That
# exists for a real bug — two adjacent `<a>` tags merging into `ChanORCID` — but
# it was applied to the whole inline class, and a superscript is glued to its
# base character:
#
#     '<i>&#951;</i><sup>2</sup><sub>p</sub>'  ->  'η 2 p'  ->  'eta2 p'
#
# `eta2 p` matches nothing downstream, where `eta2p` is what every consumer
# looks for. This is the SAME defect the v2.4.128 subscript-letter map fixed,
# arriving by a different door: that map handles a source carrying genuine
# Unicode subscript CODEPOINTS, and Word's native superscript/subscript
# FORMATTING — overwhelmingly the more common way the token is authored —
# never produces those codepoints at all. DOCX is affected too, because mammoth
# converts it to HTML before this runs.
#
# Named as a CLASS rather than as the two tags in front of us: `<a>` is a
# separate referent and keeps its space; a styling wrapper never is.
#
# `span` is deliberately EXCLUDED. It is the one inline tag with no consistent
# typographic meaning — publishers use it both as a pure styling wrapper and as
# a structural separator. The `ChanORCID` bug this padding was written for is
# itself a span case (`<span>Chan</span><span>ORCID</span>` in an author list),
# so gluing spans would reintroduce exactly the defect the rule exists to
# prevent. A pre-existing regression test caught this; it is pinned below.
GLUED_INLINE_ELEMENTS = frozenset({
    'sup', 'sub',                     # typographically glued to the base char
    'i', 'b', 'em', 'strong',         # emphasis: no visual gap to neighbours
    'u', 's', 'small', 'mark', 'var', 'abbr',
})


def html_to_text(html: str) -> str:
    """Extract text from an HTML string preserving block/inline structure.

    Args:
        html: HTML content as a string.

    Returns:
        Cleaned plain text with:
          - Newlines around block elements (paragraphs, headings, etc.)
          - Spaces around inline elements (prevents merged words)
          - Normalized whitespace (Unicode spaces → ASCII space, collapsed)
          - Maximum two consecutive newlines (no triple blanks)
          - Trimmed leading/trailing whitespace

    Example:
        >>> html_to_text("<p>Hello <a>world</a>!</p><p>Line 2</p>")
        'Hello world !\\nLine 2'
    """
    # Lazy import so the core library works without beautifulsoup4/lxml installed
    from bs4 import BeautifulSoup, NavigableString, Tag

    soup = BeautifulSoup(html, 'lxml')

    # Remove non-content elements before walking
    for tag in soup.find_all(list(IGNORED_TAGS)):
        tag.decompose()

    # Walk the tree, collecting text with block/inline-aware separators
    parts: list[str] = []
    _walk(soup, parts, NavigableString, Tag)
    text = ''.join(parts)

    # Whitespace normalization (matches Scimeto's 7-step cleanup)
    text = re.sub(r'\r\n', '\n', text)
    text = re.sub(r'\r', '\n', text)
    text = re.sub(r'[\v\f\x85\u2028\u2029]', '\n', text)
    text = re.sub(r'[\u00a0\u1680\u180e\u2000-\u200a\u202f\u205f\u3000\ufeff]', ' ', text)
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r' +\n', '\n', text)
    text = re.sub(r'\n +', '\n', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def _walk(element: Any, parts: list[str], NavigableString: type, Tag: type) -> None:
    """Recursive tree-walk matching Scimeto's walk() function.

    For each child of `element`:
      - NavigableString: append text directly
      - Tag with block tag: ensure \\n before, recurse, ensure \\n after
      - Tag with inline tag: ensure space before, recurse, ensure space after
      - <br> tag: append \\n
      - Tag in IGNORED_TAGS: already decomposed, won't appear
    """
    for child in element.children:
        if isinstance(child, NavigableString):
            parts.append(str(child))
        elif isinstance(child, Tag):
            tag_name = child.name.lower() if child.name else ''

            if tag_name == 'br':
                parts.append('\n')
                continue

            is_block = tag_name in BLOCK_ELEMENTS
            # A GLUED wrapper (sup/sub/i/b/...) gets NO padding: it wraps a run
            # with zero visual gap to its neighbours, so a space here would
            # invent a word boundary the document does not have. See
            # GLUED_INLINE_ELEMENTS for why this is a class, not two tags.
            is_glued = tag_name in GLUED_INLINE_ELEMENTS

            if is_block:
                if parts and not parts[-1].endswith('\n'):
                    parts.append('\n')
            elif not is_glued:
                # Space before inline elements (prevents "ChanORCID" merging)
                if parts and not (parts[-1].endswith(' ') or parts[-1].endswith('\n')):
                    parts.append(' ')

            _walk(child, parts, NavigableString, Tag)

            if is_block:
                if parts and not parts[-1].endswith('\n'):
                    parts.append('\n')
            elif not is_glued:
                # Space after inline elements
                if parts and not (parts[-1].endswith(' ') or parts[-1].endswith('\n')):
                    parts.append(' ')


def extract_html(
    html_bytes: bytes,
    *,
    sections: list[str] | None = None,
    max_input_bytes: int | None = None,
) -> tuple[str, str]:
    """Extract text from HTML file bytes.

    Decodes as UTF-8 with error replacement (handles malformed encoding
    gracefully), then runs the block/inline-aware tree-walk.

    Args:
        html_bytes: Raw HTML file content as bytes.
        sections: Optional list of section labels (e.g. ``["abstract",
            "methods"]``) to filter the output. When provided, ``extract_sections``
            is called and only the requested sections are returned concatenated
            in document order. Pass ``None`` (default) to return the full text.
        max_input_bytes: Optional hard cap for input size. When set and
            ``len(html_bytes)`` exceeds it, a ValueError is raised.

    Returns:
        A tuple of (text, method) where:
          - text: Extracted plain text (see html_to_text for formatting details).
            When ``sections`` is not None, only text from the requested
            sections is included.
          - method: Always "beautifulsoup".

    Requires:
        beautifulsoup4 and lxml (install with `pip install docpluck[html]`).

    Example:
        with open("article.html", "rb") as f:
            text, method = extract_html(f.read())

        # Filter to abstract only:
        with open("article.html", "rb") as f:
            text, method = extract_html(f.read(), sections=["abstract"])
    """
    if max_input_bytes is not None and len(html_bytes) > max_input_bytes:
        raise ValueError(
            f"HTML input exceeds max_input_bytes: {len(html_bytes)} > {max_input_bytes}"
        )

    html = html_bytes.decode('utf-8', errors='replace')
    text = html_to_text(html)

    if sections is not None:
        from .sections import extract_sections
        doc = extract_sections(html_bytes)
        return doc.text_for(*sections), "beautifulsoup"

    return text, "beautifulsoup"
