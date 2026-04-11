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

            if is_block:
                if parts and not parts[-1].endswith('\n'):
                    parts.append('\n')
            else:
                # Space before inline elements (prevents "ChanORCID" merging)
                if parts and not (parts[-1].endswith(' ') or parts[-1].endswith('\n')):
                    parts.append(' ')

            _walk(child, parts, NavigableString, Tag)

            if is_block:
                if parts and not parts[-1].endswith('\n'):
                    parts.append('\n')
            else:
                # Space after inline elements
                if parts and not (parts[-1].endswith(' ') or parts[-1].endswith('\n')):
                    parts.append(' ')


def extract_html(html_bytes: bytes) -> tuple[str, str]:
    """Extract text from HTML file bytes.

    Decodes as UTF-8 with error replacement (handles malformed encoding
    gracefully), then runs the block/inline-aware tree-walk.

    Args:
        html_bytes: Raw HTML file content as bytes.

    Returns:
        A tuple of (text, method) where:
          - text: Extracted plain text (see html_to_text for formatting details).
          - method: Always "beautifulsoup".

    Requires:
        beautifulsoup4 and lxml (install with `pip install docpluck[html]`).

    Example:
        with open("article.html", "rb") as f:
            text, method = extract_html(f.read())
    """
    html = html_bytes.decode('utf-8', errors='replace')
    text = html_to_text(html)
    return text, "beautifulsoup"
