# Handoff — docpluck-iterate run 6 (FIG-1, FIG-2)

**Authored:** 2026-05-16, end of run 6. **For:** a fresh `/docpluck-iterate` session.
Run 6 resumed from `docs/HANDOFF_2026-05-16_iterate_run_5.md` and shipped two
cycles from the FIG caption queue (FIG-1, FIG-2).

## State at handoff

- Last shipped library version: **v2.4.48** (tags `v2.4.47`, `v2.4.48` pushed; PyPI not published).
- docpluckapp pin: auto-bumped to **v2.4.48** — `bump-app-pin.yml` commits directly
  to `docpluckapp` master (no PR), workflow `success` on SHA `2f7e17b`.
- Production `/_diag`: `docpluck_version = 2.4.48` — verified.
- 26-paper baseline: **26/26 PASS** at v2.4.48 (0 FAIL, 0 WARN).
- Broad pytest: **1278 passed, 1 failed** — the 1 failure is `test_request_09`
  (pre-existing COL-class numbered-bibliography column-split; red since run 4,
  TRIAGE item 6; figure-caption cycles cannot affect it). 0 new failures.
- Three-tier parity: Tier-1 == Tier-2 == Tier-3 **byte-identical** for every
  affected paper in both cycles.

## What run 6 shipped

| Cycle | Version | Outcome |
|---|---|---|
| FIG-1 — figure-caption ellipsis-truncation walk-back | v2.4.47 | SHIPPED + three-tier-verified |
| FIG-2 — figure-caption walk stops at period-less complete caption | v2.4.48 | SHIPPED + three-tier-verified |

### Cycle FIG-1 (v2.4.47)

pdftotext welds a figure's following body prose onto its caption with a single
`\n`, so `_extract_caption_text`'s paragraph-walk absorbs prose to an 800-char
cap; the old 400-char cap then cut the caption mid-word with `…`. New helper
`extract_structured.py::_trim_overflowing_figure_caption` walks an overflowing
**figure** caption back to its last genuine sentence terminator instead. A
corpus scan confirmed every figure caption >400 chars is over-absorbed and
every legitimate one is ≤360 chars — so overflow is itself a sound signal. All
12 ellipsis-truncated captions across the APA corpus eliminated. Phase-5d
AI-gold verify (28 figures, 6 papers): 0 text-loss, 0 ellipsis-truncated, 0
cycle-blockers. 6 new tests.

### Cycle FIG-2 (v2.4.48)

