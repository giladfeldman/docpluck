"""Soft-hyphen (U+00AD) line-break dehyphenation — S6 fix (2026-06-06).

Source: the citationguard text-extraction handoff (Defect 1). pdftotext (and
pymupdf) emit a SOFT HYPHEN U+00AD before the newline when a word wraps across
a line. docpluck's S6 already strips bare U+00AD, but stripping alone left
`relation\\nship`, which reflowed to the space-broken `relation ship` ~1/3 of
the time. The S6 join now drops the U+00AD AND the newline when a letter
follows, recovering the whole word.

General + structural: keyed purely on "U+00AD immediately before a line break,
followed by a letter" — never on word identity or paper. Per rule 0d the
real-PDF case exercises the public entry point on the actual fixture.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from docpluck.normalize import NormalizationLevel, normalize_text
from docpluck.render import render_pdf_to_markdown


_PDF_ROOT = Path(__file__).resolve().parents[1] / ".." / "PDFextractor" / "test-pdfs"


def _norm(text: str) -> str:
    out = normalize_text(text, NormalizationLevel.academic)
    return out[0] if isinstance(out, tuple) else str(out)


SOFT = "­"


def test_soft_hyphen_line_break_joined():
    text = (
        f"This is a long enough body sentence about com{SOFT}\n"
        f"mitment and pro{SOFT}\nmotion in the replication study here."
    )
    out = _norm(text)
    assert "commitment" in out
    assert "promotion" in out
    assert SOFT not in out
    assert "com mitment" not in out
    assert "pro motion" not in out


def test_soft_hyphen_with_indented_continuation():
    """Leading whitespace on the continuation line is consumed by the join."""
    text = f"the partici{SOFT}\n   pants completed a survey about their feelings."
    out = _norm(text)
    assert "participants" in out
    assert SOFT not in out


def test_soft_hyphen_before_blank_line_not_joined_across_paragraph():
    """A U+00AD before a blank line (no letter follows on the next non-empty
    line directly) must not collapse the paragraph boundary — the bare strip
    still removes the char, but the blank line survives."""
    text = f"end of paragraph{SOFT}\n\nNew paragraph starts here with content."
    out = _norm(text)
    assert SOFT not in out
    # paragraph break preserved (still a double newline somewhere)
    assert "\n\n" in out
    assert "New paragraph starts here" in out


def test_real_hyphen_still_handled_by_s7():
    """A genuine U+002D hyphen at a line end is dehyphenated by S7 (unchanged)."""
    text = "the meta-\nanalysis showed a robust effect across the studies."
    out = _norm(text)
    assert "metaanalysis" in out or "meta-analysis" in out  # S7 joins lowercase-hyphen-wrap


def test_chan_feldman_soft_hyphen_cleared_real_pdf():
    """chan_feldman_2025_cogemo (DOI 10.1080/02699931.2024.2434156): the
    citationguard handoff measured 151 U+00AD in pymupdf and 6 space-broken
    words surviving docpluck's old bare-strip. After the S6 join: zero
    U+00AD, zero space-broken residuals, whole words recovered."""
    pdf = (_PDF_ROOT / "apa" / "chan_feldman_2025_cogemo.pdf").resolve()
    if not pdf.is_file():
        # fixture also lives under the cogemo stem in some trees
        alt = list(_PDF_ROOT.rglob("chan_feldman_2025_cogemo.pdf"))
        if not alt:
            pytest.skip("fixture chan_feldman_2025_cogemo.pdf not available locally")
        pdf = alt[0]
    md = render_pdf_to_markdown(pdf.read_bytes())
    assert md.count("­") == 0, "soft hyphens survived to rendered output"
    for broken in ("com mitment", "pro motion", "altru ism", "relation ship"):
        assert broken not in md, f"space-broken word survived: {broken!r}"
    assert "commitment" in md
    assert "promotion" in md
