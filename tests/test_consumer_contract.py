"""The field set and symbol spellings downstream consumers read (plan gap G7, 2026-11-13).

Two consumers pin docpluck's output against goldens on THEIR side; nothing on
this side failed when a key or a spelling moved, so a consumer was the first to
see it (the 2026-08-14 `eta2p` -> `eta2_p` rename silently dropped partial eta
squared from a consumer for seven days). This test asserts the library-owned
part of those goldens, so the change fails HERE, before release:

* the keys of every table, flattened row, section and normalization report;
* the flattened-row field-key set on the synthetic structure fixture;
* the normalized spelling of 22 statistical-symbol probes.

Changing an expected value below is a CONTRACT CHANGE: it needs a consumer
notice with a before/after table (CLAUDE.md), never a silent golden refresh.
The fixture PDF is a synthetic contract document (it says so on its page),
copied byte-identical from the consumers' fixture (sha256 pinned below).
"""
from __future__ import annotations

import hashlib

import pytest

from docpluck import (
    NormalizationLevel,
    extract_pdf_structured,
    extract_sections,
    flatten_tables_for_paper,
    normalize_text,
)

from tests.fixtures.consumer_contract.build import build_contract_structure_pdf

# Built on demand (the repo keeps no PDFs, so a committed fixture could not run on
# a clone); reportlab's invariant mode makes the bytes, and so this hash, stable.
_PDF_SHA = "88e1a3888b964db3cb8f092c79aff1b59adf650dc87dd40d4ce3c1fb4d7b6bfa"

TABLE_KEYS = {
    "accuracy", "bbox", "camelot_flavor", "caption", "caption_status", "cell_geometry",
    "cells", "confidence", "content_status", "footnote", "header_rows",
    "header_text_below_caption", "html", "id", "kind", "label", "n_cols", "n_rows",
    "page", "raw_text", "rendering", "whitespace",
}
ROW_KEYS = {
    "caption_status", "fields", "fields_raw", "header", "label", "page", "raw_cells",
    "row_idx", "row_label", "sentence", "table_id",
    "unparsed",  # added 2026-11-13; announced in the consumer notice
    "typed_without_header",  # added 2026-11-16 (Release B); announced in its notice
}
ROW_FIELD_KEYS = {"F", "d", "df", "df1", "df2", "p", "p_op", "p_text", "t"}
SECTION_KEYS = {
    "canonical_label", "char_end", "char_start", "confidence", "detected_via",
    "heading_text", "label", "pages", "subheadings", "text",
}
# `warnings` and `layout_repairs` are added by the service, not the library.
NORMALIZATION_KEYS = {
    "changes_made", "changes_made_by_step", "column_interleave_pages",
    "fallback_details", "fallbacks", "footnote_spans", "footnote_texts", "level",
    "page_offsets", "residual_control_chars", "steps_applied", "steps_changed", "version",
}
STRUCTURED_KEYS = {
    "fallback_details", "fallbacks", "figures", "figures_status", "method",
    "page_count", "table_extraction_version", "tables", "tables_status", "text",
    # added 2026-11-13; announced in the consumer notice
    "unmapped_glyph_fonts",
}
CAPTION_STATUSES = {"matched", "continuation", "none_found", "uncaptioned_candidate"}

# (input as printed, normalized form every consumer golden records)
SYMBOL_PROBES = [
    ("η²ₚ = .11", "eta2_p = .11"), ("ω²ₚ = .09", "omega2_p = .09"),
    ("η² = .12", "eta2 = .12"), ("ω² = .06", "omega2 = .06"), ("ε² = .05", "epsilon2 = .05"),
    ("χ²(1) = 4.10", "chi2(1) = 4.10"), ("β = 0.31", "beta = 0.31"),
    ("ΔR² = .05", "DeltaR2 = .05"), ("R² = .42", "R2 = .42"), ("ρ = .28", "rho = .28"),
    ("τ = .19", "tau = .19"), ("φ = .22", "phi = .22"), ("μ = 3.40", "mu = 3.40"),
    ("α = .05", "alpha = .05"), ("σ² = 1.44", "sigma2 = 1.44"), ("M = −1.25", "M = -1.25"),
    ("3 × 4 design", "3 * 4 design"),
    ("d = 0.15, 95% CI [−0.04, 0.34]", "d = 0.15, 95% CI [-0.04, 0.34]"),
    ("p ≤ .001", "p <= .001"), ("10² replications", "10^2 replications"),
]


@pytest.fixture(scope="module")
def structured():
    data = build_contract_structure_pdf()
    assert hashlib.sha256(data).hexdigest() == _PDF_SHA, "fixture changed"
    return data, extract_pdf_structured(data)


def test_structured_result_keys(structured):
    _, s = structured
    assert set(s) == STRUCTURED_KEYS


def test_table_keys_and_caption_status_vocabulary(structured):
    _, s = structured
    assert len(s["tables"]) == 2
    for t in s["tables"]:
        assert set(t) == TABLE_KEYS
        assert t["caption_status"] in CAPTION_STATUSES


def test_flattened_rows_keys_and_field_spellings(structured):
    _, s = structured
    rows = flatten_tables_for_paper(s["tables"])
    assert len(rows) == 5
    keys: set[str] = set()
    for r in rows:
        assert set(r) == ROW_KEYS
        keys |= set(r["fields"])
    assert keys == ROW_FIELD_KEYS


def test_section_and_normalization_report_keys(structured):
    data, s = structured
    secs = extract_sections(data).sections
    assert len(secs) == 4
    for sec in secs:
        assert set(vars(sec)) == SECTION_KEYS
        # Declared and now populated: was () on every section.
        assert sec.pages == (1,), (sec.label, sec.pages)
    _, rep = normalize_text(s["text"], NormalizationLevel.academic)
    assert set(rep.to_dict()) == NORMALIZATION_KEYS


@pytest.mark.parametrize("printed, expected", SYMBOL_PROBES)
def test_symbol_probe_spelling(printed, expected):
    out, _ = normalize_text(f"Probe line: {printed}\n", NormalizationLevel.academic)
    assert expected in out, f"{printed!r} -> {out!r}, consumers expect {expected!r}"
