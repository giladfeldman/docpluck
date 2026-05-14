---
name: docpluck-iterate
description: Use when the user wants to run an autonomous library→local→deploy iteration loop on docpluck — fix-verify-release-deploy cycles working through a backlog of corpus defects until a stop condition is met (time budget, iteration count, corpus pass-rate threshold, or explicit "until X"). Self-improving: appends LEARNINGS each cycle and proposes SKILL.md amendments after recurring patterns. Triggers on phrases like "iterate on docpluck", "run the docpluck loop", "self-improve docpluck", "fix-and-deploy until X", "keep working on the corpus", or after a v2.x.y release when the user asks to continue iterating.
tags: [docpluck, python, fastapi, nextjs, vercel, railway, neon, iterate, orchestration, self-improving, qa, deploy]
user-invocable: true
argument-hint: "[--goal time:60m | iters:5 | baseline:26/26+full:95/101 | until:\"description\"] [--no-broad-read] [--dry-run]"
---

## [MANDATORY FIRST ACTION] preflight (do NOT skip, even if orchestrated by /ship)

**Your very first action in this skill, BEFORE reading anything else, is:**

1. Run: `bash ~/.claude/skills/_shared/bin/preflight-filter.sh docpluck-iterate` and print its `🔧 skill-optimize pre-check · ...` heartbeat as your first visible output line.
2. Initialize `~/.claude/skills/_shared/run-meta/docpluck-iterate.json` per `~/.claude/skills/_shared/preflight.md` step 6 (include `phase_start_sha` from `git rev-parse HEAD`).
3. Load `~/.claude/skills/_shared/quality-loop/core.md` into working memory. Although `docpluck-iterate` is not a `-qa`/`-review`/`-cleanup`/`-deploy` skill itself, it ORCHESTRATES those skills cycle-by-cycle and the spine rules R1–R5 apply transitively. Treat any FAIL from those orchestrated skills as a phase failure for this skill.

If you skip these steps, the postflight heartbeat will be missing and the run will produce no learning signal — defeating the whole point of a self-improving loop.

---

# Docpluck Iterate

You are the iteration orchestrator for the Docpluck library + app system. You run the **library → local verify → release → deploy → broad-read** cycle repeatedly until a user-defined stop condition is met. Every cycle you append to a per-skill `LEARNINGS.md`, update an always-visible TODO, and feed signal to `skill-optimize` via the standard preflight/postflight wiring so future runs of you (and other docpluck skills) get smarter.

**This is the meta-skill above `docpluck-qa`, `docpluck-review`, `docpluck-cleanup`, `docpluck-deploy`.** You delegate to those for their narrow jobs and own the loop itself.

## Project locations

| Repo | Path | Visibility |
|------|------|------------|
| Library | `C:\Users\filin\Dropbox\Vibe\MetaScienceTools\docpluck` | public (PyPI: `docpluck`) |
| App | `C:\Users\filin\Dropbox\Vibe\MetaScienceTools\PDFextractor` | private (Vercel + Railway) |

The library auto-bump bot in `docpluck/.github/workflows/bump-app-pin.yml` opens a PR in `docpluckapp` whenever a `v*.*.*` tag is pushed. The app's `.github/workflows/verify-railway-deploy.yml` polls `/health` for ≤8 min after each push and asserts `docpluck_version` matches the requirements.txt pin.

---

## Phase 0 · Setup & stop-condition (always; ask the user if missing)

Before any iteration, establish:

1. **Termination goal** — REQUIRED. Ask the user if not in `--goal` argument:
   - `time:<n>m` / `time:<n>h` — wall-clock budget. Stop when budget exhausted (mid-cycle: finish current cycle, do NOT start a new one).
   - `iters:<n>` — fixed cycle count.
   - `baseline:26/26+full:N/101` — sustained corpus thresholds across two consecutive cycles.
   - `until:"<description>"` — free-form ("until xiao Methods section is detected", "until all isolated tables have raw_text on prod"). You judge completion at end of each cycle and ask the user to confirm.
   - **Default if user is vague:** `time:60m` plus an explicit confirm-to-continue at minute 60.

2. **Active TRIAGE doc.** Read the most recent `docs/TRIAGE_*.md`. Per memory `project_triage_md_is_work_queue`, this — not the latest handoff — is the canonical work queue. If the most recent triage is older than 7 days OR predates the most recent release tag, schedule a **broad-read pass** (Phase 2) on cycle 1 and update TRIAGE in place.

3. **Most recent HANDOFF doc.** Read it for context only — it's a snapshot from a prior session, not a queue.

4. **Project lessons.** Read `<project>/.claude/skills/_project/lessons.md`. These are durable cross-skill notes that frame how the loop runs.

5. **Per-skill LEARNINGS.** Read `.claude/skills/docpluck-iterate/LEARNINGS.md` if it exists. Recent entries inform what to do/avoid this run. Pay special attention to entries < 30 days old — they reflect the current state of the codebase and tooling.

6. **Current TODO.** Read `tmp/iterate-todo.md` if it exists (or initialize it — see "TODO format" below).

7. **Print the cycle plan.** One paragraph stating the stop condition, expected cycle count, and which TRIAGE items you're targeting first. The user should be able to interrupt before any code changes.

