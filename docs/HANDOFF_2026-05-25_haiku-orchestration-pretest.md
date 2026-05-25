# Haiku-orchestration pre-test — results

**Dates:** 2026-05-23 (design) → 2026-05-25 (execution + report)
**Spec:** [`docs/superpowers/specs/2026-05-23-haiku-orchestration-pretest-design.md`](superpowers/specs/2026-05-23-haiku-orchestration-pretest-design.md)
**Plan:** [`docs/superpowers/plans/2026-05-23-haiku-orchestration-pretest.md`](superpowers/plans/2026-05-23-haiku-orchestration-pretest.md)
**Start SHA:** `5735903`

## TL;DR

The Haiku-orchestration pattern **works for bulk read/diff tasks** (Test 1 directional). It **does NOT work as a substitute for Opus when generating extraction ground truth** (Test 2 clear).

- **Test 1 (diagnose docpluck output vs gold):** Both arms reached the same FAIL verdict on the same 5 defect classes. Haiku absorbed ~193k tokens of bulk reading/diffing at API cost ~$0.50; Opus-solo cost ~126k tokens at ~$3–4. Haiku-side savings are real — but only if Opus orchestration overhead stays low.
- **Test 2 (generate gold reading.md from PDFs):** Opus golds scored 5/5/5/5/5/0 across the board. Haiku golds scored 3/2/2/2/2/7–8 — coverage gap, severe hallucinations (wrong author names, wrong p-values, fabricated references, paragraph duplication, inverted figure interpretations). **Do not use Haiku for gold-generation.**

## Test 1 — Diagnose docpluck output vs gold (Opus solo vs Opus + Haiku)

Scope: 1 paper (`jama-open-1`), 1 diagnostic cycle, scaled down from the original 3-PDF/3-cycle plan because the harness limit prevented subagents from dispatching sub-subagents (see "Honest limits" below). Both arms stopped at verdict; neither attempted fixes.

| Metric | Arm A (Opus solo) | Arm B (Opus + Haiku) |
|---|---|---|
| Verdict | FAIL | FAIL |
| Defect classes found | 5 | 5 (same classes) |
| Wall time | ~4 min | ~3.2 min |
| Opus tokens (clean) | **125,896** (fresh-context subagent) | not cleanly measured¹ |
| Haiku tokens (clean) | 0 | **193,154** (3 subagent dispatches) |
| Direct tool calls (orchestration) | 31 | ~7 |
| API-rate cost on measured tokens | ~$1.90–$9.45 (high uncertainty: input/output split unknown)² | ~$0.19–$0.97 |

¹ Arm B's Opus orchestration ran from this top-level session, which carried ~200k+ tokens of accumulated context (spec, plan, prior tool calls). My orchestration tokens are not directly comparable to Arm A's fresh-context 126k.

² Opus API rates: $15/M input, $75/M output. Range reflects unknown input/output split inside Arm A's subagent return.

### Both arms found the same defects on jama-open-1

