# HANDOFF — docpluck-iterate (2026-06-17, v2.4.91 shipped)

> **Supersedes** `HANDOFF_2026-06-17_iterate_resume-cycle1.md` for forward work. This session
> resumed that queue and **shipped the single-column heading fix as v2.4.91** (the handoff's #1
> "headings first" item), **completed the canary case-norm verification and the 3-paper rotating-pool
> onboarding**, and **reconfirmed the RC-1 + table defects at the new HEAD**. The run remains
> **OPEN / PARTIAL — standing verdict FAIL** (iterate-gate `--cycle 1` = FAIL on I3; the canary corpus
> is genuinely broken on pre-existing table/column-interleave defects).

## TL;DR

- **v2.4.91 SHIPPED + LIVE.** Single-column subsection-heading promotion. tag `v2.4.91` → PyPI →
  docpluckapp pin `@v2.4.91` (auto-bump **auto-merged**, master `9af3c49`) → prod Railway `/_diag` = **2.4.91**.
  Local `PDFextractor/` synced.
- **Verified, not just shipped.** ar_apa_011 gains exactly `### Overview` / `### Practice instructions` /
  `### Self-control assessment` — **AI-verified vs the article-finder reading gold (`new_headings_are_real=true`,
  zero hallucination)**. 26/26 baseline, full suite **1748 passed**, 23 new regression tests. Two-column
  canary papers byte-identical (gate stays OFF). A new abbreviation-glossary false promotion on plos_med
  (`### Anesthesiologists; CI, …`) was caught by AI-verify and fixed (fragment guard) before ship.
- **Concurrent-stream merge (user-approved).** `render.py` combined a parallel session's refinements
  (the `chen_2021_jesp` `_prev_is_clean_boundary` scale-item guard + `_LEADING_FRAGMENT_PREPS`) with this
  session's single-column gate (`_raw_text_is_single_column`) + abbreviation-glossary `;`/`,` fragment
  guard. One coherent feature, verified together; provenance documented in commit `662c4df`.
- **Canary rotating pool expanded 2 → 5** (efendic/maier/xiao onboarded; golds pre-existed in the
  article-finder cache; PDFs aligned to test-pdfs; titles verified). `rotation_pool_too_small` +
  `onboarding_pending` sanity warnings **cleared**.
- **Canary case-norm "quick win" was already fixed** at HEAD (verified: `finding_key` fully case-folds;
  covered by `test_canary_audit.sh` case 1a). Memory `feedback_canary_gate_nondeterministic` already current.
- **RC-1 + tables remain OPEN** (multi-cycle architectural). Reconfirmed at v2.4.91 (see Open queue).

## Deploy state — v2.4.91 LIVE, coherent

| Layer | State |
|---|---|
| Library `origin/main` HEAD | `7edc62f` (canary onboarding) on top of `662c4df` (v2.4.91 feat) — clean tree |
| Library tag `v2.4.91` | live; PyPI published; prod Railway `/_diag` = `2.4.91`; RC-1 flags default OFF |
| docpluckapp `origin/master` pin | `@v2.4.91` (master `9af3c49`, auto-bump auto-merged) ✅; local `PDFextractor/` synced |

> ⚠ Cosmetic: the v2.4.91 commit subject (`662c4df`) has a stray leading `@ ` (a PowerShell-here-string
> token leaked through the Bash tool). The CHANGELOG, tag, and body are correct; not worth a force-push to
> already-deployed `main`. Use `git commit -F <file>` for multi-line messages in the Bash tool, not `@'…'@`.

## Gate state — `iterate-gate.sh --cycle 1` = **FAIL** (run OPEN/PARTIAL)

Only **I3** fires (verdict-on-truth): all 5 fixed/rotating canary papers FAIL on pre-existing table/column
defects — non-overridable by design, and correct (the corpus IS broken). **Every other rule passed**: I1
(phase_5d ran), I2 (all canary AI-verified this cycle), I5 (corpus sweep), I9 (locator via article-finder),
I10 (artifacts exist), I11 (gold-sha matches cache), I12 (lesson-readback). The `rotation_pool_too_small` /
`onboarding_pending` sanity warnings are now gone. **Do NOT run `--close`** until tables + RC-1 clear (I6).

## Per-paper findings at HEAD (v2.4.91, flag-OFF shipping; AI gold = article-finder `reading`)

Fresh 5-way Sonnet AI-verify this session (renders at `tmp/iterate/cycle-1/<stem>.md`):

