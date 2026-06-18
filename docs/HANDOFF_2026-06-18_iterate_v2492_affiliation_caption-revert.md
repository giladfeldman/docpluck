# HANDOFF — docpluck-iterate (2026-06-18, v2.4.92 shipped; caption-guard reverted)

> **Supersedes** `HANDOFF_2026-06-17_iterate_v2491_shipped.md` for forward work. This session
> resumed that queue, **shipped the affiliation-heading guard as v2.4.92** (the safest open item),
> **attempted and cleanly REVERTED a caption-follows guard** (cycle 3, no release — the full-corpus
> regression gate caught a false-positive regression), and **re-scoped the cell-label class into the
> table cluster**. Run remains **OPEN / PARTIAL — standing verdict FAIL** (iterate-gate `--cycle 2`
> = FAIL on I3; the canary corpus is genuinely broken on pre-existing table/column-interleave defects).
> Paused at the architectural boundary by user direction.

## TL;DR

- **v2.4.92 SHIPPED + LIVE.** Affiliation-heading guard: an affiliation/institution line can never be
  promoted to a `### ` subsection heading. tag `v2.4.92` → docpluckapp pin `@v2.4.92` (auto-merged) →
  prod Railway `/_diag` = **2.4.92**. Local `PDFextractor/` synced via auto-bump.
- **Verified, not just shipped.** Fixes chandrashekar's `### Department of Philosophy, Lake Forest
  College`. **0 false positives across 47 golds / 2226 real headings**; deterministic corpus
  render-diff (guard-live vs bypassed) changed **only chandrashekar** (all 12 cross-publisher sample
  papers byte-identical); full suite **2027 passed**; 23 new tests; **5-way Sonnet AI-verify** vs the
  article-finder golds = affiliation guard confirmed working on every canary paper, **no new
  text-loss / hallucination**.
- **Cycle 3 caption-follows guard: ATTEMPTED + REVERTED (no release).** Two render-layer signals for
  maier's `### Identifiable victim` (a Figure 2 panel label): lowercase-continuation MISSED (promoter
  sees pre-relocation text), caption-follows OVER-REACHED (full 48-paper corpus diff demoted 4
  legitimate headings-before-tables). Reverted to v2.4.92 HEAD. **The cell-label class is
  table-content-as-prose → folded into the table cluster, not a render-layer cycle.**
- **Tables + RC-1 remain OPEN** (multi-cycle architectural). The remaining path to corpus-clean is
  architectural and was paused here by user direction.

## Deploy state — v2.4.92 LIVE, coherent

| Layer | State |
|---|---|
| Library `origin/main` HEAD | `c671929` (cycle 2+3 docs journal) on top of `cf420ca` (v2.4.92 feat) — clean tree |
| Library tag `v2.4.92` | live; prod Railway `/_diag` = `2.4.92` |
| docpluckapp `origin/master` pin | `@v2.4.92` (auto-bump auto-merged) ✅; local `PDFextractor/` synced |

## Gate state — `iterate-gate.sh --cycle 2` = **FAIL** (run OPEN/PARTIAL); cycle 3 = INVESTIGATE+REVERT

Cycle 2: only **I3** fires (verdict-on-truth): all 5 canary papers FAIL on pre-existing table/column
defects — non-overridable by design, and correct (the corpus IS broken). Every other rule passed
(I1, I2, I5, I9, I10, I11, I12). Cycle 3 produced no release (guard reverted), so it has no PASS to
gate. **Do NOT run `--close`** until tables + RC-1 clear (I6).

> ⚠ **Process trap (re-record after every commit):** the pre-commit `canary-audit.sh` hook OVERWRITES
> run-meta `phase_5d_runs` with regression-only "PASS-for-gate" verdicts (even on AUDIT_DEFERRED). After
> any commit, re-read `phase_5d_runs` and re-record the truthful per-paper AI-verify verdicts before
> `iterate-gate.sh --cycle N`, or I3 wrongly stays green on a broken corpus. Memory:
> `feedback_canary_audit_clobbers_phase5d`. Spawned as background task `task_c678d4e6`.

## Cycles run this session

| Cycle | Target | Version | Papers | Outcome |
|---|---|---|---|---|
| 2 | G5d affiliation→`### ` heading | **v2.4.92** | chandrashekar (+canary verify ×5) | SHIPPED — zero-regression, AI `FIX-CORRECT` |
| 3 | cell/condition-label→`### ` heading | (none) | maier | INVESTIGATE+REVERT — no clean render-layer signal |

## Bugs fixed this run

- **G5d affiliation-heading promotion (v2.4.92).** `_looks_like_affiliation_line` + a reject in
  `_promote_isolated_titlecase_subsection_headings` (runs before the chain-promotion bypass). Keyed on
  affiliation grammar (unit-phrase head OR institution-terminated phrase), never paper identity.
  Demotes to body text (text preserved). Tests: `tests/test_affiliation_heading_promote_guard_real_pdf.py`.

## Per-paper findings at HEAD (v2.4.92; AI gold = article-finder `reading`)

5-way Sonnet AI-verify this session (renders at `tmp/iterate/cycle-2/<stem>.md`):

