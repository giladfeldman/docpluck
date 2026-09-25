"""A single-paper run must not exit 0 when that paper was never compared.

WHY THIS IS A TEST.  Measured 2026-09-25:
``verify_corpus.py --paper 10.1109/access.2025.3645087`` printed ``PDF_DRIFT``
(the repository copy had become the IEEE version of record, the baseline was
built from the arXiv preprint) and then ``Exit 0 here means this paper passed``
-- and exited 0.  Nothing was rendered.  ``--paper`` skips the PARTIAL-coverage
refusal by design, and the final ``return`` only counted FAIL and ERROR, so a
paper that was SKIPPED (drifted source, no PDF, no baseline) read as a pass.
That is a green result from an empty input.

Each arm drives ``main()`` to the branch it names and asserts that branch's own
message fired, so a stub that never reaches it cannot pass.  The PASS arm is the
two-sided control: the fix must not turn a real single-paper pass red.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import verify_corpus as vc

KEY = "10.9999__example.single"
VIEW = "render-baseline__docpluck@9.9.9"


def _run(monkeypatch, capsys, tmp_path, *, baseline, pdf, drift=False, status="PASS",
         argv=None):
    if not (vc.ARTICLE_FINDER / "ai-gold.py").is_file():
        pytest.skip("article-finder not installed; main() short-circuits to SKIP")
    base = tmp_path / "base.md"
    base.write_text("# T\n\nbody\n", encoding="utf-8")
    src = tmp_path / "paper.pdf"
    src.write_bytes(b"%PDF-1.4 stand-in")
    sha = vc._sha256(src)
    monkeypatch.setattr(vc, "_resolve_baseline_view",
                        lambda spec: vc.Resolution(view=VIEW, pinned=True))
    monkeypatch.setattr(vc, "_expected_papers", lambda view: [KEY])
    monkeypatch.setattr(vc, "_baseline_for",
                        lambda key, view: (base, "0" * 64 if drift else sha) if baseline else (None, None))
    monkeypatch.setattr(vc, "_find_pdf", lambda key: src if pdf else None)
    monkeypatch.setattr(vc, "_run_render", lambda p: ("# T\n\nbody\n", 0.0))
    monkeypatch.setattr(vc, "_classify", lambda k, md, b: (status, {
        "char_ratio_vs_spike": 1.0, "jaccard_vs_spike": 1.0, "total_chars": 10,
        "section_count": 1, "table_html_count": 0, "longest_fig_caption_chars": 0,
    }, []))
    monkeypatch.setattr(sys, "argv", argv or ["verify_corpus.py", "--paper", KEY])
    code = vc.main()
    out = capsys.readouterr()
    return code, out.out + out.err


def test_drifted_paper_is_not_a_pass(monkeypatch, capsys, tmp_path):
    code, text = _run(monkeypatch, capsys, tmp_path, baseline=True, pdf=True, drift=True)
    assert "PDF_DRIFT" in text
    assert "NOT COMPARED" in text
    assert code == 1


def test_missing_pdf_is_not_a_pass(monkeypatch, capsys, tmp_path):
    code, text = _run(monkeypatch, capsys, tmp_path, baseline=True, pdf=False)
    assert "NO_PDF" in text
    assert "NOT COMPARED" in text
    assert code == 1


def test_missing_baseline_is_not_a_pass(monkeypatch, capsys, tmp_path):
    code, text = _run(monkeypatch, capsys, tmp_path, baseline=False, pdf=True)
    assert "NO_BASE" in text
    assert "NOT COMPARED" in text
    assert code == 1


def test_compared_passing_paper_still_exits_0(monkeypatch, capsys, tmp_path):
    code, text = _run(monkeypatch, capsys, tmp_path, baseline=True, pdf=True)
    assert "PASS" in text
    assert "NOT COMPARED" not in text
    assert code == 0


def test_compared_failing_paper_exits_1(monkeypatch, capsys, tmp_path):
    code, text = _run(monkeypatch, capsys, tmp_path, baseline=True, pdf=True, status="FAIL")
    assert "FAIL" in text
    assert code == 1


def test_diff_dump_lands_outside_the_repo(monkeypatch, capsys, tmp_path):
    """``--diff`` writes a render, i.e. publication text. It used to go to the
    repo's own ``tmp/`` -- gitignored, but the custody rule forbids article
    text in this repo even when ignored."""
    dump_root = tmp_path / "systemp"
    monkeypatch.setattr(vc.tempfile, "gettempdir", lambda: str(dump_root))
    code, text = _run(monkeypatch, capsys, tmp_path, baseline=True, pdf=True,
                      argv=["verify_corpus.py", "--paper", KEY, "--diff"])
    assert code == 0
    dumped = list(dump_root.rglob("*.rendered.md"))
    assert len(dumped) == 1, text
    assert REPO_ROOT.resolve() not in dumped[0].resolve().parents
    assert not (REPO_ROOT / "tmp" / f"{KEY}.rendered.md").exists()
