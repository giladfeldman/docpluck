"""``page_numbers_stripped`` is an occurrence count; ``headers_removed`` is never fabricated.

Closes the remainder of the 2026-08-22 tag blocker (fleet ask
``2026-08-22T114401Z-docpluck-changes-made-telemetry-is-false``). Its CORRECTION
established that ``changes_made`` values were CHARACTER DELTAS published under
occurrence-shaped names — the multiplier was the DIGIT COUNT (two-digit page
numbers reported 2.00x, three-digit 3.00x) — and that ``headers_removed`` fired
on documents containing zero headers because the S9 ``_track`` call reused the
``before`` snapshot captured for P0, republishing P0's page-number characters
under a second key. v1.9.63 fixed the sign/dash/quote family with explicit
``count=`` (tests/test_changes_made_is_an_exact_count.py); these two keys were
the ask's original fixtures and were still deltas.

Written RED against eb3e84d (both keys wrong on every fixture below), then the
call sites were fixed. Fixtures vary number count and digit width
INDEPENDENTLY, because the ask's own defect was mistaking digit-count agreement
(two sessions both using two-digit fixtures) for corroboration.
"""

import pytest

from docpluck.normalize import NormalizationLevel, normalize_text


def _doc_with_page_numbers(values, lines_per_page=24):
    """Real-shaped pagination: one number at each page end, pages split by \\f."""
    pages = []
    for i, pn in enumerate(values):
        body = "\n".join(
            f"Prose line {i}-{j} long enough to read as body text, not furniture."
            for j in range(lines_per_page)
        )
        pages.append(f"{body}\n{pn}")
    return "\n\f\n".join(pages)


def _changes_made(doc):
    result = normalize_text(doc, NormalizationLevel.academic)
    report = result[1] if isinstance(result, tuple) else result.report
    return report.changes_made


@pytest.mark.parametrize(
    "values",
    [
        pytest.param([10, 11, 12], id="3-numbers-2-digits"),
        pytest.param([10, 11, 12, 13], id="4-numbers-2-digits"),
        pytest.param([101, 102, 103], id="3-numbers-3-digits"),
        pytest.param([101, 102, 103, 104], id="4-numbers-3-digits"),
    ],
)
def test_page_numbers_stripped_counts_numbers_not_characters(values):
    """The count equals the number of page numbers, whatever their width.

    Old behaviour: 4 two-digit numbers reported 8, 4 three-digit reported 12.
    """
    cm = _changes_made(_doc_with_page_numbers(values))
    assert cm.get("page_numbers_stripped") == len(values), (
        f"expected exactly {len(values)} (one per page number), got "
        f"{cm.get('page_numbers_stripped')!r} — a character delta, not a count"
    )


def test_headers_removed_never_fires_on_a_document_with_no_headers():
    """The ask's founding fixture: page numbers only, zero headers.

    Old behaviour: ``headers_removed: 8`` — P0's page-number characters
    republished under a second key via a stale ``before`` snapshot.
    """
    cm = _changes_made(_doc_with_page_numbers([10, 11, 12, 13]))
    assert "headers_removed" not in cm, (
        f"headers_removed={cm['headers_removed']!r} reported for a document "
        "containing zero headers"
    )


def test_4digit_sequential_run_is_counted_as_page_numbers_not_headers():
    """Pattern B (continuous pagination, e.g. PSPB 1228..) blanks page-number
    lines; its telemetry belongs under ``page_numbers_stripped``, exactly
    counted — not under ``headers_removed``, which that code never touched.
    """
    doc = _doc_with_page_numbers([1228, 1229, 1230, 1231])
    cm = _changes_made(doc)
    assert "headers_removed" not in cm, (
        "4-digit page-number blanking reported itself as header removal"
    )
    assert cm.get("page_numbers_stripped") == 4, (
        f"expected 4 blanked page-number lines, got "
        f"{cm.get('page_numbers_stripped')!r}"
    )


def test_the_telemetry_fix_does_not_touch_the_text():
    """Counting is observation: the normalized text is what it always was —
    page numbers gone, every prose line intact."""
    doc = _doc_with_page_numbers([10, 11, 12, 13])
    result = normalize_text(doc, NormalizationLevel.academic)
    text = result[0] if isinstance(result, tuple) else result.text
    for pn in (10, 11, 12, 13):
        assert f"\n{pn}\n" not in f"\n{text}\n"
    assert text.count("Prose line") == 4 * 24


def test_repeated_lines_stripped_counts_lines_not_characters():
    """Consult round CF3917B2B065 (Grok + Fable, 2026-09-03): P0q published
    ``repeated_lines_stripped`` as a character delta while ``_removed_per_line``
    held the exact figure at the call site — Fable measured 1287 reported for 39
    removed lines. Same class as the two keys fixed in 9291fc3, one step above.
    """
    header = "Journal of Measured Examples and Repeated Furniture Lines"
    pages = []
    for i in range(6):
        body = "\n".join(
            f"Body sentence {i}-{j} long enough to read as prose, not furniture."
            for j in range(22)
        )
        pages.append(f"{header}\n{body}")
    doc = "\n\f\n".join(pages)
    cm = _changes_made(doc)
    assert cm.get("repeated_lines_stripped") == 5, (
        f"expected 5 (six copies, first kept), got "
        f"{cm.get('repeated_lines_stripped')!r} — a character delta, not a count"
    )
