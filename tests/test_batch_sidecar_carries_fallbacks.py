"""The batch pipeline must read the telemetry channel back out.

## The defect, found by an independent review of v2.4.134 — the fix that stopped one layer short

v2.4.134's headline was "telemetry that actually reaches a consumer, from every channel". It gave
`NormalizationReport` a `fallbacks` channel precisely because every `record_fallback` inside
normalization had been write-only.

And then `batch.py` — which owns the corpus pipeline and writes the per-file `.json` sidecar a
consumer actually reads — never copied it out of the report. `grep -i fallback docpluck/batch.py`
returned **zero matches**. The report carried the value; `ExtractionFileResult` had no field for it;
the sidecar therefore could not contain it.

**This is the third appearance of one shape in this file's history**, and the second in two
releases:

* v2.4.126 — `ExtractionReport.to_dict` was a hand-written key list that silently dropped fields
  added to the dataclass afterwards;
* v2.4.128 — `batch.py` called `normalize_text` without `dropped_minus_layout`, so the corpus
  pipeline received none of the layout-proven glyph repairs;
* v2.4.134 — the fix for write-only telemetry was itself write-only for the highest-volume
  consumer of it.

The project's fourth check is *every value computed is read back*. These tests are that check,
asserted against the artifact on disk rather than against the dataclass.
"""

from __future__ import annotations

import json
from dataclasses import fields

from docpluck.batch import ExtractionFileResult, _build_sidecar


def test_the_result_declares_a_fallbacks_field():
    names = {f.name for f in fields(ExtractionFileResult)}
    assert "fallbacks" in names, (
        "the batch result cannot carry what normalization recorded"
    )
    assert "fallback_details" in names


def test_the_sidecar_serializes_them():
    """Against the dict that is written to disk — a field on the dataclass that
    the sidecar filters out is still invisible to a consumer."""
    result = ExtractionFileResult(path="p.pdf", ok=True)
    result.fallbacks = {"w0h_ambiguous_pairing_refused": 2}
    result.fallback_details = {"w0h_ambiguous_pairing_refused": {".428": 2}}

    sidecar = _build_sidecar(
        source="p.pdf",
        level="academic",
        info={"version": "2.4.134"},
        result=result,
        changes_made={},
    )
    # Round-trip through JSON: the sidecar is written with `json.dumps`, so a
    # value that cannot survive that is not actually delivered.
    round_tripped = json.loads(json.dumps(sidecar))
    assert round_tripped["fallbacks"] == {"w0h_ambiguous_pairing_refused": 2}
    assert round_tripped["fallback_details"] == {
        "w0h_ambiguous_pairing_refused": {".428": 2}
    }


def test_every_declared_result_field_reaches_the_sidecar_or_is_named_as_skipped():
    """The general guard, not another one-field patch.

    A field added to `ExtractionFileResult` must either appear in the sidecar or
    be listed in `_SIDECAR_SKIP_RESULT_FIELDS` with a reason. Without this, the
    next field added lands on the report and silently misses the artifact — which
    is precisely how this defect and the two before it happened.
    """
    from docpluck.batch import _SIDECAR_SKIP_RESULT_FIELDS

    sidecar = _build_sidecar(
        source="p.pdf",
        level="academic",
        info={"version": "2.4.134"},
        result=ExtractionFileResult(path="p.pdf", ok=True),
        changes_made={},
    )
    declared = {f.name for f in fields(ExtractionFileResult)}
    missing = declared - set(sidecar) - set(_SIDECAR_SKIP_RESULT_FIELDS)
    assert not missing, (
        f"declared but never serialized, and not named as a deliberate omission: "
        f"{sorted(missing)}"
    )
