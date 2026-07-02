# Findings — parallel-session verification pass (2026-07-01, ~01:00–01:45)

> Written by a **second** `docpluck-iterate` session that ran concurrently with the
> primary cycle-1 session. To avoid colliding with the primary session (which owns
> the `extract_structured.py` table-capture path + the shared run-meta cycle state),
> this session **ceded** the table-capture verification/release and recorded its
> independent findings here instead. The primary session's run-meta showed
> `cycle_status[1] = FAIL` (correctly). These notes are inputs for whoever closes
> cycle 1 and plans the next cycles.

## 1. Guard-diff (a transient larger cycle-1 variant vs v2.4.99 HEAD) — ZERO table regressions

A structured guard-diff (table kind/shape/flattened-fields, working tree vs the
clean `dp_baseline_head` worktree @ 4cea4c6) over the canary+handoff corpus found
**no table regressions** — every change was an improvement or a data-preserving
re-segmentation:

| Paper | Change | Verdict |
|-------|--------|---------|
| cog_emo Table 8 (flat) | CI_upper `0.33 → −0.33`, `0.67 → −0.67` | ✅ CI-minus recovery, matches body-text gold |
| cog_emo Table 9 | `0×0 isolated → 12×4 structured` | ✅ recovered stub |
| cog_emo Table 6 | `7×4 f=7 → 9×2 f=0` | ✅ removed 7 GARBAGE flat rows (`{"group":"IV construct"}`, prose fragments — no real stats) |
| efendic Table 2 | `0×0 isolated → 11×5 structured` | ⚠️ recovered BUT caption-bleed + glyph (see §3) |
| chandrashekar T7/T8 | stubs → `12×9`/`15×9` (corpus cells 108→221) | ✅ recovered |
| plos_med T4/T5 | T4 `16×3→8×3`, T5 `2×3→15×3` (total cells 201→201) | ✅ correctly re-split; **T5 recovered the 13 SAE rows (the B1 canary!)** |
| efendic T3 | `12×9 → 13×5` (flat fields identical) | ✅ cleaner shape, no data loss |
| maier T11 | `23×8 → 22×8` (flat 17→20) | ✅ +3 flat |

**NOTE:** the working tree was mutated by a concurrent writer mid-session — the
larger variant I guard-diffed (with `_assign_tables_to_captions_global` global
caption→table assignment + full side-by-side `_detect_column_gutters`/`isolate`)
was **rolled back** to a smaller cycle-1 (`_find_caption_for_table` + a
"duplicate-starvation rescue"). Neither sibling worktree (cogemo-t8, efendic-t1)
carries the global-assign approach either, so it appears **deliberately abandoned**.
The guard-diff numbers above therefore describe a SUPERSEDED variant; re-run the
guard-diff against the FINAL chosen tree before trusting them for the release.

## 2. PRE-EXISTING test failures (fail with v2.4.99 HEAD code too — NOT cycle-1 regressions)

`tests/test_r1_whitespace_cells_wiring_real_pdf.py::test_b1_whitespace_cells_wiring_live`
fails for **two** parametrizations:
- `[chan_feldman_2025_cogemo.pdf-8-50]`
- `[maier_2023_collabra.pdf-11-50]`

**Proven pre-existing:** stashing all cycle-1 table-code changes (detect/whitespace/
camelot/extract_structured) and re-running with HEAD code → the test **still fails
identically**. It is environment-gated: `_CORPUS = parents[2]/PDFextractor/test-pdfs/apa`,
so it **skips** in any checkout whose `parents[2]` lacks that path (e.g. the
`dp_baseline_head` temp worktree skips it — which is why CI/baseline never flagged it).

**Root cause:** for cog_emo Table 8 the region resolves (bbox present, 125 words
inside) but `signal=caption_only` (`_aligned_row_run` finds < 3 aligned rows on this
tight-kerned intercorrelation matrix), and BOTH `whitespace_cells` and
`char_whitespace_cells` return **0 cells** → `cells_total=0 < 50` → assert fails. The
RC-T char-level fallback does not fire here. The full `extract_pdf_structured` path
works around it (region-driven Camelot extracts cog_emo T8 as 12×8), so this is a
gap in the **direct `whitespace_cells(region=…)` fallback**, not the main pipeline.

