# Subagent parallelization — operational detail

> Extracted from `SKILL.md` (the "Subagent parallelization" MANDATE section) on 2026-06-15 to keep the SKILL under the size guideline. The MANDATE itself, the per-cycle self-check, and the provenance stay inline in SKILL.md; this file holds the safety checklist, the where-to-parallelize table, the concrete fan-out patterns, the anti-patterns, and the when-in-doubt defaults. Load on demand whenever you are about to fan out work.

> **Added 2026-05-14 by user directive, RE-STATED 2026-05-15** ("use subagents to optimize the whole process whenever possible"). The re-statement means the directive slipped — treat this as a HARD MANDATE, not advice.

**MANDATE (restated):** Before doing ANY batch of 2+ independent units of work inline, STOP and ask: *"could N parallel background subagents do this instead?"* If yes and the safety checklist passes, you MUST fan out. Doing serially in the orchestrator's own context what subagents could do in parallel is a process defect — it is slow and burns the orchestrator's context window. This applies to: per-paper renders, gold extractions, AI-gold verifications, broad-read reader-passes, diagnostic captures, cross-paper sweeps. The orchestrator keeps ONLY: code edits, git/release operations, version bumps, and <60s one-offs.

Iteration is dominated by I/O + AI work that is naturally parallel across papers. The orchestrator (the `docpluck-iterate` skill) MUST aggressively fan out to `Agent` subagents whenever there are 2+ independent units of work, when the work passes the safety checklist below.

## Safety checklist — must pass ALL 4 before parallelizing

1. **No shared file state.** Each parallel unit must write to a distinct output path (e.g., `tmp/<paper>_gold.md` for paper A vs `tmp/<paper>_gold.md` for paper B — different paths). Never have two agents writing the same file.
2. **No shared git state.** Never run two parallel agents that modify git (commits, tags, branches, pushes). Git operations are sequential.
3. **No sequential dependency.** Agent B does not consume an artifact agent A produces in the same fan-out batch. If A→B, run sequentially.
4. **Self-contained briefs.** Each subagent prompt is a complete, standalone instruction set — absolute paths, no references to "the prior conversation", no implicit context.

If ANY checklist item fails, run sequentially.

## Where to parallelize (and where to use `run_in_background: true`)

| Phase / step | Parallel? | How | Background? |
|---|---|---|---|
| **Phase 2 broad-read** — render 8-10 sample papers from publishers | YES | One `Bash` subprocess per paper OR one `Agent` per paper-cluster | Foreground for ≤4; background for more |
| **Phase 5d gold-extraction** — DELEGATED to `article-finder generate-gold`; docpluck-iterate does NOT generate golds | N/A | `article-finder` owns extraction + its own parallelization | N/A |
| **Phase 5d verification** — compare rendered.md ↔ gold for each affected paper | YES | One `Agent` per paper (independent inputs) | **Background** (1-2 min each) |
| **Phase 5d cross-paper sweep** — corpus-level pattern detection on 5 papers | YES, but only ONE agent for the whole sweep | Single agent reading 5 paper pairs and emitting a corpus-level findings list | Foreground (one call, ~3-4 min) |
| **Diagnostic artifact capture** — `pdftotext` + `extract_pdf_structured` per paper | YES | One `Bash` per paper | Foreground (each <5s) |
| **Phase 5b broad pytest** — independent of Phase 5d verification | YES | `Bash` with `run_in_background: true` | Background; check via `Monitor` |
| **Phase 5c 26-paper baseline** — independent of Phase 5d | YES | `Bash` with `run_in_background: true` | Background; ~10 min |
| **Phase 6c rendered ↔ tables-tab parity** — across affected papers | YES | One `Bash` per paper | Foreground; each <5s |
| **Phase 8 Tier-3 prod parity** — across affected papers (POST-deploy) | YES | One `Bash` curl per paper | Foreground; each <10s |
| **Phase 7 release** — version bump + commit + tag + push + auto-bump merge | **NO** | Sequential git operations | N/A |
| **Phase 4 library fix** — code edits | **NO** | Orchestrator holds architectural context | N/A |
| **/docpluck-cleanup, /docpluck-review, /docpluck-deploy** — meta-skill chain | **NO** to running 2 at once | Each is sequential per its own internal logic | Foreground; chain them |

## Concrete fan-out patterns to use

**Pattern A — obtain golds, then fan-out VERIFICATION for affected papers (typical Phase 5d):**

```
1. Identify N affected papers for this cycle.
2. For each paper: resolve the canonical key and `ai-gold.py check` the shared cache.
   On a miss, gold generation is DELEGATED to `article-finder generate-gold` — docpluck
   NEVER dispatches its own gold-extraction subagent (see Phase 5d Step 1; 2026-05-16
   directive). Copy each `reading` view to `tmp/<paper>_gold.md`.
3. While golds are obtained, render the affected papers at the working-tree version
   via a single `Bash` script that renders them in sequence (Camelot is not thread-safe;
   keep render serial).
4. As each gold is ready, optionally dispatch its verifier Agent immediately (background).
   Or wait for all golds, then dispatch all verifiers in a single multi-tool-call message.
5. Aggregate verdicts as they return; queue defects per rule 0e.
```

**Pattern B — background long-running tasks during planning:**

```
1. Kick off the 26-paper baseline (`Bash` with run_in_background=true).
2. Kick off the broad pytest (`Bash` with run_in_background=true).
3. While both run, do Phase 3 TRIAGE re-read + Phase 4 code edit planning.
4. By the time you need 5b/5c results, they're already done.
```

**Pattern C — corpus sweep with a single agent:**

```
For the every-3rd-cycle corpus sweep, do NOT fan out 5 separate agents.
Use ONE agent given paths to 5 paper pairs and ask for a corpus-level
findings list. This produces a coherent ranking; 5 independent agents
would each produce a local list and the orchestrator would have to
merge them by hand.
```

## Anti-patterns to avoid

| Anti-pattern | Why it's wrong |
|---|---|
| "Dispatch 10 agents to each fix a different defect" | Multiple agents editing the same library code → merge conflicts, lost work. Orchestrator does fixes. |
| "Dispatch parallel agents to bump version" | Two agents racing on `pyproject.toml` / `__init__.py` / git → broken commits. |
| "Dispatch parallel agents to render the same paper" | Same `tmp/<paper>_v<version>.md` written twice → race condition. |
| "Skip the Pattern-A wait and do verify before gold exists" | Verifier needs gold as input; sequential dependency. |
| "Dispatch a subagent to read the PDF and produce a gold" | docpluck-iterate does NOT generate ground truth — generation is delegated to `article-finder generate-gold` (one producer, one protocol; 2026-05-16 directive). A local extraction subagent re-forks the gold. |
| "Use multiple agents for a single small task" | Subagent dispatch has fixed overhead (~30s). For tasks <60s, do it inline. |
| "Subagents share my conversation context" | They DON'T. Each subagent prompt must be self-contained — give absolute paths, restate the goal, restate the discipline. |

## When in doubt

Default to **sequential** when:
- You're not sure if outputs collide.
- The task takes <1 minute (overhead > benefit).
- The task modifies global state (git, env, settings).

Default to **parallel** when:
- 3+ independent items with the same pattern (papers, sections, checks).
- Each item takes ≥2 minutes.
- Each item has a distinct output path.
