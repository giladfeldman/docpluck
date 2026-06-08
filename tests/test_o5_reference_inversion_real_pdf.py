"""O5 reference reading-order inversion fix — real-PDF regression test (v2.4.80).

Background
==========
On some two-column papers whose final page stacks a full-width contributor
table (CRediT) ABOVE a two-column reference list, pdftotext serializes the page
columns out of order — it emits the RIGHT reference column before the LEFT
column that carries the ``References`` heading. The result: a block of reference
entries is stranded ABOVE the ``References`` heading in the extracted text, and
any consumer that scans for references *after* the heading silently misses them.

Reported by citationguard-iterate (2026-06-07, O5: "36 chen refs stranded before
the References header"). Root cause + fix are documented in
``docs/superpowers/handoffs/2026-06-07-text-extraction-defects-from-citationguard-iterate.md``
and ``docs/superpowers/specs/2026-06-07-ip_feldman-B4-R4-column-interleave-diagnosis.md``.

The fix (general, keyed on a STRUCTURAL SIGNATURE — reference-list entries
appearing before their own ``References`` heading on a page, never on paper
identity):
  - ``_detect_reference_inversion_pages`` flags such pages (cheap, text-only);
  - ``extract_page_text_columns`` re-extracts them left-column-then-right via a
    full-height GUTTER-STRIP midline detector that bypasses the y-row bilateral
    gate (so the banded contributor table doesn't block the prose columns);
  - the re-extraction is accepted ONLY under a word-preservation guard (the
    reorder must not drop or fabricate any substantial word — rules 0a / 0b).

This fixes chen_2021_jesp (page 19) and jamison_2020_jesp (page 9), the only two
of the 101-paper corpus that exhibit the signature.

Real-PDF (rule 0d) + structural-signature general fix (rule 16).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from docpluck.extract import extract_pdf
from docpluck.extract_columns import _detect_reference_inversion_pages
from docpluck.render import render_pdf_to_markdown

_CORPUS = Path(__file__).resolve().parents[2] / "PDFextractor" / "test-pdfs" / "apa"

# A reference-LIST entry at line start ("Surname, F. M.") — same shape the
# detector keys on. Used here to count entries before/after the heading.
_REF_ENTRY = re.compile(r"^[A-ZÀ-Þ][\w'’\-]+,\s+(?:[A-ZÀ-Þ]\.\s*)+")


def _ref_entries_split(md: str) -> tuple[int, int]:
    """(count of reference-entry lines before the References heading,
    count after it) in a rendered .md."""
    m = re.search(r"\n#*\s*References\s*\n", md)
    assert m is not None, "rendered .md has no References heading"
    head = m.start()
    before = sum(1 for ln in md[:head].splitlines() if _REF_ENTRY.match(ln))
    after = sum(1 for ln in md[head:].splitlines() if _REF_ENTRY.match(ln))
    return before, after


@pytest.mark.parametrize(
    "stem, expect_page",
    [("chen_2021_jesp", 19), ("jamison_2020_jesp", 9)],
)
def test_o5_inversion_detected_and_corrected(stem: str, expect_page: int):
    pdf = _CORPUS / f"{stem}.pdf"
    if not pdf.exists():
        pytest.skip(f"corpus fixture missing: {pdf}")
    b = pdf.read_bytes()

    text, method = extract_pdf(b)
    # The inversion-correction fired and tagged the corrected page.
    assert f"column_corrected:{expect_page}" in method or re.search(
        rf"column_corrected:[\d,]*\b{expect_page}\b", method
    ), f"{stem}: O5 correction did not fire on page {expect_page} (method={method!r})"

    # No reference-list entry is stranded before the References heading, and a
    # substantial reference list now follows it.
    md = render_pdf_to_markdown(b)
    before, after = _ref_entries_split(md)
    assert before == 0, (
        f"{stem}: {before} reference entries still stranded BEFORE the "
        f"References heading — O5 inversion not corrected."
    )
    assert after >= 20, (
        f"{stem}: only {after} reference entries after the heading — "
        f"the reference list looks truncated/lost (rule 0a)."
    )


@pytest.mark.parametrize("stem", ["chen_2021_jesp", "jamison_2020_jesp"])
def test_o5_correction_preserves_all_reference_text(stem: str):
    """The reorder must not LOSE text: a sample of reference surnames known to
    have been stranded must be present in the corrected output (rule 0a)."""
    pdf = _CORPUS / f"{stem}.pdf"
    if not pdf.exists():
        pytest.skip(f"corpus fixture missing: {pdf}")
    md = render_pdf_to_markdown(pdf.read_bytes())
    # Surnames that appear in these papers' reference lists (stable anchors).
    anchors = {
        "chen_2021_jesp": ["Aarts", "Benjamini", "Fischhoff", "Fritz", "Gelman", "Nosek"],
        "jamison_2020_jesp": ["Baron", "Bostyn", "Connolly"],
    }[stem]
    for name in anchors:
        assert name in md, f"{stem}: reference author {name!r} lost from output (rule 0a)"


def test_o5_detector_is_selective():
    """The detector must NOT fire on a normally-ordered reference paper
    (heading THEN entries). Guards against the reorder churning correct papers."""
    pdf = _CORPUS.parents[0] / "ama" / "jama_open_1.pdf"
    if not pdf.exists():
        pytest.skip(f"corpus fixture missing: {pdf}")
    b = pdf.read_bytes()
    text, _ = extract_pdf(b)
    ff = [0] + [i + 1 for i, ch in enumerate(text) if ch == "\f"]
    assert _detect_reference_inversion_pages(text, tuple(ff)) == (), (
        "inversion detector false-fired on a normally-ordered paper"
    )
