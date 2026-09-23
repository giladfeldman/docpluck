"""Reference-list ROTATION on heading-less continuation pages — real-PDF gate.

Reported by a downstream consumer's canary audit (2026-09-22) and verified by
rasterizing the page: on chen_2021_jesp (10.1016/j.jesp.2021.104154) page 20,
pdftotext emits the RIGHT reference column before the LEFT one. The entry after
"Gregory (2011)" (end of p19) came out as "Nosek, Spies & Motyl (2012)", and the
30 entries Groß (2015) … Nestler (2009) surfaced after Zwaan (2018). Nothing was
lost — order only — so every word-count gate stayed green.

The O5 inversion detector could not see it: it needs the page's own
``References`` heading, and a continuation page has none. The signature used
instead is the alphabet itself: a right-column-first page reads as two sorted
runs, the second of which belongs before the first ("N..Z" then "G..N").

Prevalence, measured 2026-09-23 over a random 500-paper sample of the article
repository (seed 20260923): the signature fired on 88 pages in 57 papers
(11%), essentially all JESP and Collabra. Before this change 42 of the 88 were
corrected; after it 87. The one refusal is a false trigger (a
Psychological Science page pdftotext already had in the right order, made to
look rotated by wrapped author lines) which the acceptance check correctly
rejected. The second fixture here, maier_2023_collabra
(10.1525/collabra.90203), exercises the edge-trimmed path: centred header,
centred "References" title, centred footer and a vertical margin watermark.
"""

from __future__ import annotations

import re
import subprocess

import pytest

from docpluck.extract import extract_pdf
from docpluck.extract_columns import (
    _accept_reorder,
    _char_multiset,
    _detect_reference_rotation_pages,
    _longest_sorted_run,
    _reference_entry_keys,
    _reference_rotation_resolved,
    _word_multiset,
    extract_page_text_edge_trimmed,
)
from docpluck.extract_layout import extract_pdf_layout
from docpluck.testing import require_corpus_pdf
from docpluck.version import resolve_pdftotext_executable

CHEN = "apa/chen_2021_jesp.pdf"
MAIER = "apa/maier_2023_collabra.pdf"


def _raw_pdftotext(pdf) -> str:
    return subprocess.run(
        [resolve_pdftotext_executable(), "-enc", "UTF-8", str(pdf), "-"],
        capture_output=True, encoding="utf-8", errors="replace", check=True,
    ).stdout


def _offsets(text: str) -> tuple[int, ...]:
    return tuple([0] + [i + 1 for i, ch in enumerate(text) if ch == "\f"])


@pytest.fixture(scope="module")
def chen():
    pdf = require_corpus_pdf(CHEN)
    return pdf, extract_pdf(pdf.read_bytes())


@pytest.fixture(scope="module")
def maier():
    pdf = require_corpus_pdf(MAIER)
    return pdf, extract_pdf(pdf.read_bytes())


# ── the defect exists in the input (two-sided: otherwise the fix proves nothing)


@pytest.mark.parametrize("rel, pages", [(CHEN, (20,)), (MAIER, (18, 19, 20))])
def test_raw_pdftotext_serializes_these_pages_right_column_first(rel, pages):
    raw = _raw_pdftotext(require_corpus_pdf(rel))
    flagged = _detect_reference_rotation_pages(raw, _offsets(raw))
    for p in pages:
        assert p in flagged, (
            f"{rel}: page {p} no longer reads as a rotated reference list in raw "
            f"pdftotext output (flagged={flagged}); if pdftotext changed, this "
            "fixture no longer exercises the fix"
        )


def test_detector_does_not_fire_on_a_correctly_ordered_reference_list():
    raw = _raw_pdftotext(require_corpus_pdf("ama/jama_open_1.pdf"))
    assert _detect_reference_rotation_pages(raw, _offsets(raw)) == ()


# ── the fix, through the production entry point


def test_chen_page_20_is_corrected_and_tagged(chen):
    _pdf, (text, method) = chen
    m = re.search(r"column_corrected:([\d,]+)", method)
    assert m and "20" in m.group(1).split(","), method


