# Handoff — docpluck-iterate 2026-06-25 · branch reconciliation + RC-1 banded flip REJECTED

**Run verdict: PARTIAL.** Two clean fixes shipped; the canary corpus is NOT clean (4 open architectural FAILs). Standing corpus verdict: **FAIL** (rule 0e-bis) — the iterate-gate `--close` correctly does not green-close.

## 1. State at handoff
- **Library version: v2.4.97** (`__version__` 2.4.97, `NORMALIZATION_VERSION` 1.9.35, `TABLE_EXTRACTION_VERSION` 2.4.2).
- **`main` = `origin/main` = `v2.4.97` tag = `59cff5b`** (this run's commit, on top of the FF'd v2.4.97). **App pin `@v2.4.97` on docpluckapp `origin/master`** → production in sync. `check_app_pin_sync.py` = PASS.
- Working tree clean (all changes committed). `tmp/` working artifacts only.

## 2. What this run did

### Shipped (clean, verified)
1. **Branch reconciliation (the headline).** At session start `main` (local AND `origin/main`) was at the v2.4.95-era commit `2dbdd98`, but tags `v2.4.96`/`v2.4.97` were already pushed **4 commits ahead** (real, test-backed RC-T render-strip + DP-2/DP-5 flatten work) and the app pin had auto-bumped to `@v2.4.97`. So **production ran v2.4.97 while the library mainline + working tree claimed v2.4.95** — a prior session tagged+pushed without advancing the branch, and the tree was checked out backwards. Fast-forwarded `main` (local + origin) to `813aa4c` (v2.4.97). Now mainline == latest tag == app pin. (User-authorized FF.)
2. **`check_app_pin_sync.py` direction bug + test** (commit `59cff5b`). `compare()` told a checkout BEHIND its latest tag it was "ahead — tag+push v2.4.95" (would have tagged an OLDER version — hit live this session). Fixed via ordered `_vtuple()`; `tests/test_check_app_pin_sync.py` (10 cases, fails-before/passes-after).

### Investigated and correctly NOT shipped
3. **RC-T table-data recovery == the RC-1 banded layout-channel work (architectural, multi-session).** 4 canary tables render as caption-only orphans with their data LOST vs gold (ip_feldman T10 = a real 7-row regression table dropped; chan_feldman T6/T9; chandrashekar T2). Probed 4 recovery angles — all bottom out in full-page Camelot bbox / region-overshoot-into-prose / RC-1 interleave INSIDE the table region / tight-kerned glued stat cells. The orphan `### Table N` heading is the DELIBERATE v2.4.55 clean-fail (keeps caption for `table_parity`), not the bug. Evidence written to `docs/superpowers/specs/2026-06-21-rc-t-table-region-prose-contamination.md` (UPDATE 2026-06-25).
4. **RC-1 banded default-flip ATTEMPTED, REJECTED by 8-canary AI-verify.** Word-preservation corpus scan = **26/26 baseline PRESERVED, 0 violations** (looked safe). But 8 parallel Sonnet verifiers (Claude Max) found **3 ON_REGRESSION** (deterministically confirmed): `ar_apa` injects `M. Muraven / Journal` running-header furniture ×2 + inverts Abstract/Intro order; `chan_feldman` injects Power-Analysis prose into Extension; `maier` (SINGLE-COLUMN) fragments prose via a false-positive gutter. Plus 4 ON_NEUTRAL, 1 ON_BETTER (ip_feldman). **The word-multiset gate was BLIND to all 3 regressions** (reorder/furniture-injection preserves the multiset). Flag stays default-OFF. Precise gap-5/6/7 blockers + a stricter zero-regression re-verify gate written to `docs/superpowers/specs/2026-06-08-rc1-region-aware-column-architecture.md` (UPDATE 2026-06-25).

## 3. Open queue (NOT dropped — rule 0e-bis)

| # | Item | Class | Where |
|---|---|---|---|
| O1 | 4 canary table-data / sidebar FAILs (ip_feldman T10, chan_feldman T6/T9, chandrashekar T2, plos_med sidebar) | RC-T/RC-1 architectural | RC-1 + RC-T specs |
| O2 | RC-1 banded flag gap-5 (single-column false-positive — maier), gap-6 (furniture pulled into band — ar_apa), gap-7 (band spans section boundary — chan_feldman) | architectural | RC-1 spec UPDATE 2026-06-25 |
| O3 | **canary-audit.sh hook clobbers run-meta `phase_5d_runs`+`cycle_status` with deferred-PASS** — fired on BOTH pushes this session, masking the FAIL corpus as green; restored truthful verdicts each time | substrate bug | `~/.claude/skills/_shared/iterate-loop/canary-audit.sh` (memory `feedback_canary_audit_clobbers_phase5d`) |
| O4 | Audit ~37 `_strip_phantom` th-stripped tables for wrongly-stripped REAL tables | pre-existing | carried from prior run |

## 4. Next-session opener (RC-1 banded, the queued architectural cycle)
1. Read the RC-1 spec UPDATE 2026-06-25 — the 3 confirmed regressions ARE the gap-5/6/7 blockers, with file/line pointers.
2. **Fix gap-5 first (single-column false-positive):** add a strict single-column guard so the banded path is a no-op unless `_detect_column_interleave_pages` flags the page AND a full-height gutter with substantial both-side word mass exists (not a local whitespace river). `maier` must verify ON_NEUTRAL.
3. Then gap-6 (re-apply running-header/footer strip per band crop) + gap-7 (cut bands at `##`/`###` heading rows).
4. **Re-verify gate (stricter):** all 8 canaries ON_BETTER/ON_NEUTRAL, ZERO ON_REGRESSION, under AI-verify + word-preservation scan + 26-baseline, before flipping the default. Renders + per-paper verdicts from this run: `tmp/iterate/cycle-1/<stem>.flag{OFF,ON}.md`; verdicts in run-meta `corpus_sweeps` (2026-06-25).
5. Table-DATA recovery (O1) is downstream of the banded work landing cleanly — re-probe band-clipped `whitespace_cells` + a char-level x-gap column detector for tight-kerned cells once the prose-band path is correct.

## 5. Stop reason
User-directed scope (reconcile branch → authorize RC-T → start RC-1 banded session). RC-1 banded recovery is a multi-session architectural effort; the flip was correctly rejected by AI-verify this run. Run closed as PARTIAL with the punch-list above — the 2 landable fixes shipped, the architectural corpus work is queued with a sharpened spec.

## 6. Process note
The `check_app_pin_sync.py` PASS hid the branch-vs-tag lag (it compares pin-to-tag, not branch-to-tag). New project lesson added: at session start, compare `git rev-parse main origin/main` to the latest `v*` tag. And: word-preservation/char-ratio gates are blind to reading-order regressions — AI-verify is mandatory before any reorder default flip (re-validated hard rule).