8. **Methodology smell-test** (MANDATORY, added 2026-05-14 cycle-15 postmortem). Before any code change, the orchestrator answers ALL six checks in writing. If any answer is "no" or "unclear," the cycle STOPS and the methodology is repaired first.

   a. **Ground-truth source check.** What is THIS cycle's ground truth for verification? It MUST be an AI multimodal read of the source PDF (`tmp/<paper>_gold.md`, generated via `Read` with `pages=N-M` or pypdfium2 fallback). pdftotext / Camelot / pdfplumber output is NEVER the truth — only diagnostic. If the cycle plans to use anything other than AI-gold as truth, STOP — methodology is broken.

   b. **Cross-output coverage check.** Which outputs of the library will be affected by this cycle's fix? The output set includes: raw text, normalized text, sections, structured tables JSON, structured figures JSON, rendered .md, frontend Rendered tab, frontend Tables tab, frontend Sections tab, frontend Raw/Normalized tabs. The cycle's verification MUST cover every affected output, not only the rendered .md.

   c. **Recurrence check.** Has the user given the same correction (about ground truth, methodology, or process) before, in this session or a prior one? Search LEARNINGS.md + memory for the topic. If yes, the methodology has a regression hole and must be re-grounded before continuing. Don't add the user's correction "again" — figure out why it slipped back, and fix the slip.

   d. **Coverage matrix check.** Read `tmp/corpus-coverage.md` (or initialize it — see Phase 0.9 below). Which (paper × output-view) cells are still unverified? The cycle should advance the matrix, not just touch the same 4 canonical papers each time.

   e. **Defect-density check.** If 3+ cycles in a row found NEW critical defects in the same output, the prior verification didn't see those defects. Why? The skill needs a methodology amendment, not just another code fix.

   f. **Postmortem-pending check.** Are there defect classes in the active TRIAGE that haven't had their methodology-gap postmortem written? If yes, write the postmortem (template in LEARNINGS.md "Catastrophic-bug postmortem template") BEFORE starting the code fix. A postmortem-free fix is a fix that won't generalize.

9. **Corpus coverage matrix init.** If `tmp/corpus-coverage.md` doesn't exist, initialize it from the full test-PDF set (`PDFextractor/test-pdfs/**/*.pdf`). The matrix is `papers × outputs`, with cells in `{pending, gold-generated, gold-verified, fixed-and-reverified}`. Every cycle must advance at least one cell from one state to the next. Papers progress: pending → gold-generated → gold-verified → (defects queued) → fix shipped → fixed-and-reverified.

   The matrix replaces the 4-paper "canonical" tunnel-vision that let 14 cycles miss broad-corpus defects. The user's directive (2026-05-14, session-end): "docpluck as an academic scientific product has to be near perfect. document all lessons learned and improve the skill as you go. self-learning and improvement have to baked into the skill."

---

## Subagent parallelization (cross-cutting principle, applies to every phase below)

> Added 2026-05-14 by user directive: "use subagents whenever possible to speed up the process. do this carefully and safely but use subagents when this can be done without any fear of issues."

Iteration is dominated by I/O + AI work that is naturally parallel across papers. The orchestrator (this skill) should aggressively fan out to `Agent` subagents whenever there are 2+ independent units of work, BUT only when the work passes the safety checklist below.

### Safety checklist — must pass ALL 4 before parallelizing

1. **No shared file state.** Each parallel unit must write to a distinct output path (e.g., `tmp/<paper>_gold.md` for paper A vs `tmp/<paper>_gold.md` for paper B — different paths). Never have two agents writing the same file.
2. **No shared git state.** Never run two parallel agents that modify git (commits, tags, branches, pushes). Git operations are sequential.
3. **No sequential dependency.** Agent B does not consume an artifact agent A produces in the same fan-out batch. If A→B, run sequentially.
4. **Self-contained briefs.** Each subagent prompt is a complete, standalone instruction set — absolute paths, no references to "the prior conversation", no implicit context.

If ANY checklist item fails, run sequentially.

### Where to parallelize (and where to use `run_in_background: true`)

| Phase / step | Parallel? | How | Background? |
|---|---|---|---|
| **Phase 2 broad-read** — render 8-10 sample papers from publishers | YES | One `Bash` subprocess per paper OR one `Agent` per paper-cluster | Foreground for ≤4; background for more |
| **Phase 5d gold-extraction** — generate `tmp/<paper>_gold.md` for each canonical / affected paper | YES | One `Agent` per paper (each reads its own PDF via `Read` with `pages=`) | **Background** (3-5 min each; orchestrator does other work while waiting) |
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

### Concrete fan-out patterns to use

**Pattern A — fan-out gold extraction + verification for affected papers (typical Phase 5d):**

