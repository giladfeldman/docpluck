# Haiku-orchestration pre-test — design

**Date:** 2026-05-23
**Status:** Approved, pending implementation plan
**Owner:** giladfel@gmail.com

## Why

Iteration-heavy work on docpluck burns Opus 4.7 tokens fast enough that a Claude Max 5-hour window runs out before the work does. Question: can Opus orchestrate Haiku 4.5 subagents for the bulk grunt work (reading, diffing, drafting) while retaining judgment for architecture/commits, and deliver comparable quality at materially lower Opus-token cost?

This pre-test answers that question on a small, controlled task before any wider workflow change.

## Scope

Two independent tests on the same 3 PDFs, in isolated worktrees, starting from the same docpluck commit:

- **Test 1 — iteration efficiency.** `/docpluck-iterate` run twice: once Opus-solo (arm A), once Opus orchestrating Haiku subagents (arm B). Compare tokens, time, quality.
- **Test 2 — extractor model comparison.** Regenerate AI gold for the same 3 PDFs using Haiku 4.5; compare field-by-field to existing Opus golds via blind 3rd judge.

Out of scope: any conclusion about long-running iteration. N=3 PDFs is suggestive only.

## Inputs

- **Repo:** `C:\Users\filin\Dropbox\Vibe\MetaScienceTools\docpluck`
- **Starting commit:** the tip of `main` after the user commits/stashes current uncommitted changes (prerequisite — see Prerequisites below).
- **3 PDFs:** `jama-open-1`, `jama-open-2`, `jama-open-3`. All three:
  - Are in the cycle-9 STRIP-bucket open queue (`tmp/iterate-todo.md` P0 cluster, "Author affiliations and article information are listed at the end of this article").
  - Already have AI gold under `ArticleRepository/ai_gold/jama_open_{1,2,3}/`.
  - Are same defect class → comparable difficulty across the 3.
- **Gold source:** `~/.claude/skills/article-finder/gold-generation.md` protocol (canonical).
- **Tooling baseline:** docpluck v2.4.59, service_version 1.5.1.

## Prerequisites

1. User commits or stashes the current dirty state in the docpluck repo (5 files modified per `git status`). Both arms must start clean from the same commit SHA.
2. The arm-B delegation rules below are followed strictly. Drift in delegation invalidates the comparison.

## Architecture

### Worktrees

Two worktrees off the same starting commit:

- `docpluck/.worktrees/armA-opus-solo` — branch `pretest/armA-opus-solo`
- `docpluck/.worktrees/armB-opus-haiku` — branch `pretest/armB-opus-haiku`

Per-worktree run-meta is captured separately (the spine writes to `~/.claude/skills/_shared/run-meta/docpluck-iterate.json`; we snapshot and reset between runs).

### Arm A — Opus solo (control)

Fresh Claude Code session at the arm-A worktree. Single command:

```
/docpluck-iterate --goal "PASS on jama-open-1, jama-open-2, jama-open-3" --no-broad-read
```

All work runs on Opus 4.7 (main + any default subagents). Iterate-loop spine runs normally. Cycle until done or hard stop.

### Arm B — Opus orchestrating Haiku

Fresh Claude Code session at the arm-B worktree. Same `/docpluck-iterate` invocation.

**Opus retains (non-delegable):**
- Plan, cycle structure, root-cause diagnosis
- All `iterate-gate.sh --cycle N` and `--close` calls
- Final code edits to `docpluck/normalize.py`, `extract*.py`, `sections/`, `render.py`
- All `git commit` actions, version bumps, CHANGELOG entries
- Verdict decisions (PASS/FAIL/BLOCKED)

