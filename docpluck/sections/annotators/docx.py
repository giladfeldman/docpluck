"""DOCX markup-aware annotator (Tier 1).

mammoth converts DOCX to HTML, mapping "Heading 1"–"Heading 6" paragraph
styles to <h1>–<h6>. We delegate to the HTML annotator after conversion.

When the DOCX uses ad-hoc bold instead of real Heading styles, mammoth
emits <p><strong>...</strong></p> and we get no headings — the partitioner
falls back to text-only annotation by yielding a single span. (Fallback
to text annotator for ad-hoc-bold DOCX is deferred — see TODO.)
"""

from __future__ import annotations

from ..blocks import BlockHint


def annotate_docx(docx_bytes: bytes) -> tuple[str, list[BlockHint]]:
    import io
    import mammoth  # type: ignore

    result = mammoth.convert_to_html(io.BytesIO(docx_bytes))
    html = result.value  # str

    from .html import annotate_html
    return annotate_html(html.encode("utf-8"))
