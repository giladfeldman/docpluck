"""HTML markup-aware heading annotator (Tier 1).

Uses beautifulsoup4 to walk the DOM, emitting BlockHints for <h1>-<h6>
elements with `heading_source="markup"` and a `heading_strength` derived
from heading depth. Body text content (the surrounding string used as the
`text` argument to the partitioner) is reconstructed by concatenating
extracted text in document order with `\\n\\n` separators between blocks.
"""

from __future__ import annotations

from ..blocks import BlockHint


def annotate_html(html_bytes: bytes) -> tuple[str, list[BlockHint]]:
    """Return (reconstructed_text, hints).

    The reconstructed text is what the sectioner partitions over. Hint
    char_start/char_end offsets refer into this text.
    """
    from bs4 import BeautifulSoup  # type: ignore

    soup = BeautifulSoup(html_bytes, "html.parser")

    parts: list[str] = []
    hints: list[BlockHint] = []
    cursor = 0

    HEADING_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6"}
    BLOCK_TAGS = HEADING_TAGS | {"p", "li", "div", "section", "article",
                                  "blockquote", "pre"}
    # Containers that hold block-level children but are not themselves
    # walked as blocks. Their text would otherwise be absorbed twice.
    CONTAINER_TAGS = BLOCK_TAGS | {"ul", "ol", "dl", "dt",
                                    "table", "tbody", "thead", "tfoot",
                                    "tr", "th", "td", "caption"}

    body = soup.body or soup

    for el in body.descendants:
        name = getattr(el, "name", None)
        if name not in BLOCK_TAGS:
            continue
        # Get only this element's text WITHOUT descending into block children.
        # We do that by collecting only text-node children + inline-only descendants.
        text_chunks: list[str] = []
        for child in el.children:
            child_name = getattr(child, "name", None)
            if child_name in CONTAINER_TAGS:
                # Block child handled separately when iteration reaches it.
                continue
            child_text = child.get_text() if child_name else str(child)
            if child_text:
                text_chunks.append(child_text)
        block_text = " ".join(t.strip() for t in text_chunks if t.strip())
        if not block_text:
            continue

        sep = "\n\n" if parts else ""
        block_start = cursor + len(sep)
        block_end = block_start + len(block_text)
        parts.append(sep + block_text)
        cursor = block_end

        if name in HEADING_TAGS:
            depth = int(name[1])
            strength = "strong" if depth <= 3 else "weak"
            hints.append(BlockHint(
                text=block_text,
                char_start=block_start,
                char_end=block_end,
                page=None,
                is_heading_candidate=True,
                heading_strength=strength,
                heading_source="markup",
            ))

    return "".join(parts), hints
