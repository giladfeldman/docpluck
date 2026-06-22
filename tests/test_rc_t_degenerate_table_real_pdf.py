"""RC-T degenerate prose-table guard — regression tests (v2.4.96, 2026-06-21).

Camelot runs free-form (``flavor="stream"``, no ``table_areas``), so on a
text-heavy page it returns a whole-page bbox and folds body prose into table
cells — including the ``<thead>``. ``_strip_phantom_camelot_tables`` drops such
tables, but its prose-detection function-word set was missing ``"the"`` (the
single most common English function word), so an 8-word prose ``<th>`` counted
only fn=2 and slipped under the fn>=3 bar:

  * maier_2023 Table 7   <th> "Following the analyses conducted in Study 1 of Small"
  * chan_feldman Table 6 <th> "associations between the six measures of interest: …"

Both emitted a garbage prose ``<table>``. Adding ``"the"`` → fn>=3 (with the
unchanged verb>=2 bar) → correctly stripped (fail-clean: the ``### Table N``
heading + caption remain — table_parity preserved — but no fabricated grid).

The ``>=8``-word ``<th>`` gate + verb>=2 bar keep this FP-safe: legit
prose-bearing comparison tables survive — chan_feldman Table 2 (correlation
matrix whose <th> "C. F. CHAN AND G. FELDMAN Target article" is 8 words but
fn=1) and Table 5 (comparison table whose *cells* are full sentences). The
stripped prose is a Camelot duplicate; the clean original remains in the body
text channel (no TEXT-LOSS, rule 0a).

Real-PDF (rule 0d) + structural-signature general fix (rule 16). PDFs are
closed-access (``feedback_no_pdfs_in_repo``); each test skips when the article
repository fixture is absent.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from docpluck.render import render_pdf_to_markdown

from .conftest import pdf_available, pdf_path, requires_pdftotext

# Real-PDF Camelot extraction is non-deterministic under parallel xdist load
# (10 concurrent Ghostscript/temp-dir subprocesses make Camelot intermittently
# return no tables — the "tables present" FP-guards then false-fail). These
# tests run for real SERIALLY (`pytest tests/ -q`, the canonical /docpluck-qa
# command); skip them under an xdist worker so the parallel gate stays green.
# Same convention as test_tables_flatten_blank_header_recovery.py.
_skip_under_xdist = pytest.mark.skipif(
    bool(os.environ.get("PYTEST_XDIST_WORKER")),
    reason="real-PDF Camelot extraction is non-deterministic under parallel "
    "xdist load; runs serially (isolation/serial run is the real gate)",
)


def _norm(s: str) -> str:
    """Collapse whitespace — Camelot cells join words with double spaces, the
    body text channel uses single spaces; normalize both before substring tests."""
    return re.sub(r"\s+", " ", s)


def _tables_text(md: str) -> str:
    """Whitespace-normalized concatenation of every <table>…</table> block."""
    return _norm("\n".join(re.findall(r"<table.*?</table>", md, re.DOTALL | re.IGNORECASE)))


def _render_key(doi_key: str) -> str:
    if not pdf_available("articlerepo", f"{doi_key}.pdf"):
        pytest.skip(f"closed-access fixture missing: {doi_key}.pdf")
    return render_pdf_to_markdown(Path(pdf_path("articlerepo", f"{doi_key}.pdf")).read_bytes())


@pytest.fixture(scope="module")
def maier_md() -> str:
    return _render_key("10.1525__collabra.90203")


@pytest.fixture(scope="module")
def chan_md() -> str:
    return _render_key("10.1080__02699931.2024.2434156")


@pytest.fixture(scope="module")
def ipf_md() -> str:
    return _render_key("10.1177__01461672251327169")


@pytest.fixture(scope="module")
def amp_md() -> str:
    """amp_1 lives in the committed test-pdfs corpus (not the article repo)."""
    if not pdf_available("docpluck", "aom", "amp_1.pdf"):
        pytest.skip("corpus fixture missing: aom/amp_1.pdf")
    return render_pdf_to_markdown(Path(pdf_path("docpluck", "aom", "amp_1.pdf")).read_bytes())


# ── the fix: garbage prose tables stripped (FAIL at HEAD, PASS after) ──────────


@requires_pdftotext
@_skip_under_xdist
def test_maier_t7_prose_header_not_in_any_table(maier_md: str):
    """maier Table 7: the Discussion line Camelot folded into a <th> must not
    survive inside a <table> (a garbage prose grid at HEAD)."""
    assert "Following the analyses conducted in Study 1 of Small" not in _tables_text(maier_md), (
        "maier T7 prose <th> still inside a <table> — the degenerate prose table "
        "was not stripped. Check that _FUNCTION_WORDS_IN_PROSE includes 'the' in "
        "_strip_phantom_camelot_tables (docpluck/render.py)."
    )


@requires_pdftotext
@_skip_under_xdist
def test_maier_t7_heading_preserved_and_prose_in_body(maier_md: str):
    """Fail-clean, not delete: the `### Table 7` heading survives (table_parity)
    and the stripped prose remains in the body (no TEXT-LOSS, rule 0a)."""
    assert "### Table 7" in maier_md, "maier `### Table 7` heading lost (table_parity broken)"
    assert "Following the analyses conducted in Study 1 of Small" in _norm(maier_md), (
        "maier T7 Discussion prose vanished entirely — the strip removed body "
        "text, not just the duplicate table cell (rule 0a TEXT-LOSS)."
    )


@requires_pdftotext
@_skip_under_xdist
def test_chan_feldman_t6_prose_not_in_any_table(chan_md: str):
    """chan_feldman Table 6: a Measures-section sentence Camelot clustered into a
    grid must not survive inside a <table>."""
    assert "associations between the six measures of interest" not in _tables_text(chan_md), (
        "chan_feldman T6 prose still inside a <table> — degenerate prose table "
        "not stripped."
    )


@requires_pdftotext
@_skip_under_xdist
def test_chan_feldman_t6_prose_survives_in_body(chan_md: str):
    assert "associations between the six measures of interest" in _norm(chan_md), (
        "chan_feldman T6 prose vanished entirely (rule 0a TEXT-LOSS)."
    )


# ── FP guards: legit prose-bearing tables MUST survive ────────────────────────


@requires_pdftotext
@_skip_under_xdist
def test_chan_feldman_t2_correlation_table_survives(chan_md: str):
    """FP guard: the Table 2 correlation matrix (a real table whose <th> carries
    a running-header leak '1232 C. F. CHAN AND G. FELDMAN' — 8 words but fn=1)
    must NOT be suppressed; its data must remain in a <table>."""
    tables = _tables_text(chan_md)
    assert "Degree" in tables and "apology" in tables, (
        "chan_feldman T2 correlation data missing from all <table> blocks — the "
        "guard over-fired on a real table (FP). The fn=1 running-header <th> must "
        "not qualify (verb>=2 + fn>=3 bar)."
    )


@requires_pdftotext
@_skip_under_xdist
def test_chan_feldman_t5_comparison_table_survives(chan_md: str):
    """FP guard: the Table 5 comparison table (real 4-column data whose cells are
    full descriptive sentences) must survive — prose *in cells* is legitimate for
    a comparison table; only an >=8-word prose <th> triggers the guard."""
    tables = _tables_text(chan_md)
    assert "N = 239" in tables and "N = 794" in tables, (
        "chan_feldman T5 comparison data missing from all <table> blocks — the "
        "guard over-fired on a legit prose-bearing comparison table (FP)."
    )


# ── guard: ip_feldman has no prose tables (already clean at HEAD) ──────────────


@requires_pdftotext
@_skip_under_xdist
def test_ip_feldman_no_discussion_prose_in_tables(ipf_md: str):
    """ip_feldman T10's Discussion prose ('ported and documented below …') was a
    whole-page-bbox region; it must never appear inside a <table>."""
    assert "ported and documented below" not in _tables_text(ipf_md), (
        "ip_feldman Discussion prose leaked into a <table>."
    )


@requires_pdftotext
@_skip_under_xdist
def test_amp1_t5_title_leak_table_survives(amp_md: str):
    """FP guard (the title-leak exclusion). amp_1 Table 5 leaks its own caption
    ("Improving Scholarly Impact Assessment Using the CSII: Implications for
    Policymaking and Practice") into the <th> over a REAL grid (Domains /
    Policymaking / Practice + descriptions). With "the" counted, that <th>
    reaches fn=3 — but it is the table's own TITLE, not body prose, so the
    caption-token-overlap gate must keep the table. A naive 'add the' would
    strip this real table (the FP the full-corpus diff caught)."""
    tables = _tables_text(amp_md)
    assert "Domains" in tables and "Policymaking" in tables and "Practice" in tables, (
        "amp_1 T5 real grid (Domains/Policymaking/Practice) missing from all "
        "<table> blocks — the 'the' body-prose path over-fired on a title-leak "
        "(FP). Check the caption-token-overlap title-leak gate in "
        "_strip_phantom_camelot_tables (render.py)."
    )
    assert "uniform metric for comparing impact" in tables, (
        "amp_1 T5 description cell lost — real table was stripped (FP)."
    )
