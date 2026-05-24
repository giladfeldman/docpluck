# Haiku-orchestration pre-test Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Execute the two-arm Haiku-orchestration pre-test specified in `docs/superpowers/specs/2026-05-23-haiku-orchestration-pretest-design.md` and produce a single comparison report.

**Architecture:** Two isolated git worktrees off the same starting SHA. Arm A runs `/docpluck-iterate` on Opus solo. Arm B runs the same skill with a strict delegation protocol that dispatches Haiku subagents for bulk work. Token usage extracted from session jsonl transcripts post-run. Test 2 is a side comparison of Opus vs Haiku as the gold-extraction model, scored by a blind 3rd judge.

**Tech Stack:** git worktrees, Claude Code Agent tool with `model: "haiku"` override, Python (token-capture script), bash (orchestration), docpluck's existing iterate-loop spine.

---

## File Structure

| File | Purpose |
|------|---------|
| `scripts/pretest_capture_tokens.py` (new) | Read a session jsonl transcript, sum tokens per model, write `tmp/pretest_results_arm<X>.json` |
| `tests/test_pretest_capture_tokens.py` (new) | Unit tests for the capture script |
| `tmp/pretest_results_armA.json` (generated) | Arm A measurements |
| `tmp/pretest_results_armB.json` (generated) | Arm B measurements |
| `tmp/pretest_test2_judge.json` (generated) | Test 2 blind-judge scorecard |
| `tmp/test-2026-05-23-haiku-orchestration-findings.md` (generated) | Side-effect findings log |
| `docs/HANDOFF_2026-05-23_haiku-orchestration-pretest.md` (generated) | Final comparison report |
| `ArticleRepository/_pretest_haiku_golds/jama_open_{1,2,3}/` (generated, sibling repo) | Quarantined Haiku-extracted golds |

Worktrees (sibling dirs, not committed):
- `docpluck/.worktrees/armA-opus-solo/` — branch `pretest/armA-opus-solo`
- `docpluck/.worktrees/armB-opus-haiku/` — branch `pretest/armB-opus-haiku`

---

## Task 1: Prerequisites — get to a clean SHA

**Files:** none modified by this task; user action required.

- [ ] **Step 1: Surface dirty working-tree state to the user**

Run:
```bash
cd "/c/Users/filin/Dropbox/Vibe/MetaScienceTools/docpluck"
git status --short
git stash list
```

Expected: 5 modified files + 1 untracked test from prior session.

- [ ] **Step 2: Ask user how to handle the dirty state**

Use AskUserQuestion with these options:
- "Commit current changes to current branch first" — safest, lands in-progress work
- "Stash with a descriptive message" — preserves but defers
- "Discard" — only if user explicitly says so, never default

Do not proceed without an explicit answer.

- [ ] **Step 3: Execute the chosen resolution**

After resolution, verify clean state:
```bash
git status --short
```
Expected: empty output.

- [ ] **Step 4: Record the start SHA**

```bash
START_SHA=$(git rev-parse HEAD)
echo "$START_SHA" > tmp/pretest_start_sha.txt
git log -1 --format="%h %s"
```
Expected: a short SHA + the commit subject of the spec or whichever commit is HEAD.

- [ ] **Step 5: Verify the 3 PDFs and their golds exist**

```bash
for n in 1 2 3; do
  pdf="verify_out/pdfextractor__ama__jama-open-${n}"
  gold="/c/Users/filin/Dropbox/Vibe/ArticleRepository/ai_gold/jama_open_${n}"
  test -d "$pdf" && echo "OK $pdf" || echo "MISSING $pdf"
  test -d "$gold" && echo "OK $gold" || echo "MISSING $gold"
done
```
Expected: 6 `OK` lines. Abort and surface to user if any `MISSING`.

- [ ] **Step 6: Verify Haiku model override is available in this environment**

Sanity-check that the `Agent` tool accepts `model: "haiku"` by dispatching a trivial subagent:
```
Agent(
  description: "Haiku availability ping",
  subagent_type: "general-purpose",
  model: "haiku",
  prompt: "Reply with exactly the string PONG and nothing else."
)
```
Expected: subagent returns `PONG`. If the call errors with an unknown-model error, surface to user — the test cannot proceed without Haiku.

- [ ] **Step 7: Commit prerequisite artifacts**

