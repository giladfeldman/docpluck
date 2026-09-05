"""
docpluck.extract_docx_structured — text + structured tables from a DOCX.

The DOCX counterpart of :func:`docpluck.extract_pdf_structured`, returning the
**same** :class:`StructuredResult`, so a consumer reading `result["tables"]` and
`flatten_tables_for_paper(result["tables"])` needs no second code path and no
field is renamed. Purely additive: nothing on the PDF path changes.

WHAT THIS CLOSES. `extract_pdf_structured` is PDF-only, so `tables[]` and
`flattened_rows[]` came back empty for every DOCX, and any downstream tool that
verifies statistics from table rows received nothing at all for that entire
input format -- while the DOCX had stated its grid exactly, in `w:tbl`. The
numbers were in the file, fully structured, and docpluck was discarding them.

Engine choice is measured, not inherited: `docs/BENCHMARKS_docx_engines_2026-09.md`.
"""

from __future__ import annotations

from .extract_docx import extract_docx
from .extract_structured import TABLE_EXTRACTION_VERSION, StructuredResult
from .figures import Figure
from .tables import Table
from .tables.docx_tables import extract_tables_docx
from .telemetry import fallback_scope


def extract_docx_structured(
    docx_bytes: bytes,
    *,
    max_input_bytes: int | None = None,
) -> StructuredResult:
    """Extract text + structured tables from DOCX bytes.

    Args:
        docx_bytes: Raw DOCX file content.
        max_input_bytes: Optional hard cap on input size; ``ValueError`` above it.

    Returns:
        A :class:`StructuredResult` -- the identical shape
        :func:`extract_pdf_structured` returns.

        ``page_count`` is **0** and ``figures`` is **empty**, and both are
        deliberate rather than unimplemented-and-hidden:

        * **page_count 0** -- OOXML has no page model. Pagination is computed by
          whichever renderer opens the file, with that machine's fonts and
          printer metrics, so two openings of one file can disagree. Any number
          docpluck put here would be a value it cannot know, and a consumer
          would have no way to tell it from a measured one.
        * **figures []** -- DOCX figure extraction is NOT IMPLEMENTED. Stated
          here, in the docstring a caller reads, rather than left to look like a
          document that happens to contain no figures. Adding it means detecting
          `Figure N` captions around `<img>` elements; it is not a side effect of
          the table work and is not smuggled in as a half-feature.

        Per-table, the fields with no DOCX meaning are `None` or zero **with the
        reason recorded on the table itself** (`cell_geometry`); see
        :func:`docpluck.tables.docx_tables.extract_tables_docx`.

    Raises:
        ValueError: malformed DOCX, or input above ``max_input_bytes``.
        ImportError: mammoth is not installed (``pip install docpluck[docx]``).

    Example:
        with open("paper.docx", "rb") as f:
            result = extract_docx_structured(f.read())
        rows = flatten_tables_for_paper(result["tables"])
    """
    # One telemetry scope across the whole extraction, including its early
    # returns -- the same wrapper shape as `extract_pdf_structured`, and for the
    # same reason: a `return` added later cannot forget to attach `fallbacks`.
    with fallback_scope() as fb:
        result = _extract_docx_structured(
            docx_bytes, max_input_bytes=max_input_bytes
        )
    result["fallbacks"] = dict(fb.counters)
    result["fallback_details"] = fb.details
    return result


def _extract_docx_structured(
    docx_bytes: bytes,
    *,
    max_input_bytes: int | None = None,
) -> StructuredResult:
    text, method = extract_docx(docx_bytes, max_input_bytes=max_input_bytes)

    tables: list[Table]
    try:
        tables, table_method = extract_tables_docx(docx_bytes)
        method_pieces = [method, f"tables:{table_method}"]
    except Exception as exc:
        # Degrade the way the PDF path degrades when Camelot fails: never lose a
        # working text extraction because the table pass raised. But SAY SO --
        # an empty `tables` with no explanation is indistinguishable from a
        # document that has none, which is the false green this project keeps
        # finding.
        from .telemetry import record_fallback

        record_fallback("docx_table_extraction_exception", detail=type(exc).__name__)
        tables = []
        method_pieces = [method, f"tables_failed:{type(exc).__name__}"]

    figures: list[Figure] = []

    return {
        "text": text,
        "method": "+".join(method_pieces),
        # Not a page count of zero pages -- a statement that DOCX has no pages.
        # See the docstring.
        "page_count": 0,
        "tables": tables,
        "figures": figures,
        "table_extraction_version": TABLE_EXTRACTION_VERSION,
        # Overwritten by the wrapper above; present here so every return path of
        # this function already carries the declared keys.
        "fallbacks": {},
        "fallback_details": {},
    }


__all__ = ["extract_docx_structured"]
