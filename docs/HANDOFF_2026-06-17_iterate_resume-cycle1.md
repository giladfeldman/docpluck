# HANDOFF — docpluck-iterate resume (2026-06-17, cycle 1)

> **Supersedes** `HANDOFF_2026-06-16_docpluck-iterate-resume.md` for forward work. This session
> reconciled a (second) concurrent-stream divergence, **reproduced every cycle-2 canary finding at
> the post-handoff HEAD**, **disproved RC-1 flip-readiness with deterministic evidence**, captured
> two user direction decisions, and investigated the heading-demotion fix to a precise blocked state.
> No release cut. Run remains **OPEN / PARTIAL — standing verdict FAIL** (iterate-gate `--cycle 1` = FAIL on I3).

## TL;DR

- **State reconciled.** On resume the repo had advanced **7 commits past** the 2026-06-16 handoff base
  (`436fc5a` → `cfe86f7`), all a **Cursor stream** (telemetry counters, extraction guardrails,
  fallback-exception metadata, docs, CI docs-guard) — unrelated to RC-1. Also: an uncommitted
  `canary.json` edit I didn't make (stripped `expected_pdf_sha` from all 5 papers + flipped
  `render_command` to bare `python`) + a stale Dropbox conflicted-copy. **User confirmed Cursor was
  done; reverted the canary edit** (bare `python` is the known empty-render hazard,
  `feedback_canary_render_python_alias_empty`; dropping `expected_pdf_sha` weakens the provenance
  gate) and deleted the conflict copy. Working tree clean. Version still **v2.4.90**, RC-1 dark.
- **All 5 canary papers FAIL at HEAD (flag-OFF = shipping).** The 2026-06-16 I3 findings **reproduce**
  — they are real, not stale. AI-verified each (flag-OFF **and** flag-ON) vs the article-finder
  `reading` gold via parallel Sonnet subagents → I2 coverage gap **closed**.
- **RC-1 is NOT flip-ready — flipping would regress production.** Under `DOCPLUCK_COLUMN_CORRECT_BANDED=1`
  / `…_GENERAL=1`: net-neutral body on ip_feldman / plos_med / chandrashekar (B6 interleave **not**
  resolved), a minor improvement on chan_feldman (2 headings), and a **deterministic REGRESSION on
  ar_apa** (Abstract emitted before Introduction; intro sentences sliced mid-phrase and one spliced
  into the Methods section; running-header "M. Muraven / Journal of Experimental" leaked into body).
  **Handoff item-1 premise ("refinements → flip the default") is invalidated.** Flags must stay OFF.
- **User decisions (this session):** (1) **Debug the RC-1 band path properly** (multi-cycle). (2)
  **Headings first**, tables later.
- **Heading-demotion fix investigated → blocked, precisely scoped, reverted (no regression shipped).**
  See "Cycle 2 — heading fix" below.

## Deploy state — v2.4.90 LIVE, coherent (unchanged this session)

| Layer | State |
|---|---|
| Library `origin/main` HEAD | `cfe86f7` (Cursor stream; no RC-1/iterate code change) — **clean working tree** |
| Library tag `v2.4.90` | live; prod Railway `/_diag` = `2.4.90`, RC-1 dark (flags default OFF) |
| docpluckapp `origin/master` pin | `@v2.4.90` (master `9aba482`) ✅; local `PDFextractor/` now in sync (was stale) |

## Gate state — `iterate-gate.sh --cycle 1` = **FAIL** (run OPEN/PARTIAL)

Run-meta (`~/.claude/skills/_shared/run-meta/docpluck-iterate.json`) records cycle 1 = `INVESTIGATE-RESCOPE`.
- **I3 verdict-on-truth — FAIL (the genuine, expected one):** all 5 canary papers FAIL at HEAD —
  ip_feldman (3), plos_med_1 (4), chandrashekar (3), chan_feldman (3), ar_apa (3). Run cannot close
  until these clear. This is correct; the corpus is genuinely broken.
- I12 lesson-readback: cleared after running `lesson-readback.sh` (11 matched cards; notably
  `reproduce-triage-defect-at-head` and `release-version-collision-with-parallel-uncommitted-stream`,
  both of which applied directly this session).
- **run-meta data-shape gotcha (fixed):** `cycle_targets` MUST be a dict `{"<cycle>": [canonical-stems]}`
  (the gate does `cycle_targets.get(str(cycle))`), and `phase_5d_runs[].paper_stem` /
  `open_findings[].paper_stem` MUST use the **canary canonical stems** (`ip_feldman_2025_pspb`, not
  `ip_feldman`). A flat list / short stems silently de-registers verdicts (papers show NEVER_VERIFIED)
  and crashes the digest under `--cycle` mode. Now correct in run-meta.
- ⚠ canary sanity (pre-existing, not a violation): `rotating_pool` size 2 == `rotation_size` 2 → no
  rotation; onboard `efendic_2022_affect`, `maier_2023_collabra`, `xiao_2021_crsp` into article-finder
  to expand the pool (per `onboarding_status.still_to_onboard_before_use`).

## Per-paper findings at HEAD (flag-OFF shipping; AI gold = article-finder `reading`)