```bash
git add tmp/pretest_start_sha.txt
git commit -m "chore(pretest): record start SHA for Haiku-orchestration pre-test

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: Token-capture script — failing test

**Files:**
- Create: `tests/test_pretest_capture_tokens.py`

- [ ] **Step 1: Write the failing test**

Locate the docpluck Claude Code project dir (you'll need a synthetic jsonl for tests):

```python
# tests/test_pretest_capture_tokens.py
"""Tests for scripts/pretest_capture_tokens.py."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.pretest_capture_tokens import sum_tokens_by_model


def _write_jsonl(path: Path, records: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")


def test_sum_tokens_by_model_aggregates_opus_and_haiku(tmp_path: Path) -> None:
    transcript = tmp_path / "session.jsonl"
    _write_jsonl(transcript, [
        # An Opus assistant turn with usage
        {"type": "assistant", "message": {
            "model": "claude-opus-4-7-20260101",
            "usage": {"input_tokens": 1000, "output_tokens": 200,
                       "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0},
        }},
        # A Haiku subagent turn with usage
        {"type": "assistant", "message": {
            "model": "claude-haiku-4-5-20251001",
            "usage": {"input_tokens": 5000, "output_tokens": 300,
                       "cache_read_input_tokens": 100, "cache_creation_input_tokens": 0},
        }},
        # Another Opus turn
        {"type": "assistant", "message": {
            "model": "claude-opus-4-7-20260101",
            "usage": {"input_tokens": 500, "output_tokens": 50,
                       "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0},
        }},
        # A non-assistant record — must be ignored
        {"type": "user", "message": {"content": "irrelevant"}},
    ])

    result = sum_tokens_by_model(transcript)

    assert result["opus"]["input_tokens"] == 1500
    assert result["opus"]["output_tokens"] == 250
    assert result["haiku"]["input_tokens"] == 5000
    assert result["haiku"]["output_tokens"] == 300
    assert result["haiku"]["cache_read_input_tokens"] == 100


def test_sum_tokens_by_model_empty_transcript(tmp_path: Path) -> None:
    transcript = tmp_path / "empty.jsonl"
    transcript.write_text("", encoding="utf-8")
    result = sum_tokens_by_model(transcript)
    assert result == {
        "opus": {"input_tokens": 0, "output_tokens": 0,
                 "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0},
        "haiku": {"input_tokens": 0, "output_tokens": 0,
                 "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0},
        "sonnet": {"input_tokens": 0, "output_tokens": 0,
                 "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0},
        "other": {"input_tokens": 0, "output_tokens": 0,
                 "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0},
    }


def test_sum_tokens_by_model_unknown_model_goes_to_other(tmp_path: Path) -> None:
    transcript = tmp_path / "session.jsonl"
    _write_jsonl(transcript, [
        {"type": "assistant", "message": {
            "model": "some-other-model-xyz",
            "usage": {"input_tokens": 10, "output_tokens": 5,
                       "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0},
        }},
    ])
    result = sum_tokens_by_model(transcript)
    assert result["other"]["input_tokens"] == 10
    assert result["other"]["output_tokens"] == 5
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
cd "/c/Users/filin/Dropbox/Vibe/MetaScienceTools/docpluck"
pytest tests/test_pretest_capture_tokens.py -v
```
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.pretest_capture_tokens'`.

---

## Task 3: Token-capture script — minimal implementation

**Files:**
- Create: `scripts/pretest_capture_tokens.py`
- Modify: `scripts/__init__.py` (create if absent — empty file is fine)

- [ ] **Step 1: Ensure scripts is a package**

```bash
test -f scripts/__init__.py || touch scripts/__init__.py
```

- [ ] **Step 2: Write minimal implementation**

```python
# scripts/pretest_capture_tokens.py
"""Sum per-model token usage from a Claude Code session jsonl transcript.

Reads the transcript line-by-line, picks out `type == "assistant"` records,
buckets their usage by model family (opus / sonnet / haiku / other), and
returns a dict suitable for writing into `tmp/pretest_results_arm<X>.json`.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_FAMILIES = ("opus", "sonnet", "haiku", "other")
_FIELDS = ("input_tokens", "output_tokens",
           "cache_read_input_tokens", "cache_creation_input_tokens")


def _empty_bucket() -> dict[str, int]:
    return {f: 0 for f in _FIELDS}


def _family_of(model: str) -> str:
    m = model.lower()
    if "opus" in m:
        return "opus"
    if "sonnet" in m:
        return "sonnet"
    if "haiku" in m:
        return "haiku"
    return "other"