**Recommendation:** either (a) make `whitespace_cells`/`char_whitespace_cells` recover
a grid from this `caption_only` 125-word region, or (b) if the direct fallback is no
longer load-bearing for these papers, lower the test's `min_cells` expectation or mark
the cog_emo-p8 / maier-p11 cases `xfail` with a reference to this finding — do NOT
silently delete the test. **Leave-nothing-behind: this is a real open defect to fix,
not to ignore.**

## 3. efendic Tables 2–5 recovery is NET-BETTER but DEFECTIVE (AI-gold FAIL)

Independent Sonnet AI-gold verify (vs the `reading` gold) on the efendic working-tree
render returned FAIL. The recovered Tables 2–5 (were `0×0` stubs) carry the correct
B/CI/p once decoded, BUT:
- **Caption-tail bleed into every table header:** `<th>as the DV.<br>Predictors</th>`,
  `<th>by Risks/Benefits.<br>Predictors</th>`. The region top-clip uses the caption's
  FIRST line; a multi-line WRAPPED caption leaves its continuation line inside the grid.
  `_drop_caption_first_row`'s `_CAPTION_TAIL_FRAGMENT_RE` only catches a bare `(YYYY)`
  tail (chandrashekar), not a prose tail like `as the DV.`.
- **Table 2's 4th-col header borrows Table 3's DV label** (`DV: Change in non-manipulated
  attribute`) — the region absorbed a neighbouring caption fragment.
- **GLYPH `2`-for-minus uncorrected on the B column:** raw cells are `20.09`/`21.09`
  (should be `−0.09`/`−1.09`) AND the CI brackets are `[20.21, 0.04]` (→ W0b fixes the
  bracket, but the standalone B estimate stays `20.09`). On the bled/ragged grid the
  W0d CI-pairing recovery does not reach the B cell; on a CLEAN `<tr>` it does
  (`recover_minus_via_ci_pairing` fixes `20.09 → −0.09` in isolation — verified). So the
  **caption-bleed is upstream of the glyph bug**: fix the leading-caption-row strip and
  the grid de-raggs, then W0b+W0d recover the signs.

