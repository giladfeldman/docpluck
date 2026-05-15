# Handoff — Autonomous 10-hour docpluck-iterate run · APA corpus first, then everything

**Authored:** 2026-05-15, end of the v2.4.32 session (cycles 15n + 15e + 15f-1 shipped).
**Audience:** A fresh Claude session that will run **`/docpluck-iterate` unattended for ~10 hours with no user prompts**.
**Mandate:** Fix as much of the corpus as possible. **APA first, as widely as possible. When APA is exhausted, move to every other publisher.**

---

## 0. How to start (do this first, exactly)

Invoke the skill in autonomous mode:

```
/docpluck-iterate --goal time:10h --no-confirm --autonomous
```

Then follow `.claude/skills/docpluck-iterate/SKILL.md` — but with the autonomous overrides in §2 below. Do **not** wait for the user. Do **not** ask questions. The user is asleep; there will be no answer for 10 hours.

Your very first actions (SKILL.md mandates these — do not skip):
1. `bash ~/.claude/skills/_shared/bin/preflight-filter.sh docpluck-iterate` and print the heartbeat.
2. Re-initialize `~/.claude/skills/_shared/run-meta/docpluck-iterate.json` (`phase_start_sha` = `git rev-parse HEAD`, `started_at` = now).
3. Load `~/.claude/skills/_shared/quality-loop/core.md`.
4. Read this handoff, the active TRIAGE (`docs/TRIAGE_2026-05-14_phase_5d_gold_audit.md`), `CLAUDE.md`, `LESSONS.md`, and `.claude/skills/docpluck-iterate/LEARNINGS.md` (last ~3 entries).

---

## 1. State at handoff

