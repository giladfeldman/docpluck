# FINDINGS 2026-07-02 — Concurrent table-capture session reconciliation → v2.4.101

Reconciles the tangle of ~5 concurrent Claude Code sessions + 6 sibling branches
that the two `HANDOFF_2026-07-01_reconcile_concurrent_table_*.md` docs mapped, into
ONE verified release. Ground truth throughout = AI multimodal read of the source
PDF, never pdftotext/Camelot (project rule).

## The pivotal decision: reject the global-assignment pairing refactor

The uncommitted main-tree WIP had replaced greedy `_find_caption_for_table` with a
global per-page max-token-overlap assignment (`_assign_tables_to_captions_global` /
`_best_assignment_for_page`). **Empirically confirmed to regress
`test_chan_feldman_t6_prose_not_in_any_table`** (ran it on the working tree → FAIL;
on clean HEAD 8559c23 → PASS). This is the exact regression the v2.4.100 CHANGELOG
recorded for global matching (reshuffles ~24 papers, promotes a degenerate prose
fragment to a caption). **Decision: keep greedy + `_rescue_duplicate_starved_captions`
(v2.4.100); discard the global refactor.** The good idea from it (bare-digit token
exclusion) was ported onto greedy; its reading-order tie-break was tried and also
rejected (it perturbed greedy visit order corpus-wide and re-introduced the same
chan_feldman T6 regression — see the `_CAPTION_TOKEN_RE` comment in
`extract_structured.py`).

## What landed (integration branch off 8559c23 → v2.4.101)

| Fix | Files | Result |
|-----|-------|--------|
| chandrashekar side-by-side de-interleave | extract_structured, camelot_extract, whitespace | T4 17×2-merge → 9×2, both captions gold-exact |
| efendic T1 categorical + T2 detect | detect (unified), whitespace | T1 3×2→5×3, T2 0×0→11×5 |
| efendic T3 running-header + T2-5 caption-tail-prose strip | camelot_extract | grids start at the real `Predictors` header |
| collabra_77859 T2↔3 bare-digit exclusion | extract_structured | Tables 2/3/4/5 correct + deterministic |
| cog_emo T8 caption-marker hint | camelot_extract, extract_structured | T8 recovers 17×6 matrix, T9 12×8 |
| RR major-section heading promoter | render | 5–12-word Sentence-case `##` headings promoted |
| dropped-minus CI-upper recovery | normalize, cell_cleaning, flatten | `[-0.78,0.67]` → `[-0.78,-0.67]` |

Versions: `__version__`/`pyproject` 2.4.101, `NORMALIZATION_VERSION` 1.9.36,
`TABLE_EXTRACTION_VERSION` 2.4.7.

## Verification (the zero-regression gate)

- **Unit + real-PDF table suites** green (per-file, Camelot-flake-safe);
  `test_chan_feldman_t6_prose_not_in_any_table` PASS; 904 render/section/normalize
  tests pass.
- **Camelot is DETERMINISTIC on this host.** Two identical-code (8559c23) corpus
  captures were **byte-identical** (101/101 papers, 392 tables each). So — contrary
  to the standing `feedback_camelot_flake_cumulative_load` caution — every
  BEFORE/AFTER table diff here is a REAL code effect, not flake. (Flake still
  appears under whole-suite pytest cumulative load; the per-PDF-subprocess capture
  harness avoids it.)
- **101-PDF structured diff** vs v2.4.100: 4 target papers all improved as their
  FINDINGS predicted; 27 non-target papers changed. AI-gold re-verification of a
  broad sample of the 27 (three parallel Sonnet auditors, ground truth = the PDF):
  **15 BETTER, 5 SAME, 0 WORSE** — recovered truncated/missing data rows
  (jama_open_10, amd_2 T3, jamison T3, bjps_6, plos_med_1 T5, jdm_16 T6),
  corrected caption→table pairings (ieee_access_4 T8/T10), correct caption-tail
  strips (korbmacher ×3, ip_feldman T9). The one regression the auditors surfaced —
  **jdm_.2023.16 Table 7 rendered as caption-only** (its absorbed caption-tail
  header tripped `render._strip_phantom_camelot_tables`, which drops the whole
  table) — was root-caused and fixed the same run by broadening the upstream
  caption-tail-prose strip (`_is_caption_tail_prose`).

## Cleanup performed
- The global-assignment refactor discarded; tangled main-tree WIP snapshotted to
  git stash + scratchpad before reconciliation.
- Sibling branches merged/superseded: `feat/efendic-t1-categorical-table`,
  `worktree-cogemo-t8-caption-hint`, `feat/major-section-heading-promotion`; the
  three May `agent-*` locked worktrees are month-old leftovers (their work long
  since shipped) — safe to prune.