| Paper | Verdict | Dominant defects (all PRE-EXISTING unless noted) |
|---|---|---|
| chandrashekar_2023_mp | FAIL | **affiliation heading FIXED ✓**; Tables 7-10 header-shell collapse; cell-label headings `IV2: No-default` / `Participation rate` |
| ip_feldman_2025_pspb | FAIL | affiliation guard confirmed working; `### Reasons for change` (Table 5 col-label); Table 5 fragmentation |
| plos_med_1 | FAIL | Table 4 wrong-content; Table 5 empty `<tbody>` (13 SAE rows lost); Table 2 sub-rows; Fig 1 flow-diagram absent; front-matter blocks (Funding/Competing/abbrev) in body |
| efendic_2022_affect | FAIL | affiliation metadata leak mid-paragraph (Affect Heuristic); Table 1 column collapse; supplementary material absent |
| maier_2023_collabra | FAIL | cell/condition-label headings (`Identifiable victim` [caption-adjacent], `Without joint condition [S1]`, `Target article`); Abstract split; Tables 4/5/7/8 collapse |

## Open queue (priority — standing verdict FAIL, run not done; ALL remaining items architectural)

1. **Tables — TEXT-LOSS / structuring (highest user impact).** plos_med is worst (Table 5's 13 SAE
   rows empty `<tbody>`, Table 4 wrong content). Then chandrashekar T7-10 header-shell collapse
   (`EstimateZpOR [95% CI]` merged), maier T4/5/7/8, efendic Table 1 column collapse, ip_feldman
   T3/4/5/10. Camelot/extraction-layer, multi-cycle. Suggested start: the empty-`<tbody>`/header-shell
   collapse root-cause class (spans plos_med T5 + chandrashekar T7-10). **A full table fix carries the
   modified-Approach-B bbox-computation decision OUTSTANDING SINCE 2026-05-22 — NEEDS A USER SCOPE
   DECISION before coding.**
2. **Cell/condition-label → heading promotion (FOLD INTO #1).** ip_feldman `Reasons for change`,
   chandrashekar `IV2: No-default`/`Participation rate`, maier `Without joint condition [S1]`/`Target
   article`/`Identifiable victim`. Confirmed this session: these are table/supplementary content dumped
   into the prose stream — NOT fixable by a render-layer heading guard (cycle 3 proved both candidate
   signals fail; caption-follows demotes legitimate headings-before-tables). Fix upstream with the
   table-extraction work.
3. **RC-1 two-column band path (user-approved multi-session, RISKIEST).** Flags stay OFF — flag-ON
   still scrambles section order (Introduction before Abstract) + leaks running-headers. Fix
   band-cut/reorder under the word-preservation guard before any flip. Spec:
   `docs/superpowers/specs/2026-06-08-rc1-region-aware-column-architecture.md`.
4. **Residual metadata-leaks (lower severity).** Affiliation/front-matter text as body past the
   masthead zone (efendic Affect-Heuristic; plos Funding/Competing/abbrev blocks; maier Abstract
   split). `_strip_frontmatter_masthead_block` can't reach past the first `## ` — needs a body-zone
   furniture strip or the interleave fix.

## Process improvements recorded this run (durable)

1. **Instrument the PROMOTER-INPUT, not the final .md.** A render-pass guard inside
   `_promote_isolated_titlecase_subsection_headings` sees pre-relocation text; the final .md's line
   adjacency differs (captions/tables are spliced later). Monkeypatch-wrap the function and print
   (prev, cand, next) from the text it receives.
2. **A bounded sample gives FALSE CONFIDENCE — run the full-corpus regression diff (rule 19).** Cycle
   3's 11-paper diff said "clean"; the 48-paper diff revealed 4 real-heading false positives. The FP
   pattern lives in the long tail.
3. **canary-audit clobbers `phase_5d_runs`** — re-record truthful AI-verify verdicts after every
   commit (memory `feedback_canary_audit_clobbers_phase5d`; spawned `task_c678d4e6`).

## How to resume

1. `/docpluck-iterate --resume`. **FIRST** `git status` + `git log --oneline -5` in BOTH repos
   (concurrent co-editing of `render.py` is a recurring hazard; a stray `REQUEST_10_TABLE_FLATTEN_
   HTTP_EXPOSURE.md` from the ESCImate team was present in the working tree this session — not ours).
2. The remaining queue is architectural. Item 1 (tables) needs the **bbox-computation scope decision**
   surfaced to the user before coding. Don't start coding a table fix without it.
3. After any commit, re-record `phase_5d_runs` before `iterate-gate.sh --cycle N` (canary-audit clobber).
4. `iterate-gate.sh --close` only when the corpus is clean (I6) — currently 5 canary papers FAIL.

## Files changed this run (committed)

- `docpluck/render.py`, `docpluck/__init__.py`, `pyproject.toml`, `CHANGELOG.md` — v2.4.92 affiliation
  guard (`cf420ca`).
- `tests/test_affiliation_heading_promote_guard_real_pdf.py` — new, 23 cases (`cf420ca`).
- `.claude/skills/docpluck-iterate/LEARNINGS.md`, `.claude/skills/_project/lessons.md` — cycle 2+3
  journal incl. the caption-revert and canary-audit-clobber lessons (`c671929`).
- Cycle 3 caption-follows guard: ATTEMPTED then fully REVERTED — **no code change persisted**.

## Stop reason

Both safe render-layer slices banked (v2.4.91 single-column, v2.4.92 affiliation). Cycle 3's
render-layer attempt at the cell-label class reverted cleanly (no clean signal). All remaining
corpus-clean work is architectural (table-extraction bbox decision + RC-1) and was **paused here by
explicit user direction** to resume in a dedicated session.
