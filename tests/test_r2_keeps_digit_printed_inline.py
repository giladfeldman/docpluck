"""R2 (reference page-number scrub) must not delete a digit printed inside a line.

10.1177/01461672251327169 p17 prints "Registered report stage 1 manuscript
template." on one line. The paper's page 1 put "1" in the page-number set, and
R2 removed it as a leaked page number: "stage manuscript template". A leaked
page number is never printed between the same two words on one line; it
reaches the entry only when the reference lines are joined.
"""

from __future__ import annotations

import re

from docpluck.extract import extract_pdf
from docpluck.normalize import NormalizationLevel, _r2_printed_inline, normalize_text
from docpluck.testing import require_corpus_pdf


def _match(refs: str, digit: str) -> re.Match[str]:
    m = re.search(r"(?<=[a-z])(\s+)" + digit + r"(\s+)(?=[a-z])", refs)
    assert m
    return m


def test_a_digit_printed_inside_the_line_is_kept():
    raw = "Feldman, G. (2023). Registered report stage 1 manuscript template.\n"
    refs = raw
    assert _r2_printed_inline(raw, refs, _match(refs, "1"), "1")


def test_a_page_number_on_its_own_line_is_still_a_leak():
    raw = "A study of psychological\n\x0c41\nscience in adults.\n"
    refs = "A study of psychological 41 science in adults."
    assert not _r2_printed_inline(raw, refs, _match(refs, "41"), "41")


def test_the_same_words_elsewhere_do_not_count():
    """Only the exact word-digit-word triple on one line counts."""
    raw = "stage 2 manuscript\nA study of stage\n1\nmanuscript\n"
    refs = "A study of stage 1 manuscript"
    assert not _r2_printed_inline(raw, refs, _match(refs, "1"), "1")


def test_the_reference_title_keeps_its_numeral_on_the_real_paper():
    raw, _ = extract_pdf(require_corpus_pdf("apa/ip_feldman_2025_pspb.pdf").read_bytes())
    assert "Registered report stage 1 manuscript template" in raw, "fixture changed"
    out, _ = normalize_text(raw, NormalizationLevel.academic)
    assert "Registered report stage 1 manuscript template" in out
