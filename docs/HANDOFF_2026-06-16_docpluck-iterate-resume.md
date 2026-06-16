# HANDOFF — docpluck-iterate resume (2026-06-16)

> **Supersedes** `HANDOFF_2026-06-15_rc1-step2-continue.md` for forward work. That doc (written by the
> session that shipped v2.4.90) remains the authoritative description of *what RC-1 Step 2 is* and the
> deploy record — read it for the algorithm + remaining-work detail. This doc adds the 2026-06-16
> session: a concurrent-session collision was detected and cleaned up, and v2.4.90 state was
> re-verified.

## TL;DR

- **v2.4.90 (RC-1 Step 2, ship-dark) is LIVE and COHERENT in production.** Prod Railway
  `/_diag` = `docpluck_version 2.4.90`; tag `v2.4.90` (`1325d14`) pushed; docpluckapp `origin/master`
  pin = `@v2.4.90` (auto-bump `694e9cb`). Version-pin coherence (R-0085) ✅ tag = prod = origin pin.
- **A concurrent Claude session collision was cleaned up.** While this session independently started
  RC-1 Step 2, another session was implementing the *same* feature in the *same* files and committed
  first — sweeping this session's uncommitted duplicate (`extract_page_text_bands` + 3 helpers) into
  the **v2.4.90 release commit** as orphaned, uncalled dead code. **Removed** on `main` in
  commit `436fc5a` (190 lines; 69 column-path tests + full suite green; behaviour-identical —
  the functions were never called, no name collision). See "Collision + cleanup" below.
- **The run is OPEN / PARTIAL — standing verdict FAIL** (rule 0e-bis). Cycle-2 iterate-gate FAILs on
  I2 (owed AI-verify) + I3 (open structural findings on 5 canary papers) + I10 (Camelot rendered_sha
  drift). It correctly **cannot close** until the canary findings clear. Forward punch-list below.

## Collision + cleanup (this session)

- **Cause:** the system-prompt git snapshot ("clean") was stale by the time a second session began
  co-editing. This session added `extract_page_text_bands`/`_min_crossing_gutter`/`_row_is_two_column`/
  `_segment_into_bands` to `extract_columns.py`; the other session's `git add` swept them into
  `1325d14` (v2.4.90). The shipped duplicate is **inert** (uncalled — the splice calls the other
  session's `extract_page_text_banded`; distinct names, no shadowing) but is dead code that violated
  LEAVE-NOTHING-BEHIND.
- **Fix:** removed the entire orphaned block from `main` (commit `436fc5a`). **No version bump,
  no re-tag, no redeploy** — the removal is a pure no-op (zero rendered-output change; the active path
  is byte-identical), so it rides into the next tagged release rather than forcing deploy churn for
  inert code. The tagged `v2.4.90` (and prod) still contain the inert duplicate; this is harmless and
  superseded by `main`.
- **Durable lesson:** `.claude/skills/_project/lessons.md` → "On resume, `git status` BEFORE editing
  source" (run a fresh `git status` + `git log` on every resume; treat "File modified since read" on a
  file you didn't touch as a STOP-and-check-for-concurrent-editor signal; surface collisions to the
  user rather than racing or unilaterally reverting).

## Deploy state — v2.4.90 LIVE, coherent