```
1. Identify N affected papers for this cycle.
2. For each paper without `tmp/<paper>_gold.md`: dispatch one Agent (run_in_background=true)
   to read the PDF and write the gold. Do this for ALL papers in a single message
   with multiple Agent tool calls (true parallel dispatch).
3. While golds are generating, render the affected papers at the working-tree version
   via a single `Bash` script that renders them in sequence (Camelot is not thread-safe;
   keep render serial).
4. As each gold completes, optionally dispatch its verifier Agent immediately (background).
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

### Anti-patterns to avoid

| Anti-pattern | Why it's wrong |
|---|---|
| "Dispatch 10 agents to each fix a different defect" | Multiple agents editing the same library code → merge conflicts, lost work. Orchestrator does fixes. |
| "Dispatch parallel agents to bump version" | Two agents racing on `pyproject.toml` / `__init__.py` / git → broken commits. |
| "Dispatch parallel agents to render the same paper" | Same `tmp/<paper>_v<version>.md` written twice → race condition. |
| "Skip the Pattern-A wait and do verify before gold exists" | Verifier needs gold as input; sequential dependency. |
| "Fan out gold extraction in foreground (no background)" | 4 papers × 3 min each = 12 min blocked. Background dispatch lets the orchestrator do other work and reduces wall-clock to ~3 min. |
| "Use multiple agents for a single small task" | Subagent dispatch has fixed overhead (~30s). For tasks <60s, do it inline. |
| "Subagents share my conversation context" | They DON'T. Each subagent prompt must be self-contained — give absolute paths, restate the goal, restate the discipline. |

### When in doubt

Default to **sequential** when:
- You're not sure if outputs collide.
- The task takes <1 minute (overhead > benefit).
- The task modifies global state (git, env, settings).

Default to **parallel** when:
- 3+ independent items with the same pattern (papers, sections, checks).
- Each item takes ≥2 minutes.
- Each item has a distinct output path.

---

## Phase 1 · Cycle bootstrap (every cycle)

At the start of each cycle, print one heartbeat line:

```
🔁 docpluck-iterate · cycle <N>/<expected> · goal=<stop-condition> · target=<top TRIAGE item> · todo=<pending count>
```

Then refresh state — re-read TRIAGE (in case the user edited it between cycles) and the TODO.

---

## Phase 2 · Periodic broad-read (cycle 1, then every 3–5 cycles)

**This is mandatory** per memory `feedback_optimize_for_outcomes_not_iterations`. Discovery beats verification — char-ratio + Jaccard verifiers are blind to "right words in wrong order under wrong heading."

```bash
# Render 8–10 random papers across publishers (APA, AOM, IEEE, Nature, JAMA)
python -u -c "
import sys, random
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from pathlib import Path
from docpluck.render import render_pdf_to_markdown
random.seed(<cycle_number>)  # reproducible
candidates = [
    *(Path('../PDFextractor/test-pdfs/apa').glob('*.pdf')),
    *(Path('../PDFextractor/test-pdfs/aom').glob('*.pdf'))[:3],
    *(Path('../PDFextractor/test-pdfs/nature').glob('*.pdf'))[:2],
    *(Path('../PDFextractor/test-pdfs/ieee').glob('*.pdf'))[:2],
    *(Path('../PDFextractor/test-pdfs/jama').glob('*.pdf'))[:1],
]
for p in random.sample(candidates, 10):
    md = render_pdf_to_markdown(p.read_bytes())
    out = Path(f'tmp/broad_{p.stem}_v<current>.md')
    out.write_text(md, encoding='utf-8')
    print(f'OK {p.parent.name}/{p.stem} {len(md)} chars')
" 2>&1 | grep -Ev "UserWarning|cols, rows"
```

For each rendered .md, **read the first 30 lines as a USER would** — title, abstract, keywords, intro start. Note any of:
- title leak (running header in title line)
- section boundary errors (Methods missing, Introduction starts on metadata)
- keyword/abstract bleed (per the v2.4.15 fix pattern)
- footnotes/acknowledgments inlined mid-prose
- table caption + cell-stack drift
- raw text bleed past table boundary
- repeated paragraphs / cut-off mid-word

**Update TRIAGE in place:** strike-through resolved items, add new ones discovered here, re-rank by **severity × cost**. Severity = papers affected. Cost = C1 (single iter) / C2 (multi-iter) / C3 (library-architectural) / C4 (cross-cutting). Pick the cycle target from the new top-3.

**Skip rule:** if a previous cycle in this same run did a broad-read AND no library-level change has happened since, you may skip this cycle's broad-read with `--no-broad-read`. Otherwise do not skip.

**Parallelize the rendering:** if sampling 8+ papers, render them in a single Python script that loops sequentially (Camelot is NOT thread-safe — keep renders serial within a process), but you can launch the script in `Bash` with `run_in_background=true` and do other planning while it runs. See "Subagent parallelization" Pattern B.

---

## Phase 3 · Triage & pick

From the (now-fresh) TRIAGE, pick **one** target. Heuristic:

1. Highest severity × lowest cost (S0×C1 first; S2×C3 last).
2. **Avoid C4 (architectural) unless explicitly user-approved** — a single iteration cannot land an architectural change safely.
3. If two items tie, prefer the one with a concrete root-cause hypothesis already in the TRIAGE notes.
4. If TRIAGE is empty after a broad-read, surface "diminishing returns — corpus is at quality floor for current detection ability" and ask the user whether to switch focus (e.g. expand to 50-PDF or 101-PDF corpus per `docs/HANDOFF_2026-05-13_apa_50_expansion_*.md`).

Mark the picked item `IN PROGRESS` in TRIAGE and in `tmp/iterate-todo.md`.

---

## Phase 4 · Library fix (one class at a time)

**The discipline (from CLAUDE.md):**

1. **One class of defect per cycle.** Don't fix three things in one commit — they can't be reverted independently if a regression appears.
2. **Layer-of-origin rule (LESSONS L-001):** fix in the layer that owns the artifact. Body-text issues → `normalize.py` / `sections/`. Title/table/figure issues → layout-channel consumers. **Never swap text-extraction tool as a fix for downstream problems.**
3. **Add a regression test in the same edit** in the matching `tests/test_*.py` file. The test must fail at HEAD before your fix and pass after.
4. **No silent ImportError fallbacks** for settled-on deps — see memory `feedback_no_silent_optional_deps`. Declare loudly in `pyproject.toml` and let missing deps fail at import.

Code with the Edit / Write tools. Do not delegate the actual code change to a subagent — you need to hold the architectural context.

---

## Phase 5 · Tier 1 — Library verification (the real library, the real PDFs)

This is meta-science software — zero text loss, zero hallucinations, full structural correctness. Phase 5 verifies the LIBRARY tier (standalone Python). Phase 6 verifies LOCAL-APP parity. Phase 8 verifies PRODUCTION parity. **All three tiers must match.**

Per memory `feedback_ai_verification_mandatory`: AI-verification + visual inspection are mandatory. If budget is tight, scope the **code change** smaller — never scope verification smaller. Use `awk '{print; fflush()}'` after every `python -u` to defeat Windows pipe buffering.

**Iron rule (the recurring trap, called out explicitly):** every unit test, every fixture, every regression case runs against the **actual library code** (`docpluck.*`) and an **actual PDF** in `../PDFextractor/test-pdfs/`. NEVER ship a fix whose regression test uses synthesized `text = "ABSTRACT\nblah..."` strings as a stand-in. Synthetic-text contract tests are useful as helpers but never substitute for a real-PDF regression test. The rationale and detection rule is in [references/real-library-real-pdf.md](references/real-library-real-pdf.md).

| Step | What | Time | Gate |
|------|------|------|------|
| 5a | Targeted unit tests (real-PDF fixtures + contract tests both) | ≤30s | Must pass; 3-retry max before revert |
| 5b | Broad pytest (no camelot fixtures) | ~5 min | Must pass; run in background + Monitor |
| 5c | `scripts/verify_corpus.py` 26-paper baseline | ~10 min | **Hard gate: 26/26 PASS, single WARN blocks** |
| 5d | **Full-document AI verify against AI gold** (every affected paper, every cycle, every affected output view) | ~2-4 min/paper × N-views | MANDATORY — no text loss, no hallucinations, structural correctness across ALL output views (raw / normalized / sections / tables JSON / figures JSON / rendered .md / frontend tabs) |
| 5e | Camelot-bearing tests (only if touched table extraction) | ~10 min | Required only when relevant |
| 5f | **Cross-output consistency check** (mandatory cycle-15+ requirement) | ~1 min/paper | Verifies that the same fact appears identically across views (section labels in sections JSON match the `##` headings in rendered .md; table cells in structured JSON match the `<table>` HTML in rendered .md; etc.). Cross-view drift is its own defect class. |
| 5g | **Methodology meta-audit** (every 3rd cycle, or after any user correction) | ~3 min | Dispatches a subagent that audits the LAST 3 cycles' verification approach against the Phase 0.8 smell-test. If methodology has drifted, the audit reports it and the loop fixes the methodology before the next code change. |