**Opus delegates to Haiku via `Agent(subagent_type: "general-purpose", model: "haiku")`** (the Agent tool's `model` parameter accepts `haiku|sonnet|opus`; `haiku` resolves to Haiku 4.5 in this environment):
- Reading any file > 200 lines (return summary + relevant excerpts)
- Per-PDF diff of rendered .md vs gold (one Haiku subagent per PDF, parallel)
- Drafting candidate normalize.py patches (Opus reviews, accepts or rewrites)
- Drafting per-paper Phase 5d analysis briefs
- Drafting test cases (Opus reviews before writing to disk)

Delegation brief template (Opus → Haiku) is in [Appendix A](#appendix-a-haiku-delegation-brief-template).

### Stop conditions (both arms)

Goal-boxed, with a hard ceiling:
- **Goal:** all 3 PDFs PASS AI-verify (verdict from spine's Phase 5d).
- **Hard ceiling:** 90 minutes wall-clock OR 3 cycles, whichever first.
- If hard ceiling hits before goal: record final punch-list, do NOT continue.

## Test 2 — extractor model comparison

Independent of Test 1. Driven from a third fresh session.

1. For each of the 3 PDFs, regenerate the AI gold using Haiku 4.5 as the extractor. Mechanism: spawn `Agent(subagent_type: "general-purpose", model: "haiku")` with the `article-finder` gold-generation prompt (loaded verbatim from `~/.claude/skills/article-finder/gold-generation.md`) and the PDF path. Output to a quarantined dir: `ArticleRepository/_pretest_haiku_golds/jama_open_{1,2,3}/`. Do NOT overwrite the canonical Opus golds in `ai_gold/`. The implementation plan must verify article-finder's gold-generation prompt can be loaded standalone — if it requires Opus-specific tooling we fall back to a stripped extraction prompt and note the deviation.
2. Spawn a fresh Opus session as a **blind judge**. Inputs per PDF: `{pdf_path, gold_X, gold_Y}` with X/Y randomly assigned per PDF (we record the mapping but don't tell the judge). Judge scores each gold on:
   - Coverage (which fields are populated)
   - Accuracy (each populated field correct vs source PDF)
   - Hallucination (fields populated with content not present)
   - Structure fidelity (sections, tables, citations)
3. After judge returns, un-blind and tabulate.

## Measurement

Per arm of Test 1, captured to `tmp/pretest_results_arm{A,B}.json`:

```json
{
  "arm": "A" | "B",
  "start_sha": "...",
  "end_sha": "...",
  "cycles_run": <int>,
  "papers_passed": ["..."],
  "papers_failed": ["..."],
  "tokens": {
    "opus_input": <int>, "opus_output": <int>,
    "haiku_input": <int>, "haiku_output": <int>
  },
  "wall_time_minutes": <float>,
  "api_equivalent_cost_usd": <float>,
  "diff_lines_changed": <int>,
  "regression_baseline_26_paper": "PASS" | "FAIL" | "<n> regressions",
  "stop_reason": "goal" | "time" | "cycles"
}
```

**API-equivalent cost** uses public per-token API rates (Opus 4.7: $15 in / $75 out per M; Haiku 4.5: $1 in / $5 out per M). This is *not* what the user pays on Max — it's the right unit for measuring efficiency.

**Token capture method:** at end of each arm, read the session transcript from `~/.claude/projects/.../*.jsonl` and sum `input_tokens` / `output_tokens` grouped by model. Cross-check against `/cost` output.

For Test 2: per-PDF judge scorecard in `tmp/pretest_test2_judge.json`.

## Side-effect findings log

`docpluck/tmp/test-2026-05-23-haiku-orchestration-findings.md`

Any defect, doc drift, skill bug, or unrelated issue noticed during either arm gets appended here. **It is NOT fixed in-flight.** This deliberately violates the LEAVE-NOTHING-BEHIND working directive — a one-time exception, scoped to this test, because in-flight fixes would contaminate the token/time comparison. The log feeds a follow-up cleanup session.

Format per entry:
```
## <ISO timestamp> · arm <A|B>
**Where:** <file:line or component>
**What:** <one-paragraph description>
**Severity guess:** trivial | moderate | serious
**Defer reason:** "Test 2026-05-23 in flight — fix in follow-up session"
```

## Output

After both tests complete, produce a single report:
`docs/HANDOFF_2026-05-23_haiku-orchestration-pretest.md`

Contents:
- Numbers table (arm A vs arm B, tokens / time / quality / cost)
- Test 2 judge scorecard
- Qualitative observations from arm B (where Haiku was useful, where it failed)
- Recommendation: adopt the pattern broadly, adopt with constraints, or reject
- Pointer to findings log

## Risks and honest limits

1. **N=3 is small.** Results are directional, not conclusive. Read accordingly.
2. **Arm B is harder to drive than arm A.** The orchestration is manual; quality of arm B depends on how well Opus delegates. Bad delegation makes arm B look worse than the pattern's ceiling.
3. **Iterate-gate.sh always runs in main = Opus.** Floor on arm B savings. Big infrastructure files (`iterate-loop/core.md`, etc.) loaded into the main context are unavoidable Opus tokens.
4. **Haiku patch quality is the open question.** If Haiku-drafted patches need ≥3 rework rounds from Opus, savings collapse. This is exactly what we're measuring.
5. **The 3 JAMAs share a defect class.** A single root-cause fix may resolve all 3 in 1 cycle, making cycle-count differentials uninformative. Token-per-cycle is the more sensitive metric.

## Appendix A — Haiku delegation brief template

Used by Opus main when spawning Haiku subagents in arm B. Every brief must be self-contained (Haiku has no conversation memory).

```
TASK: <one sentence>
CONTEXT: <repo path, paper key, what stage of the iterate cycle>
INPUTS:
  - <file paths Haiku must read>
  - <relevant gold path>
DELIVERABLE: <exact format — diff, JSON, prose summary under N words>
CONSTRAINTS:
  - Do NOT write to disk
  - Do NOT run iterate-gate.sh
  - Do NOT commit
  - Report findings, don't fix them
SUCCESS CRITERIA: <when this subagent's output is good enough>
```

## Approval

Approved by user 2026-05-23 ("ok"). Implementation plan to follow via `superpowers:writing-plans`.
