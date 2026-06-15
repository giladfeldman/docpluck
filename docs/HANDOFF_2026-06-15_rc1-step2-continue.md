# HANDOFF — docpluck-iterate: RC-1 Step 2 continuation (2026-06-15, POST-DEPLOY)

Fresh-session handoff written at session close. The B7 + RC-1-Step-2 release is **shipped to
production**; this doc is the durable punch-list for the next session to continue the RC-1 work and
the rest of the open run. Companion (history): `docs/HANDOFF_2026-06-15_docpluck-iterate-resume.md`.

## Deployed state — v2.4.90 LIVE in production ✅

| Layer | State |
|---|---|
| Library `origin/main` | `818c3d0` (pushed) |
| Library tag | `v2.4.90` → `1325d14` (pushed) |
| App pin (`docpluckapp/service/requirements.txt`) | `docpluck[all] @ git+…@v2.4.90` (auto-bump commit `694e9cbb`, direct to main) |
| Railway service | `/_diag` `docpluck_version=2.4.90`; `verify-railway-deploy` CI **success**; `/health` **200** |

- **v2.4.89 B7** (dropped-minus sign-flip recovery): **ACTIVE in prod.** Restores correctly-signed
  effect sizes for downstream consumers (escicheck). AI-verified.
- **v2.4.90 RC-1 Step 2** (per-band column re-extraction): **SHIPPED DARK** behind
  `DOCPLUCK_COLUMN_CORRECT_BANDED` (default OFF ⇒ prod default path byte-identical, 26/26 baseline
  unchanged). AI-verified ON_BETTER on chan_feldman + chandrashekar (0 text-loss/halluc/regression).
- **`v2.4.89` tag is LOCAL-ONLY** (not pushed — intermediate; `v2.4.90` already contains B7's code).
  Push it only if you want complete tag history; not required for the deploy.
- **`SKIP_CANARY=1` was used** for the v2.4.90 main+tag push (**user-authorized 2026-06-15**). The
  strict tag canary flagged 3 **case-variant** findings (`perce/Perce`, `we/We`,
  `extensions/Extensions`) as NEW via the known finding-key case-norm bug; flag-OFF output is
  byte-identical to v2.4.89 (26/26 baseline char-match) ⇒ confirmed **false positive, not a
  regression**. See remaining-work item 5.

## What RC-1 Step 2 IS (don't re-derive)

- `extract_page_text_banded` in `docpluck/extract_columns.py`: segments a flagged two-column page
  into horizontal **y-bands**; a band whose central gutter strip `[gx±4pt]` is glyph-free is
  two-column prose → re-extracted left-then-right; a full-width band (table/banner/title) is kept
  as-is; bands reassemble at glyph-free cut lines (overlapping bands merge → full-width so a tall
  title glyph is never bisected). Runs as a **fallback inside `splice_column_corrected_pages`** only
  when the whole-page corrector returns `""`, under the **unconditional word-preservation guard**
  (rejects any non-pure-reorder → can only ADD a correct reorder, never ship corruption).
- Design + remaining-work detail: `docs/superpowers/specs/2026-06-08-rc1-region-aware-column-architecture.md`
  → "Step 2 — remaining work".
- Tests: `tests/test_rc1_banded_column_real_pdf.py`. Durable lesson: shared card
  `band-reextraction-lean-on-word-preservation-guard` + `.claude/skills/_project/lessons.md`.
- Validation harnesses (in `tmp/`, gitignored — re-runnable): `tmp/rc1_band_extract.py` (corpus
  word-preservation + coverage scan), `tmp/rc1_lib_check.py` (flag on/off whole-doc word-safety),
  `tmp/rc1_render_verify.py` (render flag on/off for AI-verify).

## Remaining work (priority order)

1. **RC-1 Step 2 refinements → then flip the default.** Convert the conservative first cut to
   default-ON: (a) **band-cut word clips** (~6/71 flagged pages, currently guard-rejected so they
   stay interleaved — no corruption) — snap each inter-band cut to a provably glyph-free scanline in
   BOTH crops, or detect+repair the boundary-clipped token post-crop; (b) **per-row both-sides
   under-detection** (baseline-offset columns bucket separately) — needs a band-level reconciliation,
   not a blanket per-row relaxation (gutter-clear-only raised guard-rejections 6→12 of 71); (c)
   **hard title+sidebar pages** (PSPB p1) — size-aware band handling so a large-font title is its own
   full-width band without swallowing the adjacent 2-col sidebar. Then flip
   `DOCPLUCK_COLUMN_CORRECT_BANDED` + `DOCPLUCK_COLUMN_CORRECT_GENERAL` defaults once a full-corpus
   AI-verify + 26-baseline are clean with flags ON.
2. **Full canary AI-verify coverage (cycle-2 gate I2).** This cycle AI-verified chan_feldman +
   chandrashekar (ON_BETTER). Still owe a flag-ON AI-verify vs article-finder reading gold for
   **ip_feldman, plos_med, collabra, jesp, ar_apa** before cycle 2 can reach PASS.
3. **Table-structuring** (empty-shell / swapped / unstructured-fallback tables) — the TABLE-class
   findings on every two-column paper; a SEPARATE root cause from RC-1 reading-order. Per the TRIAGE,
   tackle after RC-1 lands (fixing it while RC-1 is open is whack-a-mole).
4. **B1 table-completeness** (plos_med_1 Tables 2/3/4/5 lose rows/cols/body) — **DECISION NEEDED:**
   this is *beyond* the originally-approved B7+RC-1 scope. Get a scope nod from the user before doing
   it.
5. **Canary case-norm false-positive fix** (so future release tags don't need `SKIP_CANARY`). The
   finding-key normalization in the canary-audit script (TODO ~line 165 per memory
   `feedback_canary_gate_nondeterministic`) treats case variants (`we`/`We`) as distinct → re-flags
   pre-existing backlog as "new". Lowercase-normalize the finding key.
6. **Residuals:** metadata-leak (RC-2 residual on plos affiliations/abbrev/running-headers),
   heading-demotion, B7 `.245` painted-pixel minus (documented OCR-only limitation — no action).

## How to resume

1. `/docpluck-iterate --resume` — reads `~/.claude/skills/_shared/run-meta/docpluck-iterate.json`
   (cycle 2 recorded, verdict **PARTIAL**, `run_closeout` PARTIAL-PAUSED with the `open_classes`
   above; the SKIP_CANARY override is logged in `notes`).
2. Start with **item 1** (RC-1 refinements) — it's the path to flipping the default and closing the
   dominant defect, then **item 2** (full canary coverage) to clear the cycle-2 gate.
3. The run **cannot close** (I6) until the canary findings clear + full coverage is recorded. It is
   correctly **OPEN/PARTIAL** — do not report it "clean" until the corpus is.
