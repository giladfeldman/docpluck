"""The text-loss differential must SEE a deletion and be BLIND to a re-wrap.

Why this test exists (todo.md W-0007, 2026-08-28)
-------------------------------------------------
A normalization change deleted an article's title on
`10.1001/jamanetworkopen.2023.39337` -- the title line vanished in all ELEVEN of
its occurrences -- and three gates reported green, each blind for a different
reason: the idempotency test is satisfied BY a stable deletion, the canary held no
paper carrying the signature, and every count-based comparison scores furniture
removal and data loss identically.

`tools/diag/text_loss_differential.py` is the instrument that does see it. Three
weaker ones were built and rejected first, all defeated by the SAME false positive
-- a re-wrap read as a deletion. So the load-bearing property of this tool is not
"it catches deletions"; it is **it catches deletions WITHOUT catching re-wraps**,
and that is what these cases pin.

The mutations are applied to a REAL render rather than a hand-built fixture: a
synthetic string can only confirm the author's model of the defect. No publication
text is stored here -- the paper is fetched through article-finder at run time and
the test skips when it is unavailable (article-finder is the sole custodian).

Watched RED before it was trusted: an unguarded arm B reported 8 false losses on
the re-wrap case (`<tr>` 70x, the running head 10x) with nothing deleted at all,
which is instrument 1's defect reproduced. That is the `test_rewrap_is_not_loss`
case below.
"""

from __future__ import annotations

import importlib.util
import os
import re
import subprocess
import sys
import textwrap

import pytest

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_TOOL = os.path.join(_REPO, "tools", "diag", "text_loss_differential.py")


def _load_tool():
    spec = importlib.util.spec_from_file_location("text_loss_differential", _TOOL)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


tld = pytest.importorskip("importlib") and _load_tool()

DOI = "10.1001/jamanetworkopen.2023.39337"


def _render_via_article_finder(tmp_path) -> str:
    """Render the canary paper at HEAD. Skips if the paper is not in custody."""
    finder = os.path.expanduser("~/.claude/skills/article-finder/cache-check.py")
    if not os.path.exists(finder):
        pytest.skip("article-finder not present on this machine")
    probe = subprocess.run([sys.executable, finder, DOI], capture_output=True, text=True)
    if probe.returncode != 0 or '"found": true' not in probe.stdout:
        pytest.skip(f"{DOI} is not in article-finder custody on this machine")

    out = str(tmp_path / "render.md")
    r = subprocess.run(
        [sys.executable, os.path.join(_REPO, "tools", "render_for_audit.py"),
         "--key", DOI, "--out", out],
        capture_output=True, text=True, cwd=_REPO,
    )
    if r.returncode != 0 or not os.path.exists(out):
        pytest.skip(f"render_for_audit could not produce an artifact: {r.stderr[-300:]}")
    text = open(out, encoding="utf-8").read()
    # A probe that measured almost nothing reports a clean run. Assert the input.
    assert len(text) > 10_000, f"render is only {len(text)} chars - the probe is broken, not the tool"
    return text


@pytest.fixture(scope="module")
def rendered(tmp_path_factory):
    return _render_via_article_finder(tmp_path_factory.mktemp("w0007"))


def test_identical_is_not_loss(rendered):
    """The floor. An instrument that flags an unchanged document is unusable."""
    r = tld.compare(rendered, rendered)
    assert r["arm_a_deleted_spans"] == []
    assert r["arm_b_all_copies_gone"] == []
    assert r["loss"] is False


def test_rewrap_is_not_loss(rendered):
    """THE discriminating case -- it is what defeated the three rejected instruments.

    Re-wrapping moves every line boundary while deleting nothing. A line-multiset
    diff, a whole-line substring test, and an unguarded arm B all call this a
    deletion. The word-level collapse (arm A) and arm B's absent-from-collapsed-
    text clause must both stay silent.
    """
    rewrapped = "\n\n".join(
        textwrap.fill(p, width=57) for p in re.split(r"\n\s*\n", rendered)
    )
    assert rewrapped != rendered, "the re-wrap changed nothing - the control is inert"
    r = tld.compare(rendered, rewrapped)
    assert r["arm_a_deleted_spans"] == [], "arm A false-flagged a re-wrap"
    assert r["arm_b_all_copies_gone"] == [], "arm B false-flagged a re-wrap"
    assert r["loss"] is False


def test_deleted_statistic_is_caught_and_labelled(rendered):
    """Arm A must see a removed statistic AND mark it as carrying one."""
    m = re.search(r"^.*\d+\.\d+.*\(.*\d+\.\d+.*\).*$", rendered, re.MULTILINE)
    assert m, "no statistic-shaped line in the render - the control cannot be built"
    sabotaged = rendered.replace(m.group(0) + "\n", "", 1)
    assert sabotaged != rendered

    r = tld.compare(rendered, sabotaged)
    assert r["loss"] is True
    assert r["arm_a_deleted_spans"], "arm A missed a deleted statistic"
    assert r["arm_a_spans_carrying_statistics"], \
        "the deleted span was found but not labelled as carrying a statistic"


def test_all_copies_gone_is_caught(rendered):
    """Arm B must see the JAMA signature: a repeated line losing EVERY copy.

    Arm A alone is not sufficient here in general -- a title is not statistical
    content, so it lands in the non-statistical bucket and only arm B names it as
    the all-copies-gone shape.
    """
    counts = tld.line_counts(rendered)
    repeated = [ln for ln, n in counts.items() if n >= tld.MIN_COPIES and len(ln) > 20]
    if not repeated:
        pytest.skip("this render carries no line repeated >=MIN_COPIES times")
    victim = repeated[0]
    stripped = rendered.replace(victim, "")

    r = tld.compare(rendered, stripped)
    assert r["loss"] is True
    hits = [g["excerpt"] for g in r["arm_b_all_copies_gone"]]
    assert any(victim[:60] in h for h in hits), \
        f"arm B did not name the line that lost all {counts[victim]} copies"


def test_empty_after_is_never_a_pass(rendered):
    """A total wipe is the largest possible loss and must never read as clean."""
    r = tld.compare(rendered, "")
    assert r["loss"] is True


def test_empty_before_is_a_setup_error_not_a_green(tmp_path):
    """A green computed from an empty reference is the false green this tool exists
    to prevent, so the CLI must exit 2 (setup error) rather than 0."""
    before = tmp_path / "before.md"
    after = tmp_path / "after.md"
    before.write_text("", encoding="utf-8")
    after.write_text("anything at all\n", encoding="utf-8")
    r = subprocess.run(
        [sys.executable, _TOOL, "--before", str(before), "--after", str(after)],
        capture_output=True, text=True,
    )
    assert r.returncode == 2, f"expected setup-error exit 2, got {r.returncode}"


def test_two_single_files_are_compared_regardless_of_name(tmp_path):
    """Regression: the CLI matched by basename, so two differently-named files
    compared NOTHING and reported a setup error. Found by this tool's own controls
    on 2026-08-28, on the most common invocation there is."""
    a, b = tmp_path / "one.md", tmp_path / "two.md"
    body = "alpha beta gamma delta epsilon zeta eta theta\n" * 40
    a.write_text(body, encoding="utf-8")
    b.write_text(body, encoding="utf-8")
    r = subprocess.run(
        [sys.executable, _TOOL, "--before", str(a), "--after", str(b)],
        capture_output=True, text=True,
    )
    assert r.returncode == 0, f"expected a clean compare, got {r.returncode}: {r.stderr[-200:]}"
    assert "no loss detected" in r.stdout