**Recommended fix (general, for the owning session):** broaden the leading-row strip
in `camelot_extract._drop_caption_first_row` (or add a region-path
`_trim_leading_caption_rows` mirroring `_trim_trailing_prose_rows`) to drop a leading
**single-populated-cell prose-tail row** (lowercase-leading or sentence-ending, no
stat) that sits ABOVE the real header row — keyed on the layout invariant "the caption
is continuous text; the grid header is multiple short cells." This recovers efendic 2–5
cleanly AND unblocks the glyph recovery. For a meta-science tool, **wrong numbers
(`20.09` for `−0.09`) are dangerous** — if the clean recovery can't be guaranteed,
quality-gate the bled table back to a `0×0` stub (efendic's body text covers the stat)
rather than shipping corrupted coefficients.

## 4. cog_emo Table 8 under-segmentation — still open (owned by the `cogemo-t8-caption-hint` worktree)

AI-gold verify confirms the rendered "Table 8" carries Table-9-style content
(Hypothesis/p/r/CI) while the real Table-8 intercorrelation MATRIX is lost; Table 9 is
recovered but drops its Replication columns. This is deferred-backlog item 1. The
`cogemo-t8-caption-hint` worktree is implementing a `_caption_hint_number` pairing
(extract the table's own absorbed caption number as the authoritative identity). Let
that session land it.

## 5. Pre-existing `##`/`###` heading demotions — being fixed as "cycle 2" (this session's worktree)

BOTH cog_emo AND efendic AI-gold verdicts flag section headings demoted to body text
(cog_emo: "Original hypotheses and findings in the target article", "Measures",
"Extension: …", "Citation of the target research article"; efendic: "Design, Procedure,
and Measures", "Analysis Strategy", "Declaration of Conflicting Interests", "Funding",
"ORCID iD"). **Confirmed pre-existing** (render.py is unmodified by cycle 1; baseline
and working-tree renders demote identically). Root cause: `_looks_like_titlecase_
subsection_label` accepts only ≤6-word/≤60-char lines, so 7–12-word Sentence-case
`##`-level major-section titles fall through.

**✅ FIXED — ready to merge.** Branch **`feat/major-section-heading-promotion`**
(worktree `.claude/worktrees/agent-a9e7adc97f3c73895`, off v2.4.99 = 03e5d55), commits
`0306535` + `166164c`. Adds a NEW `_promote_isolated_major_section_headings`
(`##`-level, 5–12 words, ≤80 chars, Sentence-case, no sentence terminator except an
optional colon, followed by genuine body prose) that runs AFTER the existing `###`
promoter and NEVER relaxes its ≤6-word B2-over-promotion guards. Full veto set:
clause-opener, balanced-parentheses, leading-close-bracket, author-year-citation,
continuation-tail word, dangling-2nd-to-last-function-word, possessive-tail, and a
heading-above check (won't promote the paper title). **Verified:** 193 tests pass
(incl. 7 negative regression cases for the real column-wrap truncation fragments a
broad canary render surfaced — efendic "Both studies had…", maier "Reanalysis…on the
Identifiable"/"Affective Reactions (with…", ip_feldman "…Using Target's"); all existing
render + heading-guard tests green; end-to-end render of ip_feldman/cog_emo/efendic/
maier = **0 false-positive `## ` headings**, cog_emo's 3 genuine major-section headings
promoted. **render.py-only → zero overlap with the table-capture cycle** (main-tree
render.py is byte-identical to HEAD). **MERGE THIS into cycle 1 (or ship as its own
release) — it resolves the heading-demotion half of BOTH the cog_emo and efendic
AI-gold FAILs, which is currently blocking `cycle_status[1]` from leaving FAIL.**
**FINAL branch tip: `7cfb09f`** (4 commits: `0306535` promoter + `166164c` truncation
guards + `407d4cc` docs + `7cfb09f` corpus-broad-read refinement). Worktree clean.
The 4th commit ran a broad-read across all 18 local APA papers, which surfaced ~12
false positives on OTHER papers (wrapped body sentences, acknowledgments, citations,
table captions, two-column truncation fragments) — **all eliminated** by the structural
guards (incl. a `_MAJOR_SECTION_TRUNCATION_JOINTS = {the,a,an,and}` dangling-joint set
scoped so complete prepositional tails like "…of Donation" survive). Final tally: 0
clear false positives; genuine long headings promoted per-paper (cog_emo 6, ip_feldman
3, chandrashekar 2, maier 1, xiao 1, efendic 0, ar_apa 1); B2 guards hold (ip_feldman
"Supplemental Materials" stays body). Test totals: 198 passed / 9 skipped (promoter +
the 3 heading-guard suites) + 88 passed / 0 failed on the broader section suites.

**Safe-side note:** genuine headings the SOURCE truncates mid-title at a column break
(chandrashekar "Part 2: Replication of Johnson, Bellman, and Lohse", maier "Reanalysis
of a Meta-Analysis on the Identifiable") are left as BODY rather than promoted — they
are structurally indistinguishable from wrapped-sentence fragments, and the guards err
toward not fabricating a partial `##` (a demoted line beats a fake heading). Recovering
those needs column-wrapped-heading RE-JOINING first (a separate concern).

**Integration is conflict-free:** the 4-commit patch `git apply --check`s cleanly onto
the CURRENT main HEAD (4cea4c6) — render.py + the new test are byte-disjoint from the
table-capture changes. Ready-made patch: `tmp/cycle2_full.patch`
(`git format-patch 03e5d55..7cfb09f`). To integrate: `git am tmp/cycle2_full.patch`
(or `git cherry-pick 0306535 166164c 407d4cc 7cfb09f`). No version bump on the branch —
fold into the cycle-1 → v2.4.100 bump, or ship as its own patch release; either way it
belongs in the same release that closes the cog_emo/efendic heading half of
`cycle_status[1] = FAIL`.
