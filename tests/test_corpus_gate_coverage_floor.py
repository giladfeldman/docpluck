"""The corpus gate must refuse a baseline view that covers fewer papers than
an older sibling -- and must say so when it could not check at all.

WHY THIS IS A TEST.  Measured 2026-09-17: ``--latest`` resolved
``render-baseline__docpluck`` to ``@2.4.143``, which a release had re-baselined
over SIX papers while ``@2.4.126`` held twenty-six.  ``scripts/verify_corpus.py``
then resolved 6 of 6 PDFs, took its "all resolved" branch, and printed a clean
per-paper PASS.  Nothing was broken in the gate's own logic: its denominator
comes from ``_expected_papers(view)``, the view it had just resolved, so from
the gate's point of view the corpus really was six papers.  The three-state
SKIP / PARTIAL / full design cannot fire against a denominator that shrank with
the numerator -- which is the same failure the module docstring says the
directory-glob rewrite was meant to end, arriving through a different door.

The high-water mark is computed by article-finder, the custodian, because it is
the only party that sees every sibling version; it is ASSERTED here.  The
custodian publishes it as a ``LATEST-COVERAGE:`` line on stderr of every
``--latest`` resolution -- on the healthy resolution too, deliberately.  A
consumer that can only learn of a shortfall from the PRESENCE of a warning
cannot distinguish "no shortfall" from "this build of the custodian does not
check", so the absence of the line is itself a refusal (``test_missing_coverage_
line_is_a_refusal``), not a pass.

Each arm below asserts the branch it means to exercise actually FIRED, by
matching the message that branch alone prints.  An earlier shape of this test
that only asserted the exit code passed against a stub that never reached the
floor at all.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import verify_corpus as vc  # noqa: E402

FAMILY = "render-baseline__docpluck"


def _stderr(view: str, papers: int | None, max_view: str, max_papers: int | None) -> str:
    lines = []
    if papers is not None and max_papers is not None:
        lines.append(
            f"LATEST-COVERAGE: view={view} papers={papers} "
            f"max_view={max_view} max_papers={max_papers}"
        )
    lines.append(f"resolved --latest to view {view}")
    return "\n".join(lines) + "\n"


def _fake_af(stderr: str, stdout: str = ""):
    def af(script: str, *args: str) -> subprocess.CompletedProcess:
        if script == "ai-gold.py" and "--latest" in args:
            return subprocess.CompletedProcess([], 0, stdout, stderr)
        return subprocess.CompletedProcess([], 0, "", "")
    return af


def _run_main(monkeypatch, capsys, *, stderr: str, expected=()):
    monkeypatch.setattr(vc, "_af", _fake_af(stderr))
    monkeypatch.setattr(vc, "_expected_papers", lambda view: list(expected))
    monkeypatch.setattr(sys, "argv", ["verify_corpus.py"])
    monkeypatch.setattr(vc, "ARTICLE_FINDER", vc.ARTICLE_FINDER)
    if not (vc.ARTICLE_FINDER / "ai-gold.py").is_file():
        pytest.skip("article-finder not installed; main() short-circuits to SKIP")
    code = vc.main()
    return code, capsys.readouterr().err


def test_shrunken_latest_view_is_refused(monkeypatch, capsys):
    """The 2026-09-17 shape: newest version covers 1, an older one covers 26."""
    code, err = _run_main(
        monkeypatch, capsys,
        stderr=_stderr(f"{FAMILY}@2.4.143-dev-2c8b0dd", 1, f"{FAMILY}@2.4.126", 26),
        expected=["10.1177__01461672251327169"],
    )
    assert "COVERAGE FLOOR: refusing" in err, err
    assert "holds 1 papers" in err and "holds 26" in err, err
    assert code == 1


def test_full_coverage_view_passes_the_floor(monkeypatch, capsys):
    """Control: an equal-coverage view must NOT be refused.

    Without this arm a floor that refused everything would satisfy the test
    above, and the gate would be dead in the opposite direction.
    """
    code, err = _run_main(
        monkeypatch, capsys,
        stderr=_stderr(f"{FAMILY}@2.4.143", 28, f"{FAMILY}@2.4.143", 28),
        expected=[],  # -> the documented SKIP, reached only past the floor
    )
    assert "coverage floor: OK" in err, err
    assert "COVERAGE FLOOR: refusing" not in err, err
    assert code == 0


def test_missing_coverage_line_is_a_refusal(monkeypatch, capsys):
    """An older custodian emits no LATEST-COVERAGE line -- that is not a pass."""
    code, err = _run_main(
        monkeypatch, capsys,
        stderr=_stderr(f"{FAMILY}@2.4.143", None, "", None),
        expected=["10.1177__01461672251327169"],
    )
    assert "reported no coverage" in err, err
    assert code == 1


def test_explicit_pin_is_not_failed_but_is_not_blessed(monkeypatch, capsys):
    """A pinned view skips the floor, and says that it did."""
    monkeypatch.setattr(sys, "argv",
                        ["verify_corpus.py", "--baseline-view", f"{FAMILY}@2.4.126"])
    monkeypatch.setattr(vc, "_expected_papers", lambda view: [])
    if not (vc.ARTICLE_FINDER / "ai-gold.py").is_file():
        pytest.skip("article-finder not installed")
    code = vc.main()
    err = capsys.readouterr().err
    assert "coverage floor: NOT APPLIED" in err, err
    assert code == 0


@pytest.mark.skipif(
    not (vc.ARTICLE_FINDER / "ai-gold.py").is_file(),
    reason="article-finder is not installed on this machine",
)
def test_live_family_latest_is_at_its_high_water_mark():
    """The real store, not a stub: today's default must not be a shrunken view.

    This is the alarm the gate could not raise for itself.  It fails while the
    newest registered baseline covers fewer papers than an older one, and the
    remedy is to carry the missing papers forward -- never to lower the floor.
    """
    res = vc._resolve_baseline_view(vc.DEFAULT_BASELINE_SPEC)
    assert res is not None, f"no registered baseline for {vc.DEFAULT_BASELINE_SPEC}"
    assert res.papers is not None, (
        "the custodian emitted no LATEST-COVERAGE line; article-finder is too "
        "old for this gate"
    )
    assert not res.shortfall, (
        f"{res.view} holds {res.papers} papers but {res.max_view} holds "
        f"{res.max_papers}. Re-baseline the missing papers at the released tag."
    )
