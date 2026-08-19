"""DOCX markup-aware annotator (Tier 1).

mammoth converts DOCX to HTML, mapping "Heading 1"–"Heading 6" paragraph
styles to <h1>–<h6>. We delegate to the HTML annotator after conversion.

When the DOCX uses ad-hoc bold instead of real Heading styles, mammoth
emits <p><strong>...</strong></p> and we get no headings — the partitioner
falls back to text-only annotation by yielding a single span. (Fallback
to text annotator for ad-hoc-bold DOCX is deferred — see TODO.)
"""

from __future__ import annotations

from ...telemetry import record_fallback
from ..blocks import BlockHint


def annotate_docx(docx_bytes: bytes) -> tuple[str, list[BlockHint]]:
    import io
    import mammoth  # type: ignore

    # THE OMML FIX HAS TO RUN HERE TOO — this path bypassed it entirely.
    #
    # v2.4.131 fixed mammoth's silent deletion of equations in `extract_docx`,
    # so `ηp2 = .361` stopped being delivered as `= .361`. But `extract_sections`
    # does NOT go through `extract_docx`: `sections/__init__.py` calls this
    # annotator with the raw bytes, and this function called mammoth directly.
    # **So the public `extract_sections(docx)` path was still deleting the name
    # of every statistic, one release after the defect was declared fixed** —
    # and MetaESCI runs an editable install of this tree, so it was live for it.
    # Found 2026-08-15 by an independent review (Fable 5) that asked which
    # callers reach mammoth, rather than which callers reach the fix.
    #
    # This is "a capability nothing invokes is not shipped" in its subtler form:
    # the capability IS invoked, just not on every path that needs it. The
    # four-checks rule's second item — *every production path is wired, not just
    # the one you were looking at* — is exactly this case.
    from ...extract_docx import _inline_omml_runs

    result = mammoth.convert_to_html(io.BytesIO(_inline_omml_runs(docx_bytes)))
    html = result.value  # str

    # mammoth NAMES every element it drops ("An unrecognised element was
    # ignored: m:oMath"). Those messages were discarded here and in
    # `extract_docx`, which is why the OMML deletion went unnoticed for years —
    # the library was announcing it on every affected file the whole time.
    # Surfaced as a module-level record so a caller can see what was lost.
    global LAST_CONVERSION_MESSAGES
    LAST_CONVERSION_MESSAGES = [str(m) for m in (result.messages or ())]
    # ...and a module global is not a reader either. The fix for "we discard the
    # library's diagnostic channel" captured the channel into a variable that
    # nothing — not even its own test — ever read (register H3d), which is the
    # same defect one step further along. Recording it puts it in the same place
    # every other silent substitution goes, so it reaches a consumer through
    # `NormalizationReport.fallbacks` / `StructuredResult["fallbacks"]`.
    for _msg in LAST_CONVERSION_MESSAGES:
        record_fallback("docx_mammoth_conversion_message", detail=_msg[:80])

    from .html import annotate_html
    return annotate_html(html.encode("utf-8"))


# What mammoth reported about the most recent conversion on this path. Read it
# rather than guessing what the converter silently dropped.
LAST_CONVERSION_MESSAGES: list[str] = []