| Paper | Verdict | Dominant defects |
|---|---|---|
| **plos_med_1** | FAIL (4 TEXT-LOSS) | Table 2 ~10 rows lost; Table 3 loses 2 of 4 cols; Table 4 replaced by garbled Table-3 fragment; **Table 5 all 13 SAE rows lost**. The worst — real downloaded-table corruption. |
| ip_feldman_2025_pspb | FAIL (3) | Method subsection order inverted; Table 3 col-merge, Table 4 truncation, Table 10 empty body; Table 2 hypothesis rows mid-Introduction. |
| chandrashekar_2023_mp | FAIL (3) | B6 column interleave in Method; Tables 7/8/9/10 collapse to header shells; Figure 4/5 captions inline in Discussion. |
| chan_feldman_2025_cogemo | FAIL (3) | PCIRR study-design table column interleave; multiple `##` headings demoted to body; Table 7 truncation, Table 8/9 swap. |
| ar_apa_j_jesp_2009_12_011 | FAIL (3) | B7 sign-flip β=−.245→.245 (painted-pixel minus, OCR-only — no action); subsection headings demoted to body; Camelot raw dump inline (non-det I10). |

Renders saved at `tmp/iterate/resume/<stem>.off.md` (shipping) and `.on.md` (RC-1 candidate).

## Cycle 2 — heading fix (user-chosen "headings first"): WORKING for single-column, BLOCKED for two-column

**Root cause (general, structural):** JESP/Elsevier single-column papers emit subsection headings
("Overview", "Practice instructions", "Self-control assessment") on their own line with **no blank
padding on either side**, glued between the prior subsection's body and their own body. Every existing
promoter requires `blank_before AND blank_after`, so they stay demoted to body text.

**The working fix (single-column only):** in `_promote_isolated_titlecase_subsection_headings`
(`docpluck/render.py`), relax the hard `blank_before` reject (~line 2348) to admit a no-blank-before
candidate when the immediately-preceding line is a **sentence-terminated PROSE line** (clean paragraph
boundary, not a mid-sentence column-wrap), letting all existing downstream guards
(`_prev_paragraph_is_sentence_terminated`, single-line cell reject, sibling-label reject, prose-next)
still apply. **Verified: ar_apa gains exactly `### Overview` / `### Practice instructions` /
`### Self-control assessment`, 0 removed.**

**Why it's blocked (the trap — see `_project/lessons.md` 2026-06-17 entry):** the same relaxation
**over-promotes 5 two-column table-cell / measures-list labels on ip_feldman** (`### Others ratings`,
`### Address order effects`, `### Prevalence Estimation Error: …`) — the **G5d hallucinated-heading
blocker**. The natural discriminator (single-column body wraps wide ~60-90 chars; two-column table
cells are ~30 chars) **works on raw pdftotext but is useless at the promoter**, because earlier
render-pipeline steps JOIN wrapped lines first (measured: "Others ratings" body max width **36 raw →
112 in-pipeline**). A width gate inside the promoter therefore admits everything. **Reverted; no
release** (must not ship a G5d regression).

**The precisely-scoped next step (immediate, not "later"):** compute a document-level
`is_single_column` signal from the **raw pdftotext output before line-joining** (e.g. median raw
body-line width ≥ ~62, and/or zero column-interleave flagged pages from
`extract._detect_column_interleave_pages`) at the render entry point, thread it into
`_promote_isolated_titlecase_subsection_headings`, and apply the no-blank-padding relaxation **only
when single-column**. Two-column subsection headings are already handled by the blank-isolation /
chain paths, so single-column gating both fixes JESP/Elsevier AND prevents the two-column
over-promotion. Alternative signal: the layout/font channel (headings are bold/larger). Add a
`*_real_pdf` test on ar_apa (asserts the 3 headings) + ip_feldman (asserts zero new headings), then
gate on the 26-baseline + a corpus-wide heading-count-delta scan + AI re-verify of any paper whose
heading count changes.

## Open queue (priority — standing verdict FAIL, run not done)

1. **Cycle 2 (in progress): heading-demotion fix** — implement the single-column-gated relaxation
   above. Verify with the deterministic heading-delta one-liner
   (`diff <(grep -E '^#{1,4} ' before) <(grep -E '^#{1,4} ' after)`) on ar_apa (+3) and ip_feldman
   (+0), then 26-baseline + canary re-verify.
2. **RC-1 band-path debugging (user-approved, multi-cycle).** Start from the ar_apa flag-ON
   regression (deterministic, body-prose channel): the band splice slices intro sentences mid-phrase,
   inverts Abstract/Introduction, splices an intro tail into Methods, and leaks a running header. Fix
   the band-cut/reorder under the word-preservation guard BEFORE any flip is reconsidered. Spec:
   `docs/superpowers/specs/2026-06-08-rc1-region-aware-column-architecture.md`.
3. **Table TEXT-LOSS / structuring (deferred to after headings, per user).** plos_med_1 is the
   highest user impact (Tables 2-5 lose rows/cols/body; Table 5's 13 SAE rows). The canary B1 item —
   user nod to open the table-completeness work still stands as the gate to start (was "headings
   first").
4. **Canary case-norm false-positive (quick win, independent).** `feedback_canary_gate_nondeterministic`
   (TODO ~line 165): lowercase-normalize the finding key so case variants aren't re-flagged as new.
5. **Onboard 3 rotating-pool papers** (efendic/maier/xiao) into article-finder to fix the
   `rotation_pool_too_small` sanity warning.
6. **Residuals:** ar_apa B7 painted-pixel minus (OCR-only, documented, no action); metadata-leak / I10
   Camelot non-determinism on table-bearing renders (body-prose verification is stable).

## How to resume

1. `/docpluck-iterate --resume`. **FIRST** run a fresh `git status` + `git log --oneline -8` (the
   repo has had ≥2 concurrent-stream divergences in 2 days) and `cd ../PDFextractor && git status`.
2. Reproduce each open finding at HEAD before trusting it (the cost estimate / verdict can be stale).
3. Pick up **Cycle 2** (heading single-column gate) — the root cause, working fix, and the exact
   blocker are all documented above; this is a code-ready next cycle, not a fresh investigation.
4. `iterate-gate.sh --cycle N` every cycle; `--close` only when the corpus is clean (I6).
