"""Per-fixture smoke assertions driven by MANIFEST.json."""


import pytest
from tests.structured_fixtures import fixture_entries, resolve_fixture


# Default tolerance for table/figure count comparisons.
# Bumped from 2 → 6 after the v2 pipeline change (LESSONS L-006): Camelot +
# caption-regex finds different (often more) tables than pdfplumber's
# caption-anchored geometric pipeline. Per-fixture recalibration of MANIFEST
# expected_tables/expected_figures is a separate follow-up. The wider tolerance
# is acceptable because the smoke tests are coarse "doesn't crash, reasonable
# count" checks — semantic content is verified by per-fixture assertions
# elsewhere.
COUNT_TOLERANCE = 6

# Fixtures that genuinely extract ZERO tables today, each with the measurement
# that put it here. This is a RECORD OF A DEFECT, not an allowance: the
# assertion below is two-sided, so the moment one of these starts producing a
# table the test goes red and the entry must be deleted.
#
# It exists because tightening the zero case surfaced a real, pre-existing loss
# that the ±6 tolerance had been hiding. Measured 2026-09-21 across all twelve
# fixtures (expected -> actual): chan 8->9, chen 11->15, efendic 1->5,
# ip_feldman 7->10, bmc 1->4, ieee_lattice 1->1, jama 1->3, amj 5->5,
# scirep 1->4, nat_comms 0->0, ieee_figure_heavy 8->8 -- and this one alone at
# 1->0. Every other fixture meets or exceeds its expectation, so the gate is
# live for eleven of twelve rather than waived wholesale.
#
# RESOLVED 2026-09-24, and the resolution is worth keeping in view: the one entry
# here, "nature_minimal_rule", was NOT a capture defect. The fixture pointed at the
# wrong paper (nat_comms_1 prints no table at all), and the paper it was meant for
# (nat_comms_2) had its `Table 1 |` caption invisible to the caption pattern. Both
# were fixed; this dict is empty and the mechanism stays for the next real zero.
KNOWN_ZERO_TABLE_FIXTURES: dict[str, str] = {}


@pytest.mark.parametrize("entry", fixture_entries(), ids=lambda e: e.get("id", "?"))
def test_table_count_within_tolerance(entry):
    pdf = resolve_fixture(entry["id"])
    from docpluck import extract_pdf_structured
    expected = entry["expected_tables"]
    result = extract_pdf_structured(pdf.read_bytes())
    # CAPTIONED tables are what `expected_tables` counts. Since 2026-09-24 a grid
    # no caption claims is kept as caption_status="uncaptioned_candidate" (owner
    # directive: retain and label), and those are extra by construction -- 13 of
    # them on nat_comms_2 alone, mostly structure inside figures -- so counting
    # them here would measure the candidates, not the captioned tables.
    actual = sum(1 for t in result["tables"] if t.get("caption_status") == "matched")
    # A TOTAL loss of the table channel must not be inside the tolerance band.
    # Measured 2026-09-21: 8 of these 12 fixtures expect <= 6 tables, so with
    # COUNT_TOLERANCE = 6 a run that extracted ZERO tables passed for all eight
    # of them. The tolerance exists to absorb capture-quality drift of a few
    # tables, not to absorb the capability being gone -- so zero is its own
    # assertion now, rather than a point inside the band.
    if expected > 0:
        recorded = KNOWN_ZERO_TABLE_FIXTURES.get(entry["id"])
        if recorded is None:
            assert actual > 0, (
                f"{entry['id']}: expected {expected} tables and got NONE. The "
                f"table channel produced nothing at all, which the "
                f"±{COUNT_TOLERANCE} tolerance below would have accepted. "
                f"method={result['method']}"
            )
        else:
            # Two-sided, so the record cannot rot into an excuse: the day this
            # fixture starts producing tables, THIS assertion goes red and the
            # entry has to be removed -- rather than the zero quietly becoming
            # permanent because nobody re-measured it.
            assert actual == 0, (
                f"{entry['id']} is recorded as extracting ZERO tables "
                f"({recorded}) but now extracts {actual}. Delete it from "
                f"KNOWN_ZERO_TABLE_FIXTURES so the real assertion protects it."
            )
    assert abs(actual - expected) <= COUNT_TOLERANCE, (
        f"{entry['id']}: expected {expected} tables (±{COUNT_TOLERANCE}), got {actual}"
    )


@pytest.mark.parametrize("entry", fixture_entries(), ids=lambda e: e.get("id", "?"))
def test_figure_count_within_tolerance(entry):
    pdf = resolve_fixture(entry["id"])
    from docpluck import extract_pdf_structured
    expected = entry["expected_figures"]
    result = extract_pdf_structured(pdf.read_bytes())
    actual = len(result["figures"])
    # Same hole as tables, found the same way: with COUNT_TOLERANCE = 6, ZERO
    # figures passed for every fixture expecting <= 6. Measured 2026-09-24, two
    # Nature Communications fixtures extracted 0 figures while printing 4 and 5
    # -- every `Fig. N |` caption was invisible -- and this test stayed green.
    if expected > 0:
        assert actual > 0, (
            f"{entry['id']}: expected {expected} figures and got NONE; the "
            f"±{COUNT_TOLERANCE} tolerance below would have accepted that. "
            f"method={result['method']}"
        )
    assert abs(actual - expected) <= COUNT_TOLERANCE, (
        f"{entry['id']}: expected {expected} figures (±{COUNT_TOLERANCE}), got {actual}"
    )


@pytest.mark.parametrize("entry", fixture_entries(), ids=lambda e: e.get("id", "?"))
def test_extract_pdf_structured_does_not_raise(entry):
    """Hard guarantee: never raise on any fixture, regardless of extraction quality."""
    pdf = resolve_fixture(entry["id"])
    from docpluck import extract_pdf_structured
    # Should not raise
    result = extract_pdf_structured(pdf.read_bytes())
    assert isinstance(result, dict)
    assert "text" in result
    assert isinstance(result["tables"], list)
    assert isinstance(result["figures"], list)


@pytest.mark.parametrize("entry", fixture_entries(), ids=lambda e: e.get("id", "?"))
def test_table_html_renders_when_structured(entry):
    """Every structured table must have non-empty HTML; isolated must have None."""
    pdf = resolve_fixture(entry["id"])
    from docpluck import extract_pdf_structured
    result = extract_pdf_structured(pdf.read_bytes())
    for t in result["tables"]:
        if t["kind"] == "structured":
            assert t["html"] is not None
            assert "<table>" in t["html"]
            assert isinstance(t["cells"], list)
            assert len(t["cells"]) > 0
            # v2.4.133: `kind` no longer encodes the capture path — it used to
            # carry the out-of-type value "whitespace" for the layout-channel
            # column-gap fallback (register C4). The engine is now recorded by
            # `camelot_flavor`, and a path with no capture-quality signal
            # reports None rather than inventing one.
            if t["camelot_flavor"] is not None:
                assert t["confidence"] is not None
                assert 0.0 <= t["confidence"] <= 1.0
            else:
                assert t["confidence"] is None
        else:
            assert t["kind"] == "isolated"
            assert t["html"] is None
            assert t["confidence"] is None
            assert t["cells"] == []