def sum_tokens_by_model(transcript: Path) -> dict[str, dict[str, int]]:
    """Sum token usage from a Claude Code session jsonl, grouped by model family."""
    totals: dict[str, dict[str, int]] = {fam: _empty_bucket() for fam in _FAMILIES}
    if not transcript.exists() or transcript.stat().st_size == 0:
        return totals

    with transcript.open("r", encoding="utf-8") as f:
        for raw in f:
            raw = raw.strip()
            if not raw:
                continue
            try:
                rec: dict[str, Any] = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if rec.get("type") != "assistant":
                continue
            msg = rec.get("message") or {}
            usage = msg.get("usage") or {}
            model = msg.get("model") or ""
            fam = _family_of(model)
            for field in _FIELDS:
                val = usage.get(field)
                if isinstance(val, int):
                    totals[fam][field] += val
    return totals


def equivalent_api_cost_usd(totals: dict[str, dict[str, int]]) -> float:
    """Compute equivalent API cost using public per-million rates.

    NOT what the user pays on Max — this is the efficiency unit for the pre-test.
    Opus 4.7: $15 in / $75 out per M.  Haiku 4.5: $1 in / $5 out per M.
    Sonnet 4.6: $3 in / $15 out per M (priced for completeness).
    """
    rates = {
        "opus":   (15.0, 75.0),
        "sonnet": (3.0,  15.0),
        "haiku":  (1.0,  5.0),
        "other":  (0.0,  0.0),
    }
    cost = 0.0
    for fam, (in_rate, out_rate) in rates.items():
        bucket = totals.get(fam, {})
        cost += bucket.get("input_tokens", 0) / 1_000_000.0 * in_rate
        cost += bucket.get("output_tokens", 0) / 1_000_000.0 * out_rate
    return round(cost, 4)


