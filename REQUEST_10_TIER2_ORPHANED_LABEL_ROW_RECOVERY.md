# Tier-2 — Camelot orphaned-label / multi-block table row recovery (successor to REQUEST_10)

**Status:** ✅ SHIPPED in docpluck **v2.4.94** (2026-06-19). The fix was NOT the
orphaned-label synthesis this doc originally specced — see the corrected root
cause below. Delivered as a cross-flavor lattice-augmentation + numeric-
continuation merge; PROSECCO Table 2 now flattens R1–R6 sign-correct. See
CHANGELOG v2.4.94 + `LESSONS.md` L-009.
**Owner:** docpluck table-extraction layer. **Verification arbiter:** ESCImate
`docpluck_shootout.R` + article-finder AI gold.

## Problem (root cause CORRECTED 2026-06-19 after grounded investigation)

> **The original hypothesis below was WRONG.** It assumed Camelot's stream
> parser drops the rows / they live as orphaned labels needing layout-channel
> synthesis. Direct inspection of raw Camelot output for PROSECCO page 9
> disproves that. The true root cause is **stream-vs-lattice flavor selection +
> a cross-flavor header/body split**, documented below.

### Evidence (raw Camelot, page 9, 2026-06-19)

- **Camelot STREAM** returns a **15×9** table (acc 99.9) that **contains every
  data row** — "Resection complete", "adjusted for stratification factors",
  "remnant (mean SD)", AND the size-distribution sub-rows — with R2/R3/R5/R6's
  values present (`−1.83% (−11.2–7.5)`, `7.7 (−3.2–18.5)`, `0.82% (−8.63–10.28)`,
  `8.4 (−3.1–19.9)`). BUT: (a) stream **lost the column-header text** — its row 0
  is `['', 'N = 98', 'N = 89', '', '', 'N = 94', 'N = 85', 'CI)', '']` (no "Risk
  diff. (95% CI)" / "P value" / "ITT" / "PP"); and (b) stream **vertically
  splits** each logical row — the value is on one grid row and its `(percentage)`
  / CI-upper-bound tail (`8.34)`, `10.28)`) on the next.
- **Camelot LATTICE** returns a clean **3×9** table (acc 100) with **correct
  headers** (`ITT`/`PP`, `Risk diff. (95% CI)`, `P value`) and the merged first
  data row (`86(87.8%)`, `−1.01% (−10.36–8.34)`) — but only that **one** data
  row (the lattice box bbox covers just the ruled top band, y≈638–705; stream's
  bbox spans y≈485–677, i.e. the lower rows).
- **`_pick_best_per_page`** (camelot_extract.py) makes **lattice own page 9**
  (it has a ≥2×2, acc≥80 table), so the richer 15-row stream table is
  **discarded**. That is why only "Resection complete" survives.

So: **lattice = good headers + 1 row; stream = all rows + broken headers +
split cells. Neither flavor is independently sufficient.** `flatten` (already
fixed in v2.4.93) is not the issue; the data never reaches it.

## Scope / why it's separated from Tier-1

The correct fix is a **cross-flavor column-aligned merge** in the table-CAPTURE
layer: when lattice and stream cover the same region with the same column count,
combine lattice's clean header (+rows) with the stream rows lattice missed,
plus a **numeric-continuation merge** to rejoin stream's split value/parenthetical
cells. This touches `_pick_best_per_page` (documented jama_open_1 regression
history) and `_merge_continuation_rows` (delicate) — broad, regression-risky on
the 100+ PDF / 2000+ test corpus, hence a separate full-verification pass.

## Candidate approach (CORRECTED — to be validated)

1. **Numeric-continuation merge** (`cell_cleaning._merge_continuation_rows`):
   extend the empty-/parenthetical-col0 continuation rule to merge rows whose
   non-empty cells are all *fragments* (parentheticals `(87.8%)`, CI-tails
   `8.34)`), column-aligned with the parent — rejoining stream's stacked
   value/parenthetical rows. General improvement for any stacked-cell table.
2. **Cross-flavor merge** (`camelot_extract`): when a page is lattice-owned but a
   same-page **stream** table has the **same n_cols** and a **bbox extending
   below** the lattice table's bbox, append stream's missed lower rows (after
   continuation-merge), mapped onto lattice's columns, so the result has
   lattice's headers + all rows. Gate hard on equal-col-count + bbox-containment.
3. Baseline-gate: full 2000+ test suite + cross-publisher render-diff, zero
   regressions.

### ORIGINAL (incorrect) hypothesis — retained for the record

~~Camelot's stream parser never binds the orphaned-label rows into the table
region; recover them by detecting orphaned label lines in the layout channel and
synthesizing rows.~~ Disproved: stream DOES capture the rows; the loss is in
flavor selection + header/body split, not orphaned labels.

## Acceptance

1. PROSECCO Table 2 captures all three data rows → `flatten_tables_for_paper`
   emits R1–R6 (six arm-records) with sign-correct CIs.
2. Full 26-paper baseline + a broad cross-publisher table sample: **zero**
   row-count or cell regressions on tables that already captured correctly
   (deterministic render-diff + AI-gold).
3. ESCImate `docpluck_shootout.R` shows R2/R3/R5/R6 detected by `check_text()`
   with zero new false positives on `escimate_validation`.

## References

- Tier-1: `REQUEST_10_TABLE_FLATTEN_HTTP_EXPOSURE.md`, `REPLY_FROM_DOCPLUCK_v2.4.93.md`, CHANGELOG v2.4.93.
- Lesson: `LESSONS.md` L-009 (capture bounds flatten).
- Reproducer: `python ~/.claude/skills/article-finder/cache-check.py "10.1371/journal.pmed.1004323"`.
- Capture code: `docpluck/extract_structured.py`, `docpluck/tables/camelot_extract.py`, `docpluck/tables/cell_cleaning.py`.
