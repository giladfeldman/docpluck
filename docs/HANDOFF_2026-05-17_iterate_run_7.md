# Handoff — docpluck-iterate run 7 (FIG-3a/3b/3c, FIG-4, HALLUC-HEAD-1)

**Authored:** 2026-05-17, end of run 7. **For:** a fresh `/docpluck-iterate` session.
Run 7 resumed from `docs/HANDOFF_2026-05-16_iterate_run_6.md` and shipped
**five** cycles end-to-end (v2.4.49 → v2.4.53), resolving the entire FIG
caption-cluster plus the CRediT slice of HALLUC-HEAD.

## State at handoff

- Last shipped library version: **v2.4.53** (tags `v2.4.49`–`v2.4.53` pushed; PyPI not published).
- docpluckapp pin: auto-bumped to **v2.4.53** — `bump-app-pin.yml` `success` on every tag.
- Production `/_diag`: `docpluck_version = 2.4.53` — verified.
- 26-paper baseline: **26/26 PASS** at v2.4.53 (verified every cycle).
- Broad pytest: **1308 passed, 1 failed** — the 1 failure is `test_request_09`
  (pre-existing COL-class numbered-bibliography column-split; red since run 4,
  TRIAGE queue item; caption/heading cycles cannot affect it). 0 new failures.
- Three-tier parity: Tier-1 == Tier-2 == Tier-3 byte-identical (modulo the
  documented CRLF HTTP delta) for every affected paper in all 5 cycles.

## What run 7 shipped

| Cycle | Version | Defect | Outcome |
|---|---|---|---|
| FIG-3a | v2.4.49 | figure caption absorbs body prose at a lowercase-`. `-boundary | SHIPPED — 5 captions trimmed, 2 legit continuations guarded |
| FIG-3b | v2.4.50 | caption anchored to a body-text in-text reference, not the real caption | SHIPPED — 14 caption groups corrected (APA/AOM/IEEE/Vancouver) |
| FIG-3c | v2.4.51 | figure caption double-emitted (inline body + `### Figure N` block) | SHIPPED — ~21 captions de-duplicated across 5 APA papers |
| FIG-4 | v2.4.52 | legit long figure caption (efendic Fig 1, 498 chars) truncated by the 400-char overflow trim | SHIPPED — full Note recovered |
| HALLUC-HEAD-1 | v2.4.53 | CRediT role `Methodology` promoted to a `## ` heading inside the contributor-roles block | SHIPPED — 3 papers fixed |

Each cycle: reproduce → corpus-scan → code → targeted tests → broad pytest →
26-paper baseline → Phase-5d AI-gold verify → Tier-2 local-app → release →
Tier-3 prod → LEARNINGS/lessons/TRIAGE. ~36 new tests added across
`test_figure_caption_trim_real_pdf.py`, `test_caption_regex.py`, `test_render.py`.

### Cycle detail

- **FIG-3a (v2.4.49):** `_trim_caption_at_body_prose_boundary` gained a
  lowercase-initial-tail branch — a `. ` followed by a lowercase word is
  absorbed body prose. Guarded against abbreviations, caption-`Note.` labels
  (`_CAPTION_LABEL_WORDS`), and significance-legend tails
  (`_SIGNIFICANCE_LEGEND_TAIL_RE`). Phase-5d 18/18 figures PASS.
- **FIG-3b (v2.4.50):** new `caption_anchor_is_in_text_reference` in
  `tables/captions.py`; `extract_pdf_structured`'s caption dedup now prefers a
  non-reference anchor. The classifier advances past the `^\s*` the caption
  regex absorbs before inspecting line structure. Phase-5d 51/51 captions PASS.
- **FIG-3c (v2.4.51):** new render post-processor
  `_suppress_inline_duplicate_figure_captions` drops the inline body copy of a
  caption, but ONLY when the `### Figure N` block caption fully covers it
  (no text-loss). Runs after every glyph-normalization pass (a stray ligature
  would otherwise defeat the equality check). Phase-5d 3/3 papers PASS.
- **FIG-4 (v2.4.52):** `_extract_caption_text` tracks `stopped_at_break` — the
  400-char overflow trim now applies only to a runaway caption (walk ran to the
  cap), not a complete caption bounded by a real `\n\n`. efendic Fig 1's 498-char
  Note recovered.
- **HALLUC-HEAD-1 (v2.4.53):** new render post-processor
  `_demote_credit_role_headings` demotes a `## <CRediT-role>` heading when ≥3
  other CRediT role tokens sit in the ±10-line window. 3 papers' hallucinated
  `## Methodology` removed, real `## Method` kept.

### Standing verdict — PARTIAL (rule 0e-bis)

Run 7 shipped 5 verified incremental fixes — the **entire FIG caption-cluster
(FIG-1 … FIG-4) is now resolved corpus-wide**, plus the CRediT slice of
HALLUC-HEAD. But the APA corpus is **NOT clean**: ~8 APA papers still FAIL
Phase-5d on pre-existing defects (TBL-CAP, FIG-3c-2, G5d, HALLUC-HEAD-2,
G5c-2, the TABLE cluster, COL). The run does not declare the corpus done.