The `_extract_caption_text` paragraph-walk only stopped at a `\n\n` blank-line
break when the preceding text ended with `.!?`. Two caption shapes end WITHOUT
a period — an APA period-less Title-Case figure title (efendic Figs 4/5) and a
trailing significance legend `*** p < .001` (chandrashekar Figs 1/3) — so the
walk sailed past the `\n\n` that legitimately ends them and absorbed the
following body prose. New helper `_caption_is_complete_without_terminator`
recognizes both period-less complete-caption shapes and stops the walk.
(Reading the raw pdftotext text was the key step — the `\n\n` boundary already
existed; the walk just didn't honor a period-less caption end.) Label stripped
case-insensitively (pdftotext emits `FIGURE 15.` while `cap.label` is
title-case); leading PMC `Author Manuscript` running header stripped (else it
reads as a 4-word title — a regression caught by the IEEE-bearing targeted
tests). efendic Figs 4/5 + chandrashekar Figs 1/3 recovered to AI gold.
Phase-5d AI-gold verify (10 figures, 2 papers): 8 PASS, 2 RESIDUAL-ABSORB
(untargeted), 0 text-loss, 0 regressions. 7 new tests.

### Standing verdict — FAIL / PARTIAL (rule 0e-bis)

FIG-1 + FIG-2 shipped verified incremental fixes — the figure-caption
ellipsis-truncation and period-less over-absorption defect classes are resolved
corpus-wide. But the APA corpus is **not clean**: 3 caption residuals remain
(FIG-3) and ~11 APA papers still FAIL Phase-5d on pre-existing defects (G5c-2,
HALLUC-HEAD, TABLE cluster, COL). The run does not declare the corpus done.

## Open queue — recommended order for the next session

Per the TRIAGE "SESSION-3 STANDING VERDICT" (updated this run):

1. **FIG-3 caption residual (no-`\n\n`) + double-emission** — S2, C2-C3.
   (a) chandrashekar Fig 4 (`and Linos, 2022).` citation fragment) + Fig 5
   (`peoples' preferences. Given …` body prose) — absorbed via a `. `-boundary
   the FIG-2 walk-stop does not reach (no `\n\n`; a `. ` followed by a
   lowercase-initial fragment). Fix: widen `_trim_caption_at_body_prose_boundary`
   to trim a figure caption at a real `. ` terminator followed by a
   lowercase-initial word (a caption's own sentences always start capitalized —
   exclude known continuation openers `n =`/`p <`/`note`/`bars`/…).
   (b) chan_feldman Fig 10 — the caption ANCHOR latched onto a `Figure 10`
   reference in body prose; the whole "caption" is body prose. A caption-
   DETECTION defect, distinct root cause.
   (c) figure-caption **double-emission** — caption present both in body prose
   AND as a `### Figure N` block (~8 papers); render-layer body/caption de-dup.
2. **G5c-2 partitioner split-heading rejoin** — S1, C3. 5 jdm_m.2022.2 cases.
3. **G5d named/unnumbered heading demotion** — S1, C2-C3, ~7 papers.
4. **HALLUC-HEAD** — mid-sentence words promoted to `##` headings. S1, C2.
5. **TABLE structure destruction** — ~11 papers. S0/S1, C3 — largest blocker.
6. **COL column-interleave** (incl. `test_request_09`) + **GLYPH** 011
   deleted-minus. S0, C3-C4, layout-channel — escalate.

## Process notes

- **Release path:** both run-6 cycles used the lean-checks release path — the
  Phase-7 `/docpluck-cleanup` + `/docpluck-review` sub-skills were skipped;
  essential hard-rule checks done inline (extraction-layer regex-only changes in
  `extract_structured.py`; no `-layout`/AGPL/tool-swap/U+2212/ImportError/
  HTML-table surface; general fixes keyed on structural signatures; real-PDF
  tests added; version bumps consistent). Recorded as `spine_skips`. 26/26
  baseline + three-tier byte-identical are the no-regression evidence.
- **PROPOSED SKILL AMENDMENT (awaiting user approval):** the Phase-7
  cleanup/review SPINE-SKIP has now recurred in 4 cycles (13, G5c-1, FIG-1,
  FIG-2) — every time for a low-risk library-internal regex/render change
  touching none of the hard-rule surfaces. Recommend codifying a documented
  "lean release path" branch in the docpluck-iterate SKILL.md Phase 7 with an
  explicit eligibility checklist (no `-layout`/AGPL/tool-swap/U+2212/
  ImportError/HTML-table/`normalize.py`-S-step surface; 26/26 baseline green;
  three-tier byte-identical) so it is a first-class branch, not a per-cycle
  spine-skip. User decides.
- **Run the same-code-path test files FIRST.** FIG-2's first implementation
  regressed ieee_access_2 PMC captions; running `test_figure_caption_trim` +
  `test_chart_data_trim` (the IEEE-bearing files) as the first verification
  step surfaced it in ~30s, before the 12-minute broad suite.
- **Stale local uvicorn:** the local service must be restarted at Phase 6 of
  EVERY cycle to pick up new library code (module cache). Port 8000 can stay
  held by a dying uvicorn for a few seconds — if a restart fails to bind,
  kill any process on :8000 and retry. Note: a psutil `cmdline` scan for
  "uvicorn"/"app.main" also matches the scanning script itself — match on the
  listening port, not the cmdline substring.
- **Prod auth for Tier-3:** `dp_` admin key via
  `frontend/scripts/get-or-create-admin-key.mjs`; pass `DATABASE_URL` through
  `tr -d '\r"' | xargs` first (the raw `.env.local` value carries a Windows
  `\r` that makes `neon()` reject the connection string).

## Stop reason

Goal was `until:"context window hits ~60%"`. Run 6 completed two full cycles
(FIG-1, FIG-2) end to end — reproduce → code → Tier-1 → Tier-2 → release →
Tier-3 → self-improvement each. Stopped before bootstrapping FIG-3 because the
context budget was reached; FIG-3 is a fresh C2-C3 cycle (three sub-parts: a
`. `-boundary trim, a caption-anchor fix, and render-layer double-emission
de-dup). The next `/docpluck-iterate` session resumes at FIG-3 from the queue
above.