1. **RUNNING_HEADER_LEAK** — `Downloaded from jamanetwork.com…` watermark and `October 27, 2023` page-marker date leak into body text 11+ times.
2. **HALLUC_HEAD** — `### 1.0. Mean glucose level`, `### Control`, `### Body weight, kg`, `### Total cholesterol` promoted from Table 2 cell content into the heading hierarchy.
3. **ABSTRACT_LEVEL_MISMATCH** — Gold has `## Abstract` with h3 children (Importance/Objective/Design/Interventions/Main Outcomes/Results/Conclusions and Relevance). Rendered has `## Abstract` with NO subsections; instead `## Findings`, `## RESULTS`, `## CONCLUSIONS AND RELEVANCE` appear at h2 level, breaking hierarchy.
4. **MISSING_SECTION** — `## Key Points` (JAMA Open's structured-summary sidebar) is entirely absent from rendered output.
5. **TABLE_STRUCTURE_CORRUPT** — Table 3 has `<th>JAMA Network Open | Nutrition, Obesity, and Exercise</th>` (journal masthead) and `<td>Discussion</td>` (section name as data cell).

### Qualitative read

- Haiku produced JSON-structured summaries of both 1395-line rendered.md and 374-line gold.md in 12-43 seconds each. Quality was sufficient for a downstream Opus or Haiku diff step to identify all 5 defect classes.
- Arm A burned 31 tool calls on the same work that Arm B (Opus orchestrator side) did in ~7 tool calls.
- The pattern's actual win condition is **Opus stays as planner/judge with low tool-call count; Haiku does the per-file reading**. Both arms confirm Haiku is competent at structured summarization tasks given a clear schema.

### What this does NOT tell us

- Whether Haiku-drafted **code patches** would be accepted by Opus or need rework (test was diagnose-only, no fixes attempted).
- Whether the pattern survives multi-cycle iteration (test was 1 cycle).
- Whether arm B's orchestration overhead exceeds arm A's solo cost on harder/larger inputs (N=1 PDF).

## Test 2 — Gold extractor (Opus vs Haiku)

Scope: 2 fresh APA papers (not in active iterate queue), both with existing Opus-generated gold. Each Haiku regen took 2-3 tool calls.

### Generation cost

| Paper | PDF pages | Opus gold size | Haiku regen tokens | Haiku gold size | Wall time |
|---|---|---|---|---|---|
| maier_2023_collabra | 21 | 97,483 bytes | 94,524 | 92,931 (95%) | 4.2 min |
| efendic_2022_affect | 12 | 56,548 bytes | 71,097 | 51,264 (91%) | 2.6 min |

Haiku golds are 91-95% the size of Opus golds — size is NOT a useful quality signal (see below).

### Blind judge scorecard (Opus judge, fresh context, 228k tokens, paths-revealed-provenance flagged but stated content-only)

| Paper | Model | Coverage | Accuracy | Hallucination↓ | Structure | Prose |
|---|---|---|---|---|---|---|
| maier_2023_collabra | **Opus** | 5 | 5 | 0 | 5 | 5 |
| maier_2023_collabra | Haiku | 3 | 2 | **8** | 2 | 2 |
| efendic_2022_affect | **Opus** | 5 | 5 | 0 | 5 | 5 |
| efendic_2022_affect | Haiku | 3 | 2 | **7** | 3 | 2 |

### Specific Haiku failure modes (auditable, independent of any provenance hint)

**maier_2023_collabra (Haiku gold):**
- Wrong citations: `Bergh & Bernstein, 2021` (PDF: Reinstein), `Smith et al., 2015` (PDF: 2013), `Lee & Feeley, 2010` (PDF: 2016).
- Wrong stats: `r = 0.064` (PDF: 0.004 — off by 16×); ANOVA design `2 × 5` repeated multiple times (PDF: 2 × 3); abstract CI `[.000, .005]` (PDF: [.000, .003]).
- Corrupted table: Table 10 `r` column shows sample-size values (`.170, .165`) where correlation coefficients should be — data-shape confusion.
- Severe duplication: "The Identifiable Victim Effect" paragraphs and the H5d section repeated 2-3 times verbatim.
- Truncated: Scope Insensitivity / Irrational Decision Making / Limitations sections largely missing.
- **References list absent entirely.**

**efendic_2022_affect (Haiku gold):**
- Author confusion: `Henrick et al., 2019` (PDF: Efendić et al., 2019 — replaced the actual author name).
- Wrong SE values: Table 2 intercept SE `0.04` (PDF: 0.06); Table 4 Direction SE `0.03` (PDF: 0.09).
- Wrong scale anchors: rating described as `1 (not at all risky) to 10 (extremely risky)` (PDF: anchored 1 / 5 moderate / 10 very risky — 3-anchor scale).
- Fabricated references: `Giroux, C. (2021)`, `Ruelle, J.A. (2003)` (PDF: Russell), `Vanpoucke` (PDF: Vanpaemel), `Västfjäll 2008` invented; wrong title/journal for Slovic et al. (2002).
- Citation replacement: `Phelan & Sureden` substituted for Thaler & Sunstein.
- **Figure 4 interpretation inverted** — Haiku says +1 SD pleasure shows shallower slope than −1 SD; PDF says the opposite.

### Why this matters

Docpluck's verification pipeline assumes the AI gold is the source of truth. **If gold generation drifts (wrong author names, fabricated references, inverted figure interpretations), every downstream verdict is corrupted.** The 7-8 hallucinations per Haiku gold are not noise — they're systematic enough to fool a downstream FAIL-comparison check that doesn't audit the gold itself.

This rules out Haiku-as-gold-extractor for docpluck's current verification model. The Opus golds remain canonical. If cost-reduction in gold-gen is needed, the right experiment is **Opus-with-thinking-budget capped** or **Sonnet 4.6** as the gold extractor, not Haiku.

## Combined recommendations

1. **Haiku-orchestration for bulk read/diff: pursue.** Test 1 was directionally positive. Next experiment: run the full original plan (3 PDFs, 3 cycles, fresh top-level Opus session) and include fix-drafting in scope. If Haiku-drafted patches survive Opus review ≥80% of the time, the pattern is production-ready.
2. **Haiku-as-gold-extractor: reject.** Test 2 is clear. Even with N=2 the failure modes are too severe (wrong author names, inverted figures, fabricated references). Not safe for any verification pipeline that treats the gold as ground truth.
3. **The bigger question — "expensive iterate skills with cheaper models":** the pattern that's likely to actually save credits is **Opus-stays-planner + Haiku-does-per-file-summarization**. NOT "swap Opus for Haiku on the whole task." This pretest didn't measure code-patch quality from Haiku — that's the next pretest to design.
4. **Workshop angle (free local models):** unchanged from the brainstorm — Ollama + Qwen2.5-Coder-7B is the realistic floor for student laptops. Local Haiku-class quality is currently unreachable for free.

## Issues found during the test (deferred per LEAVE-NOTHING-BEHIND exception)

These were flagged but NOT fixed in-flight per the pretest design. **Triage in a follow-up session.**

### Docpluck library — jama-open-1 defect cluster (newly surfaced, not in canary)

The 5 defect classes listed in Test 1 above. Severity: SERIOUS. Spans:
- `docpluck/normalize.py` — F0 running-header strip misses JAMA's `Downloaded from jamanetwork.com…` watermark and `October 27, 2023` date-line.
- `docpluck/sections/` — abstract subsection promotion to h2 instead of h3 when JAMA structured abstract is parsed; column-interleave variant for left abstract + right Key Points sidebar.
- `docpluck/sections/annotators/text.py` (or wherever heading promotion lives) — table-cell content promoted to h3 headings (`### 1.0. Mean glucose level`, etc.).
- `docpluck/tables/` — Table 3 row-cell pollution: journal masthead in `<th>`, section name in `<td>`.

Recommended follow-up: add jama-open-1 to the iterate canary set, run a normal `/docpluck-iterate` cycle dedicated to it.

### Article-finder skill — usability sharp edge

From Arm A subagent's observation: `ai-gold.py resolve` fails on the stem name (`jama_open_1`) and on the source PDF file path, but `ai-gold.py check jama_open_1 --view reading` works directly. The `RESOLVE the canonical key` step in `article-finder/SKILL.md` doesn't document this fallback. Severity: MODERATE (causes wasted cycles for new users).

Recommended follow-up: amend `article-finder/SKILL.md` and `article-finder/gold-generation.md` to document the stem-vs-DOI resolve behavior, OR fix `ai-gold.py resolve` to accept stems.

### Plan deviation (informational, not a defect)

- The original plan committed `tmp/pretest_start_sha.txt`. `tmp/` is gitignored, so the commit silently no-op'd. Future plans should either use a non-gitignored location or `git add -f`.
- The original plan instructed both arms to run via fresh top-level sessions; the user opted for an in-session run via subagents. We hit a harness limit (subagents can't dispatch sub-subagents), then a CLI auth limit (`claude -p` from Bash gets 401 even with `ANTHROPIC_API_KEY` set, because the Claude Code parent uses managed-by-host provider context). We scaled the experiment down accordingly. **For a clean re-run at full scope, the original plan stands: open fresh top-level sessions per arm.**

## Methodology + limits

- **N=1 PDF in Test 1, N=2 PDFs in Test 2.** Both are pretest scope, intentionally small. Results are directional.
- **Test 1 was diagnose-only, not full iterate.** The original plan included fix attempts; we scoped down. The bulk-read savings shown here may not survive a fix-and-rework workflow where Opus rejects many Haiku patch drafts.
- **Test 2 judge saw paths revealing provenance** (`ai_gold/` vs `_pretest_haiku_golds/`). The judge flagged this in its return; we cannot fully rule out hint-leakage on the 1-5 rubric scores. However: the specific factual errors enumerated by the judge (wrong author names, wrong p-values, fabricated references) are auditable against the PDF and independent of any provenance hint. The qualitative conclusion (Haiku golds have severe hallucinations) is robust; the exact 5-vs-2 score margins less so.
- **Token counts on Arm B Opus side are not measurable** because this session's accumulated context contaminates the cost. Reported as Opus tool-call count instead.
- **All four Haiku subagent runs in this pretest had non-trivial fixed overhead** — the simplest Haiku ping (`PONG`-only) consumed 41,528 tokens. This is Claude Code's per-subagent system-prompt + tool-definition load. It puts a floor on per-Agent-call cost (~$0.04 at API rates). Pattern only wins if each Haiku call absorbs >>40k tokens of real work, which both Test 1 and Test 2 cleared.

## Artifacts

| File | Purpose |
|---|---|
| `tmp/pretest_start_sha.txt` | Starting commit (5735903) |
| `tmp/pretest_test2_blind_mapping.json` | Test 2 X/Y labelling key |
| `tmp/pretest_test2_judge.json` | Test 2 blind judge raw scorecard |
| `tmp/pretest_test2_unblinded.json` | Test 2 un-blinded scorecard |
| `tmp/run_meta_pre_pretest.json` | Iterate-skill run-meta snapshot, pre-test |
| `.worktrees/armA-opus-solo/tmp/*` | Arm A rendered.md, gold.md, run-meta, timestamps, findings |
| `.worktrees/armB-opus-haiku/tmp/*` | Arm B rendered.md, gold.md, timestamps, findings |
| `ArticleRepository/_pretest_haiku_golds/maier_2023_collabra/reading.md` | Haiku-extracted gold (do NOT use for verification) |
| `ArticleRepository/_pretest_haiku_golds/efendic_2022_affect/reading.md` | Haiku-extracted gold (do NOT use for verification) |
| `scripts/pretest_capture_tokens.py` | Reusable token-capture utility (not exercised in scaled-down run) |

## Cleanup status

- Two worktrees still live: `pretest/armA-opus-solo` and `pretest/armB-opus-haiku`. Branches retained pending user decision on whether to delete them.
- Quarantined Haiku golds remain at `_pretest_haiku_golds/` — recommend keeping for one cycle, then deleting.
- Token-capture script is committed to `main` as `5735903` and remains useful for future pretests.

## Approved follow-ups (queued, not started)

1. Add jama-open-1 to docpluck iterate canary set; run a dedicated cycle to fix the 5 defect classes (SERIOUS).
2. Document or fix `ai-gold.py resolve` stem-vs-DOI behavior (MODERATE).
3. Design and run the next pretest: **Haiku-drafted code patches reviewed by Opus** (the open question this pretest did not answer).