| Paper | Verdict | Dominant defects (all PRE-EXISTING; unchanged by v2.4.91) |
|---|---|---|
| **plos_med_1** | FAIL | Table 2 keeps 1 of ~11 rows; **Table 4 renders the wrong table's content** (anesthetic-complication rows + "PLOS MEDICINE" header); **Table 5 `<tbody>` empty — all 13 SAE rows lost**; raw cell fragments leak above Table 1. Highest user impact. |
| ip_feldman_2025_pspb | FAIL | `### Reasons for change` (Table 5 col-label promoted — **pre-existing G5d, two-column path**); Table 3 col-merge, Table 4/5 truncation, Table 10 empty; Method order inverted; Table 2 hypothesis rows mid-Introduction. |
| chandrashekar_2023_mp | FAIL | Tables 7-10 collapse to header shells (`EstimateZpOR [95% CI]` merged); B6 Method column-interleave; `### Department of Philosophy, Lake Forest College` promoted in Abstract (interleave). |
| chan_feldman_2025_cogemo | FAIL | PCIRR study-design table interleaved to prose; Tables 1/3/4/7 row-loss; **Table 8/9 swapped**; running-header `1232 C. F. CHAN AND G. FELDMAN` in Table 2 thead; several `##` headings demoted. |
| ar_apa_j_jesp_2009_12_011 | FAIL | **Headings fixed (+3 ✓)**; residual: Table 1 emitted twice (raw column-dump + HTML) with grouped-header misplacement; figure axis-labels leak into Results; `Supplemental analyses` still demoted to body; B7 painted-pixel minus (OCR-only). |

## Open queue (priority — standing verdict FAIL, run not done)

1. **Tables — TEXT-LOSS / structuring (highest user impact, user item 3).** plos_med_1 is the worst
   (Table 5's 13 SAE rows empty, Table 4 wrong content). Then chandrashekar Tables 7-10 header-shell
   collapse, chan_feldman Table 8/9 swap + row-loss, ip_feldman Table 3/4/5/10. Camelot/extraction-layer,
   multi-cycle. Start with one root-cause class (e.g. the empty-`<tbody>`/header-shell collapse, which
   spans plos_med T5 + chandrashekar T7-10).
2. **RC-1 band path (user-approved multi-cycle).** Reconfirmed at v2.4.91: ar_apa flag-ON
   (`DOCPLUCK_COLUMN_CORRECT_BANDED=1` / `…_GENERAL=1`) regresses — **section-order scramble (Introduction
   before Abstract)** + **"M. Muraven / Journal of Experimental" running-header leak**. Flags stay OFF.
   Fix band-cut/reorder under the word-preservation guard before any flip. Spec:
   `docs/superpowers/specs/2026-06-08-rc1-region-aware-column-architecture.md`. Render saved at
   `tmp/iterate/resume/ar_apa.rc1on.md`.
3. **Pre-existing G5d TWO-COLUMN heading hallucinations (separate root cause from v2.4.91's single-column
   path).** ip_feldman `### Reasons for change` (Table 5 col label) and chandrashekar `### Department of
   Philosophy, Lake Forest College` (affiliation promoted in Abstract via column-interleave). These come
   through the two-column / interleave path, NOT the single-column relaxation — needs a cell-region /
   interleave-aware demotion, likely entangled with #1 and #2.
4. **Residuals:** ar_apa B7 painted-pixel minus (OCR-only, documented, no action); table-bearing renders
   carry I10 Camelot non-determinism (body-prose verification is stable).

## How to resume

1. `/docpluck-iterate --resume`. **FIRST** `git status` + `git log --oneline -5` in BOTH repos (this file
   itself records a 3rd concurrent-co-edit of render.py — re-confirm provenance before editing).
2. Reproduce each open finding at HEAD before trusting it. Renders for all 5 canary papers are at
   `tmp/iterate/cycle-1/*.md`; the flag-ON RC-1 render at `tmp/iterate/resume/ar_apa.rc1on.md`.
3. Pick up **tables** (item 1, highest user impact) — start one root-cause class (header-shell / empty-tbody
   collapse spans plos_med T5 + chandrashekar T7-10). The fresh AI-verify findings above are the punch-list.
4. `iterate-gate.sh --cycle N` every cycle; `--close` only when the corpus is clean (I6).

## Files changed this run (committed)

- `docpluck/render.py` — `_raw_text_is_single_column`, `_is_single_col_relaxation_fragment` (+ `;`/`,`),
  single-column relaxation in `_promote_isolated_titlecase_subsection_headings`, call site.
- `docpluck/__init__.py`, `pyproject.toml` — version 2.4.91.
- `CHANGELOG.md` — v2.4.91 entry.
- `tests/test_single_column_subsection_promote_real_pdf.py` — new (23 cases).
- `.claude/skills/_project/lessons.md` — single-column-gate resolution entry.
- `.claude/skills/_project/canary.json` — rotating pool 2→5 (efendic/maier/xiao).
- `tmp/onboard_canary.py` — extended with the 3 papers (gitignored tmp/, not committed).