| Item | Value |
|---|---|
| Library version | **v2.4.32** (tag pushed; `docpluck/__init__.py` + `pyproject.toml` synced) |
| App pin | **v2.4.32** — `service/requirements.txt` on `docpluckapp` master |
| Prod `/_diag` | **v2.4.32** confirmed at `https://extraction-service-production-d0e5.up.railway.app/_diag` |
| Last library commit | `476ddbc` |
| 26-paper baseline | **26/26 PASS, 0 WARN** |
| Broad pytest | **1393 passed, 15 failed (all pre-existing — see §6), 21 skipped, 1 xfailed** |
| `NORMALIZATION_VERSION` | 1.9.0 · `SECTIONING_VERSION` unchanged |
| AI-gold cache | 469 papers / 559 views in `~/ArticleRepository/ai_gold/`, but only **16 `reading` views** (docpluck's view). See §4. |

### Auto-bump CI changed this session
`bump-app-pin.yml` now **commits the library pin directly to `docpluckapp` master — no PR**. After you `git push` a `vX.Y.Z` tag, the pin advances automatically within ~30s; there is **nothing to merge**. `verify-railway-deploy.yml` (triggers on push to master) is the post-deploy gate. Do not look for an auto-bump PR — there won't be one.

### What shipped in the session that produced this handoff
- **v2.4.31 (cycle 15n)** — figure caption placeholder repair (`_accumulated_is_label_only` + `_strip_leading_pmc_running_header`).
- **cycle 15e (G16)** — page-header-in-equations verified already-fixed; locked with a regression test. No release.
- **v2.4.32 (cycle 15f-1, G4b)** — table caption no longer absorbs linearized cell content (`_trim_table_caption_at_cell_region`).
- 7 pre-existing pytest failures fixed; the CI change above.

---

## 2. AUTONOMOUS-MODE OVERRIDES (read carefully — these replace SKILL.md defaults)

The skill body assumes a user is reachable. For this run **the user is not reachable for 10 hours.** Apply these overrides:

1. **Never call `AskUserQuestion`. Never write a `tmp/iterate-pause-cycle-*.md` and stop.** Where SKILL.md says "surface to the user and ask," instead: make the most defensible decision yourself, write the decision + rationale into `LEARNINGS.md` as a `### AUTONOMOUS DECISION (yyyy-mm-dd):` block, and continue.
2. **Soft-stop = continue.** "Diminishing returns" or "TRIAGE empty" do **not** stop the run. If APA work hits diminishing returns, *move to the next publisher* (see §3). If the entire TRIAGE empties, start a fresh broad-read pass on an un-audited publisher and refill it.
3. **Hard must-stops still stop the run** (these are real breakage, not judgment calls):
   - 26-paper baseline regresses **and** the cycle's revert also fails.
   - `git push` is rejected (branch protection / divergence).
   - Prod `/_diag` does not reach the just-shipped version after 10 min.
   - 3 consecutive cycles produce REVERT/FAIL with no shipped fix.
   On a hard must-stop: write `docs/HANDOFF_<date>_autonomous_ABORT.md` with the full failure trace and stop.
4. **One root-cause class per cycle still holds.** Autonomy is not licence to bundle unrelated fixes. Rule 0e bundling (same root cause) is still allowed and required.
5. **Every cycle still ships through the full gate**: Phase 5 (Tier 1) → Phase 6/7 (release) → Phase 8 (Tier 3 prod-verify). Never skip Phase 5d AI-gold verify. Never skip the 26-paper baseline. Autonomy means *no user check-ins*, **not** *fewer verification gates*.
6. **Self-pacing.** Use `ScheduleWakeup` / background tasks to wait out long renders, pytest, baselines, and Railway deploys. Do not burn the 10 hours idling — while a baseline runs in the background, plan or investigate the next cycle.
7. **Commit cadence.** Ship a tagged release per cycle as normal. Test-only or doc-only changes may be committed without a version bump (no tag → no deploy). Push frequently so work is never lost.
8. **Budget discipline.** ~10h. Expect 8–15 cycles. Don't spend 3 hours on one architectural defect — if a defect proves to be C3/C4 and resists a clean fix after ~2 cycles of effort, write it up in TRIAGE as "needs design", move on, and come back only if everything else is done.

---

## 3. THE WORK PLAN — APA first, then everything

### Phase A — APA corpus (do this FIRST, exhaust it before Phase B)

The APA corpus is **18 PDFs** in `../PDFextractor/test-pdfs/apa/`:

```
ar_apa_j_jesp_2009_12_010   ar_apa_j_jesp_2009_12_011   ar_apa_j_jesp_2009_12_012
chan_feldman_2025_cogemo    chandrashekar_2023_mp        chen_2021_jesp
efendic_2022_affect         ip_feldman_2025_pspb         jamison_2020_jesp
jdm_.2023.10                jdm_.2023.15                 jdm_.2023.16
jdm_m.2022.2                jdm_m.2022.3                 korbmacher_2022_kruger
maier_2023_collabra         xiao_2021_crsp               ziano_2021_joep
```

APA psychology / replication papers are the **canonical test target** (CLAUDE.md L-005 — their stat tables are real statistical results, not ML metrics). This is the corpus the library most needs to be perfect on.

**Phase A protocol:**

1. **A1 — Gold coverage.** Only 3 of 18 APA papers have a `reading` AI-gold view (`xiao_2021_crsp`, `chan_feldman_2025_cogemo`, `ip_feldman_2025_pspb`). The other 15 need golds. For each missing paper, dispatch a gold-extraction subagent (template: `.claude/skills/docpluck-iterate/references/ai-full-doc-verify.md` Step 1b) and **`register-view <key> reading <path> --producer docpluck-iterate --schema reading.v1`** to the shared cache. Parallelize: dispatch gold-extraction subagents in background batches (Pattern A in SKILL.md "Subagent parallelization"). Aim to have all 18 APA golds cached early in the run so every later cycle's verification is free.
2. **A2 — Broad-read.** Render all 18 APA papers at HEAD. Read the first 30 lines of each as a *reader* (per memory `feedback_optimize_for_outcomes_not_iterations`). Catalogue every defect. Update TRIAGE in place — strike resolved items, add new ones, rank by severity × papers-affected.
3. **A3 — Fix loop.** Pick the highest severity × lowest cost defect class. One root-cause class per cycle. Ship. Re-verify against AI-gold. Repeat. **Prefer defect classes that affect the MOST APA papers** — the user's words: "as widely as possible." A fix touching 12 APA papers beats a fix touching 1, even if the 1-paper fix is easier.
4. **A4 — APA exit criterion.** APA is "done" when either: every APA paper passes Phase 5d AI-gold verify with TEXT-LOSS = 0 and HALLUCINATION = 0, OR three consecutive APA-targeted cycles produce only cosmetic (S2) shifts. At that point, log an `### AUTONOMOUS DECISION` block ("APA corpus at quality floor — N/18 clean — moving to Phase B") and proceed to Phase B.

### Phase B — every other publisher

After APA, sweep the rest in this order (smallest-risk publishers first so cross-publisher regressions surface early):

```
nature (10) → ieee (10) → ama (10) → aom (10) → asa (10) → harvard (13) → chicago-ad (10) → vancouver (10)
```

Same protocol per publisher: gold coverage → broad-read → fix loop → exit criterion. ~93 papers total. You will not perfectly clean all of them in the remaining budget — that is fine. Maximize papers-moved-toward-clean. Keep `tmp/corpus-coverage.md` honest so the next session knows exactly where coverage stands.

---

## 4. AI-gold caching — the multi-view model (changed since older handoffs)

The article-finder cache migrated to a **multi-view** model. Each paper key holds multiple named views; docpluck-iterate uses the **`reading`** view (full prose + tables cell-by-cell + figures + references + footnotes).

```bash
# CHECK first — never re-extract a cached gold:
python ~/.claude/skills/article-finder/ai-gold.py get <key> --view reading
# stats:
python ~/.claude/skills/article-finder/ai-gold.py stats
# After a NEW gold extraction, REGISTER it (not the legacy `store`):
python ~/.claude/skills/article-finder/ai-gold.py register-view <key> reading tmp/<paper>_gold.md \
    --producer docpluck-iterate --schema reading.v1 --source-pdf <abs pdf path>
```

The cache has 469 papers but mostly `textstaging` views from other projects — those are **not** usable as docpluck ground truth. Only 16 `reading` views exist. Growing `reading` coverage to the full 111-paper corpus is part of this run's job. Ground truth is **always** an AI multimodal read of the source PDF — never pdftotext/Camelot/pdfplumber (CLAUDE.md hard rule; `feedback_ground_truth_is_ai_not_pdftotext`).

---

## 5. Open defect queue (the TRIAGE — `docs/TRIAGE_2026-05-14_phase_5d_gold_audit.md`)

Canonical work queue. Current open root-cause groups, recommended order:

| Cycle | Group | Sev | Cost | One-line |
|---|---|---|---|---|
| **15f-2** | G4a | S1 | C3 | Body-stream linearized table-cell dump duplicates the structured `<table>`. **Investigation done** — see §5.1. |
| 15g | G1 | S0 | C2-C3 | pdftotext glyph collapse (`=`→`5`, `−`→`2`, `<`→`,`, Greek). Sign-flips every stat. Highest impact. Closes the amj_1 Figure 7 xfail. |
| 15h | G3+G22 | S0 | C3 | Table cell defects + xiao Table 6 numeric SWAP. |
| 15i | G5 | S1 | C2 | Section-boundary detection under-firing (~25 headings demoted per paper). |
| 15j | G7+G8+G21 | S1 | C3 | Math-content normalization: equation destruction, body-prose splay, bracket stripping. |
| 15k | G9+G24 | S1 | C2 | Endmatter routing — Appendix/bios/Acknowledgments. |
| 15l | G10+G11 | S2 | C2 | Figure caption double-emission + orphaned body labels. |
| 15m | G12+G13+G14+G18 | S2 | C2 | Long tail — sub/superscript, reference mega-lines, URL soft-wrap, digit drift. |

**Order guidance for an APA-first run:** the broad-read in Phase A2 will re-rank these *for the APA corpus specifically*. Do the APA re-ranking first; the table above is the v2.4.28-era global ranking. G1 (glyph collapse) and G5 (section detection) are likely the widest-impact APA defects — confirm with the broad-read, then prioritize whatever hits the most APA papers.

### 5.1 Cycle 15f-2 (G4a) — investigation already done, ready to implement

The body text from `extract_sections` contains pdftotext's linearized table-cell dump (caption → ~140 short cell lines → `Note:` footnote → body prose). `render.py` emits it verbatim, so every table appears twice: once as a broken plain-text dump in the body, once as the structured `<table>`.

Confirmed at v2.4.32:
- **amle_1 / amj_1**: clean *contiguous* dumps. Each starts with a **standalone `TABLE N` line** (all-caps), then a title line, then cell lines, then a `Note:` line. Ends where body prose resumes. amle_1 has 16 such dump regions; amj_1 has 5.
- **xiao**: a *different, harder* manifestation — scattered cell fragments + bare `Table N. <title>` caption lines, not big contiguous blocks. **Scope cycle 15f-2 to the amle_1/amj_1 contiguous pattern only**; file the xiao scattered-fragment variant as a new TRIAGE item `G4a-2`.

**Recommended implementation** (render-side strip, contained — does not touch the sectioner):
- New helper in `docpluck/render.py`, e.g. `_strip_linearized_table_dumps(section_text, table_numbers)`.
- A dump starts at a line matching `^(TABLE|Table)\s+(\d+)\.?$` (standalone label) where `(\d+)` is the number of a table that **has a structured table** in `structured["tables"]` (don't strip on text pattern alone).
- From the caption line, walk forward consuming non-body-prose lines (reuse `_line_is_body_prose` from `extract_structured.py` — it already excludes `Note:` lines and short cell fragments) until the first body-prose line; cap the walk (e.g. ≤250 lines or the next `## `/`### ` heading).
- Only strip if the consumed run is substantial (≥ ~8 cell-like lines) — guards against nuking a lone caption mention.
- Tables emit at section-end regardless of caption position (verified: `body_chunks = [body_text]` then tables appended), so stripping the caption + dump from `body_text` does **not** break inline splicing.
- **Critical false-positive guard:** run the full 26-paper baseline AND Phase 5d AI-gold verify on amle_1 + amj_1 + 2 APA papers. The risk is stripping legitimate short-line-dense prose. If the baseline regresses, revert and re-scope.

---

## 6. Pre-existing pytest failures (15 — carry forward, do NOT block on these)

Broad pytest at v2.4.32 = 1393 pass / 15 fail. All 15 are pre-existing and documented:
- **12× `test_v2_backwards_compat.py::test_extract_pdf_byte_identical[*]`** — snapshot drift; the byte-identical fixtures predate pdftotext version skew. Fix = regenerate the snapshots against current pdftotext output (verify the new output against AI-gold first, then regen). A legitimate cleanup cycle if you have spare budget.
- **2× `test_sections_golden.py`** — synthetic-fixture char-offset drift; regenerate with `DOCPLUCK_REGEN_GOLDEN=1`.
- **1× `test_request_09_reference_normalization.py::test_bibliography_splits_into_45_consecutive`** — bibliography splitter regex drift.

These are not gates for shipping a cycle. But per **rule 0e**, if a cycle you run touches the same module, fix the failure in the same cycle. The byte-identical snapshot regen is itself a worthwhile autonomous cycle if APA + the TRIAGE empties.

---

## 7. Cycle protocol (condensed — full detail in SKILL.md)

Per cycle:
1. **Phase 0.8 smell-test** (6 checks, all must pass) before any code change.
2. **Phase 1** heartbeat. **Phase 2** broad-read on cycle 1 and every 3–5 cycles.
3. **Phase 3** pick one root-cause class (highest severity × widest APA reach).
4. **Phase 4** fix in the layer that owns the artifact (LESSONS L-001 — never swap the extraction tool). Add a real-PDF regression test in the same commit (rule 0d).
5. **Phase 5** Tier 1: targeted tests → broad pytest → 26-paper baseline (26/26 hard gate) → **Phase 5d AI-gold verify** (TEXT-LOSS = 0, HALLUCINATION = 0 — uncategorical blockers).
6. **Phase 7** release: bump `__version__` + `pyproject.toml` (+ `NORMALIZATION_VERSION` if normalize changed, `SECTIONING_VERSION` if sections changed) + `CHANGELOG.md`; commit; tag `vX.Y.Z`; `git push origin main && git push origin vX.Y.Z`. No PR to merge (CI change — §1).
7. **Phase 8** Tier 3: poll prod `/_diag` until it reports the new version (bounded ≤10 min); confirm.
8. **Phase 9** self-improvement — append `LEARNINGS.md`, update `tmp/iterate-todo.md` + `tmp/corpus-coverage.md`, update run-meta arrays.
9. **Phase 10** stop check (autonomous overrides §2).

`/docpluck-cleanup` + `/docpluck-review` (Phase 7 spine): run them for cycles that touch ≥2 modules or any doc; for a narrow single-helper patch they may be skipped with a recorded `SPINE-SKIP` line. Use judgment — they are cheap insurance.

---

## 8. Hard rules (DO NOT VIOLATE — from CLAUDE.md / LESSONS.md / memory)

- **0a** No text may disappear. **0b** No hallucinated text. **0c** Tier 1 = Tier 2 = Tier 3. **0d** Every cycle adds a real-PDF regression test. **0e** Fix every bug found in the same run — never defer "pre-existing" defects; group by root cause.
- Never `pdftotext -layout`. Never `pymupdf4llm`/`fitz`/`column_boxes()` (AGPL). Only pdftotext (default mode) + pdfplumber (MIT) + Camelot.
- Never swap the text-extraction tool to fix a downstream problem (L-001). Fix the layer that owns the artifact.
- Always normalize U+2212 → ASCII hyphen (the *only* sanctioned Unicode→ASCII conversion; everything else is preserved via `preserve_math_glyphs`).
- Tables emit as HTML `<table>`, not pipe-tables. No PDFs committed to the repo.
- Ground truth = AI multimodal read of the source PDF. Never pdftotext/Camelot/pdfplumber as truth.
- `awk '{print; fflush()}'` after `python -u` for any subprocess on Windows (pipe-buffering).
- Three-tier parity is sequential — Tier 1 passes → Tier 2 → Tier 3. Never parallel.

---

## 9. End-of-run deliverable

When the 10h budget is exhausted (finish the in-flight cycle, do not start a new one) OR a hard must-stop fires:
- Ensure every shipped cycle is a tagged release and prod `/_diag` matches the last tag.
- `LEARNINGS.md` has a per-cycle entry for every cycle.
- `tmp/corpus-coverage.md` is refreshed — honest about which (paper × view) cells are verified.
- Write `docs/HANDOFF_<date>_autonomous_run_<n>.md`: versions shipped, cycles run (one row each: target / version / papers affected), bugs fixed, APA papers now clean vs total, open TRIAGE top-5, and the recommended next pickup.
- Run Phase 12 postflight (`~/.claude/skills/_shared/postflight.md`) — heartbeat, run-meta finalize, spine-gate, signal-detect, write lesson cards.

---

## 10. Mandatory pre-reading (in order)

1. This handoff.
2. `docs/TRIAGE_2026-05-14_phase_5d_gold_audit.md` — the work queue.
3. `CLAUDE.md` — ground-truth + rule-0e hard rules.
4. `.claude/skills/docpluck-iterate/SKILL.md` — full phase reference.
5. `.claude/skills/docpluck-iterate/LEARNINGS.md` — last 3 entries (cycle 15n, 15e+15f investigation, 15f-1).
6. `.claude/skills/docpluck-iterate/references/ai-full-doc-verify.md` — Phase 5d protocol + multi-view ai-gold.
7. Memories: `feedback_ground_truth_is_ai_not_pdftotext`, `feedback_fix_every_bug_found`, `feedback_ai_verification_mandatory`, `feedback_optimize_for_outcomes_not_iterations`, `project_triage_md_is_work_queue`.
8. `tmp/corpus-coverage.md` + `tmp/iterate-todo.md` — current coverage + queue.

---

**Go. APA first, as wide as possible. Then everything else. Ten hours. No prompts. Ship cycles, verify against AI-gold, never let the baseline regress. Good luck.**