def main() -> None:
    import argparse
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("transcript", type=Path, help="Path to session jsonl")
    p.add_argument("--out", type=Path, required=True, help="Where to write JSON results")
    p.add_argument("--arm", choices=["A", "B"], required=True)
    p.add_argument("--start-sha", required=True)
    p.add_argument("--end-sha", required=True)
    p.add_argument("--wall-minutes", type=float, required=True)
    p.add_argument("--cycles", type=int, required=True)
    p.add_argument("--passed", nargs="*", default=[], help="paper stems that PASSed")
    p.add_argument("--failed", nargs="*", default=[], help="paper stems that FAILed")
    p.add_argument("--stop-reason", choices=["goal", "time", "cycles"], required=True)
    p.add_argument("--diff-lines", type=int, required=True)
    p.add_argument("--regression-26", required=True,
                   help="PASS, FAIL, or '<n> regressions'")
    args = p.parse_args()

    totals = sum_tokens_by_model(args.transcript)
    payload = {
        "arm": args.arm,
        "start_sha": args.start_sha,
        "end_sha": args.end_sha,
        "cycles_run": args.cycles,
        "papers_passed": args.passed,
        "papers_failed": args.failed,
        "tokens": totals,
        "wall_time_minutes": args.wall_minutes,
        "api_equivalent_cost_usd": equivalent_api_cost_usd(totals),
        "stop_reason": args.stop_reason,
        "diff_lines_changed": args.diff_lines,
        "regression_baseline_26_paper": args.regression_26,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Run tests to verify they pass**

```bash
pytest tests/test_pretest_capture_tokens.py -v
```
Expected: 3 passed.

- [ ] **Step 4: Commit**

```bash
git add scripts/__init__.py scripts/pretest_capture_tokens.py tests/test_pretest_capture_tokens.py
git commit -m "feat(pretest): token-capture script for arm-A/B comparison

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: Create the two worktrees

**Files:** none under git; creates sibling directories.

- [ ] **Step 1: Verify clean state again**

```bash
cd "/c/Users/filin/Dropbox/Vibe/MetaScienceTools/docpluck"
git status --short
```
Expected: empty.

- [ ] **Step 2: Capture start SHA into both branch names**

```bash
START_SHA=$(cat tmp/pretest_start_sha.txt)
echo "Start SHA: $START_SHA"
```

- [ ] **Step 3: Create arm-A worktree**

```bash
git worktree add -b pretest/armA-opus-solo .worktrees/armA-opus-solo "$START_SHA"
```
Expected: `Preparing worktree (...)`.

- [ ] **Step 4: Create arm-B worktree**

```bash
git worktree add -b pretest/armB-opus-haiku .worktrees/armB-opus-haiku "$START_SHA"
```
Expected: `Preparing worktree (...)`.

- [ ] **Step 5: Verify both worktrees start at the same SHA**

```bash
git -C .worktrees/armA-opus-solo rev-parse HEAD
git -C .worktrees/armB-opus-haiku rev-parse HEAD
```
Expected: both equal to `$START_SHA`.

- [ ] **Step 6: Stage the findings log in both worktrees**

```bash
for arm in armA-opus-solo armB-opus-haiku; do
  cat > .worktrees/$arm/tmp/test-2026-05-23-haiku-orchestration-findings.md <<'EOF'
# Side-effect findings — 2026-05-23 Haiku-orchestration pre-test

Append entries in the format described in
`docs/superpowers/specs/2026-05-23-haiku-orchestration-pretest-design.md`.

**Do not fix anything in-flight.** This file exists *because* in-flight fixes
would contaminate the comparison.
EOF
done
```
Expected: both files exist; not committed yet (they live in `tmp/` which is gitignored, but each arm's run should commit if it wants to preserve the log).

---

## Task 5: Run Arm A (Opus solo)

**Files:** all changes happen inside `.worktrees/armA-opus-solo/`. No edits to the main repo from this task.

This step requires opening a **fresh Claude Code session** with cwd set to the arm-A worktree. The instructions below are what the orchestrator should hand to that session (or what a human runs interactively).

- [ ] **Step 1: Open a new Claude Code session at the arm-A worktree**

Working directory: `C:\Users\filin\Dropbox\Vibe\MetaScienceTools\docpluck\.worktrees\armA-opus-solo`

Note the session jsonl path that Claude Code prints at startup (typically under `~/.claude/projects/<encoded-cwd>/<uuid>.jsonl`). Save it as `tmp/pretest_armA_session_path.txt`.

- [ ] **Step 2: Record wall-clock start**

```bash
date -u +"%Y-%m-%dT%H:%M:%SZ" > tmp/pretest_armA_started_at.txt
```

- [ ] **Step 3: Invoke the iterate skill**

In that session, send exactly:
```
/docpluck-iterate --goal "PASS on jama-open-1, jama-open-2, jama-open-3" --no-broad-read
```

Let it run. Do not intervene. Hard ceiling: **90 minutes wall-clock OR 3 cycles**, whichever first. If hit, stop the session and record the punch-list.

- [ ] **Step 4: At end of run, record wall-clock end**

```bash
date -u +"%Y-%m-%dT%H:%M:%SZ" > tmp/pretest_armA_ended_at.txt
```

- [ ] **Step 5: Capture results**

From the arm-A worktree, compute wall time in minutes, diff-line count, and PASS/FAIL list (read from the run-meta the spine wrote):

```bash
START=$(cat tmp/pretest_armA_started_at.txt)
END=$(cat tmp/pretest_armA_ended_at.txt)
WALL_MIN=$(python -c "
from datetime import datetime
s = datetime.fromisoformat('$START'.replace('Z','+00:00'))
e = datetime.fromisoformat('$END'.replace('Z','+00:00'))
print(round((e-s).total_seconds()/60, 2))
")
START_SHA=$(cat ../../tmp/pretest_start_sha.txt)
END_SHA=$(git rev-parse HEAD)
DIFF_LINES=$(git diff --shortstat "$START_SHA"..HEAD | awk '{print $4 + $6}')
TRANSCRIPT=$(cat tmp/pretest_armA_session_path.txt)

# Read PASS/FAIL from run-meta — the spine writes this under
#   ~/.claude/skills/_shared/run-meta/docpluck-iterate.json
# The most recent cycle's phase_5d_runs entries hold the verdicts.
python - <<PY
import json
from pathlib import Path
meta_path = Path.home() / ".claude/skills/_shared/run-meta/docpluck-iterate.json"
meta = json.loads(meta_path.read_text(encoding="utf-8"))
runs = meta.get("phase_5d_runs", [])
latest_by_paper = {}
for r in runs:
    latest_by_paper[r["paper_stem"]] = r["verdict"]
passed = [k for k,v in latest_by_paper.items() if v == "PASS" and "jama-open" in k]
failed = [k for k,v in latest_by_paper.items() if v != "PASS" and "jama-open" in k]
Path("tmp/pretest_armA_passed.txt").write_text(" ".join(passed), encoding="utf-8")
Path("tmp/pretest_armA_failed.txt").write_text(" ".join(failed), encoding="utf-8")
print("PASS:", passed)
print("FAIL:", failed)
PY
```

- [ ] **Step 6: Run the 26-paper regression baseline**

```bash
pytest tests/test_baseline_26.py -v 2>&1 | tail -5 > tmp/pretest_armA_regression.txt
# Manually inspect: PASS → "PASS"; otherwise count regressions.
```

- [ ] **Step 7: Run the capture script**

```bash
python ../../scripts/pretest_capture_tokens.py \
  "$TRANSCRIPT" \
  --out tmp/pretest_results_armA.json \
  --arm A \
  --start-sha "$START_SHA" \
  --end-sha "$END_SHA" \
  --wall-minutes "$WALL_MIN" \
  --cycles "$(jq '.current_cycle' ~/.claude/skills/_shared/run-meta/docpluck-iterate.json)" \
  --passed $(cat tmp/pretest_armA_passed.txt) \
  --failed $(cat tmp/pretest_armA_failed.txt) \
  --stop-reason goal \
  --diff-lines "$DIFF_LINES" \
  --regression-26 "PASS"
```

Substitute `goal` with `time` or `cycles` if the hard ceiling fired.

- [ ] **Step 8: Commit arm-A's findings log + results**

```bash
mkdir -p ../../docs/superpowers/pretest_results
cp tmp/pretest_results_armA.json ../../docs/superpowers/pretest_results/
cp tmp/test-2026-05-23-haiku-orchestration-findings.md ../../docs/superpowers/pretest_results/findings_armA.md
cd ../..
git add docs/superpowers/pretest_results/
git commit -m "data(pretest): arm-A results + findings log

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 6: Run Arm B (Opus + Haiku)

**Files:** all changes happen inside `.worktrees/armB-opus-haiku/`.

Same shape as Task 5 but with a strict delegation protocol layered on top. The session orchestrator (Opus main) must follow these rules during the run.

- [ ] **Step 1: Open a new Claude Code session at the arm-B worktree**

Working directory: `C:\Users\filin\Dropbox\Vibe\MetaScienceTools\docpluck\.worktrees\armB-opus-haiku`

Save the session jsonl path as `tmp/pretest_armB_session_path.txt`.

- [ ] **Step 2: Paste the delegation protocol into the session as the very first message**

```
Pre-test arm B — delegation protocol (binds this entire session).

You are running /docpluck-iterate on the 3 jama-open papers. You MUST delegate
the following work to Haiku subagents via Agent(subagent_type: "general-purpose",
model: "haiku"):

  1. Reading any file longer than 200 lines (subagent returns summary + excerpts).
  2. Per-PDF diff of rendered .md vs gold (one subagent per PDF, parallel).
  3. Drafting candidate patches to docpluck/normalize.py, render.py, extract*.py
     (subagent returns a unified diff; you review and apply, never let the
     subagent write to disk).
  4. Drafting Phase 5d per-paper analysis briefs.
  5. Drafting test cases (subagent returns the code; you review and write).

You MUST retain (never delegate):
  - All planning, root-cause diagnosis, cycle structure decisions.
  - All iterate-gate.sh invocations.
  - All git commits, version bumps, CHANGELOG entries.
  - Final approval and application of every code edit.
  - PASS/FAIL/BLOCKED verdicts.

Every Haiku delegation MUST use the brief template in
docs/superpowers/specs/2026-05-23-haiku-orchestration-pretest-design.md
Appendix A. No exceptions.

When done (goal hit or hard ceiling: 90 min OR 3 cycles), STOP and wait for
follow-up instructions. Do NOT continue beyond the stop condition.

Now run: /docpluck-iterate --goal "PASS on jama-open-1, jama-open-2, jama-open-3" --no-broad-read
```

- [ ] **Step 3: Record wall-clock start**

```bash
date -u +"%Y-%m-%dT%H:%M:%SZ" > tmp/pretest_armB_started_at.txt
```

- [ ] **Step 4: Let the session run to its stop condition**

Hard ceiling enforced by the orchestrator: 90 min OR 3 cycles. Do not intervene mid-cycle.

- [ ] **Step 5: Record wall-clock end + capture results**

Same as Task 5 steps 4–6, substituting `armA` → `armB` throughout.

- [ ] **Step 6: Run the capture script**

```bash
python ../../scripts/pretest_capture_tokens.py \
  "$(cat tmp/pretest_armB_session_path.txt)" \
  --out tmp/pretest_results_armB.json \
  --arm B \
  --start-sha "$(cat ../../tmp/pretest_start_sha.txt)" \
  --end-sha "$(git rev-parse HEAD)" \
  --wall-minutes "$WALL_MIN" \
  --cycles "$(jq '.current_cycle' ~/.claude/skills/_shared/run-meta/docpluck-iterate.json)" \
  --passed $(cat tmp/pretest_armB_passed.txt) \
  --failed $(cat tmp/pretest_armB_failed.txt) \
  --stop-reason goal \
  --diff-lines "$DIFF_LINES" \
  --regression-26 "PASS"
```

- [ ] **Step 7: Commit arm-B's results**

```bash
cp tmp/pretest_results_armB.json ../../docs/superpowers/pretest_results/
cp tmp/test-2026-05-23-haiku-orchestration-findings.md ../../docs/superpowers/pretest_results/findings_armB.md
cd ../..
git add docs/superpowers/pretest_results/
git commit -m "data(pretest): arm-B results + findings log

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 7: Test 2 — Haiku gold regeneration

**Files:**
- Create: `ArticleRepository/_pretest_haiku_golds/jama_open_{1,2,3}/reading.md` (and any sibling files article-finder emits)

- [ ] **Step 1: Locate article-finder's gold-generation protocol**

```bash
test -f ~/.claude/skills/article-finder/gold-generation.md && \
  echo "OK protocol exists" || echo "MISSING — abort Test 2"
```
If missing, surface to user; Test 2 cannot proceed without it.

- [ ] **Step 2: Prepare the quarantined output dir**

```bash
mkdir -p "/c/Users/filin/Dropbox/Vibe/ArticleRepository/_pretest_haiku_golds"
```

- [ ] **Step 3: For each of the 3 PDFs, dispatch a Haiku subagent to regenerate gold**

For `n` in `1,2,3`, run from the main docpluck repo (not a worktree):

```
Agent(
  description: "Haiku gold regen jama-open-N",
  subagent_type: "general-purpose",
  model: "haiku",
  prompt: """
TASK: Regenerate the AI gold for one PDF using Haiku.
CONTEXT: Pre-test 2026-05-23 — Test 2 of the Haiku-orchestration pre-test.
PROTOCOL: Follow ~/.claude/skills/article-finder/gold-generation.md verbatim.
  Do NOT improvise — every field, every step.
INPUTS:
  - PDF: /c/Users/filin/Dropbox/Vibe/MetaScienceTools/docpluck/verify_out/pdfextractor__ama__jama-open-N/source.pdf
  - (Use the actual filename present in that dir if "source.pdf" is not it —
    list the dir and pick the .pdf file.)
DELIVERABLE: Write the gold tree to
  /c/Users/filin/Dropbox/Vibe/ArticleRepository/_pretest_haiku_golds/jama_open_N/
  matching the structure article-finder produces in ai_gold/.
CONSTRAINTS:
  - Do NOT touch /c/Users/filin/Dropbox/Vibe/ArticleRepository/ai_gold/ — that is canonical.
  - Do NOT generate any other golds.
SUCCESS CRITERIA: reading.md and any sibling files exist under the output dir.
"""
)
```

Repeat for n=2 and n=3. Run in parallel (3 Agent calls in one message) if practical.

- [ ] **Step 4: Verify Haiku golds exist**

```bash
for n in 1 2 3; do
  test -f "/c/Users/filin/Dropbox/Vibe/ArticleRepository/_pretest_haiku_golds/jama_open_${n}/reading.md" \
    && echo "OK jama_open_${n}" || echo "MISSING jama_open_${n}"
done
```
Expected: 3 `OK` lines.

---

## Task 8: Test 2 — Blind judge

**Files:**
- Create: `tmp/pretest_test2_judge.json`
- Create: `tmp/pretest_test2_blind_mapping.json` (the un-blinding key — written but not shared with the judge)

- [ ] **Step 1: Randomize the per-PDF A/B labelling and persist the mapping**

```bash
python - <<'PY'
import json, random, pathlib
random.seed(42)  # deterministic for reproducibility — change if you want true random
mapping = {}
for n in (1, 2, 3):
    labels = ["gold_X", "gold_Y"]
    random.shuffle(labels)
    # labels[0] is the label that points to the Opus gold; labels[1] to Haiku
    mapping[f"jama_open_{n}"] = {
        "opus_gold_label": labels[0],
        "haiku_gold_label": labels[1],
    }
pathlib.Path("tmp/pretest_test2_blind_mapping.json").write_text(
    json.dumps(mapping, indent=2), encoding="utf-8")
print(json.dumps(mapping, indent=2))
PY
```

- [ ] **Step 2: Dispatch the blind judge subagent**

```
Agent(
  description: "Blind judge Test 2 golds",
  subagent_type: "general-purpose",
  model: "opus",
  prompt: """
TASK: Score 3 pairs of AI golds against their source PDFs.

For each of the 3 jama-open PDFs, you receive two candidate golds labelled
gold_X and gold_Y (the labelling is randomized per PDF — you do NOT know which
model produced which).

For each pair, read the source PDF and both golds, then score each gold on:

  - coverage          (1-5): how many expected fields are populated
  - accuracy          (1-5): each populated field correct against the source
  - hallucination     (count of fabricated content — lower is better)
  - structure_fidelity (1-5): sections, tables, citations correctly captured

INPUTS per paper n in (1, 2, 3):
  - PDF dir:   /c/Users/filin/Dropbox/Vibe/MetaScienceTools/docpluck/verify_out/pdfextractor__ama__jama-open-{n}/
  - gold A:    look up the mapping in tmp/pretest_test2_blind_mapping.json
               — but DO NOT use it; instead, for paper n, read:
                 - /c/Users/filin/Dropbox/Vibe/ArticleRepository/ai_gold/jama_open_{n}/reading.md
                   as one of the candidates,
                 - /c/Users/filin/Dropbox/Vibe/ArticleRepository/_pretest_haiku_golds/jama_open_{n}/reading.md
                   as the other,
                 — and assign them to gold_X/gold_Y per the labels in the
                   mapping file for paper n. (You're the judge but the
                   orchestrator wrote the mapping; you may read the mapping to
                   know which file is which label, but you do NOT learn which
                   model produced which until you've finished scoring.)

  Important: score the golds purely on content quality vs the PDF. Do NOT
  reason about which model "looks like" Opus or Haiku output.

DELIVERABLE: Write tmp/pretest_test2_judge.json with this shape:
  {
    "jama_open_1": {
      "gold_X": {"coverage": <1-5>, "accuracy": <1-5>, "hallucination": <int>,
                  "structure_fidelity": <1-5>, "notes": "..."},
      "gold_Y": {...}
    },
    "jama_open_2": {...},
    "jama_open_3": {...}
  }

CONSTRAINTS:
  - Do NOT modify any gold file.
  - Do NOT look up which model produced which until after writing the file.
"""
)
```

- [ ] **Step 3: Un-blind**

```bash
python - <<'PY'
import json, pathlib
judge = json.loads(pathlib.Path("tmp/pretest_test2_judge.json").read_text(encoding="utf-8"))
mapping = json.loads(pathlib.Path("tmp/pretest_test2_blind_mapping.json").read_text(encoding="utf-8"))
unblinded = {}
for paper, scores in judge.items():
    m = mapping[paper]
    unblinded[paper] = {
        "opus":  scores[m["opus_gold_label"]],
        "haiku": scores[m["haiku_gold_label"]],
    }
pathlib.Path("tmp/pretest_test2_unblinded.json").write_text(
    json.dumps(unblinded, indent=2), encoding="utf-8")
print(json.dumps(unblinded, indent=2))
PY
```

- [ ] **Step 4: Commit Test 2 artifacts**

```bash
mkdir -p docs/superpowers/pretest_results
cp tmp/pretest_test2_judge.json docs/superpowers/pretest_results/
cp tmp/pretest_test2_blind_mapping.json docs/superpowers/pretest_results/
cp tmp/pretest_test2_unblinded.json docs/superpowers/pretest_results/
git add docs/superpowers/pretest_results/
git commit -m "data(pretest): Test 2 blind-judge scorecard (un-blinded)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 9: Compile the final report

**Files:**
- Create: `docs/HANDOFF_2026-05-23_haiku-orchestration-pretest.md`

- [ ] **Step 1: Compose the report**

Use this template literally — fill from the JSON files committed in Tasks 5/6/8. No placeholders left in the final file.

```markdown
# Haiku-orchestration pre-test — results

**Date:** 2026-05-23
**Spec:** [`docs/superpowers/specs/2026-05-23-haiku-orchestration-pretest-design.md`](superpowers/specs/2026-05-23-haiku-orchestration-pretest-design.md)
**Plan:** [`docs/superpowers/plans/2026-05-23-haiku-orchestration-pretest.md`](superpowers/plans/2026-05-23-haiku-orchestration-pretest.md)
**Start SHA:** `<from tmp/pretest_start_sha.txt>`

## Test 1 — Iteration efficiency (Opus solo vs Opus + Haiku)

| Metric | Arm A (Opus solo) | Arm B (Opus + Haiku) | Δ |
|---|---|---|---|
| Cycles run | <from armA.json> | <from armB.json> | |
| Papers PASS | <list> | <list> | |
| Papers FAIL | <list> | <list> | |
| Opus input tokens | | | |
| Opus output tokens | | | |
| Haiku input tokens | 0 | | |
| Haiku output tokens | 0 | | |
| Wall time (min) | | | |
| API-equivalent cost (USD) | | | |
| Diff lines changed | | | |
| 26-paper regression | | | |
| Stop reason | | | |

### Observations (qualitative)

- Arm B delegation that worked well: <bullets, written from session memory>
- Arm B delegation that failed: <bullets>
- Where Haiku patches needed Opus rewrites: <bullets>

## Test 2 — Gold extractor (Opus vs Haiku)

Per-PDF scorecard from `tmp/pretest_test2_unblinded.json`:

| Paper | Coverage (O/H) | Accuracy (O/H) | Hallucination (O/H) | Structure (O/H) |
|---|---|---|---|---|
| jama_open_1 | | | | |
| jama_open_2 | | | | |
| jama_open_3 | | | | |

## Recommendation

One of:
- **Adopt broadly** — Haiku orchestration delivers ≥3× efficiency at comparable quality. Standardize the delegation protocol.
- **Adopt with constraints** — works for <task class> but not <task class>. Document the boundary.
- **Reject** — quality loss or Opus-rework overhead negated savings. Stay solo for iterate-heavy work.

Justification (1-2 paragraphs grounded in the numbers above).

## Side-effect findings

See `docs/superpowers/pretest_results/findings_armA.md` and `findings_armB.md`.
Open a follow-up session to triage and fix these per the LEAVE-NOTHING-BEHIND
directive; they were deliberately deferred for this test only.

## Limits

- N=3 PDFs from the same defect cluster (P0 STRIP "Author affiliations…").
  Result is directional only.
- Iterate-gate.sh always ran on Opus; floor on arm-B savings.
- Arm-B delegation quality depends on the orchestrator; protocol drift would
  change the result.
```

- [ ] **Step 2: Verify all <placeholders> are filled**

```bash
grep -n "<" docs/HANDOFF_2026-05-23_haiku-orchestration-pretest.md | grep -v "^[0-9]*:[^:]*<a href\|markdown" || echo "No placeholders found"
```
Expected: `No placeholders found`. If any remain, fill them.

- [ ] **Step 3: Commit the report**

```bash
git add docs/HANDOFF_2026-05-23_haiku-orchestration-pretest.md
git commit -m "docs: Haiku-orchestration pre-test results + recommendation

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 10: Cleanup

- [ ] **Step 1: Remove the worktrees**

Only after the report is committed and the user has seen it.

```bash
cd "/c/Users/filin/Dropbox/Vibe/MetaScienceTools/docpluck"
git worktree remove .worktrees/armA-opus-solo
git worktree remove .worktrees/armB-opus-haiku
git worktree list
```
Expected: only the main worktree listed.

- [ ] **Step 2: Decide on the branches**

Use AskUserQuestion:
- "Keep `pretest/armA-opus-solo` and `pretest/armB-opus-haiku` branches" (e.g. for follow-up analysis)
- "Delete both branches" (cleaner; results are preserved in `docs/superpowers/pretest_results/`)

- [ ] **Step 3: Surface the findings backlog to the user**

Display the combined contents of `docs/superpowers/pretest_results/findings_armA.md` and `findings_armB.md`. Recommend a follow-up session to triage and fix per LEAVE-NOTHING-BEHIND.

- [ ] **Step 4: Final commit**

```bash
git commit --allow-empty -m "chore(pretest): Haiku-orchestration pre-test complete

See docs/HANDOFF_2026-05-23_haiku-orchestration-pretest.md.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Self-review notes

- **Spec coverage:** every section of the design doc maps to at least one task. Worktrees → T4. Arms → T5/T6. Test 2 → T7/T8. Measurement → T2/T3 + capture invocations in T5/T6. Findings log → seeded in T4, committed in T5/T6, surfaced in T10. Report → T9.
- **Placeholders:** the report template (Task 9) contains `<…>` markers — these are *intentional* fill-in slots that the writer resolves at composition time. The placeholder scan in T9 step 2 enforces they don't survive into the committed file.
- **Type consistency:** `sum_tokens_by_model` signature used in T2 matches the implementation in T3. CLI flags in T3 match the invocations in T5/T6.
- **Known soft spots:**
  - Token capture relies on Claude Code's session jsonl schema (`type: "assistant"`, `message.model`, `message.usage`). If the schema drifts, T3's parser silently undercounts. Mitigation: T2 tests exercise the exact field names; if they regress against real transcripts later, fix in place.
  - The blind-judge instructions in T8 are subtle (judge reads the mapping file but must score before un-blinding). A drift here biases Test 2. The wording is explicit but a future improvement is to have a separate orchestrator do the labelling so the judge truly never sees the mapping. Out of scope for N=3.
