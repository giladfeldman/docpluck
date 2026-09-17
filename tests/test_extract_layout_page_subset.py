"""`extract_pdf_layout(pages=...)` — the page subset.

Why it exists: `extract_pdf` ran the full-document pdfplumber parse whenever its
cheap text-only detectors flagged ANY page for column correction, and then
corrected at most those pages. Measured 2026-09-17 on a 72-page RSOS paper with
23 flagged pages and no inversion pages — 25.3 s of pdfplumber, zero pages
changed, against 1.0 s for the pdftotext call it was correcting.

The subset is only safe if a populated page is INDISTINGUISHABLE from the same
page in a full extraction, and if a skipped page is visibly skipped rather than
quietly blank. Both are asserted here, on a real multi-page PDF, not on shape
alone.
"""

import io

import pytest


def _multipage_pdf(n_pages: int = 5) -> bytes:
    """A PDF with distinct text on every page, so a page mix-up is detectable."""
    pytest.importorskip("reportlab")
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import letter

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    for i in range(n_pages):
        c.setFont("Helvetica-Bold", 16)
        c.drawString(72, 720, f"Chapter {i}")
        c.setFont("Helvetica", 11)
        c.drawString(72, 690, f"Body text unique to page {i} zzz{i}")
        c.showPage()
    c.save()
    return buf.getvalue()


def test_full_extraction_still_reports_every_page_populated():
    """The default is unchanged, and says so rather than leaving it implicit."""
    from docpluck.extract_layout import extract_pdf_layout

    full = extract_pdf_layout(_multipage_pdf())
    assert full.populated_pages is None
    assert len(full.pages) == 5
    assert all(p.words for p in full.pages)


def test_requested_pages_are_byte_identical_to_the_full_extraction():
    from docpluck.extract_layout import extract_pdf_layout

    data = _multipage_pdf()
    full = extract_pdf_layout(data)
    subset = extract_pdf_layout(data, pages=[1, 3])

    assert subset.populated_pages == (1, 3)
    assert len(subset.pages) == len(full.pages), (
        "page INDICES must keep meaning what they meant — callers index by "
        "absolute page number"
    )
    for i in (1, 3):
        assert subset.pages[i].words == full.pages[i].words
        assert subset.pages[i].chars == full.pages[i].chars
        assert subset.pages[i].spans == full.pages[i].spans
        assert subset.pages[i].width == full.pages[i].width
        assert subset.pages[i].height == full.pages[i].height


def test_unrequested_pages_are_empty_but_keep_their_geometry():
    from docpluck.extract_layout import extract_pdf_layout

    data = _multipage_pdf()
    full = extract_pdf_layout(data)
    subset = extract_pdf_layout(data, pages=[1, 3])

    for i in (0, 2, 4):
        assert subset.pages[i].words == ()
        assert subset.pages[i].chars == ()
        assert subset.pages[i].spans == ()
        # Width/height come from the page dict, not the content stream, so they
        # are free — and a caller that needs them (every column detector does)
        # must not have to re-open the PDF for them.
        assert subset.pages[i].width == full.pages[i].width
        assert subset.pages[i].height == full.pages[i].height
        assert f"zzz{i}" not in subset.raw_text


def test_out_of_range_indices_are_ignored_not_raised():
    """`extract_pdf` derives page numbers from pdftotext form feeds, which can
    exceed pdfplumber's page count by one on a trailing form feed. Raising there
    would turn a cosmetic off-by-one into a failed extraction."""
    from docpluck.extract_layout import extract_pdf_layout

    doc = extract_pdf_layout(_multipage_pdf(), pages=[0, 99, -3])
    assert doc.populated_pages == (0,)
    assert doc.pages[0].words


def test_empty_subset_populates_nothing():
    """A green from an empty input would be the worst outcome here: it must be
    possible to tell "asked for no pages" from "asked for all of them"."""
    from docpluck.extract_layout import extract_pdf_layout

    doc = extract_pdf_layout(_multipage_pdf(), pages=[])
    assert doc.populated_pages == ()
    assert len(doc.pages) == 5
    assert all(p.words == () for p in doc.pages)


def test_extract_pdf_asks_for_only_the_flagged_pages(monkeypatch):
    """The saving has to reach `extract_pdf`, not merely exist in the library.

    A capability invoked by nothing is indistinguishable from one that was never
    built, so this asserts the CALL, by intercepting it.

    The interleave detector is FORCED rather than coaxed. A synthetic
    single-column PDF flags no pages, so the layout branch never runs and a test
    that merely watched for a wrong call would pass while observing nothing —
    verified: the spy recorded `[]`. Pinning the detector's answer makes the
    branch run every time, and the assertion is then about the only thing this
    change touched: WHICH pages the layout pass is asked for.
    """
    import docpluck.extract_layout as layout_mod
    import docpluck.normalize as normalize_mod
    from docpluck.extract import extract_pdf

    FLAGGED = [2, 4]          # 1-indexed, as the detector reports them
    monkeypatch.setattr(
        normalize_mod, "_detect_column_interleave_pages",
        lambda text, offsets: FLAGGED,
    )

    calls: list = []
    real = layout_mod.extract_pdf_layout

    def spy(pdf_bytes, *, pages=None):
        calls.append(pages)
        return real(pdf_bytes, pages=pages)

    monkeypatch.setattr(layout_mod, "extract_pdf_layout", spy)
    text, method = extract_pdf(_multipage_pdf())

    assert not text.startswith("ERROR:"), text[:200]
    assert "column_correction_failed" not in method, method
    assert calls, "the layout branch did not run — this test would be vacuous"
    for pages in calls:
        assert pages is not None, (
            "extract_pdf must never request a full-document layout parse for "
            "column correction — it only ever splices the flagged pages"
        )
        # 0-based, and exactly the flagged set: not a page more.
        assert sorted(pages) == [p - 1 for p in FLAGGED], pages


# ── The subset must not escape the one path that can use it ────────────────


def test_a_subset_layout_is_refused_by_the_full_document_consumers():
    """A page-subset doc reaching table extraction would be silent AND plausible.

    `extract_pdf_structured` and `render_pdf_to_markdown` both accept a
    precomputed `_layout_doc` and both sweep every page with it. Handed a subset,
    they would report "no table on page 40" when page 40 was never read — a wrong
    answer with no error, about a real document. So it is refused at the boundary.
    """
    import pytest as _pytest
    from docpluck.extract_layout import (
        PartialLayoutError,
        extract_pdf_layout,
        require_full_layout,
    )

    data = _multipage_pdf()
    subset = extract_pdf_layout(data, pages=[1])
    full = extract_pdf_layout(data)

    with _pytest.raises(PartialLayoutError) as exc:
        require_full_layout(subset, who="extract_pdf_structured")
    # The message has to name the caller and the coverage, or it cannot be acted on.
    assert "extract_pdf_structured" in str(exc.value)
    assert "1 of 5 pages" in str(exc.value)

    # Two-sided: the guard must PASS the things it is meant to pass, or it is
    # just an outage. A full doc and None both go through untouched.
    assert require_full_layout(full, who="x") is full
    assert require_full_layout(None, who="x") is None


def test_the_guard_is_actually_wired_into_both_consumers():
    """A guard nothing calls is indistinguishable from no guard."""
    import inspect
    from docpluck import extract_structured, render

    for mod in (extract_structured, render):
        src = inspect.getsource(mod)
        assert "require_full_layout(" in src, (
            f"{mod.__name__} accepts _layout_doc but does not check it"
        )