**Phase 5d is the keystone.** Ground truth is an **AI multimodal read of the source PDF** (`tmp/<paper>_gold.md`, generated once per paper via `Read` with `pages=N-M`, cached forever) — NOT pdftotext, NOT Camelot, NOT any deterministic extractor. Pdftotext / Camelot are *diagnostics only*: useful AFTER a finding to pinpoint the responsible library layer ("rendered says 'beta', gold says 'β', pdftotext also says 'beta' → bug is upstream in pdftotext, not in normalize.py"). A verifier subagent reads the FULL rendered .md AND the FULL gold extraction and produces a structured verdict on six checks: TEXT-LOSS, HALLUCINATION, SECTION-BOUNDARY, TABLE, FIGURE, METADATA-LEAK. TEXT-LOSS and HALLUCINATION findings are uncategorical-blockers — revert the cycle's edit, do not negotiate. See [references/ai-full-doc-verify.md](references/ai-full-doc-verify.md) for the full protocol (gold-extraction prompt template, verifier prompt template, gold caching, single-paper vs every-3rd-cycle corpus sweep). Memory `feedback_ground_truth_is_ai_not_pdftotext` and CLAUDE.md's ground-truth hard rule are the durable backstops against silently sliding back to pdftotext-as-truth.

**Heavy detail (commands, monitor patterns, common-failure table):** see [references/local-verification.md](references/local-verification.md). Load on demand when entering Phase 5.

---

## Phase 6 · Tier 2 — Local-app parity (the library inside the service)

After Phase 5 passes, before Phase 7 release, verify the library behaves IDENTICALLY when consumed by the local FastAPI service + Next.js frontend (the dev stack). Most cycles this is bytes-for-bytes match; the cycles where it isn't are exactly the ones that ship subtle production bugs.

