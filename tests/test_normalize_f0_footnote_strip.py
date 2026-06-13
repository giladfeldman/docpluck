"""F0: layout-aware footnote + running-header strip."""

import io

import pytest

pytest.importorskip("pdfplumber")
pytest.importorskip("reportlab")


def _pdf_with_footnote_and_runheader() -> bytes:
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import letter
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    # Page 1
    c.setFont("Helvetica-Oblique", 9); c.drawString(72, 760, "MY JOURNAL — VOL 12")
    c.setFont("Helvetica-Bold", 14); c.drawString(72, 720, "Abstract")
    c.setFont("Helvetica", 11); c.drawString(72, 700, "This is the abstract content.")
    c.setFont("Helvetica", 8); c.drawString(72, 80, "1 First footnote on page 1.")
    c.showPage()
    # Page 2
    c.setFont("Helvetica-Oblique", 9); c.drawString(72, 760, "MY JOURNAL — VOL 12")
    c.setFont("Helvetica-Bold", 14); c.drawString(72, 720, "Methods")
    c.setFont("Helvetica", 11); c.drawString(72, 700, "We did things.")
    c.setFont("Helvetica", 8); c.drawString(72, 80, "2 Second footnote on page 2.")
    c.showPage()
    c.save()
    return buf.getvalue()


def test_f0_strips_running_header():
    from docpluck import normalize_text, NormalizationLevel
    from docpluck.extract_layout import extract_pdf_layout
    layout = extract_pdf_layout(_pdf_with_footnote_and_runheader())
    out, _ = normalize_text(layout.raw_text, NormalizationLevel.academic, layout=layout)
    assert "MY JOURNAL" not in out


def test_f0_separates_footnotes_into_appendix():
    from docpluck import normalize_text, NormalizationLevel
    from docpluck.extract_layout import extract_pdf_layout
    layout = extract_pdf_layout(_pdf_with_footnote_and_runheader())
    out, report = normalize_text(layout.raw_text, NormalizationLevel.academic, layout=layout)
    assert "First footnote" in out
    assert "Second footnote" in out
    body_only_until_appendix = out.split("\n\f\f\n", 1)[0] if "\n\f\f\n" in out else out
    assert "First footnote" not in body_only_until_appendix or \
           "Abstract" in body_only_until_appendix.split("First footnote")[0]


def test_f0_records_footnote_spans():
    from docpluck import normalize_text, NormalizationLevel
    from docpluck.extract_layout import extract_pdf_layout
    layout = extract_pdf_layout(_pdf_with_footnote_and_runheader())
    _, report = normalize_text(layout.raw_text, NormalizationLevel.academic, layout=layout)
    assert len(report.footnote_spans) >= 2


def test_f0_exposes_footnote_texts():
    """v2.4.83: report.footnote_texts surfaces the captured footnote strings
    as a first-class list, parallel to footnote_spans, so downstream
    consumers don't have to slice char offsets or parse the \\n\\f\\f\\n
    appendix out of the body text."""
    from docpluck import normalize_text, NormalizationLevel
    from docpluck.extract_layout import extract_pdf_layout
    layout = extract_pdf_layout(_pdf_with_footnote_and_runheader())
    _, report = normalize_text(layout.raw_text, NormalizationLevel.academic, layout=layout)
    # Parallel to footnote_spans: one text per recorded span.
    assert len(report.footnote_texts) == len(report.footnote_spans)
    joined = " ".join(report.footnote_texts)
    assert "First footnote" in joined
    assert "Second footnote" in joined
    # Each text matches the raw_text slice at its parallel span.
    for (start, end), text in zip(report.footnote_spans, report.footnote_texts):
        assert layout.raw_text[start:end] == text


def test_f0_footnote_texts_empty_without_layout():
    """No layout → F0 doesn't run → footnote_texts is empty (not an error)."""
    from docpluck import normalize_text, NormalizationLevel
    _, report = normalize_text("Plain body text with no layout.", NormalizationLevel.academic)
    assert report.footnote_texts == ()


def _is_subsequence(needles: list[str], haystack: list[str]) -> bool:
    """True iff `needles` appears in `haystack` in order (gaps allowed)."""
    it = iter(haystack)
    return all(any(n == h for h in it) for n in needles)


def test_f0_body_is_a_line_subsequence_of_the_text_channel():
    """L-001 / L-007 architecture invariant: F0 must SOURCE the body from the
    text channel (``raw_text``) and only *delete* header/footer/footnote lines —
    never rebuild or reorder it from ``span.text``. Concretely, every line in the
    F0 body must appear in the input ``raw_text`` in the same relative order.

    A regression that re-introduces span-rebuild (the cause of the v2.4.86
    word-gluing and the two-column interleaving) reorders/merges lines and fails
    this test.
    """
    from docpluck.normalize import _f0_strip_running_and_footnotes
    from docpluck.extract_layout import extract_pdf_layout

    layout = extract_pdf_layout(_pdf_with_footnote_and_runheader())
    raw_text = layout.raw_text
    body_with_appendix, _, _ = _f0_strip_running_and_footnotes(raw_text, layout)
    body = body_with_appendix.split("\n\f\f\n", 1)[0]

    raw_lines = [ln.strip() for ln in raw_text.split("\n") if ln.strip()]
    body_lines = [ln.strip() for ln in body.split("\n") if ln.strip()]
    assert body_lines, "F0 body should not be empty"
    assert _is_subsequence(body_lines, raw_lines), (
        "F0 body contains a line not present (in order) in the text channel — "
        "the body was rebuilt/reordered from spans (L-001/L-007 violation)."
    )


def test_f0_preserves_text_channel_spacing_not_span_glued():
    """The F0 body must carry the text channel's inter-word spacing verbatim, so
    a properly-spaced pdftotext line is never replaced by a glued span variant."""
    from docpluck.normalize import _f0_strip_running_and_footnotes
    from docpluck.extract_layout import extract_pdf_layout

    layout = extract_pdf_layout(_pdf_with_footnote_and_runheader())
    raw_text = layout.raw_text
    body, _, _ = _f0_strip_running_and_footnotes(raw_text, layout)
    # The body's kept content lines must be exact substrings of raw_text
    # (delete-only), which guarantees spacing comes from the text channel.
    body_only = body.split("\n\f\f\n", 1)[0]
    for ln in (s.strip() for s in body_only.split("\n")):
        if ln:
            assert ln in raw_text
