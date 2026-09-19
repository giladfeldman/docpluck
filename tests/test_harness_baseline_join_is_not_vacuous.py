"""The Tier-D gate must not print a measured-looking zero it cannot measure.

MEASURED 2026-09-18, during the v2.4.144 QA phase. The corpus repoint re-keyed
every harness document id from its former per-source prefixes to
``corpus__*``, but ``scripts/harness/baseline_matrix.json`` was not regenerated:

    baseline docs 180   manifest docs 135   OVERLAP 0

``diff_baseline`` classifies a cell as a REGRESSION only when
``prior == "pass"``. With no joinable key, ``prior`` is ``None`` everywhere, so
the headline the check-7h gate is read by -- "Tier-D reports 0 regressions" --
became unconditional. Nothing was broken loudly; the gate simply stopped being
able to say no.

The two tests below are the two sides of that claim: the guard must fire when
the baseline cannot be joined, and must NOT fire when it can. Without the second,
a guard wired to always-true would look correct here.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from scripts.harness import checks as harness_checks  # noqa: E402

_CELL = {"verdict": "pass", "detail": ""}


def _matrix(doc_ids: list[str]) -> dict:
    return {d: {"academic": {"table_parity": dict(_CELL)}} for d in doc_ids}


def _with_baseline(tmp_path: Path, matrix: dict, monkeypatch) -> dict:
    p = tmp_path / "baseline_matrix.json"
    p.write_text(json.dumps(matrix), encoding="utf-8")
    monkeypatch.setattr(harness_checks, "BASELINE_PATH", p)
    return matrix


def test_a_baseline_sharing_no_keys_reports_zero_joinable_cells(tmp_path, monkeypatch):
    _with_baseline(tmp_path, _matrix(["legacysource__ama__jama-open-5"]), monkeypatch)
    diff = harness_checks.diff_baseline(_matrix(["corpus__ama__jama-open-5"]))
    assert diff["has_baseline"], "the baseline was not read at all -- test is vacuous"
    assert diff["joinable_cells"] == 0, (
        "a re-keyed baseline must report 0 joinable cells so `main()` can refuse "
        "to print an unconditional '0 REGRESSIONS'"
    )
    assert diff["regressions"] == [], "no regression is detectable across a broken join"


def test_a_joinable_baseline_is_not_flagged(tmp_path, monkeypatch):
    """The other side. A guard that always fires would pass the test above."""
    _with_baseline(tmp_path, _matrix(["corpus__ama__jama-open-5"]), monkeypatch)
    diff = harness_checks.diff_baseline(_matrix(["corpus__ama__jama-open-5"]))
    assert diff["joinable_cells"] == 1, (
        "an identically-keyed baseline must join -- the guard is now wired to "
        "always-true and would condemn every healthy run"
    )


def test_a_real_regression_is_still_seen_when_the_join_works(tmp_path, monkeypatch):
    """The gate's actual job, asserted on the same code path."""
    _with_baseline(tmp_path, _matrix(["corpus__ama__jama-open-5"]), monkeypatch)
    current = _matrix(["corpus__ama__jama-open-5"])
    current["corpus__ama__jama-open-5"]["academic"]["table_parity"]["verdict"] = "fail"
    diff = harness_checks.diff_baseline(current)
    assert diff["regressions"] == [("corpus__ama__jama-open-5", "academic", "table_parity")]


def test_the_committed_baseline_is_currently_unjoinable():
    """A ratchet on the real files: this must be FIXED by re-baselining, and when
    it is, this test fails and must be deleted -- it may never rot into an excuse."""
    base = json.loads(
        (_REPO / "scripts" / "harness" / "baseline_matrix.json").read_text(encoding="utf-8")
    )
    man = json.loads(
        (_REPO / "scripts" / "harness" / "corpus_manifest.json").read_text(encoding="utf-8")
    )
    cur = {d["id"] for d in man["documents"]}
    overlap = len(set(base) & cur)
    assert base and cur, "one of the two files parsed empty -- the instrument is broken"
    assert overlap == 0, (
        f"the baseline now joins ({overlap} shared doc ids). The re-baseline this "
        "file was written for has happened -- DELETE this test; the three above "
        "keep the guard honest."
    )