| Step | What | Gate |
|------|------|------|
| 5.5a | Restart uvicorn so service picks up new library code | uvicorn `/_diag` returns the new `docpluck.__version__` |
| 5.5b | POST each affected paper to local `/extract` and `/extract-structured` | response 200, `docpluck_version` matches |
| 5.5c | `diff tmp/<paper>_v<v>.md tmp/<paper>_v<v>_local-app.md` | **Hard gate: no content diff** (trailing newline excluded) |
| 5.5d | (every 3rd cycle) Chrome MCP — upload + click through all 5 tabs | UI matches Tier 1 outputs per tab |
| **6c** | **Rendered ↔ Tables tab parity (v2.4.22, user directive)** | **For each affected paper: (a) count `### Table N` blocks in the rendered .md, (b) call `/extract-structured` and count tables in the JSON response. (c) Both counts must match. Any `### Table N` in the .md must correspond to a structured table with the same label. Any structured table with `kind=structured` should emit as `<table>` HTML in the .md (not fenced ```unstructured-table). (d) Mismatches indicate either: table extracted-but-not-emitted in .md (render.py splice gap), table emitted as raw_text fallback when cells were available (cell-emission gap), or table-label inconsistency between structured and rendered.** Run with `python -u -c "import json; from pathlib import Path; from docpluck.extract_structured import extract_pdf_structured; r=extract_pdf_structured(Path('<pdf>').read_bytes()); print(len(r['tables']))"` and compare to `grep -c '^### Table' tmp/<paper>.md`. |

If Tier 2 diverges from Tier 1: revert or fix the divergence. Do NOT proceed to release. Phase 6 is a hard gate. Heavy detail (curl invocations, expected deltas, common divergence causes): see [references/three-tier-parity.md](references/three-tier-parity.md).

---

## Phase 7 · Release (delegate to skill-chain)

Once **all** Phase 5 gates pass, ship the cycle:

1. **Bump versions** — `__version__`, `pyproject.toml::version`, `NORMALIZATION_VERSION` (if normalize.py changed), `SECTIONING_VERSION` (if sections changed), `CHANGELOG.md` block.
2. **Invoke `/docpluck-cleanup`** — doc + version pin sync across both repos. Wait for postflight heartbeat; FAIL blocks.
3. **Invoke `/docpluck-review`** — hard-rule check on staged changes. Blockers must be fixed before tag push.
4. **Commit + tag + push library** — `git tag vX.Y.Z && git push --tags`. Never `--amend`/`--no-verify`/`--force`/`git add -A`.
5. **Wait for auto-bump bot PR** in `docpluckapp` (~30s after tag push), then merge it (`gh pr merge <N> --repo giladfeldman/docpluckapp --squash --delete-branch`).

---

## Phase 8 · Tier 3 — Production parity (the library inside prod)

After Phase 7 release lands and Railway redeploys, prod must match Tier 2 (and therefore Tier 1). Skipping this is how Tier 3 silently diverges and the bug only surfaces when an actual scientist downloads garbage.

| Step | What | Gate |
|------|------|------|
| 7a | Wait for Railway `/_diag::docpluck_version` to show the new version | ~2–4 min via bounded Monitor poll |
| 7b | POST each affected paper to prod `/extract` | response 200, `docpluck_version` matches release tag |
| 7c | `diff tmp/<paper>_v<v>_local-app.md tmp/<paper>_v<v>_prod.md` | **Hard gate: no content diff** beyond documented `tmp/known-tier-deltas.md` |
| 7d | (every 3rd cycle, or if Tier 2 had unusual deltas) Full AI verify on prod output for one paper | Verdict matches Tier 1 AI verify for the same paper |

For app-code-touching cycles (Defect classes touch FastAPI / Next.js), invoke `/docpluck-deploy` instead of inline polling — its canonical pre-flight + post-deploy checks own the deploy lifecycle.

**Hard rule:** if Tier 3 diverges from Tier 2 in any way beyond `tmp/known-tier-deltas.md`, that's a deploy issue, not a library issue — escalate. Don't try to "patch the library around" a prod-only behavior, that's how the v2.4.13 Camelot-not-installed silent-regression class of bug ships.

**Heavy detail (commands, expected deltas, divergence-cause table, full git + auto-bump + here-doc patterns):** see [references/three-tier-parity.md](references/three-tier-parity.md) (Tier 3 section) and [references/release-flow.md](references/release-flow.md).

---

## Phase 9 · Self-improvement & TODO update (mandatory every cycle)

This is what makes the loop self-improving. Skip this and you've lost the cycle's signal. Now NINE short steps, all mandatory (expanded 2026-05-14 from 5 → 9 to close the methodology hole that let 14 cycles ship under broken verification):

| Step | What | Where |
|------|------|-------|
| 8a | Append cycle journal entry | `.claude/skills/docpluck-iterate/LEARNINGS.md` |
| 8b | Append project lesson (if bug fixed or user correction) | `<project>/.claude/skills/_project/lessons.md` (R1 spine) |
| 8c | Self-report cycle outcome to run-meta | `~/.claude/skills/_shared/run-meta/docpluck-iterate.json` |
| 8d | Refresh always-visible TODO and print at cycle end | `tmp/iterate-todo.md` |
| 8e | **Refresh corpus-coverage matrix.** Update `tmp/corpus-coverage.md` for every (paper × output) cell touched this cycle. Advance the cell from one state to the next. If no cell advanced, the cycle didn't expand coverage — flag and ask why. | `tmp/corpus-coverage.md` |
| 8f | **Write methodology postmortem if applicable.** If this cycle's AI-gold verifier surfaced a defect that survived N prior cycles, write the structured postmortem (template at the top of LEARNINGS.md) BEFORE moving on. Don't leave methodology gaps undocumented — they recur. | `LEARNINGS.md` |
| 8g | **User-correction ratchet.** If the user corrected anything about methodology or process in this cycle (not just code), log it as `### USER CORRECTION (yyyy-mm-dd):` in LEARNINGS, AND add a project lesson, AND save a feedback memory, AND amend the relevant SKILL.md. Don't merely apply the correction — encode it durably. | LEARNINGS + project-lessons + memory + SKILL.md |
| 8h | **Skill-amendment proposal** if same theme hit 2+ LEARNINGS | `PROPOSED AMENDMENT` block; await user approval |
| 8i | **Verify Phase 0.8 smell-test invariants** hold at cycle-end. If any check (ground-truth source, cross-output coverage, recurrence, coverage-matrix advance, defect-density, postmortem-pending) failed, the loop is structurally broken and the next cycle starts with methodology repair, not code work. | inline self-check |

**Heavy detail (LEARNINGS template, run-meta field-by-field, TODO format, amendment proposal format, wiring diagram):** see [references/self-improvement.md](references/self-improvement.md). Load on demand at end-of-cycle.

---

## Phase 10 · Stop check (every cycle, before bootstrapping the next)

Evaluate:

1. **Goal met?**
   - `time:Nm` — wall-clock past `started_at + N`? Stop.
   - `iters:N` — N cycles complete? Stop.
   - `baseline:26/26+full:N/101` — both thresholds met for **two consecutive** cycles? Stop.
   - `until:"..."` — your judgment + ask user to confirm completion.

2. **Must-stop conditions (non-negotiable; surface to user, do NOT continue):**
   - 26-paper baseline regressed and the cycle's revert attempt also failed.
   - Three consecutive cycles produced no shipped fix (PARTIAL/REVERT/FAIL × 3).
   - User has not been pinged in the last 90 minutes AND a Phase 4–7 step requires judgment beyond your discretion (e.g. "this fix needs an architectural decision" / "TRIAGE is empty, switching focus needs scope confirmation").
   - Production `/_diag` did not reach the new version after `verify-railway-deploy.yml`'s 8-min poll.
   - `git push` was rejected (branch protection / divergence).

3. **Diminishing returns (soft signal; surface, ask):** if 3 consecutive cycles produced only metric shifts on isolated papers (small char-ratio deltas, no new ### Table headings, no new section detection), surface `"diminishing returns; should we switch focus to <next-area>?"` and let the user decide.

4. **Pre-existing-defect backlog (per rule 0e):** if Phase 5d AI verify surfaced N defects this cycle that are pre-existing (not introduced this cycle), do NOT stop. Queue each defect (or root-cause group) as an immediate-subsequent cycle. The run continues until the queue is empty. If a defect requires architectural judgment OR exceeds the user's reasonable expectations for run length (e.g. budget far exceeded, multiple new defect classes uncovered), surface to the user with a punch-list of remaining items + estimated cycle count and ask whether to continue. Never silently stop with the queue non-empty.

If continue: loop back to Phase 1.
If stop: proceed to Phase 11.

---

## Phase 11 · Final handoff doc

When the loop terminates (goal met OR must-stop), write `docs/HANDOFF_<YYYY-MM-DD>_iterate_<run-id>.md` with:

1. **State at handoff** — last shipped version, app pin, baseline pass count, prod `/_diag` snapshot.
2. **Cycles run** — one row per cycle: target, version shipped, paper count affected, LEARNINGS hits.
3. **Bugs fixed** — full list from `tmp/iterate-todo.md` "fixed this run" section.
4. **Open queue** — current TRIAGE top-5 with severity × cost.
5. **Process improvements proposed** — any pending `PROPOSED AMENDMENT` to this SKILL.md the user hasn't accepted yet.
6. **Stop reason** — which goal/condition triggered termination.

Then run the postflight (Phase 12). The handoff doc is committed to the library repo as the durable summary; the LEARNINGS.md entries are the per-cycle detail.

---

## Verification Checklist (self-verify before printing the cycle report)

Before declaring a cycle PASS / PARTIAL, confirm each item below. If you can't tick all relevant items, the verdict is **FAIL** or **REVERT** — even if individual phase tables show PASS.

- [ ] **Tier 1 — library standalone**
  - [ ] Targeted unit tests passed (5a)
  - [ ] Broad pytest passed (5b)
  - [ ] 26-paper baseline PASS 26/26 (5c) — single WARN counts as fail
  - [ ] Full-doc AI verify per affected paper: **TEXT-LOSS = 0**, **HALLUCINATION = 0** (5d)
  - [ ] At least one `*_real_pdf` test added or modified this cycle (rule 0d) — verify by git diff of `tests/`
- [ ] **Tier 2 — local-app parity**
  - [ ] uvicorn restarted post version-bump; `/_diag::docpluck_version` matches working-tree
  - [ ] `diff Tier1 Tier2` = empty for every affected paper (6c)
  - [ ] UI smoke (5 tabs) ran if cycle ≡ 0 mod 3 (6d)
- [ ] **Tier 3 — production parity**
  - [ ] Railway `/_diag::docpluck_version` matches the release tag (8a)
  - [ ] `diff Tier2 Tier3` = empty modulo `tmp/known-tier-deltas.md` (8c)
  - [ ] Prod AI verify ran if cycle ≡ 0 mod 3 or Tier 2 had unusual deltas (8d) — verdict matches Tier 1
- [ ] **Self-improvement & process**
  - [ ] LEARNINGS.md appended (or explicit "no surprises" one-liner)
  - [ ] `_project/lessons.md` appended if any bug fixed (R1 spine)
  - [ ] `tmp/iterate-todo.md` updated
  - [ ] run-meta `bugs_fixed` / `tests_added` / `verdict` set
  - [ ] Postflight heartbeat printed (R4 spine)
- [ ] **Hard rules** — none of 0a–0d, 1–15 violated this cycle

If any unchecked item is "skipped intentionally" rather than "fails": record a `SPINE-SKIP: <rule-id> — reason: <why>` line so the next run can audit the decision.

---

## Phase 12 · Postflight (always; the keystone for self-improvement)

**Final step: read `~/.claude/skills/_shared/postflight.md` and follow it exactly.**

Specifically:
1. Print the `🔧 skill-optimize post-check ...` heartbeat as visible output.
2. Finalize `~/.claude/skills/_shared/run-meta/docpluck-iterate.json` (set `duration_seconds`, `postflight_heartbeat: true`, `completed_at`, `verdict`).
3. Run `bash ~/.claude/skills/_shared/quality-loop/spine-gate.sh docpluck-iterate <phase_start_sha> 2>&1 || true` so spine effectiveness data accumulates even though the gate isn't hard-enforced for this skill.
4. Run `bash ~/.claude/skills/_shared/bin/card-hit-check.sh docpluck-iterate` and surface the hit count.
5. Run `bash ~/.claude/skills/_shared/bin/signal-detect.sh docpluck-iterate`. If signal found, write new cards to `_shared/lessons/` per the postflight protocol. Cycles that fixed bugs, took user corrections, or hit phase failures all signal — be generous in writing cards.

If you skip these, future runs of `docpluck-iterate` (and other docpluck skills with matching tags) lose access to what this run learned.

---

## Wiring with the rest of the docpluck skill ecosystem

| When | Skill | Purpose |
|------|-------|---------|
| Phase 5b/c (verification) | (inline) | The `pytest` + `verify_corpus.py` calls are inline; they're standard project commands, not skill-bearing. |
| Phase 7 (release prep) | `/docpluck-cleanup` | Doc + version pin sync across both repos. R3 spine: must run before any deploy. |
| Phase 7 (release prep) | `/docpluck-review` | Hard-rule check on staged changes. Blockers must be fixed before tag push. |
| Phase 8 (deploy) | `/docpluck-deploy` (full path only) | Canonical pre-flight + post-deploy verification. Inline polling is fine for simple cycles. |
| Phase 5 / on-demand | `/docpluck-qa` | Run the full 500+ test suite + ESCIcheck + service health. Use only at major milestones (every 5 cycles, or before a minor-version bump) — too slow per cycle. |
| Postflight | `skill-optimize` (passive) | Cards written to `_shared/lessons/` propagate to future docpluck skill runs via preflight. |
| Cross-cycle | `skill-review-lessons` (manual) | When the user wants to audit accumulated cards from this skill, they invoke `/skill-review-lessons` directly. |

**Invocation discipline:** when you delegate to `/docpluck-cleanup` / `/docpluck-review` / `/docpluck-deploy`, use the `Skill` tool, wait for its postflight heartbeat, and read its run-meta for `verdict` + `bugs_fixed`. Don't paraphrase its output — surface its status table verbatim in your cycle report.

---

## Hard rules (DO NOT VIOLATE — derived from CLAUDE.md + LESSONS.md + project memory)

### Meta-science correctness (the uncategorical-blockers — revert immediately, no negotiation)

0a. **NO TEXT MAY DISAPPEAR.** Every substantive paragraph from the source pdftotext output must appear in the rendered .md (modulo running headers, page numbers, copyright lines, watermarks per [references/ai-full-doc-verify.md](references/ai-full-doc-verify.md) allowed-omissions list). Phase 5d full-doc AI verify is the gate.

0b. **NO HALLUCINATED TEXT.** Every substantive paragraph in the rendered .md must trace back to the source pdftotext output. Renderer-added markup (headings, italic captions, fenced unstructured-table blocks) is NOT hallucination; new prose IS.

0c. **TIER 1 = TIER 2 = TIER 3.** Library output, local-app output, and production output must match byte-for-byte (modulo documented `tmp/known-tier-deltas.md`). Any cross-tier divergence is a blocker.

0d. **TESTS RUN AGAINST THE REAL LIBRARY ON REAL PDFs.** Every cycle adds at least one `*_real_pdf` test that exercises the public library entry point on an actual PDF fixture. Synthetic-text contract tests are useful as helpers but never substitute. See [references/real-library-real-pdf.md](references/real-library-real-pdf.md).

0e. **FIX EVERY BUG FOUND IN THE SAME RUN — NEVER DEFER "PRE-EXISTING" DEFECTS.** When Phase 5d AI verify (or any verification step) surfaces a defect, that defect MUST be fixed before the run ends — even if it existed in the prior release. "Pre-existing, not introduced this cycle" is NOT a license to ship around the bug; it is a hint that an earlier cycle's verification was incomplete. Queue every found defect as an immediate-subsequent cycle in the SAME run (group by root cause: e.g. "1,001 → 1.001" and "first 20 years → first years" share an A3-thousands-separator root cause, so they ship as ONE cycle). The run does not terminate until the open backlog is empty or an item is explicitly escalated to the user for scope confirmation. Accumulated deferrals are how a meta-science library silently degrades; "later" is a recipe for horrible mistakes. The `time:60m` fallback budget does NOT excuse skipping — surface to the user as a soft-stop checkpoint when the budget is exhausted, but the default is to continue. See memory `feedback_fix_every_bug_found` (2026-05-14, v2.4.16 release) and [references/ai-full-doc-verify.md](references/ai-full-doc-verify.md) Step 3 (Adjudicate).

### Library / API hard rules (from LESSONS.md + CLAUDE.md)

1. **Never use `pdftotext -layout`** (column interleaving). Enforced in `docpluck/extract.py:13–16`.
2. **Never use `pymupdf4llm` / `fitz` / `column_boxes()` / pymupdf-layout** (AGPL; incompatible with closed-source SaaS). Only pdfplumber (MIT) and pdftotext (default mode) allowed.
3. **Never swap text-extraction tool as a fix for downstream problems** (LESSONS L-001). Fix the layer that owns the artifact.
4. **Always normalize U+2212 → ASCII hyphen** in `normalize.py` step S5.
5. **No silent ImportError fallbacks for settled-on deps** (memory `feedback_no_silent_optional_deps`). Camelot, pdfplumber are mandatory — declare in `pyproject.toml`.
6. **Tables emit as HTML `<table>`, not pipe-tables** (memory `project_html_tables_in_md`).
7. **No PDFs committed to the repo** — manifest-with-skip pattern (memory `feedback_no_pdfs_in_repo`).

### Process hard rules

8. **TRIAGE.md is the work queue** (memory `project_triage_md_is_work_queue`). Handoff is one input; TRIAGE is authoritative.
9. **Don't deviate from agreed directives — ask if scope changes** (memory `feedback_dont_deviate_from_directives`). Surface entanglement explicitly.
10. **AI verification + visual inspection are mandatory** (memory `feedback_ai_verification_mandatory`). Phase 5d full-doc AI verify is non-negotiable. Scope code change smaller, never verification smaller.
11. **26-paper baseline must PASS 26/26 before every push.** Single WARN blocks.
12. **Add a regression test in the same commit as the fix** (LESSONS L-002 + project pattern). Real-PDF test required; synthetic-only does not satisfy.
13. **Bump library version every release.** Patch for fixes; minor for behavior changes that alter rendered byte content.
14. **Use `awk '{print; fflush()}'` after `python -u`** for any subprocess on Windows (memory `feedback_pdftotext_version_skew` extends to all subprocess output buffering).
15. **Three-tier parity is sequential, not parallel.** Tier 1 passes → run Tier 2. Tier 2 passes → run Tier 3. Do not start a tier before the previous one passes.

---

## Stop conditions vs must-stop conditions

| Condition | Type | Action |
|-----------|------|--------|
| Goal met (`time` / `iters` / `baseline` / `until`) | Stop | Phase 11 handoff, then Phase 12 postflight. |
| 26-paper baseline regressed AND revert failed | MUST-STOP | Surface to user with full failure trace. Do not continue. |
| 3 consecutive cycles PARTIAL/REVERT/FAIL | MUST-STOP | Surface "loop is not converging" + summary of attempted fixes. |
| `git push` rejected | MUST-STOP | Branch protection or divergence. Surface to user. |
| Prod `/_diag` doesn't reach new version after 8 min | MUST-STOP | Railway deploy is broken. Surface to user. |
| Diminishing returns (3 cycles, only metric shifts) | SOFT-STOP | Surface and ask user whether to switch focus. Default: continue. |
| TRIAGE empty after broad-read | SOFT-STOP | Surface "corpus at quality floor for current detection ability"; ask whether to expand scope (50-PDF / 101-PDF). |

---

## Quick reference

| What | Command |
|------|---------|
| Render a paper locally | `python -c "from docpluck.render import render_pdf_to_markdown; from pathlib import Path; print(render_pdf_to_markdown(Path('<pdf>').read_bytes()))"` |
| Inspect structured tables | `python -c "from docpluck.extract_structured import extract_pdf_structured; from pathlib import Path; r = extract_pdf_structured(Path('<pdf>').read_bytes()); [print(t['label'], t['kind'], len(t.get('cells') or [])) for t in r['tables']]"` |
| 26-paper baseline | `PYTHONUNBUFFERED=1 python -u scripts/verify_corpus.py 2>&1 \| awk '{print; fflush()}'` |
| Targeted unit tests | `DOCPLUCK_DISABLE_CAMELOT=1 python -u -m pytest tests/test_<module>.py -q --tb=short` |
| Probe prod | `curl -s https://extraction-service-production-d0e5.up.railway.app/_diag \| python -m json.tool` |
| Auto-bump PR check | `gh pr list --repo giladfeldman/docpluckapp --state open --search "vX.Y.Z" --json number,title` |

---

## Cycle report (print at end of every cycle)

The cycle report is a structured per-phase status table + AI-verify findings + three-tier diff + verdict. Print to the user at end of every cycle so they can scan progress without scrolling logs. Then follow it with the current state of `tmp/iterate-todo.md`.

**Full template (status-table rows, AI-verify finding bins, three-tier diff section, verdict ladder):** see [references/cycle-report-template.md](references/cycle-report-template.md). Load on demand at cycle end.

---

## Common rationalizations (red flags)

If you catch yourself thinking "I'll skip step X because Y" — STOP and consult [references/rationalizations.md](references/rationalizations.md). It's the table of every short-circuit pattern this skill has encountered (and the reality that blocks it). Most rationalizations map to a hard-rule violation; the table makes the mapping explicit.

Common triggers for consulting: about to skip Phase 5d / Phase 6 / Phase 8c verification; about to ship without a `*_real_pdf` test; about to bundle two fixes in one cycle; about to "spot-check 30 lines" instead of a full AI verify.

---

## On invocation patterns

**Foreground (recommended for first-time users):** user invokes you, you ask the goal, run cycles in foreground, the user can watch + interrupt.

**Background (advanced):** user invokes you with `--goal time:8h --no-confirm` and you run unattended overnight. In this mode:
- Switch to background-task pattern (`run_in_background: true` for long Bash commands; Monitor for events).
- Print the cycle heartbeat + TODO update at the end of each cycle so the user can scan progress on resume.
- Soft-stop conditions become hard-pings: write a `tmp/iterate-pause-cycle-<N>.md` file with the question and STOP. The user resumes with `/docpluck-iterate --resume`.

**Resume (`--resume`):** read `tmp/iterate-todo.md` and the last cycle report; pick up at the next phase. Do not re-run completed phases.

---

## Final step: read `~/.claude/skills/_shared/postflight.md` and follow it.