## Open queue — recommended order for the next session

Per the TRIAGE "SESSION 4" + "SESSION-3 STANDING VERDICT" (updated this run):

1. **TBL-CAP — table-caption over-extension into column headers** — S2, C2.
   Surfaced by the FIG-3b verifier. maier Tbl 5/9/10/11, chen Tbl 3/5/6/7/9/13/15
   splice a trailing column-header token into the caption. ENTANGLED: maier
   Tbl 1/2/3 are also double-emitted (the FIG-3c analogue for tables) and the
   second emission carries the column-header garbage. Likely needs both a
   table-caption-double-emission de-dup AND a `_trim_table_caption_at_cell_region`
   tightening.
2. **FIG-3c-2 — body-exceeds-block figure-caption double-emission** — S2, C2-C3.
   ~7 figures (chandrashekar Fig 2/4/5, jdm_m.2022.3 Fig 1/2, efendic Fig 1,
   jdm_.2023.16 Fig 1) where the inline caption copy exceeds the `### Figure N`
   block caption — de-dup needs the block caption completed first.
3. **G5d — named/unnumbered heading demotion** — S1, C2-C3, ~7 papers.
4. **HALLUC-HEAD-2 — open-ended `##` over-promotion** — S1, C2-C3. The
   non-controlled-vocabulary remainder (`## Conclusion`, `## Supplementary
   Material`, `## Data Availability Statement`, `## Evaluation`, `## Funding`/
   `## Methods` mis-promotions). Needs a dedicated section-partitioner session.
5. **G5c-2 — partitioner split-heading rejoin** — S1, C3. 5 jdm_m.2022.2 cases.
6. **TABLE structure destruction** — ~11 papers. S0/S1, C3 — largest blocker.
7. **COL column-interleave** (incl. `test_request_09`) + **GLYPH 011
   deleted-minus**. S0, C3-C4, layout-channel — escalate.

## Process notes

- **Release path:** all 5 run-7 cycles used the lean-checks release path — the
  Phase-7 `/docpluck-cleanup` + `/docpluck-review` sub-skills were skipped;
  essential hard-rule checks done inline (extraction/render-layer regex changes;
  no `-layout`/AGPL/tool-swap/U+2212/ImportError/HTML-table/`normalize.py`-S-step
  surface; general fixes keyed on structural signatures; real-PDF tests added;
  version bumps consistent). Recorded as `spine_skips`. 26/26 baseline +
  three-tier byte-identical are the no-regression evidence.
- **PROPOSED SKILL AMENDMENT (still awaiting user approval):** the Phase-7
  cleanup/review SPINE-SKIP has now recurred in **9 consecutive cycles**
  (13, G5c-1, FIG-1, FIG-2, FIG-3a, FIG-3b, FIG-3c, FIG-4, HALLUC-HEAD-1) —
  every time for a low-risk library-internal regex/render change touching none
  of the hard-rule surfaces. The run-6 handoff proposed codifying a documented
  "lean release path" branch in the docpluck-iterate SKILL.md Phase 7 with an
  explicit eligibility checklist. Run 7 is 5 more data points. **User decides.**
- **Run the same-code-path test files FIRST.** Every cycle, running the
  caption/render test files (`test_figure_caption_trim`, `test_caption_regex`,
  `test_render`) before the 16-minute broad suite caught issues fast.
- **A corpus scan before designing the guard, every cycle.** FIG-3a's scan
  found 2 false-positive classes; FIG-3b's scan caught a real classifier bug
  (`ieee_access_7`) before shipping; FIG-4's scan confirmed efendic Fig 1 is
  the only >360-char APA caption. The scan IS the verification.
- **Stale local uvicorn:** restarted at Phase 6 of every cycle (kill the PID on
  :8000 via PowerShell `Get-NetTCPConnection`, relaunch with
  `INTERNAL_SERVICE_TOKEN=tier2localtest` so `/render` accepts the
  `X-Internal-Service-Token` header — simpler than the `dp_` admin-key path,
  which is still used for Tier-3 prod).
- **A prior cycle's test can encode its own blind spot.** FIG-4 fixing the
  long-caption truncation turned a FIG-1 corpus-invariant test red (it asserted
  `len(cap) > 400` is always a defect). The test was corrected to the real
  invariant. When a fix makes a *pre-existing* test fail, check whether the test
  encoded the old buggy contract.

## Stop reason

Goal was `time:8h`. Run 7 completed five full cycles end-to-end. Stopped before
a sixth because the remaining queue is entirely C2-C3 (entangled or
broad-section-partitioner-surface) and the residual budget (~1.5h) was
insufficient to land one cleanly with full three-tier + Phase-5d verification —
per Phase 10 ("mid-cycle: finish current cycle, do NOT start a new one"). The
next `/docpluck-iterate` session resumes at **TBL-CAP** from the queue above.