def test_chen_reference_list_now_runs_gregory_then_gross(chen):
    """The exact symptom the downstream audit reported."""
    _pdf, (text, _m) = chen
    entries = [ln for ln in text.splitlines()
               if re.match(r"^[A-ZÀ-Þ][\w'’\-]+,\s+(?:[A-ZÀ-Þ]\.\s*)+", ln)]
    i = next(k for k, ln in enumerate(entries) if ln.startswith("Gregory, E."))
    assert entries[i + 1].startswith("Groß, J."), entries[i + 1]
    assert entries[-1].startswith("Zwaan, R. A."), entries[-1]
    j = next(k for k, ln in enumerate(entries) if ln.startswith("Nosek, B. A., & Lakens"))
    assert entries[j + 1].startswith("Nosek, B. A., Spies"), entries[j + 1]


@pytest.mark.parametrize("fixture, pages", [("chen", (19, 20)), ("maier", (18, 19, 20))])
def test_corrected_pages_are_sorted_and_word_identical(fixture, pages, request):
    pdf, (text, method) = request.getfixturevalue(fixture)
    raw_pages = _raw_pdftotext(pdf).split("\f")
    out_pages = text.split("\f")
    m = re.search(r"column_corrected:([\d,]+)", method)
    corrected = {int(x) for x in m.group(1).split(",")} if m else set()
    for p in pages:
        assert p in corrected, f"{fixture} p{p} not corrected ({method})"
        # Pure reorder: not a word lost, not a word invented (rules 0a / 0b).
        assert _word_multiset(out_pages[p - 1]) == _word_multiset(raw_pages[p - 1])
        # ...and not a character: the word multiset is blind to digits and
        # one-letter initials (see the digit-duplication test below).
        assert _char_multiset(out_pages[p - 1]) == _char_multiset(raw_pages[p - 1])
        keys = _reference_entry_keys(out_pages[p - 1])
        assert _longest_sorted_run(keys) >= 0.75 * len(keys), (
            f"{fixture} p{p}: {''.join(keys)}")


# ── the edge-trimmed geometry, on the page class that needs it


def test_edge_trimmed_reads_furniture_columns_and_watermark_without_splitting(maier):
    """maier p18: centred header + centred 'References' title + centred footer
    cross the gutter, and a vertical margin watermark spans the page height.
    Every word must survive the four-plus-one crop, and the body must come out
    left column (A–B) before right column (C–E)."""
    pdf, _ = maier
    b = pdf.read_bytes()
    layout = extract_pdf_layout(b, pages=[17])
    out = extract_page_text_edge_trimmed(layout, 17, b)
    raw = _raw_pdftotext(pdf).split("\f")[17]
    assert out, "edge-trimmed geometry refused a page it was built for"
    assert _word_multiset(out) == _word_multiset(raw)
    assert out.index("Alinaghi, N.") < out.index("Cameron, C. D.")
    assert out.index("References") < out.index("Alinaghi, N.")
    assert _reference_rotation_resolved(out, raw)


def test_rotation_check_refuses_a_reorder_that_changes_nothing(chen):
    """Two-sided control on the acceptance check: the raw page compared with
    itself delivers no sortedness gain and must be refused."""
    pdf, _ = chen
    raw = _raw_pdftotext(pdf).split("\f")[19]
    assert not _reference_rotation_resolved(raw, raw)


def test_a_reorder_that_duplicates_one_digit_is_refused(chen):
    """Found by the Sonnet cross-model review, 2026-09-23, then measured: the
    whole-page column crop cut a running header that crosses the gutter, the
    glyph on the cut landed in BOTH crops, and "125–135" shipped as "125–13" +
    "35" (10.1016/j.jesp.2017.05.004 p11) — on 33 of 87 corrected reference
    pages of a 500-paper sample. Every word survived, so the word-multiset
    guard passed it. The shape is reproduced here on a real page: the correct
    left-then-right reorder of chen p20, plus one duplicated digit."""
    pdf, (text, _m) = chen
    raw = _raw_pdftotext(pdf).split("")[19]
    fixed = text.split("")[19]
    assert _accept_reorder(fixed, raw, True), "control: the real reorder must pass"
    i = fixed.index("104154")
    broken = fixed[:i] + "10415 54" + fixed[i + 6:]  # one extra "5"
    assert _word_multiset(broken) == _word_multiset(raw), (
        "fixture no longer isolates the blind spot: the word guard sees it")
    assert not _accept_reorder(broken, raw, True)