| Layer | State |
|---|---|
| Library `origin/main` HEAD | `436fc5a` (dead-code-removal cleanup, post-v2.4.90; untagged, no deploy) |
| Library tag `v2.4.90` | `1325d14` (pushed) — contains inert orphan, superseded by main |
| docpluckapp `origin/master` pin | `docpluck[all] @ …@v2.4.90` (auto-bump `694e9cb`) ✅ |
| Railway `/_diag` | `docpluck_version 2.4.90`; RC-1 dark (`DOCPLUCK_COLUMN_CORRECT_BANDED` default OFF) |
| **Local `PDFextractor/` checkout** | **STALE — at `8f0f5a8` (v2.4.85 pin), 2 commits behind `origin/master`.** Cosmetic local lag only (prod/origin are correct); `cd ../PDFextractor && git pull` to sync. Not pulled this session to avoid touching the app repo while concurrent sessions may be active. |
| `v2.4.89` tag | LOCAL-ONLY (intermediate; v2.4.90 already contains B7's code). Push only for complete tag history. |

## Open queue (standing verdict FAIL — the run is not done)

Carried from `HANDOFF_2026-06-15_rc1-step2-continue.md`, priority order:

1. **RC-1 Step 2 refinements → flip the default.** (a) band-cut word clips (~6/71 flagged pages,
   guard-rejected so they stay interleaved, no corruption) — snap inter-band cuts to a glyph-free
   scanline in BOTH crops or repair boundary-clipped tokens; (b) per-row both-sides under-detection
   (baseline-offset columns bucket separately) — band-level reconciliation, NOT a blanket per-row
   relaxation (gutter-clear-only raised guard-rejections 6→12/71); (c) hard title+sidebar pages (PSPB
   p1) — size-aware band handling. Then flip `DOCPLUCK_COLUMN_CORRECT_BANDED` +
   `DOCPLUCK_COLUMN_CORRECT_GENERAL` once full-corpus AI-verify + 26-baseline are clean with flags ON.
   Spec: `docs/superpowers/specs/2026-06-08-rc1-region-aware-column-architecture.md` "Step 2 — remaining".
2. **Full canary AI-verify coverage (cycle-2 gate I2).** Cycle 2 AI-verified chan_feldman +
   chandrashekar (ON_BETTER). Still owe a **flag-ON** AI-verify vs article-finder reading gold for
   **ip_feldman, plos_med, collabra_77859, jesp_2021_104154, ar_apa** before cycle 2 can reach PASS.
3. **Table-structuring** (empty-shell / swapped / unstructured-fallback tables) — TABLE-class findings
   on every two-column paper; SEPARATE root cause from RC-1 reading-order. Tackle after RC-1 lands.
4. **B1 table-completeness** (plos_med_1 Tables 2/3/4/5 lose rows/cols/body) — **DECISION NEEDED:**
   beyond the originally-approved B7+RC-1 scope. Get a user scope nod before starting.
5. **Canary case-norm false-positive fix** so future release tags don't need `SKIP_CANARY`. The
   finding-key normalization in the canary-audit script (TODO ~line 165, memory
   `feedback_canary_gate_nondeterministic`) treats case variants (`we`/`We`) as distinct → re-flags
   pre-existing backlog as "new". Lowercase-normalize the finding key. Bounded, shippable, non-arch.
6. **Residuals:** metadata-leak (RC-2 residual on plos), heading-demotion, B7 `.245` painted-pixel
   minus (documented OCR-only limitation — no action).

## Spine / gate state (cycle 2, OPEN/PARTIAL)

`iterate-gate.sh --cycle 2` → **FAIL**:
- **I2** canary-coverage: missing AI-verify on `collabra_77859`, `jesp_2021_104154` (owed item 2).
- **I3** verdict-on-truth: FAIL verdicts on ar_apa (7), chan_feldman (14), chandrashekar (12),
  ip_feldman (7), plos_med (7) — the multi-session RC-1/table/metadata findings.
- **I10** artifact-existence: cycle-2 `rendered_sha` ≠ on-disk artifact — **Camelot non-determinism on
  Windows** (ar_apa rendered 27038B vs 27507B across identical runs; table present/absent). Body-prose
  verification is stable; table verification needs a deterministic Camelot (or retry-before-sha-pin)
  before I10 can be trusted on table-bearing renders. Known issue, not fabrication.
- **Canary sanity:** rotating_pool size 2 == rotation_size 2 (no rotation) — onboard efendic/maier/xiao.

The run **cannot close** (I6) until canary findings clear + full coverage is recorded. It is correctly
OPEN/PARTIAL — **do not report it "clean" until the corpus is.**

## How to resume

1. `/docpluck-iterate --resume`. **FIRST run a fresh `git status` + `git log --oneline -5`** (see the
   collision lesson) and `cd ../PDFextractor && git status` (the local app checkout is stale).
2. Reproduce each open finding at HEAD before trusting it (`reproduce-triage-defect-at-head`; ~26%
   verifier FP per cross-project R-0006) — note RC-1 findings need the flag ON to test the band path.
3. Start with **item 1** (RC-1 refinements → flip default) then **item 2** (full canary coverage) to
   clear the cycle-2 gate. Item 5 (canary case-norm) is a quick win that removes future `SKIP_CANARY`.
4. One root cause per cycle; real-PDF test + word-preservation + flag-ON AI-verify + full suite, 0
   regressions. `iterate-gate.sh --cycle N` every cycle; `--close` only when the corpus is clean (I6).
