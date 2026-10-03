"""harness check_glyph: a U+FFFD the paper's own text layer carries is exempt, but an
EMPTY following token (U+FFFD then whitespace/markup) carries no identity, so the
exemption there is by count -- one raw copy must not excuse every rendered one.

Review 2026-10-03 of c5a75e3: raw "a \ufffd b" and a render with three U+FFFD
followed by whitespace returned verdict 'pass' (set membership of the empty token).
Neutral strings only; no paper text lives in this repo.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from scripts.harness import checks  # noqa: E402


def _run(tmp_path, raw, rendered):
    (tmp_path / "raw.txt").write_text(raw, encoding="utf-8")
    (tmp_path / "rendered.md").write_text(rendered, encoding="utf-8")
    return checks.check_glyph(tmp_path, "pdf")


def test_extra_bare_fffd_beyond_the_raw_count_fails(tmp_path):
    r = _run(tmp_path, "a � b", "a � b and � c and � d")
    assert r["verdict"] == "fail" and r["replacement_char"] == 2


def test_the_papers_own_bare_fffd_passes(tmp_path):
    assert _run(tmp_path, "a � b", "a � b")["verdict"] == "pass"


def test_a_repeated_own_glyph_with_a_named_token_still_passes(tmp_path):
    # the table channel re-reads printed glyphs: more copies than raw, none introduced
    raw = "x �5 y"
    assert _run(tmp_path, raw, "x �5 y | �5 | �5")["verdict"] == "pass"


def test_a_new_named_token_fails(tmp_path):
    r = _run(tmp_path, "x �5 y", "x �5 y �9")
    assert r["verdict"] == "fail" and r["replacement_char"] == 1
